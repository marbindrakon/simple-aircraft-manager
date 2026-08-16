"""
Read tools (scope: read). Any role on the aircraft (pilot and above).
"""
from datetime import date

from core.models import AircraftRole, EVENT_CATEGORIES
from core.serializers import AircraftEventNestedSerializer
from health.models import ConsumableRecord
from health.services import (
    ad_status_list, aircraft_summary_payload, calculate_airworthiness,
    consumption_stats, inspection_status_list,
)
from mcp_server.access import ToolError, resolve_aircraft
from mcp_server.registry import SCOPE_READ, tool

_AIRCRAFT_ID = {
    'type': 'string',
    'description': "Aircraft UUID or tail number (e.g. 'N12345', case-insensitive)",
}

# Summary logbook text is truncated at this length; search_logbook returns
# full text (fetch one entry precisely via its entry_id parameter).
SUMMARY_LOG_TEXT_LIMIT = 300

_EVENT_CATEGORY_NAMES = [c[0] for c in EVENT_CATEGORIES]


def _check_feature(aircraft, feature, label):
    from core.features import feature_available
    if not feature_available(feature, aircraft):
        raise ToolError(f"The {label} feature is disabled for this aircraft")


# Component relation fields serialized as hyperlink lists by the web
# serializer — dead weight for agents (parent_component_id/_name and
# component_type_id/_name scalars remain for the tree and type).
_COMPONENT_DROP_FIELDS = (
    'url', 'aircraft', 'parent_component', 'component_type', 'components',
    'doc_collections', 'documents', 'squawks', 'applicable_inspections',
    'ads', 'inspections', 'ad_compliance',
)


def _slim_component(comp):
    return {k: v for k, v in comp.items() if k not in _COMPONENT_DROP_FIELDS}


def _compact_aircraft(aircraft_dict):
    """
    Context-friendly aircraft object: every top-level list field on the web
    serializer is a bare UUID list (see AircraftSerializer) that an agent can't
    act on — replace each with a `<name>_count` integer. Nested dicts like
    airworthiness pass through untouched.
    """
    out = {}
    for k, v in aircraft_dict.items():
        if k == 'url':
            continue
        if isinstance(v, list):
            out[f'{k}_count'] = len(v)
        else:
            out[k] = v
    return out


def _slim_logbook_entry(entry, truncate_text=None):
    """
    Compact a serialized logbook entry for MCP responses.

    The web serializer inlines full document payloads (log_image_detail /
    related_documents_detail), each carrying the source document's complete
    page-image manifest — repeated per entry, this dominated measured responses
    (a limit=100 search was 1.39 MB, ~68% repeated manifests). Agents only
    need a reference: {id, name} plus the entry's own page_number.

    When truncate_text is set, entry text longer than that many characters is
    cut and flagged with text_truncated/text_full_length so the agent knows to
    fetch the full entry (search_logbook with entry_id).
    """
    slim = {
        k: v for k, v in entry.items()
        if k not in ('url', 'log_image', 'log_image_detail',
                     'related_documents', 'related_documents_detail')
    }
    detail = entry.get('log_image_detail')
    slim['log_document'] = (
        {'id': detail.get('id'), 'name': detail.get('name')} if detail else None
    )
    slim['related_documents'] = [
        {'id': d.get('id'), 'name': d.get('name')}
        for d in entry.get('related_documents_detail') or []
    ]
    text = slim.get('text')
    if truncate_text and isinstance(text, str) and len(text) > truncate_text:
        slim['text'] = text[:truncate_text] + '…'
        slim['text_truncated'] = True
        slim['text_full_length'] = len(text)
    return slim


@tool(
    'list_aircraft',
    "Compact roster of all aircraft the user has access to: id, tail number, "
    "make/model, status, hours, and an airworthiness rollup (status "
    "RED/ORANGE/GREEN, can_fly, issue counts). For the issue details use "
    "get_airworthiness; for a full snapshot use get_aircraft_summary. Other "
    "tools accept the tail number directly — you rarely need the id.",
    {'type': 'object', 'properties': {}, 'required': []},
    required_scope=SCOPE_READ,
)
def list_aircraft(request, args):
    from core.models import Aircraft
    user = request.user
    qs = Aircraft.objects.all()
    if not (user.is_staff or user.is_superuser):
        accessible = AircraftRole.objects.filter(user=user).values_list('aircraft_id', flat=True)
        qs = qs.filter(id__in=accessible)
    items = []
    for ac in qs:
        aw = calculate_airworthiness(ac).to_dict()
        items.append({
            'id': str(ac.id),
            'tail_number': ac.tail_number,
            'make': ac.make,
            'model': ac.model,
            'status': ac.status,
            'tach_time': float(ac.tach_time),
            'hobbs_time': float(ac.hobbs_time),
            'airworthiness': {
                k: aw[k]
                for k in ('status', 'can_fly', 'issue_count', 'red_count', 'orange_count')
            },
        })
    return {'aircraft': items, 'count': len(items)}


