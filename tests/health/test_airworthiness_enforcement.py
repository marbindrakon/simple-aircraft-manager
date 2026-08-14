"""Server-side airworthiness enforcement on hours updates and flight logs.

When the airworthiness_enforcement feature is enabled (the default) and the
aircraft is RED, update_hours and flight_logs POSTs are rejected with 409.
"""
import datetime

import pytest

from core.models import AircraftFeature
from health.models import FlightLog, Squawk


@pytest.fixture
def grounded_aircraft(aircraft):
    Squawk.objects.create(aircraft=aircraft, priority=0, issue_reported='Engine fire')
    return aircraft


@pytest.mark.django_db
class TestAirworthinessEnforcement:
    def test_update_hours_blocked_when_grounded(self, owner_client, grounded_aircraft):
        response = owner_client.post(
            f'/api/aircraft/{grounded_aircraft.id}/update_hours/',
            {'new_tach_time': 101.0}, format='json',
        )
        assert response.status_code == 409
        assert 'grounded' in response.data['error']
        assert response.data['airworthiness']['status'] == 'RED'
        grounded_aircraft.refresh_from_db()
        assert float(grounded_aircraft.tach_time) == 100.0

    def test_flight_log_blocked_when_grounded(self, owner_client, grounded_aircraft):
        response = owner_client.post(
            f'/api/aircraft/{grounded_aircraft.id}/flight_logs/',
            {'date': datetime.date.today().isoformat(), 'tach_time': 1.0},
            format='json',
        )
        assert response.status_code == 409
        assert FlightLog.objects.count() == 0

    def test_allowed_when_enforcement_disabled(self, owner_client, grounded_aircraft):
        AircraftFeature.objects.create(
            aircraft=grounded_aircraft, feature='airworthiness_enforcement', enabled=False)
        response = owner_client.post(
            f'/api/aircraft/{grounded_aircraft.id}/update_hours/',
            {'new_tach_time': 101.0}, format='json',
        )
        assert response.status_code == 200

    def test_orange_does_not_block(self, owner_client, aircraft, replacement_component):
        # replacement at 50 hrs, component at 45 → due soon (ORANGE), not grounded
        replacement_component.hours_since_overhaul = 45
        replacement_component.save()
        response = owner_client.post(
            f'/api/aircraft/{aircraft.id}/update_hours/',
            {'new_tach_time': 101.0}, format='json',
        )
        assert response.status_code == 200
