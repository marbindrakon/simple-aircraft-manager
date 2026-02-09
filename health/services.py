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


def _end_of_month_after(start_date: date, months: int) -> date:
    """Return the last day of the month that is ``months`` after ``start_date``."""
    total_months = (start_date.year * 12 + start_date.month - 1) + months
    year = total_months // 12
    month = total_months % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


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
    """
    Check AD compliance status.

    RED if:
    - AD applies and has no compliance entry
    - AD applies and compliance is not permanent and next_due_at_time <= current_hours

    ORANGE if:
    - AD applies and compliance is not permanent and next_due_at_time <= current_hours + 10
    """
    # Get all ADs applicable to this aircraft
    aircraft_ads = AD.objects.filter(applicable_aircraft=aircraft)

    # Get all ADs applicable to aircraft components
    component_ids = aircraft.components.values_list('id', flat=True)
    component_ads = AD.objects.filter(applicable_component__in=component_ids)

    # Combine all applicable ADs
    all_ads = (aircraft_ads | component_ads).distinct()

    for ad in all_ads:
        # Get compliance records for this AD related to this aircraft
        compliance = ADCompliance.objects.filter(
            ad=ad
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date_complied').first()

        if not compliance:
            # No compliance record - RED
            result.issues.append(AirworthinessIssue(
                category='AD',
                severity=STATUS_RED,
                title=f'AD {ad.name} - No Compliance',
                description=f'{ad.short_description}. No compliance record found.',
                item_id=str(ad.id),
            ))
        elif not compliance.permanent:
            severity = None  # None / STATUS_ORANGE / STATUS_RED
            parts = []

            # Check if due based on hours
            if compliance.next_due_at_time > 0:
                if current_hours >= compliance.next_due_at_time:
                    severity = STATUS_RED
                    parts.append(f'Due at {compliance.next_due_at_time} hrs, current: {current_hours} hrs.')
                elif current_hours + HOURS_WARNING_THRESHOLD >= compliance.next_due_at_time:
                    severity = STATUS_ORANGE
                    hours_remaining = compliance.next_due_at_time - current_hours
                    parts.append(f'Due in {hours_remaining} hrs.')

            # Check if due based on calendar months
            if ad.recurring and ad.recurring_months > 0:
                next_due_date = _end_of_month_after(compliance.date_complied, ad.recurring_months)
                if today > next_due_date:
                    severity = STATUS_RED
                    parts.append(f'Due by end of {next_due_date.strftime("%B %Y")}. Last complied {compliance.date_complied}.')
                elif today + timedelta(days=DAYS_WARNING_THRESHOLD) >= next_due_date:
                    if severity is None:
                        severity = STATUS_ORANGE
                    remaining = (next_due_date - today).days
                    parts.append(f'Due by end of {next_due_date.strftime("%B %Y")}. {remaining} days remaining.')

            if severity and parts:
                title_suffix = 'Overdue' if severity == STATUS_RED else 'Due Soon'
                result.issues.append(AirworthinessIssue(
                    category='AD',
                    severity=severity,
                    title=f'AD {ad.name} - {title_suffix}',
                    description=f'{ad.short_description}. {" ".join(parts)}',
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
    """
    Check inspection recurrency.

    RED if:
    - Required inspection type applies and no record exists within recurring period

    ORANGE if:
    - Inspection coming due within 10 hours or 30 days
    """
    # Get inspection types applicable to this aircraft
    aircraft_inspections = InspectionType.objects.filter(
        applicable_aircraft=aircraft,
        required=True
    )

    # Get inspection types applicable to aircraft components
    component_ids = aircraft.components.values_list('id', flat=True)
    component_inspections = InspectionType.objects.filter(
        applicable_component__in=component_ids,
        required=True
    )

    all_inspections = (aircraft_inspections | component_inspections).distinct()

    for insp_type in all_inspections:
        # Get most recent inspection record
        last_inspection = InspectionRecord.objects.filter(
            inspection_type=insp_type
        ).filter(
            Q(aircraft=aircraft) | Q(component__aircraft=aircraft)
        ).order_by('-date').first()

        if not last_inspection:
            # No inspection record ever - RED
            result.issues.append(AirworthinessIssue(
                category='INSPECTION',
                severity=STATUS_RED,
                title=f'{insp_type.name} - Never Completed',
                description=f'Required inspection has no completion record.',
                item_id=str(insp_type.id),
            ))
            continue

        if not insp_type.recurring:
            # Non-recurring inspection completed - OK
            continue

        # Check recurring inspection due dates
        severity = None  # None / STATUS_ORANGE / STATUS_RED
        parts = []

        # Check hours-based recurrency
        if insp_type.recurring_hours > 0:
            next_due_hours = Decimal(str(insp_type.recurring_hours))

            # Check if we have logbook entry with hours
            if last_inspection.logbook_entry and last_inspection.logbook_entry.aircraft_hours_at_entry:
                hours_at_inspection = last_inspection.logbook_entry.aircraft_hours_at_entry
                hours_since_inspection = current_hours - hours_at_inspection

                if hours_since_inspection >= next_due_hours:
                    severity = STATUS_RED
                    parts.append(f'Due every {next_due_hours} hrs. Last done at {hours_at_inspection} hrs.')
                elif hours_since_inspection + HOURS_WARNING_THRESHOLD >= next_due_hours:
                    severity = STATUS_ORANGE
                    remaining = next_due_hours - hours_since_inspection
                    parts.append(f'Due in {remaining} hrs.')

        # Check calendar-based recurrency
        if insp_type.recurring_days > 0 or insp_type.recurring_months > 0:
            next_due_date = last_inspection.date
            if insp_type.recurring_months > 0:
                next_due_date = _end_of_month_after(next_due_date, insp_type.recurring_months)
            if insp_type.recurring_days > 0:
                next_due_date = next_due_date + timedelta(days=insp_type.recurring_days)

            if insp_type.recurring_months > 0 and insp_type.recurring_days == 0:
                due_label = f'Due by end of {next_due_date.strftime("%B %Y")}.'
            else:
                due_label = f'Due by {next_due_date.strftime("%b %d, %Y")}.'

            if today > next_due_date:
                severity = STATUS_RED
                parts.append(f'{due_label} Last done {last_inspection.date}.')
            elif today + timedelta(days=DAYS_WARNING_THRESHOLD) >= next_due_date:
                if severity is None:
                    severity = STATUS_ORANGE
                remaining = (next_due_date - today).days
                parts.append(f'{due_label} {remaining} days remaining.')

        if severity and parts:
            title_suffix = 'Overdue' if severity == STATUS_RED else 'Due Soon'
            result.issues.append(AirworthinessIssue(
                category='INSPECTION',
                severity=severity,
                title=f'{insp_type.name} - {title_suffix}',
                description=' '.join(parts),
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
            if component.hours_in_service >= component.replacement_hours:
                is_overdue = True
                due_description = f'Replace every {component.replacement_hours} hrs. Current: {component.hours_in_service} hrs.'
            elif component.hours_in_service + HOURS_WARNING_THRESHOLD >= component.replacement_hours:
                is_approaching = True
                remaining = component.replacement_hours - component.hours_in_service
                due_description = f'Replace in {remaining} hrs.'

        # Check calendar-based replacement
        if component.replacement_days and component.date_in_service:
            next_replace_date = component.date_in_service + timedelta(days=component.replacement_days)

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
