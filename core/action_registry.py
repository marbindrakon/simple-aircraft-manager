# Action permission routing registry.
# Each mixin registers its actions at module load time.
# AircraftViewSet.get_permissions() consults the registry.

from core.permissions import IsAircraftOwnerOrAdmin, IsAircraftPilotOrAbove
from rest_framework.permissions import SAFE_METHODS

_OWNER_ACTIONS = set()          # require IsAircraftOwnerOrAdmin always
_PILOT_ACTIONS = set()          # require IsAircraftPilotOrAbove always
_READ_PILOT_WRITE_OWNER = set() # GET → pilot, POST/DELETE → owner


def register_owner_actions(*actions):
    _OWNER_ACTIONS.update(actions)


def register_pilot_actions(*actions):
    _PILOT_ACTIONS.update(actions)


def register_read_pilot_write_owner(*actions):
    _READ_PILOT_WRITE_OWNER.update(actions)


def get_action_permissions(action_name, http_method=None):
    """Returns (found: bool, permission_classes: list | None)."""
    if action_name in _OWNER_ACTIONS:
        return True, [IsAircraftOwnerOrAdmin()]
    if action_name in _PILOT_ACTIONS:
        return True, [IsAircraftPilotOrAbove()]
    if action_name in _READ_PILOT_WRITE_OWNER:
        if http_method and http_method in SAFE_METHODS:
            return True, [IsAircraftPilotOrAbove()]
        return True, [IsAircraftOwnerOrAdmin()]
    return False, None
