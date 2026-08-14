"""
Write tools (scope: write). All map to the pilot permission tier
(PILOT_WRITE_ACTIONS) — any role on the aircraft may use them.
"""
from decimal import Decimal, InvalidOperation

from core.events import log_event
from health.models import ConsumableRecord
from health.services import (
    AircraftGroundedError, apply_hours_update, create_flight_log,
)
from mcp_server.access import ToolError, resolve_aircraft
from mcp_server.registry import SCOPE_WRITE, tool
from mcp_server.tools.read import _AIRCRAFT_ID, _check_feature


def _decimal(args, key, required=False):
    value = args.get(key)
    if value is None:
        if required:
            raise ToolError(f"'{key}' is required")
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ToolError(f"'{key}' must be a number")


def _grounded(e: AircraftGroundedError) -> ToolError:
    return ToolError(str(e))


@tool(
    'update_aircraft_hours',
    "Set the aircraft's tach reading. IMPORTANT: new_tach_time is the ABSOLUTE "
    "cumulative tach reading (e.g. 1234.5), NOT hours flown. The difference "
    "from the current reading is automatically applied to all in-service "
    "components' hours. To record a flight, use create_flight_log instead — "
    "never both for the same flight, or hours will be double-counted.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'new_tach_time': {'type': 'number', 'description': 'Absolute cumulative tach reading'},
            'new_hobbs_time': {'type': 'number', 'description': 'Absolute hobbs reading (optional)'},
        },
        'required': ['aircraft_id', 'new_tach_time'],
    },
    required_scope=SCOPE_WRITE,
)
def update_aircraft_hours(request, args):
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    new_tach = _decimal(args, 'new_tach_time', required=True)
    new_hobbs = _decimal(args, 'new_hobbs_time')
    try:
        return apply_hours_update(aircraft, new_tach, new_hobbs, request.user)
    except AircraftGroundedError as e:
        raise _grounded(e)


@tool(
    'create_flight_log',
    "Record a flight. IMPORTANT: tach_time is the DELTA — hours flown on this "
    "flight (e.g. 1.4), NOT the tach reading. It automatically increments the "
    "aircraft's tach/hobbs and all in-service components' hours. oil_added/"
    "fuel_added automatically create consumable records — do not also call "
    "add_consumable_record for the same top-off.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'date': {'type': 'string', 'description': 'Flight date (YYYY-MM-DD)'},
            'tach_time': {'type': 'number', 'description': 'Hours flown this flight (DELTA, not a reading)'},
            'hobbs_time': {'type': 'number', 'description': 'Hobbs hours flown this flight (optional delta)'},
            'tach_out': {'type': 'number'},
            'tach_in': {'type': 'number'},
            'departure_location': {'type': 'string'},
            'destination_location': {'type': 'string'},
            'route': {'type': 'string'},
            'oil_added': {'type': 'number', 'description': 'Quarts of oil added (auto-creates an oil record)'},
            'oil_added_type': {'type': 'string'},
            'oil_level_after': {'type': 'number'},
            'fuel_added': {'type': 'number', 'description': 'Gallons of fuel added (auto-creates a fuel record)'},
            'fuel_added_type': {'type': 'string'},
            'fuel_level_after': {'type': 'number'},
            'notes': {'type': 'string'},
        },
        'required': ['aircraft_id', 'date', 'tach_time'],
    },
    required_scope=SCOPE_WRITE,
)
def create_flight_log_tool(request, args):
    from health.serializers import (
        FlightLogCreateUpdateSerializer, FlightLogNestedSerializer,
    )
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    _check_feature(aircraft, 'flight_tracking', 'flight tracking')

    data = {k: v for k, v in args.items() if k != 'aircraft_id'}
    data['aircraft'] = str(aircraft.id)
    serializer = FlightLogCreateUpdateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    try:
        flight = create_flight_log(aircraft, serializer, request.user)
    except AircraftGroundedError as e:
        raise _grounded(e)
    return FlightLogNestedSerializer(flight).data


@tool(
    'create_squawk',
    "Report a squawk (an issue with the aircraft). Priorities: 0=Ground "
    "Aircraft (grounds the plane — use only for safety-of-flight issues), "
    "1=Fix Soon, 2=Fix at Next Inspection, 3=Fix Eventually (default).",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'issue_reported': {'type': 'string', 'description': 'Description of the issue'},
            'priority': {'type': 'integer', 'enum': [0, 1, 2, 3]},
            'notes': {'type': 'string'},
        },
        'required': ['aircraft_id', 'issue_reported'],
    },
    required_scope=SCOPE_WRITE,
)
def create_squawk(request, args):
    from health.serializers import SquawkCreateUpdateSerializer, SquawkNestedSerializer
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])

    data = {k: v for k, v in args.items() if k != 'aircraft_id'}
    data['aircraft'] = aircraft.id
    serializer = SquawkCreateUpdateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    # reported_by is not a serializer field (clients must not set it), so
    # attribute the squawk at save time.
    squawk = serializer.save(reported_by=request.user)
    log_event(
        aircraft, 'squawk',
        f"Squawk reported: {squawk.get_priority_display()}",
        user=request.user,
    )
    return SquawkNestedSerializer(squawk, context={'request': request}).data


