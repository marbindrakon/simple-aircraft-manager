import datetime
from decimal import Decimal

import pytest

from core.models import AircraftEvent
from health.models import FlightLog

pytestmark = pytest.mark.django_db


def _make_flight(aircraft, tach_out=100.0, tach_in=110.0, date=None):
    """Helper to create a FlightLog for an aircraft."""
    return FlightLog.objects.create(
        aircraft=aircraft,
        date=date or datetime.date.today(),
        tach_time=Decimal(str(tach_in - tach_out)),
        tach_out=Decimal(str(tach_out)),
        tach_in=Decimal(str(tach_in)),
    )


def _get_results(data):
    """Extract list of results from either paginated or non-paginated DRF response."""
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class TestFlightLogList:
    def test_owner_sees_their_logs(self, owner_client, aircraft):
        flight = _make_flight(aircraft)
        resp = owner_client.get('/api/flight-logs/')
        assert resp.status_code == 200
        ids = [r['id'] for r in _get_results(resp.data)]
        assert str(flight.id) in ids

    def test_other_client_sees_empty_list(self, other_client, aircraft):
        _make_flight(aircraft)
        resp = other_client.get('/api/flight-logs/')
        assert resp.status_code == 200
        assert _get_results(resp.data) == []

    def test_admin_sees_all_logs(self, admin_client, aircraft):
        flight = _make_flight(aircraft)
        resp = admin_client.get('/api/flight-logs/')
        assert resp.status_code == 200
        ids = [r['id'] for r in _get_results(resp.data)]
        assert str(flight.id) in ids

    def test_pilot_can_list_flight_logs(self, pilot_client, aircraft_with_pilot):
        flight = _make_flight(aircraft_with_pilot)
        resp = pilot_client.get('/api/flight-logs/')
        assert resp.status_code == 200
        ids = [r['id'] for r in _get_results(resp.data)]
        assert str(flight.id) in ids


class TestFlightLogDetail:
    def test_owner_can_get_detail(self, owner_client, aircraft):
        flight = _make_flight(aircraft)
        resp = owner_client.get(f'/api/flight-logs/{flight.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == str(flight.id)

    def test_other_client_gets_404(self, other_client, aircraft):
        flight = _make_flight(aircraft)
        resp = other_client.get(f'/api/flight-logs/{flight.id}/')
        assert resp.status_code == 404

    def test_pilot_can_get_detail(self, pilot_client, aircraft_with_pilot):
        flight = _make_flight(aircraft_with_pilot)
        resp = pilot_client.get(f'/api/flight-logs/{flight.id}/')
        assert resp.status_code == 200


class TestFlightLogUpdate:
    def test_owner_patch_updates_aircraft_tach_time(self, owner_client, aircraft):
        # Create flight: tach_out=100, tach_in=110, tach_time=10
        flight = _make_flight(aircraft, tach_out=100.0, tach_in=110.0)
        initial_tach = Decimal(str(aircraft.tach_time))  # 100.0 from fixture

        # PATCH to change tach_in to 115, making tach_time=15 (delta=+5 from old 10)
        resp = owner_client.patch(
            f'/api/flight-logs/{flight.id}/',
            {
                'aircraft': str(aircraft.id),
                'date': str(flight.date),
                'tach_time': '15.0',
                'tach_out': '100.0',
                'tach_in': '115.0',
            },
            format='json',
        )
        assert resp.status_code == 200

        aircraft.refresh_from_db()
        # aircraft.tach_time should have increased by 5 (delta between new=15 and old=10)
        assert aircraft.tach_time == initial_tach + Decimal('5.0')

    def test_pilot_cannot_patch_flight_log(self, pilot_client, aircraft_with_pilot):
        # Pilot has a role → record is in queryset → blocked by IsAircraftOwnerOrAdmin → 403
        flight = _make_flight(aircraft_with_pilot)
        resp = pilot_client.patch(
            f'/api/flight-logs/{flight.id}/',
            {'tach_time': '20.0'},
            format='json',
        )
        assert resp.status_code == 403

    def test_other_client_cannot_patch(self, other_client, aircraft):
        # other_client has no role → record excluded from queryset → 404
        flight = _make_flight(aircraft)
        resp = other_client.patch(
            f'/api/flight-logs/{flight.id}/',
            {'tach_time': '20.0'},
            format='json',
        )
        assert resp.status_code == 404


class TestFlightLogDelete:
    def test_owner_can_delete_flight_log(self, owner_client, aircraft):
        flight = _make_flight(aircraft)
        flight_id = flight.id
        resp = owner_client.delete(f'/api/flight-logs/{flight_id}/')
        assert resp.status_code == 204
        assert not FlightLog.objects.filter(id=flight_id).exists()

    def test_delete_logs_aircraft_event(self, owner_client, aircraft):
        flight = _make_flight(aircraft)
        owner_client.delete(f'/api/flight-logs/{flight.id}/')
        events = AircraftEvent.objects.filter(aircraft=aircraft, event_name='Flight log deleted')
        assert events.exists()

    def test_pilot_cannot_delete_flight_log(self, pilot_client, aircraft_with_pilot):
        # Pilot has a role → record is in queryset → blocked by IsAircraftOwnerOrAdmin → 403
        flight = _make_flight(aircraft_with_pilot)
        resp = pilot_client.delete(f'/api/flight-logs/{flight.id}/')
        assert resp.status_code == 403
        assert FlightLog.objects.filter(id=flight.id).exists()

    def test_other_client_gets_404_on_delete(self, other_client, aircraft):
        flight = _make_flight(aircraft)
        resp = other_client.delete(f'/api/flight-logs/{flight.id}/')
        assert resp.status_code == 404