@tool(
    'get_aircraft_summary',
    "Full snapshot of one aircraft: details with airworthiness, all components "
    "(with hours and criticality), the 10 most recent logbook entries, active "
    "squawks, notes, and the per-aircraft feature flags. Related records "
    "appear as <name>_count integers — fetch detail with the dedicated tools "
    "(get_compliance_status, search_logbook, list_flight_logs, get_events). "
    "Recent logbook text is truncated (text_truncated=true when cut) — fetch "
    "an interesting entry's full text with search_logbook and its entry_id. "
    "Check the features map before using feature-gated tools (flight logs, "
    "oil/fuel records).",
    {'type': 'object', 'properties': {'aircraft_id': _AIRCRAFT_ID}, 'required': ['aircraft_id']},
    required_scope=SCOPE_READ,
)
def get_aircraft_summary(request, args):
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    payload = aircraft_summary_payload(aircraft, request)
    # Context-friendly shaping (web payload is untouched): counts instead of
    # UUID lists, components without hyperlink-list relations, logbook entries
    # without inlined document page manifests, no static feature catalog.
    payload['aircraft'] = _compact_aircraft(payload['aircraft'])
    payload['components'] = [_slim_component(c) for c in payload['components']]
    payload['recent_logs'] = [
        _slim_logbook_entry(e, truncate_text=SUMMARY_LOG_TEXT_LIMIT)
        for e in payload['recent_logs']
    ]
    payload.pop('feature_catalog', None)
    return payload


@tool(
    'get_airworthiness',
    "Airworthiness status of an aircraft: RED (grounded), ORANGE (attention "
    "due soon), or GREEN, with can_fly and each contributing issue (overdue "
    "ADs, grounding squawks, overdue inspections, components past replacement).",
    {'type': 'object', 'properties': {'aircraft_id': _AIRCRAFT_ID}, 'required': ['aircraft_id']},
    required_scope=SCOPE_READ,
)
def get_airworthiness(request, args):
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    return calculate_airworthiness(aircraft).to_dict()


@tool(
    'get_compliance_status',
    "Regulatory compliance detail for an aircraft: every applicable AD "
    "(airworthiness directive) and inspection type with its latest "
    "compliance/inspection record, a compliance_status label (compliant, "
    "due_soon, overdue, no_compliance/never_completed, conditional), and "
    "next-due date/hours where applicable.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'include': {
                'type': 'array',
                'items': {'type': 'string', 'enum': ['ads', 'inspections']},
                'description': "Sections to include (default: both)",
            },
        },
        'required': ['aircraft_id'],
    },
    required_scope=SCOPE_READ,
)
def get_compliance_status(request, args):
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    include = args.get('include') or ['ads', 'inspections']
    result = {}
    if 'ads' in include:
        result['ads'] = ad_status_list(aircraft)
    if 'inspections' in include:
        result['inspections'] = inspection_status_list(aircraft)
    if not result:
        raise ToolError("include must contain 'ads' and/or 'inspections'")
    return result


@tool(
    'list_squawks',
    "List squawks (reported issues) for an aircraft, newest first. Priorities: "
    "0=Ground Aircraft (grounds the plane), 1=Fix Soon, 2=Fix at Next "
    "Inspection, 3=Fix Eventually.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'resolved': {'type': 'boolean', 'description': 'Filter by resolved state (omit for all)'},
        },
        'required': ['aircraft_id'],
    },
    required_scope=SCOPE_READ,
)
def list_squawks(request, args):
    from health.serializers import SquawkNestedSerializer
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    squawks = aircraft.squawks.all().order_by('-created_at')
    if 'resolved' in args:
        squawks = squawks.filter(resolved=args['resolved'])
    data = SquawkNestedSerializer(squawks, many=True, context={'request': request}).data
    return {'squawks': data, 'count': len(data)}


@tool(
    'get_events',
    "Recent activity log for an aircraft (who did what, when): hours updates, "
    "flights, maintenance, squawks, notes, etc.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'category': {
                'type': 'string',
                'enum': _EVENT_CATEGORY_NAMES,
                'description': 'Only events in this category',
            },
            'limit': {'type': 'integer', 'description': 'Max events to return (default 50, max 200)'},
        },
        'required': ['aircraft_id'],
    },
    required_scope=SCOPE_READ,
)
def get_events(request, args):
    from core.models import AircraftEvent
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    qs = AircraftEvent.objects.filter(aircraft=aircraft).select_related('user')
    category = args.get('category')
    if category:
        if category not in _EVENT_CATEGORY_NAMES:
            raise ToolError(f"Invalid category '{category}'. Valid: {', '.join(_EVENT_CATEGORY_NAMES)}")
        qs = qs.filter(category=category)
    total = qs.count()
    limit = min(max(int(args.get('limit', 50)), 1), 200)
    events = AircraftEventNestedSerializer(qs[:limit], many=True).data
    return {'events': events, 'total': total}


