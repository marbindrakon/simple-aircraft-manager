"""
Tests for health/services.py:
  - end_of_month_after
  - ad_compliance_status
  - inspection_compliance_status
  - calculate_airworthiness
"""

import datetime
from decimal import Decimal

import pytest

from health.models import (
    AD, ADCompliance, Component, ComponentType, InspectionRecord, InspectionType, Squawk,
)
from health.services import (
    STATUS_COMPLIANT,
    STATUS_DUE_SOON,
    STATUS_OVERDUE,
    ad_compliance_status,
    calculate_airworthiness,
    end_of_month_after,
    inspection_compliance_status,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# end_of_month_after
# ---------------------------------------------------------------------------

class TestEndOfMonthAfter:

    def test_jan31_plus_1_month_gives_feb_end(self):
        """Adding 1 month to Jan 31 should give the last day of February."""
        result = end_of_month_after(datetime.date(2023, 1, 31), 1)
        assert result == datetime.date(2023, 2, 28)

    def test_jan31_plus_1_month_leap_year(self):
        """Adding 1 month to Jan 31 in a leap year should give Feb 29."""
        result = end_of_month_after(datetime.date(2024, 1, 31), 1)
        assert result == datetime.date(2024, 2, 29)

    def test_dec31_plus_1_month_gives_jan31_next_year(self):
        """Adding 1 month to Dec 31 should give Jan 31 of the next year."""
        result = end_of_month_after(datetime.date(2023, 12, 31), 1)
        assert result == datetime.date(2024, 1, 31)

    def test_6_months_from_march(self):
        """Adding 6 months from March 15 should land in September."""
        result = end_of_month_after(datetime.date(2023, 3, 15), 6)
        assert result == datetime.date(2023, 9, 30)

    def test_12_months_from_feb29_leap_to_non_leap(self):
        """Adding 12 months from Feb 29, 2020 (leap) should give Feb 28, 2021."""
        result = end_of_month_after(datetime.date(2020, 2, 29), 12)
        assert result == datetime.date(2021, 2, 28)

    def test_returns_last_day_of_target_month(self):
        """Result is always the last day of the computed month."""
        result = end_of_month_after(datetime.date(2023, 8, 1), 1)
        assert result == datetime.date(2023, 9, 30)


# ---------------------------------------------------------------------------
# ad_compliance_status
# ---------------------------------------------------------------------------

class TestAdComplianceStatus:

    def _make_ad(self, aircraft, **kwargs):
        defaults = dict(
            name='TEST-AD',
            short_description='Test AD',
            mandatory=True,
            compliance_type='standard',
            recurring=False,
            recurring_hours=Decimal('0.0'),
            recurring_months=0,
        )
        defaults.update(kwargs)
        ad = AD.objects.create(**defaults)
        ad.applicable_aircraft.add(aircraft)
        return ad

    def _make_compliance(self, ad, aircraft, **kwargs):
        defaults = dict(
            date_complied=datetime.date.today(),
            compliance_notes='',
            permanent=False,
            next_due_at_time=Decimal('0.0'),
        )
        defaults.update(kwargs)
        return ADCompliance.objects.create(ad=ad, aircraft=aircraft, **defaults)

    def test_conditional_ad_always_compliant_without_record(self, aircraft):
        ad = self._make_ad(aircraft, compliance_type='conditional')
        rank, _ = ad_compliance_status(ad, None, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_conditional_ad_always_compliant_with_record(self, aircraft):
        ad = self._make_ad(aircraft, compliance_type='conditional')
        compliance = self._make_compliance(ad, aircraft)
        rank, _ = ad_compliance_status(ad, compliance, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_mandatory_ad_no_compliance_is_overdue(self, aircraft):
        ad = self._make_ad(aircraft, mandatory=True)
        rank, _ = ad_compliance_status(ad, None, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE

    def test_permanent_compliance_is_compliant(self, aircraft):
        ad = self._make_ad(aircraft)
        compliance = self._make_compliance(ad, aircraft, permanent=True)
        rank, _ = ad_compliance_status(ad, compliance, Decimal('200.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_non_recurring_with_compliance_is_compliant(self, aircraft):
        """Non-recurring AD with one compliance record (next_due_at_time=0) → COMPLIANT."""
        ad = self._make_ad(aircraft, recurring=False)
        compliance = self._make_compliance(
            ad, aircraft,
            next_due_at_time=Decimal('0.0'),
            permanent=False,
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_hours_based_recurring_compliant(self, aircraft):
        """Aircraft tach=50, last complied at 0, next_due_at_time=100 → COMPLIANT."""
        ad = self._make_ad(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        compliance = self._make_compliance(
            ad, aircraft,
            next_due_at_time=Decimal('100.0'),
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('50.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_hours_based_recurring_due_soon(self, aircraft):
        """Within 10 hrs of next_due_at_time → DUE_SOON."""
        ad = self._make_ad(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        compliance = self._make_compliance(
            ad, aircraft,
            next_due_at_time=Decimal('100.0'),
        )
        # 95 hours: 100 - 95 = 5 hrs remaining → within 10-hr threshold
        rank, _ = ad_compliance_status(ad, compliance, Decimal('95.0'), datetime.date.today())
        assert rank == STATUS_DUE_SOON

    def test_hours_based_recurring_overdue(self, aircraft):
        """At or past next_due_at_time → OVERDUE."""
        ad = self._make_ad(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        compliance = self._make_compliance(
            ad, aircraft,
            next_due_at_time=Decimal('100.0'),
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('105.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE

    def test_calendar_based_recurring_compliant(self, aircraft):
        """Complied today with 12-month interval → COMPLIANT."""
        ad = self._make_ad(aircraft, recurring=True, recurring_months=12)
        compliance = self._make_compliance(
            ad, aircraft,
            date_complied=datetime.date.today(),
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_calendar_based_recurring_due_soon(self, aircraft):
        """Complied 11.5 months ago (within 30 days of next due) → DUE_SOON."""
        ad = self._make_ad(aircraft, recurring=True, recurring_months=12)
        complied_date = datetime.date.today() - datetime.timedelta(days=350)
        compliance = self._make_compliance(
            ad, aircraft,
            date_complied=complied_date,
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_DUE_SOON

    def test_calendar_based_recurring_overdue(self, aircraft):
        """Complied 13 months ago → OVERDUE."""
        ad = self._make_ad(aircraft, recurring=True, recurring_months=12)
        complied_date = datetime.date.today() - datetime.timedelta(days=400)
        compliance = self._make_compliance(
            ad, aircraft,
            date_complied=complied_date,
        )
        rank, _ = ad_compliance_status(ad, compliance, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE


# ---------------------------------------------------------------------------
# inspection_compliance_status
# ---------------------------------------------------------------------------

class TestInspectionComplianceStatus:

    def _make_insp_type(self, aircraft, **kwargs):
        defaults = dict(
            name='Test Inspection',
            recurring=False,
            required=True,
            recurring_months=0,
            recurring_days=0,
            recurring_hours=Decimal('0.0'),
        )
        defaults.update(kwargs)
        it = InspectionType.objects.create(**defaults)
        it.applicable_aircraft.add(aircraft)
        return it

    def _make_record(self, insp_type, aircraft, **kwargs):
        defaults = dict(
            date=datetime.date.today(),
            aircraft_hours=None,
        )
        defaults.update(kwargs)
        return InspectionRecord.objects.create(
            inspection_type=insp_type,
            aircraft=aircraft,
            **defaults,
        )

    def test_non_recurring_with_record_is_compliant(self, aircraft):
        insp_type = self._make_insp_type(aircraft, recurring=False)
        record = self._make_record(insp_type, aircraft)
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_non_recurring_without_record_is_overdue(self, aircraft):
        insp_type = self._make_insp_type(aircraft, recurring=False)
        rank, _ = inspection_compliance_status(insp_type, None, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE

    def test_recurring_months_record_today_is_compliant(self, aircraft):
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_months=12)
        record = self._make_record(insp_type, aircraft, date=datetime.date.today())
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_recurring_months_record_almost_due_is_due_soon(self, aircraft):
        """Record from ~11.9 months ago (within 30 days of next due) → DUE_SOON."""
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_months=12)
        record_date = datetime.date.today() - datetime.timedelta(days=350)
        record = self._make_record(insp_type, aircraft, date=record_date)
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_DUE_SOON

    def test_recurring_months_record_13_months_ago_is_overdue(self, aircraft):
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_months=12)
        record_date = datetime.date.today() - datetime.timedelta(days=400)
        record = self._make_record(insp_type, aircraft, date=record_date)
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE

    def test_recurring_hours_compliant(self, aircraft):
        """Record at 0 hrs, aircraft now at 50, interval=100 → COMPLIANT."""
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        record = self._make_record(insp_type, aircraft, aircraft_hours=Decimal('0.0'))
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('50.0'), datetime.date.today())
        assert rank == STATUS_COMPLIANT

    def test_recurring_hours_due_soon(self, aircraft):
        """Record at 0 hrs, aircraft now at 95, interval=100 → DUE_SOON (5 hrs left, within 10-hr threshold)."""
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        record = self._make_record(insp_type, aircraft, aircraft_hours=Decimal('0.0'))
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('95.0'), datetime.date.today())
        assert rank == STATUS_DUE_SOON

    def test_recurring_hours_overdue(self, aircraft):
        """Record at 0 hrs, aircraft now at 105, interval=100 → OVERDUE."""
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_hours=Decimal('100.0'))
        record = self._make_record(insp_type, aircraft, aircraft_hours=Decimal('0.0'))
        rank, _ = inspection_compliance_status(insp_type, record, Decimal('105.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE

    def test_recurring_no_record_is_overdue(self, aircraft):
        insp_type = self._make_insp_type(aircraft, recurring=True, recurring_months=12)
        rank, _ = inspection_compliance_status(insp_type, None, Decimal('100.0'), datetime.date.today())
        assert rank == STATUS_OVERDUE


# ---------------------------------------------------------------------------
# calculate_airworthiness
# ---------------------------------------------------------------------------

class TestCalculateAirworthiness:

    def test_clean_aircraft_is_green(self, aircraft):
        """Aircraft with no issues should be GREEN."""
        result = calculate_airworthiness(aircraft)
        assert result.status == 'GREEN'
        assert result.issues == []

    def test_grounding_squawk_gives_red(self, aircraft):
        """Unresolved priority-0 squawk → RED."""
        Squawk.objects.create(
            aircraft=aircraft,
            priority=0,
            issue_reported='Engine fire',
            resolved=False,
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'RED'
        categories = [i.category for i in result.issues]
        assert 'SQUAWK' in categories

    def test_resolved_grounding_squawk_does_not_trigger_red(self, aircraft):
        """Resolved priority-0 squawk should NOT affect airworthiness."""
        Squawk.objects.create(
            aircraft=aircraft,
            priority=0,
            issue_reported='Fixed issue',
            resolved=True,
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'GREEN'

    def test_mandatory_overdue_ad_gives_red(self, aircraft):
        """Mandatory AD with no compliance → RED."""
        ad = AD.objects.create(
            name='AD-OVERDUE',
            short_description='Overdue AD',
            mandatory=True,
            compliance_type='standard',
        )
        ad.applicable_aircraft.add(aircraft)
        result = calculate_airworthiness(aircraft)
        assert result.status == 'RED'
        categories = [i.category for i in result.issues]
        assert 'AD' in categories

    def test_non_mandatory_ad_does_not_trigger_red(self, aircraft):
        """Non-mandatory AD with no compliance → no RED."""
        ad = AD.objects.create(
            name='AD-OPTIONAL',
            short_description='Optional bulletin',
            mandatory=False,
            compliance_type='standard',
        )
        ad.applicable_aircraft.add(aircraft)
        result = calculate_airworthiness(aircraft)
        assert result.status == 'GREEN'

    def test_overdue_required_inspection_gives_red(self, aircraft):
        """Required recurring inspection with no record → RED."""
        insp_type = InspectionType.objects.create(
            name='Annual',
            recurring=True,
            required=True,
            recurring_months=12,
        )
        insp_type.applicable_aircraft.add(aircraft)
        result = calculate_airworthiness(aircraft)
        assert result.status == 'RED'
        categories = [i.category for i in result.issues]
        assert 'INSPECTION' in categories

    def test_overdue_replacement_critical_in_use_component_gives_red(self, aircraft, component_type):
        """replacement_critical IN-USE component past its hours interval → RED."""
        Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            status='IN-USE',
            date_in_service=datetime.date.today(),
            manufacturer='Champion',
            model='Oil Filter',
            replacement_critical=True,
            replacement_hours=50,
            hours_since_overhaul=Decimal('60.0'),
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'RED'
        categories = [i.category for i in result.issues]
        assert 'COMPONENT' in categories

    def test_spare_replacement_critical_component_is_not_checked(self, aircraft, component_type):
        """SPARE component should not trigger airworthiness issues even if overdue."""
        Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            status='SPARE',
            date_in_service=datetime.date.today(),
            manufacturer='Champion',
            model='Oil Filter',
            replacement_critical=True,
            replacement_hours=50,
            hours_since_overhaul=Decimal('60.0'),
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'GREEN'

    def test_approaching_replacement_hours_gives_orange(self, aircraft, component_type):
        """Component within 10 hrs of replacement → ORANGE."""
        Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            status='IN-USE',
            date_in_service=datetime.date.today(),
            manufacturer='Champion',
            model='Oil Filter',
            replacement_critical=True,
            replacement_hours=50,
            hours_since_overhaul=Decimal('45.0'),  # 5 hrs left → within 10-hr threshold
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'ORANGE'
        severities = [i.severity for i in result.issues]
        assert 'ORANGE' in severities

    def test_multiple_issues_worst_wins(self, aircraft, component_type):
        """Multiple issues: ORANGE + RED → overall RED."""
        # Orange: approaching replacement
        Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            status='IN-USE',
            date_in_service=datetime.date.today(),
            manufacturer='Champion',
            model='Oil Filter',
            replacement_critical=True,
            replacement_hours=50,
            hours_since_overhaul=Decimal('45.0'),
        )
        # Red: grounding squawk
        Squawk.objects.create(
            aircraft=aircraft,
            priority=0,
            issue_reported='Grounding issue',
            resolved=False,
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'RED'
        severities = [i.severity for i in result.issues]
        assert 'RED' in severities
        assert 'ORANGE' in severities

    def test_approaching_inspection_gives_orange(self, aircraft):
        """Required inspection due within 30 days → ORANGE."""
        insp_type = InspectionType.objects.create(
            name='Annual',
            recurring=True,
            required=True,
            recurring_months=12,
        )
        insp_type.applicable_aircraft.add(aircraft)
        # Record from ~11.9 months ago → due within 30 days
        record_date = datetime.date.today() - datetime.timedelta(days=350)
        InspectionRecord.objects.create(
            inspection_type=insp_type,
            aircraft=aircraft,
            date=record_date,
        )
        result = calculate_airworthiness(aircraft)
        assert result.status == 'ORANGE'
