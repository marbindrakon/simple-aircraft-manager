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
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from django.db.models import Q

from health.models import (
    AD, ADCompliance, Squawk, InspectionType, InspectionRecord, Component
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
    current_hours = aircraft.flight_time
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


def _check_ad_compliance(aircraft, current_hours: Decimal, today: date, result: AirworthinessStatus):
    """Check AD compliance status."""
    aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)
    component_ids = aircraft.components.values_list('id', flat=True)
    component_ads = AD.objects.filter(applicable_component__in=component_ids)
    all_ads = (aircraft_ads | component_ads).distinct()

    for ad in all_ads:
        if ad.compliance_type == 'conditional':
            continue

        compliance = ADCompliance.objects.filter(
            ad=ad
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date_complied').first()

        rank, _ = ad_compliance_status(ad, compliance, current_hours, today)

        if rank == STATUS_OVERDUE:
            if not compliance:
                desc = f'{ad.short_description}. No compliance record found.'
            else:
                desc = f'{ad.short_description}. Compliance overdue.'
            result.issues.append(AirworthinessIssue(
                category='AD',
                severity=STATUS_RED,
                title=f'AD {ad.name} - Overdue',
                description=desc,
                item_id=str(ad.id),
            ))
        elif rank == STATUS_DUE_SOON:
            result.issues.append(AirworthinessIssue(
                category='AD',
                severity=STATUS_ORANGE,
                title=f'AD {ad.name} - Due Soon',
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
