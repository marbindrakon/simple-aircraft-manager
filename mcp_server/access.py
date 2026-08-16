"""
Aircraft resolution and access checks for MCP tools.
"""
import uuid

from django.core.exceptions import ValidationError

from core.models import Aircraft
from core.permissions import get_user_role


class ToolError(Exception):
    """User-facing tool failure — the message is returned to the MCP client
    as an isError result (never a stack trace)."""


def resolve_aircraft(user, identifier, require_owner=False):
    """
    Return the Aircraft the user may access, or raise ToolError.

    `identifier` is either the aircraft UUID or its tail number
    (case-insensitive). Tail numbers are not globally unique, so tail lookup
    only considers aircraft the user holds a role on and errors on ambiguity.
    Unknown identifiers and no-role aircraft raise the same "not found" error
    so the endpoint can't be used to enumerate aircraft. Any role (pilot and
    above) grants access — the v1 tool set matches the pilot permission tier.
    Pass require_owner=True for the few tools that map to owner-only web
    actions (e.g. resolving squawks).
    """
    identifier = str(identifier).strip()
    try:
        uuid.UUID(identifier)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False

    if is_uuid:
        try:
            aircraft = Aircraft.objects.get(id=identifier)
        except (Aircraft.DoesNotExist, ValidationError, ValueError):
            raise ToolError('Aircraft not found')
        role = get_user_role(user, aircraft)
        if role is None:
            raise ToolError('Aircraft not found')
    else:
        matches = [
            ac for ac in Aircraft.objects.filter(tail_number__iexact=identifier)
            if get_user_role(user, ac) is not None
        ]
        if not matches:
            raise ToolError('Aircraft not found')
        if len(matches) > 1:
            raise ToolError(
                f"Multiple accessible aircraft share tail number '{identifier}' — "
                "pass the aircraft UUID instead (see list_aircraft)"
            )
        aircraft = matches[0]
        role = get_user_role(user, aircraft)

    if require_owner and role not in ('owner', 'admin'):
        raise ToolError('This action requires the owner role on this aircraft')
    return aircraft