@tool(
    'resolve_squawk',
    "Mark a squawk as resolved (the closing half of the squawk workflow — "
    "resolving a priority-0 squawk can un-ground the aircraft). Requires the "
    "OWNER role on the aircraft; pilots can report squawks but not resolve "
    "them.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'squawk_id': {'type': 'string', 'description': 'Squawk UUID (from list_squawks)'},
            'notes': {'type': 'string', 'description': 'Resolution notes to append to the squawk'},
        },
        'required': ['aircraft_id', 'squawk_id'],
    },
    required_scope=SCOPE_WRITE,
)
def resolve_squawk(request, args):
    from django.core.exceptions import ValidationError
    from health.models import Squawk
    from health.serializers import SquawkNestedSerializer

    aircraft = resolve_aircraft(request.user, args['aircraft_id'], require_owner=True)
    try:
        squawk = aircraft.squawks.get(id=args['squawk_id'])
    except (Squawk.DoesNotExist, ValidationError, ValueError, TypeError):
        raise ToolError('Squawk not found')

    already_resolved = squawk.resolved
    squawk.resolved = True
    notes = args.get('notes')
    if notes:
        squawk.notes = f"{squawk.notes}\n{notes}".strip()
    squawk.save()
    if not already_resolved:
        log_event(
            aircraft, 'squawk',
            f"Squawk resolved: {squawk.get_priority_display()}",
            user=request.user,
        )
    return SquawkNestedSerializer(squawk, context={'request': request}).data


@tool(
    'add_note',
    "Add a free-text note to an aircraft. Set public=true only if the note "
    "should be visible through the aircraft's public share links.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'text': {'type': 'string'},
            'public': {'type': 'boolean', 'description': 'Visible via public share links (default false)'},
        },
        'required': ['aircraft_id', 'text'],
    },
    required_scope=SCOPE_WRITE,
)
def add_note(request, args):
    from core.serializers import (
        AircraftNoteCreateUpdateSerializer, AircraftNoteNestedSerializer,
    )
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])

    data = {k: v for k, v in args.items() if k != 'aircraft_id'}
    data['aircraft'] = aircraft.id
    serializer = AircraftNoteCreateUpdateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    note = serializer.save(added_by=request.user)
    log_event(aircraft, 'note', "Note added", user=request.user)
    return AircraftNoteNestedSerializer(note, context={'request': request}).data


@tool(
    'add_consumable_record',
    "Record an oil or fuel top-off done outside a flight. flight_hours "
    "defaults to the aircraft's current tach reading. Do NOT use this for "
    "oil/fuel added during a flight you are logging with create_flight_log — "
    "that tool records them automatically.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'type': {'type': 'string', 'enum': ['oil', 'fuel']},
            'date': {'type': 'string', 'description': 'Date added (YYYY-MM-DD)'},
            'quantity_added': {'type': 'number', 'description': 'Quarts (oil) or gallons (fuel)'},
            'level_after': {'type': 'number'},
            'consumable_type': {'type': 'string', 'description': 'e.g. oil grade or fuel type'},
            'flight_hours': {'type': 'number', 'description': 'Tach reading when added (default: current)'},
            'notes': {'type': 'string'},
        },
        'required': ['aircraft_id', 'type', 'date', 'quantity_added'],
    },
    required_scope=SCOPE_WRITE,
)
def add_consumable_record(request, args):
    from health.serializers import (
        ConsumableRecordCreateSerializer, ConsumableRecordNestedSerializer,
    )
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    record_type = args['type']
    if record_type == ConsumableRecord.RECORD_TYPE_OIL:
        _check_feature(aircraft, 'oil_consumption', 'oil consumption tracking')
    elif record_type == ConsumableRecord.RECORD_TYPE_FUEL:
        _check_feature(aircraft, 'fuel_consumption', 'fuel consumption tracking')
    else:
        raise ToolError("type must be 'oil' or 'fuel'")

    unit = 'qt' if record_type == ConsumableRecord.RECORD_TYPE_OIL else 'gal'
    data = {k: v for k, v in args.items() if k not in ('aircraft_id', 'type')}
    data['aircraft'] = aircraft.id
    data['record_type'] = record_type
    if not data.get('flight_hours'):
        data['flight_hours'] = str(aircraft.tach_time)

    serializer = ConsumableRecordCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    record = serializer.save()
    log_event(
        aircraft, record_type,
        f"{record_type.capitalize()} added: {record.quantity_added} {unit}",
        user=request.user,
    )
    return ConsumableRecordNestedSerializer(record).data
