"""
Aircraft resolution and access checks for MCP tools.
"""
from django.core.exceptions import ValidationError

from core.models import Aircraft
from core.permissions import get_user_role


class ToolError(Exception):
    """User-facing tool failure — the message is returned to the MCP client
    as an isError result (never a stack trace)."""


def resolve_aircraft(user, aircraft_id, require_owner=False):
    """
    Return the Aircraft the user may access, or raise ToolError.

    Unknown IDs and no-role aircraft raise the same "not found" error so the
    endpoint can't be used to enumerate aircraft UUIDs. Any role (pilot and
    above) grants access — the v1 tool set matches the pilot permission tier.
    Pass require_owner=True for the few tools that map to owner-only web
    actions (e.g. resolving squawks).
    """
    try:
        aircraft = Aircraft.objects.get(id=aircraft_id)
    except (Aircraft.DoesNotExist, ValidationError, ValueError, TypeError):
        raise ToolError('Aircraft not found')
    role = get_user_role(user, aircraft)
    if role is None:
        raise ToolError('Aircraft not found')
    if require_owner and role not in ('owner', 'admin'):
        raise ToolError('This action requires the owner role on this aircraft')
    return aircraft
