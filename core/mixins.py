from functools import reduce

from core.events import log_event


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
        return reduce(getattr, self.aircraft_field.split('.'), instance)

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
