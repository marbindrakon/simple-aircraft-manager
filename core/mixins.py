from functools import reduce

from rest_framework import permissions

from core.events import log_event


class AircraftScopedMixin:
    """ViewSet mixin that scopes querysets and checks permissions per-aircraft.

    Class attributes:
        aircraft_fk_path (str): Required — ORM lookup path from this model to
            Aircraft, using double-underscore notation for queryset filtering.
            E.g. 'aircraft' or 'document__aircraft'.
    """

    aircraft_fk_path = None  # must be set by subclass

    def get_queryset(self):
        from core.models import AircraftRole
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff or user.is_superuser:
            return qs
        accessible = AircraftRole.objects.filter(user=user).values_list('aircraft_id', flat=True)
        assert self.aircraft_fk_path, f"{self.__class__.__name__} must set aircraft_fk_path"
        return qs.filter(**{f'{self.aircraft_fk_path}__in': accessible})

    def _resolve_aircraft_from_instance(self, instance):
        """Walk the dot-notation path to resolve the Aircraft instance."""
        path = self.aircraft_fk_path.replace('__', '.')
        return reduce(getattr, path.split('.'), instance)

    def _resolve_aircraft_from_validated_data(self, validated_data):
        """Resolve the Aircraft instance from serializer validated_data.

        Walks the aircraft_fk_path (e.g. 'aircraft' or 'document__aircraft')
        through validated_data then attribute access, matching the pattern used
        by get_queryset() and _resolve_aircraft_from_instance().
        """
        parts = self.aircraft_fk_path.split('__')
        obj = validated_data.get(parts[0])
        for part in parts[1:]:
            if obj is None:
                return None
            obj = getattr(obj, part, None)
        return obj

    def perform_create(self, serializer):
        """Enforce aircraft-level role checks before saving a new instance.

        DRF only calls check_object_permissions() for actions that call
        get_object() (retrieve, update, destroy).  For create, no object
        exists yet, so we must check the incoming aircraft FK ourselves.
        """
        from core.permissions import get_user_role, ROLE_HIERARCHY, PILOT_WRITABLE_MODELS
        aircraft = self._resolve_aircraft_from_validated_data(serializer.validated_data)
        if aircraft is not None:
            role = get_user_role(self.request.user, aircraft)
            if role is None:
                self.permission_denied(self.request)
            model_name = serializer.Meta.model.__name__.lower()
            if model_name not in PILOT_WRITABLE_MODELS:
                if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get('owner', 0):
                    self.permission_denied(self.request)
        super().perform_create(serializer)

    def check_object_permissions(self, request, obj):
        """Check aircraft-level permissions after DRF's standard checks."""
        super().check_object_permissions(request, obj)
        from core.permissions import (
            get_user_role, ROLE_HIERARCHY, PILOT_WRITE_ACTIONS,
            PILOT_WRITABLE_MODELS,
        )
        from core.models import Aircraft
        aircraft = self._resolve_aircraft_from_instance(obj)
        if not isinstance(aircraft, Aircraft):
            self.permission_denied(request)

        role = get_user_role(request.user, aircraft)
        if role is None:
            self.permission_denied(request)

        # Safe methods allowed for any role
        if request.method in permissions.SAFE_METHODS:
            return

        # Check if this model is pilot-writable
        model_name = obj.__class__.__name__.lower()
        if model_name in PILOT_WRITABLE_MODELS:
            return  # pilot+ can write these

        # Everything else requires owner+
        if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get('owner', 0):
            self.permission_denied(request)


class EventLoggingMixin:
    """ViewSet mixin that auto-logs create/update/delete as AircraftEvents.

    Class attributes:
        event_category (str): Required — category key for EVENT_CATEGORIES.
        aircraft_field (str): Dot-notation path to resolve the Aircraft FK
            from the instance (default 'aircraft').  For example,
            DocumentImageViewSet uses 'document.aircraft'.
        event_name_created / event_name_updated / event_name_deleted (str):
            Optional overrides.  When omitted, names are generated from the
            model's verbose_name (e.g. "Component created").
    """

    event_category = None  # must be set by subclass
    aircraft_field = 'aircraft'

    event_name_created = None
    event_name_updated = None
    event_name_deleted = None

    def _resolve_aircraft(self, instance):
        """Follow a dotted path to reach the Aircraft instance."""
        try:
            return reduce(getattr, self.aircraft_field.split('.'), instance)
        except AttributeError:
            return None

    def _model_label(self):
        return self.queryset.model._meta.verbose_name.capitalize()

    def _log(self, aircraft, name):
        if aircraft is None:
            return
        user = self.request.user if hasattr(self, 'request') else None
        log_event(aircraft, self.event_category, name, user=user)

    def perform_create(self, serializer):
        instance = serializer.save()
        name = self.event_name_created or f"{self._model_label()} created"
        self._log(self._resolve_aircraft(instance), name)
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        name = self.event_name_updated or f"{self._model_label()} updated"
        self._log(self._resolve_aircraft(instance), name)
        return instance

    def perform_destroy(self, instance):
        # Resolve aircraft *before* delete to avoid stale FK
        name = self.event_name_deleted or f"{self._model_label()} deleted"
        aircraft = self._resolve_aircraft(instance)
        user = self.request.user if hasattr(self, 'request') else None
        instance.delete()
        if aircraft:
            log_event(aircraft, self.event_category, name, user=user)
