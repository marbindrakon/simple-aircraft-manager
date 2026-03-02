from django.conf import settings
from rest_framework import permissions

from core.models import Aircraft, AircraftRole

# Role hierarchy: admin > owner > pilot
ROLE_HIERARCHY = {'admin': 3, 'owner': 2, 'pilot': 1}

# Actions that pilots are allowed to write to
PILOT_WRITE_ACTIONS = {
    'update_hours', 'squawks', 'notes', 'oil_records', 'fuel_records', 'flight_logs',
}

# Models that pilots can CREATE via standalone viewsets.
# This set is consulted only by AircraftScopedMixin.perform_create — it does NOT
# grant update or delete access.  For all unsafe methods on existing objects,
# check_object_permissions requires owner+ regardless of this set.
PILOT_CREATABLE_MODELS = {'squawk', 'consumablerecord', 'aircraftnote'}


def get_user_role(user, aircraft):
    """Return the effective role for a user on an aircraft.

    Returns 'admin', 'owner', 'pilot', or None.
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return 'admin'
    try:
        role_obj = AircraftRole.objects.get(aircraft=aircraft, user=user)
        return role_obj.role
    except AircraftRole.DoesNotExist:
        return None


def get_user_role_from_prefetch(user, aircraft):
    """Like get_user_role but uses prefetched roles to avoid extra queries."""
    if not user or not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return 'admin'
    for role in aircraft.roles.all():
        if role.user_id == user.id:
            return role.role
    return None


def has_aircraft_permission(user, aircraft, required_role):
    """Check if user has at least the required role on the aircraft."""
    role = get_user_role(user, aircraft)
    if role is None:
        return False
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def _resolve_aircraft(obj):
    """Resolve the Aircraft instance from a model object.

    Walks the FK chain via the object's _aircraft_fk_fields (set by
    AircraftScopedMixin) or falls back to common patterns.
    """
    if isinstance(obj, Aircraft):
        return obj
    # Direct FK
    if hasattr(obj, 'aircraft') and isinstance(obj.aircraft, Aircraft):
        return obj.aircraft
    # One level deep (e.g., DocumentImage.document.aircraft)
    if hasattr(obj, 'document') and hasattr(obj.document, 'aircraft'):
        return obj.document.aircraft
    return None


class IsAircraftOwnerOrAdmin(permissions.BasePermission):
    """Requires owner or admin role on the aircraft."""

    def has_object_permission(self, request, view, obj):
        aircraft = _resolve_aircraft(obj)
        if aircraft is None:
            return False
        return has_aircraft_permission(request.user, aircraft, 'owner')


class IsAircraftPilotOrAbove(permissions.BasePermission):
    """Requires at least pilot role.

    Safe methods (GET, HEAD, OPTIONS) are allowed for any role >= pilot.
    Unsafe methods are allowed for owners+ unless the action is in PILOT_WRITE_ACTIONS.
    """

    def has_object_permission(self, request, view, obj):
        aircraft = _resolve_aircraft(obj)
        if aircraft is None:
            return False
        role = get_user_role(request.user, aircraft)
        if role is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        action = getattr(view, 'action', None)
        if action in PILOT_WRITE_ACTIONS:
            return True  # pilot+ can do these
        return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get('owner', 0)


def user_can_create_aircraft(user):
    """
    Return True if the user is permitted to create or import aircraft.

    Controlled by the AIRCRAFT_CREATE_PERMISSION setting:
      'any'    — any authenticated user (default)
      'owners' — users who already own at least one aircraft (plus admins)
      'admin'  — staff/superusers only
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    setting = getattr(settings, 'AIRCRAFT_CREATE_PERMISSION', 'any')
    if setting == 'admin':
        return False
    if setting == 'owners':
        return AircraftRole.objects.filter(user=user, role='owner').exists()
    return True  # 'any'


class CanCreateAircraft(permissions.BasePermission):
    """DRF permission enforcing AIRCRAFT_CREATE_PERMISSION."""

    def has_permission(self, request, view):
        return user_can_create_aircraft(request.user)


class IsAdAircraftOwnerOrAdmin(permissions.BasePermission):
    """
    Allows write access to an AD if the user is an admin, or is an owner of
    at least one aircraft that the AD is currently associated with.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        from core.models import AircraftRole
        return AircraftRole.objects.filter(
            user=user,
            role='owner',
            aircraft__in=obj.applicable_aircraft.all(),
        ).exists()


class IsPublicShareOrAuthenticated(permissions.BasePermission):
    """Allows unauthenticated read access via share token, or authenticated role-based access."""

    def has_permission(self, request, view):
        # If there's a share_token in the URL, allow read access
        share_token = view.kwargs.get('share_token')
        if share_token and request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated
