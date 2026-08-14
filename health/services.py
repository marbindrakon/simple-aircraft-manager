"""
Airworthiness status calculation service.

Determines if an aircraft is safe to fly based on:
1. AD compliance status
2. Grounding squawks
3. Inspection recurrency
4. Component replacement intervals
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q

from health.models import (
    AD, ADCompliance, Squawk, InspectionType, InspectionRecord, Component,
    ConsumableRecord,
)


# Status constants
STATUS_RED = 'RED'
STATUS_ORANGE = 'ORANGE'
STATUS_GREEN = 'GREEN'

# Thresholds for ORANGE status
HOURS_WARNING_THRESHOLD = Decimal('10.0')  # 10 flight hours
DAYS_WARNING_THRESHOLD = 30  # 30 days


@dataclass
class AirworthinessIssue:
    """Represents a single airworthiness issue."""
    category: str  # 'AD', 'SQUAWK', 'INSPECTION', 'COMPONENT'
    severity: str  # 'RED' or 'ORANGE'
    title: str
    description: str
    item_id: str = ''


@dataclass
class AirworthinessStatus:
    """Complete airworthiness status for an aircraft."""
    status: str = STATUS_GREEN
    issues: List[AirworthinessIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'status': self.status,
            'can_fly': self.status == STATUS_GREEN,
            'issues': [
                {
                    'category': issue.category,
                    'severity': issue.severity,
                    'title': issue.title,
                    'description': issue.description,
                    'item_id': issue.item_id,
                }
                for issue in self.issues
            ],
            'issue_count': len(self.issues),
            'red_count': sum(1 for i in self.issues if i.severity == STATUS_RED),
            'orange_count': sum(1 for i in self.issues if i.severity == STATUS_ORANGE),
        }


def end_of_month_after(start_date: date, months: int) -> date:
    """Return the last day of the month that is ``months`` after ``start_date``."""
    total_months = (start_date.year * 12 + start_date.month - 1) + months
    year = total_months // 12
    month = total_months % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


# ── Shared status helpers used by both airworthiness checks and API views ──

# Status rank: 0=compliant, 1=due_soon, 2=overdue
STATUS_COMPLIANT = 0
STATUS_DUE_SOON = 1
STATUS_OVERDUE = 2
STATUS_LABELS = ['compliant', 'due_soon', 'overdue']


def ad_compliance_status(ad, compliance, current_hours: Decimal, today: date) -> Tuple[int, dict]:
    """
    Compute the compliance status rank for a single AD given its latest compliance record.
    Returns (status_rank, extra_fields_dict) where extra_fields_dict may contain
    'next_due_date' and 'next_due_date_display' keys.
    """
    extras = {}

    if ad.compliance_type == 'conditional':
        return (STATUS_COMPLIANT if compliance else STATUS_COMPLIANT), extras

    if not compliance:
        return STATUS_OVERDUE, extras

    if compliance.permanent:
        return STATUS_COMPLIANT, extras

    rank = STATUS_COMPLIANT

    # Hours-based due
    if compliance.next_due_at_time > 0:
        if current_hours >= compliance.next_due_at_time:
            rank = max(rank, STATUS_OVERDUE)
        elif current_hours + HOURS_WARNING_THRESHOLD >= compliance.next_due_at_time:
            rank = max(rank, STATUS_DUE_SOON)

    # Calendar-based due (month recurrence)
    if ad.recurring and ad.recurring_months > 0:
        next_due_date = end_of_month_after(compliance.date_complied, ad.recurring_months)
        extras['next_due_date'] = next_due_date.isoformat()
        extras['next_due_date_display'] = next_due_date.strftime('%B %Y')
        if today > next_due_date:
            rank = max(rank, STATUS_OVERDUE)
        elif today + timedelta(days=DAYS_WARNING_THRESHOLD) >= next_due_date:
            rank = max(rank, STATUS_DUE_SOON)

    return rank, extras


def inspection_compliance_status(insp_type, last_record, current_hours: Decimal, today: date) -> Tuple[int, dict]:
    """
    Compute the compliance status rank for a single inspection type given its
    latest inspection record.  Returns (status_rank, extra_fields_dict) where
    extra_fields_dict may contain 'next_due_date' and 'next_due_hours' keys.
    """
    extras = {}

    if not last_record:
        return STATUS_OVERDUE, extras

    if not insp_type.recurring:
        return STATUS_COMPLIANT, extras

    rank = STATUS_COMPLIANT

    # Calendar-based check
    if insp_type.recurring_months > 0 or insp_type.recurring_days > 0:
        nd = last_record.date
        if insp_type.recurring_months > 0:
            nd = end_of_month_after(nd, insp_type.recurring_months)
        if insp_type.recurring_days > 0:
            nd = nd + timedelta(days=insp_type.recurring_days)
        extras['next_due_date'] = nd.isoformat()
        if today > nd:
            rank = max(rank, STATUS_OVERDUE)
        elif today + timedelta(days=DAYS_WARNING_THRESHOLD) >= nd:
            rank = max(rank, STATUS_DUE_SOON)

    # Hours-based check
    if insp_type.recurring_hours > 0:
        recurring_hrs = Decimal(str(insp_type.recurring_hours))
        hours_at = last_record.aircraft_hours
        if hours_at is None and last_record.logbook_entry:
            hours_at = last_record.logbook_entry.aircraft_hours_at_entry
        if hours_at is not None:
            hours_since = current_hours - hours_at
            extras['next_due_hours'] = float(hours_at + recurring_hrs)
            if hours_since >= recurring_hrs:
                rank = max(rank, STATUS_OVERDUE)
            elif hours_since + HOURS_WARNING_THRESHOLD >= recurring_hrs:
                rank = max(rank, STATUS_DUE_SOON)

    return rank, extras


def calculate_airworthiness(aircraft) -> AirworthinessStatus:
    """
    Calculate the airworthiness status for an aircraft.

    Returns an AirworthinessStatus object containing:
    - status: RED, ORANGE, or GREEN
    - issues: List of specific issues found
    """
    result = AirworthinessStatus()
    current_hours = aircraft.tach_time - aircraft.tach_time_offset
    today = date.today()

    # Check all conditions
    _check_ad_compliance(aircraft, current_hours, today, result)
    _check_grounding_squawks(aircraft, result)
    _check_inspection_recurrency(aircraft, current_hours, today, result)
    _check_component_replacement(aircraft, current_hours, today, result)

    # Determine overall status (RED takes priority over ORANGE)
    if any(issue.severity == STATUS_RED for issue in result.issues):
        result.status = STATUS_RED
    elif any(issue.severity == STATUS_ORANGE for issue in result.issues):
        result.status = STATUS_ORANGE
    else:
        result.status = STATUS_GREEN

    return result


_BULLETIN_LABEL = {'ad': 'AD', 'saib': 'SAIB', 'sb': 'SB', 'alert': 'Alert', 'other': 'Bulletin'}


def _check_ad_compliance(aircraft, current_hours: Decimal, today: date, result: AirworthinessStatus):
    """Check AD compliance status."""
    aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)
    component_ids = aircraft.components.values_list('id', flat=True)
    component_ads = AD.objects.filter(applicable_component__in=component_ids)
    all_ads = (aircraft_ads | component_ads).distinct()

    for ad in all_ads:
        if ad.compliance_type == 'conditional':
            continue
        if not ad.mandatory:
            continue

        compliance = ADCompliance.objects.filter(
            ad=ad
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date_complied').first()

        rank, _ = ad_compliance_status(ad, compliance, current_hours, today)

        type_label = _BULLETIN_LABEL.get(ad.bulletin_type, 'AD')

        if rank == STATUS_OVERDUE:
            if not compliance:
                desc = f'{ad.short_description}. No compliance record found.'
            else:
                desc = f'{ad.short_description}. Compliance overdue.'
            result.issues.append(AirworthinessIssue(
                category='AD',
                severity=STATUS_RED,
                title=f'{type_label} {ad.name} - Overdue',
                description=desc,
                item_id=str(ad.id),
            ))
        elif rank == STATUS_DUE_SOON:
            result.issues.append(AirworthinessIssue(
                category='AD',
                severity=STATUS_ORANGE,
                title=f'{type_label} {ad.name} - Due Soon',
                description=f'{ad.short_description}. Compliance due soon.',
                item_id=str(ad.id),
            ))


def _check_grounding_squawks(aircraft, result: AirworthinessStatus):
    """
    Check for grounding squawks.

    RED if:
    - Squawk exists with priority=0 (Ground Aircraft) and not resolved
    """
    grounding_squawks = Squawk.objects.filter(
        aircraft=aircraft,
        priority=0,  # Ground Aircraft
        resolved=False
    )

    for squawk in grounding_squawks:
        result.issues.append(AirworthinessIssue(
            category='SQUAWK',
            severity=STATUS_RED,
            title='Grounding Squawk',
            description=squawk.issue_reported[:100] if squawk.issue_reported else 'No description',
            item_id=str(squawk.id),
        ))


def _check_inspection_recurrency(aircraft, current_hours: Decimal, today: date, result: AirworthinessStatus):
    """Check inspection recurrency for required inspection types."""
    aircraft_inspections = InspectionType.objects.filter(
        applicable_aircraft=aircraft, required=True
    )
    component_ids = aircraft.components.values_list('id', flat=True)
    component_inspections = InspectionType.objects.filter(
        applicable_component__in=component_ids, required=True
    )
    all_inspections = (aircraft_inspections | component_inspections).distinct()

    for insp_type in all_inspections:
        last_inspection = InspectionRecord.objects.filter(
            inspection_type=insp_type
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date').first()

        rank, _ = inspection_compliance_status(insp_type, last_inspection, current_hours, today)

        if rank == STATUS_OVERDUE:
            if not last_inspection:
                desc = 'Required inspection has no completion record.'
                title = f'{insp_type.name} - Never Completed'
            else:
                desc = 'Inspection overdue.'
                title = f'{insp_type.name} - Overdue'
            result.issues.append(AirworthinessIssue(
                category='INSPECTION',
                severity=STATUS_RED,
                title=title,
                description=desc,
                item_id=str(insp_type.id),
            ))
        elif rank == STATUS_DUE_SOON:
            result.issues.append(AirworthinessIssue(
                category='INSPECTION',
                severity=STATUS_ORANGE,
                title=f'{insp_type.name} - Due Soon',
                description='Inspection due soon.',
                item_id=str(insp_type.id),
            ))


def _check_component_replacement(aircraft, current_hours: Decimal, today: date, result: AirworthinessStatus):
    """
    Check component replacement intervals.

    RED if:
    - Component has replacement_critical=True and exceeds replacement interval

    ORANGE if:
    - Approaching replacement interval within 10 hours or 30 days
    """
    critical_components = aircraft.components.filter(
        replacement_critical=True,
        status='IN-USE'
    )

    for component in critical_components:
        is_overdue = False
        is_approaching = False
        due_description = ''

        # Check hours-based replacement
        if component.replacement_hours:
            if component.hours_since_overhaul >= component.replacement_hours:
                is_overdue = True
                due_description = f'Replace every {component.replacement_hours} hrs. Current: {component.hours_since_overhaul} hrs.'
            elif component.hours_since_overhaul + HOURS_WARNING_THRESHOLD >= component.replacement_hours:
                is_approaching = True
                remaining = component.replacement_hours - component.hours_since_overhaul
                due_description = f'Replace in {remaining} hrs.'

        # Check calendar-based replacement
        if component.replacement_days and component.overhaul_date:
            next_replace_date = component.overhaul_date + timedelta(days=component.replacement_days)

            if today >= next_replace_date:
                is_overdue = True
                due_description = f'Replace every {component.replacement_days} days. In service since {component.date_in_service}.'
            elif today + timedelta(days=DAYS_WARNING_THRESHOLD) >= next_replace_date:
                is_approaching = True
                remaining = (next_replace_date - today).days
                due_description = f'Replace in {remaining} days.'

        component_name = f"{component.component_type.name}"
        if component.install_location:
            component_name += f" ({component.install_location})"

        if is_overdue:
            result.issues.append(AirworthinessIssue(
                category='COMPONENT',
                severity=STATUS_RED,
                title=f'{component_name} - Replacement Overdue',
                description=due_description,
                item_id=str(component.id),
            ))
        elif is_approaching:
            result.issues.append(AirworthinessIssue(
                category='COMPONENT',
                severity=STATUS_ORANGE,
                title=f'{component_name} - Replacement Due Soon',
                description=due_description,
                item_id=str(component.id),
            ))


# ---------------------------------------------------------------------------
# Shared aircraft write/read services
#
# Used by both the AircraftViewSet actions (health/aircraft_actions.py) and the
# MCP server tools (mcp_server/) so the two surfaces share one implementation.
# ---------------------------------------------------------------------------


class AircraftGroundedError(Exception):
    """Write rejected: the aircraft is grounded (RED) and the
    airworthiness_enforcement feature is enabled for it."""

    def __init__(self, airworthiness: AirworthinessStatus):
        self.airworthiness = airworthiness
        grounding = '; '.join(
            issue.title for issue in airworthiness.issues
            if issue.severity == STATUS_RED
        )
        message = "Aircraft is grounded and airworthiness enforcement is enabled"
        if grounding:
            message = f"{message}: {grounding}"
        super().__init__(message)


def enforce_airworthiness(aircraft):
    """
    Raise AircraftGroundedError when the aircraft's airworthiness status is RED
    and the per-aircraft airworthiness_enforcement feature is enabled.

    Called before writes that record flight activity (hours updates, flight
    logs). ORANGE (due soon) never blocks; maintenance writes that can clear a
    grounding (compliance records, inspections, squawk resolution) are never
    routed through this check.
    """
    from core.features import feature_available
    if not feature_available('airworthiness_enforcement', aircraft):
        return
    result = calculate_airworthiness(aircraft)
    if result.status == STATUS_RED:
        raise AircraftGroundedError(result)


def apply_hours_update(aircraft, new_tach_time: Decimal, new_hobbs_time: Optional[Decimal], user) -> Dict[str, Any]:
    """
    Set the aircraft's absolute tach (and optionally hobbs) reading and cascade
    the delta to all IN-USE components' hours_in_service/hours_since_overhaul
    (clamped at 0 so corrections can't go negative). Logs an 'hours' event.

    Raises AircraftGroundedError when airworthiness enforcement blocks the write.
    """
    from core.events import log_event

    enforce_airworthiness(aircraft)

    hours_delta = new_tach_time - aircraft.tach_time
    old_tach = aircraft.tach_time

    aircraft.tach_time = new_tach_time
    if new_hobbs_time is not None:
        aircraft.hobbs_time = new_hobbs_time
    aircraft.save()

    # ALWAYS update all in-service components (not optional)
    # Clamp component hours at 0 to prevent negative values on corrections.
    components = aircraft.components.filter(status='IN-USE')
    updated_components = []
    for component in components:
        component.hours_in_service = max(Decimal('0'), component.hours_in_service + hours_delta)
        component.hours_since_overhaul = max(Decimal('0'), component.hours_since_overhaul + hours_delta)
        component.save()
        updated_components.append(str(component.id))

    delta_sign = '+' if hours_delta >= 0 else ''
    log_event(
        aircraft, 'hours',
        f"Hours {'updated' if hours_delta >= 0 else 'corrected'} to {new_tach_time}",
        user=user,
        notes=f"Previous: {old_tach}, delta: {delta_sign}{hours_delta}",
    )

    return {
        'success': True,
        'aircraft_hours': float(aircraft.tach_time),  # backward compat
        'tach_time': float(aircraft.tach_time),
        'hobbs_time': float(aircraft.hobbs_time),
        'hours_added': float(hours_delta),
        'components_updated': len(updated_components),
    }


def create_flight_log(aircraft, serializer, user):
    """
    Create a flight log from a valid FlightLogCreateUpdateSerializer and apply
    its side effects atomically: increment aircraft tach/hobbs by the flight
    delta, sync IN-USE component hours, auto-create oil/fuel ConsumableRecords,
    and log a 'flight' event. Returns the FlightLog instance.

    Raises AircraftGroundedError when airworthiness enforcement blocks the write.
    """
    from core.events import log_event

    enforce_airworthiness(aircraft)

    with transaction.atomic():
        flight = serializer.save()
        tach_delta = flight.tach_time
        aircraft.tach_time += tach_delta
        if flight.hobbs_time:
            aircraft.hobbs_time += flight.hobbs_time
        aircraft.save()

        # Sync IN-USE component hours
        for comp in aircraft.components.filter(status='IN-USE'):
            comp.hours_in_service += tach_delta
            comp.hours_since_overhaul += tach_delta
            comp.save()

        # Auto-create ConsumableRecords for oil/fuel added
        if flight.oil_added:
            ConsumableRecord.objects.create(
                record_type=ConsumableRecord.RECORD_TYPE_OIL,
                aircraft=aircraft,
                date=flight.date,
                quantity_added=flight.oil_added,
                level_after=flight.oil_level_after,
                consumable_type=flight.oil_added_type or '',
                flight_hours=aircraft.tach_time,
                notes=f"Auto-created from flight log {flight.id}",
            )
        if flight.fuel_added:
            ConsumableRecord.objects.create(
                record_type=ConsumableRecord.RECORD_TYPE_FUEL,
                aircraft=aircraft,
                date=flight.date,
                quantity_added=flight.fuel_added,
                level_after=flight.fuel_level_after,
                consumable_type=flight.fuel_added_type or '',
                flight_hours=aircraft.tach_time,
                notes=f"Auto-created from flight log {flight.id}",
            )

        route_str = ''
        if flight.departure_location and flight.destination_location:
            route_str = f" ({flight.departure_location}→{flight.destination_location})"
        log_event(
            aircraft, 'flight',
            f"Flight logged: {flight.tach_time} hrs{route_str}",
            user=user,
        )

    return flight


def ad_status_list(aircraft) -> List[Dict[str, Any]]:
    """
    Serialized list of all ADs applicable to the aircraft (directly or via its
    components), each with latest_compliance and a compliance_status label
    ('compliant' | 'due_soon' | 'overdue' | 'no_compliance' | 'conditional')
    plus next-due extras from ad_compliance_status().
    """
    from health.serializers import ADNestedSerializer, ADComplianceNestedSerializer

    component_ids = aircraft.components.values_list('id', flat=True)
    aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)
    component_ads = AD.objects.filter(applicable_component__in=component_ids)
    all_ads = (aircraft_ads | component_ads).distinct()

    current_hours = aircraft.tach_time - aircraft.tach_time_offset

    ads_data = []
    for ad in all_ads:
        ad_dict = ADNestedSerializer(ad).data

        # Get latest compliance record
        compliance = ADCompliance.objects.filter(
            ad=ad
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date_complied').first()

        if compliance:
            ad_dict['latest_compliance'] = ADComplianceNestedSerializer(compliance).data
        else:
            ad_dict['latest_compliance'] = None

        # Conditional ADs use a separate status that doesn't affect airworthiness
        if ad.compliance_type == 'conditional':
            ad_dict['compliance_status'] = 'compliant' if compliance else 'conditional'
            ads_data.append(ad_dict)
            continue

        if not compliance:
            ad_dict['compliance_status'] = 'no_compliance'
        elif compliance.permanent:
            ad_dict['compliance_status'] = 'compliant'
        else:
            today = date.today()
            rank, extras = ad_compliance_status(ad, compliance, current_hours, today)
            ad_dict.update(extras)
            ad_dict['compliance_status'] = STATUS_LABELS[rank]

        ads_data.append(ad_dict)

    return ads_data


def inspection_status_list(aircraft) -> List[Dict[str, Any]]:
    """
    Serialized list of all InspectionTypes applicable to the aircraft (directly
    or via its components), each with latest_record and a compliance_status
    label ('compliant' | 'due_soon' | 'overdue' | 'never_completed') plus
    next-due extras from inspection_compliance_status().
    """
    from health.serializers import (
        InspectionTypeNestedSerializer, InspectionRecordNestedSerializer,
    )

    component_ids = aircraft.components.values_list('id', flat=True)
    aircraft_inspections = InspectionType.objects.filter(applicable_aircraft=aircraft)
    component_inspections = InspectionType.objects.filter(applicable_component__in=component_ids)
    all_types = (aircraft_inspections | component_inspections).distinct()

    current_hours = aircraft.tach_time - aircraft.tach_time_offset
    today = date.today()

    result = []
    for insp_type in all_types:
        type_dict = InspectionTypeNestedSerializer(insp_type).data

        last_record = InspectionRecord.objects.filter(
            inspection_type=insp_type
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date').first()

        if last_record:
            type_dict['latest_record'] = InspectionRecordNestedSerializer(last_record).data
        else:
            type_dict['latest_record'] = None

        if not last_record:
            type_dict['compliance_status'] = 'never_completed'
        else:
            rank, extras = inspection_compliance_status(insp_type, last_record, current_hours, today)
            type_dict.update(extras)
            type_dict['compliance_status'] = STATUS_LABELS[rank]

        result.append(type_dict)

    return result


def _iqr_outlier_bounds(values: List[float]) -> Optional[Tuple[float, float]]:
    """IQR outlier bounds matching the chart logic in
    aircraft-detail-consumables.js (computeOutlierBounds)."""
    if len(values) < 5:
        return None
    nums = sorted(values)
    n = len(nums)
    q1 = nums[n // 4]
    q3 = nums[(3 * n) // 4]
    iqr = q3 - q1
    if iqr == 0:
        return None
    return (q1 - 1.5 * iqr, q3 + 1.5 * iqr)


def consumption_stats(aircraft, record_type: str) -> Dict[str, Any]:
    """
    Server-side oil/fuel consumption statistics, mirroring the chart math in
    aircraft-detail-consumables.js: per-interval datapoints between consecutive
    records (sorted by flight_hours; only intervals with quantity > 0 and hours
    delta > 0), averaged over the last 20 datapoints with IQR outliers and
    excluded_from_averages records left out (falling back to all datapoints in
    the window when everything is excluded).

    Metric: oil → hours per quart (hours_delta / qty); fuel → gallons per hour
    (qty / hours_delta).
    """
    records = list(
        aircraft.consumable_records
        .filter(record_type=record_type)
        .order_by('flight_hours', 'date')
    )

    is_oil = record_type == ConsumableRecord.RECORD_TYPE_OIL
    metric_name = 'hours_per_quart' if is_oil else 'gallons_per_hour'

    datapoints = []  # (value, excluded_from_averages)
    for prev, cur in zip(records, records[1:]):
        if prev.flight_hours is None or cur.flight_hours is None:
            continue
        hours_delta = float(cur.flight_hours) - float(prev.flight_hours)
        qty = float(cur.quantity_added)
        if qty > 0 and hours_delta > 0:
            value = (hours_delta / qty) if is_oil else (qty / hours_delta)
            datapoints.append((value, bool(cur.excluded_from_averages)))

    stats: Dict[str, Any] = {
        'record_type': record_type,
        'metric': metric_name,
        'record_count': len(records),
        'interval_count': len(datapoints),
        'average': None,
        'excluded_from_average': 0,
    }
    if records:
        stats['first_record_date'] = records[0].date.isoformat()
        stats['last_record_date'] = records[-1].date.isoformat()
        stats['total_quantity_added'] = float(sum(r.quantity_added for r in records))

    if not datapoints:
        return stats

    values = [v for v, _ in datapoints]
    bounds = _iqr_outlier_bounds(values)

    window = datapoints[-20:]
    included = [
        v for v, excluded in window
        if not excluded and (bounds is None or bounds[0] <= v <= bounds[1])
    ]
    # Fallback: if every point is excluded, include them all
    source = included if included else [v for v, _ in window]
    stats['average'] = round(sum(source) / len(source), 1)
    stats['excluded_from_average'] = len(window) - len(included)
    stats['latest_value'] = round(values[-1], 1)
    return stats


def aircraft_summary_payload(aircraft, request) -> Dict[str, Any]:
    """
    The aircraft summary payload served by GET /api/aircraft/{id}/summary/ and
    the MCP get_aircraft_summary tool: aircraft (with airworthiness), all
    components, 10 most recent logbook entries, active squawks, notes, and the
    per-aircraft feature map.
    """
    from core.features import feature_available, get_feature_catalog, get_known_feature_names
    from core.serializers import AircraftSerializer, AircraftNoteNestedSerializer
    from health.serializers import (
        ComponentSerializer, LogbookEntrySerializer, SquawkNestedSerializer,
    )

    context = {'request': request}
    return {
        'aircraft': AircraftSerializer(aircraft, context=context).data,
        'components': ComponentSerializer(
            aircraft.components.all(), many=True, context=context
        ).data,
        'recent_logs': LogbookEntrySerializer(
            aircraft.logbook_entries.order_by('-date')[:10], many=True, context=context
        ).data,
        'active_squawks': SquawkNestedSerializer(
            aircraft.squawks.filter(resolved=False), many=True, context=context
        ).data,
        'notes': AircraftNoteNestedSerializer(
            aircraft.notes.order_by('-added_timestamp'), many=True, context=context
        ).data,
        'features': {f: feature_available(f, aircraft) for f in get_known_feature_names()},
        'feature_catalog': get_feature_catalog(),
    }