@tool(
    'search_logbook',
    "Search an aircraft's maintenance logbook entries (inspections, parts "
    "replaced, mechanic signoffs — not per-flight records), newest first, "
    "with full entry text. Page through large result sets with offset; total "
    "reflects the active filters. Pass entry_id to fetch exactly one entry "
    "(e.g. to expand a truncated summary entry). Source documents are "
    "returned as {id, name} references plus the entry's page_number.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'entry_id': {'type': 'string', 'description': 'Fetch a single entry by its UUID (other filters ignored)'},
            'query': {'type': 'string', 'description': 'Text to match in entry text or signoff person'},
            'log_type': {'type': 'string', 'enum': ['AC', 'ENG', 'PROP', 'OTHER'],
                         'description': 'Logbook: AC=airframe, ENG=engine, PROP=propeller'},
            'entry_type': {'type': 'string',
                           'enum': ['MAINTENANCE', 'INSPECTION', 'FLIGHT', 'HOURS_UPDATE', 'OTHER']},
            'date_from': {'type': 'string', 'description': 'ISO date (YYYY-MM-DD), inclusive'},
            'date_to': {'type': 'string', 'description': 'ISO date (YYYY-MM-DD), inclusive'},
            'limit': {'type': 'integer', 'description': 'Max entries (default 20, max 100)'},
            'offset': {'type': 'integer', 'description': 'Entries to skip, for pagination (default 0)'},
        },
        'required': ['aircraft_id'],
    },
    required_scope=SCOPE_READ,
)
def search_logbook(request, args):
    from django.db.models import Q
    from health.serializers import LogbookEntrySerializer

    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    qs = aircraft.logbook_entries.all()

    entry_id = args.get('entry_id')
    if entry_id:
        from django.core.exceptions import ValidationError
        try:
            qs = qs.filter(id=entry_id)
        except (ValidationError, ValueError):
            raise ToolError('entry_id must be a UUID')

    query = args.get('query')
    if query:
        qs = qs.filter(Q(text__icontains=query) | Q(signoff_person__icontains=query))
    if args.get('log_type'):
        qs = qs.filter(log_type=args['log_type'])
    if args.get('entry_type'):
        qs = qs.filter(entry_type=args['entry_type'])
    for key, lookup in (('date_from', 'date__gte'), ('date_to', 'date__lte')):
        if args.get(key):
            try:
                qs = qs.filter(**{lookup: date.fromisoformat(args[key])})
            except ValueError:
                raise ToolError(f"{key} must be an ISO date (YYYY-MM-DD)")

    total = qs.count()
    limit = min(max(int(args.get('limit', 20)), 1), 100)
    offset = max(int(args.get('offset', 0)), 0)
    data = LogbookEntrySerializer(
        qs.order_by('-date', '-id')[offset:offset + limit],
        many=True, context={'request': request},
    ).data
    return {
        'entries': [_slim_logbook_entry(e) for e in data],
        'total': total,
        'offset': offset,
        'limit': limit,
    }


@tool(
    'list_flight_logs',
    "List flight log entries for an aircraft (per-flight records: date, tach "
    "delta, route, oil/fuel added), newest first.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'limit': {'type': 'integer', 'description': 'Max entries (default 25, max 100)'},
        },
        'required': ['aircraft_id'],
    },
    required_scope=SCOPE_READ,
)
def list_flight_logs(request, args):
    from health.serializers import FlightLogNestedSerializer
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    qs = aircraft.flight_logs.all()
    total = qs.count()
    limit = min(max(int(args.get('limit', 25)), 1), 100)
    data = FlightLogNestedSerializer(qs[:limit], many=True).data
    return {'flight_logs': data, 'total': total}


@tool(
    'get_consumption_stats',
    "Oil or fuel consumption statistics computed from the aircraft's "
    "consumable records: oil → average hours per quart, fuel → average gallons "
    "per hour (burn rate). Averages use the last 20 intervals, excluding "
    "statistical outliers and records marked excluded_from_averages.",
    {
        'type': 'object',
        'properties': {
            'aircraft_id': _AIRCRAFT_ID,
            'type': {'type': 'string', 'enum': ['oil', 'fuel']},
        },
        'required': ['aircraft_id', 'type'],
    },
    required_scope=SCOPE_READ,
)
def get_consumption_stats(request, args):
    aircraft = resolve_aircraft(request.user, args['aircraft_id'])
    record_type = args['type']
    if record_type == ConsumableRecord.RECORD_TYPE_OIL:
        _check_feature(aircraft, 'oil_consumption', 'oil consumption tracking')
    elif record_type == ConsumableRecord.RECORD_TYPE_FUEL:
        _check_feature(aircraft, 'fuel_consumption', 'fuel consumption tracking')
    else:
        raise ToolError("type must be 'oil' or 'fuel'")
    return consumption_stats(aircraft, record_type)
