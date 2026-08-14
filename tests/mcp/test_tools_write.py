"""Write tools: side-effect parity with the web actions, RBAC, enforcement."""
import datetime
from decimal import Decimal

import pytest

from core.models import AircraftEvent, AircraftFeature
from health.models import ConsumableRecord, FlightLog, Squawk

from .conftest import tool_error, tool_payload

pytestmark = pytest.mark.urls('tests.mcp.urls')


class TestUpdateAircraftHours:
    def test_updates_hours_and_cascades_to_components(self, owner_mcp_client, aircraft, component):
        payload = tool_payload(owner_mcp_client, 'update_aircraft_hours', {
            'aircraft_id': str(aircraft.id),
            'new_tach_time': 105.5,
            'new_hobbs_time': 106.0,
        })
        assert payload['tach_time'] == 105.5
        assert payload['hobbs_time'] == 106.0
        assert payload['hours_added'] == 5.5
        assert payload['components_updated'] == 1
        component.refresh_from_db()
        assert component.hours_in_service == Decimal('5.5')
        assert component.hours_since_overhaul == Decimal('5.5')
        assert AircraftEvent.objects.filter(aircraft=aircraft, category='hours').exists()

    def test_pilot_can_update(self, pilot_mcp_client, aircraft_with_pilot):
        payload = tool_payload(pilot_mcp_client, 'update_aircraft_hours', {
            'aircraft_id': str(aircraft_with_pilot.id), 'new_tach_time': 101.0,
        })
        assert payload['success'] is True

    def test_no_role_not_found(self, other_mcp_client, aircraft):
        assert tool_error(other_mcp_client, 'update_aircraft_hours', {
            'aircraft_id': str(aircraft.id), 'new_tach_time': 200.0,
        }) == 'Aircraft not found'
        aircraft.refresh_from_db()
        assert float(aircraft.tach_time) == 100.0

    def test_grounded_aircraft_blocked_when_enforced(self, owner_mcp_client, aircraft):
        Squawk.objects.create(aircraft=aircraft, priority=0, issue_reported='Engine fire')
        message = tool_error(owner_mcp_client, 'update_aircraft_hours', {
            'aircraft_id': str(aircraft.id), 'new_tach_time': 101.0,
        })
        assert 'grounded' in message
        aircraft.refresh_from_db()
        assert float(aircraft.tach_time) == 100.0

    def test_grounded_aircraft_allowed_when_enforcement_off(self, owner_mcp_client, aircraft):
        Squawk.objects.create(aircraft=aircraft, priority=0, issue_reported='Engine fire')
        AircraftFeature.objects.create(
            aircraft=aircraft, feature='airworthiness_enforcement', enabled=False)
        payload = tool_payload(owner_mcp_client, 'update_aircraft_hours', {
            'aircraft_id': str(aircraft.id), 'new_tach_time': 101.0,
        })
        assert payload['success'] is True


class TestCreateFlightLog:
    def test_flight_log_side_effects(self, owner_mcp_client, aircraft, component):
        payload = tool_payload(owner_mcp_client, 'create_flight_log', {
            'aircraft_id': str(aircraft.id),
            'date': datetime.date.today().isoformat(),
            'tach_time': 1.5,
            'departure_location': 'KPDX',
            'destination_location': 'KSEA',
            'oil_added': 1,
            'fuel_added': 20,
        })
        assert payload['tach_time'] == '1.5'
        aircraft.refresh_from_db()
        assert aircraft.tach_time == Decimal('101.5')
        component.refresh_from_db()
        assert component.hours_in_service == Decimal('1.5')
        # Auto-created consumable records
        assert ConsumableRecord.objects.filter(aircraft=aircraft, record_type='oil').count() == 1
        assert ConsumableRecord.objects.filter(aircraft=aircraft, record_type='fuel').count() == 1
        assert AircraftEvent.objects.filter(aircraft=aircraft, category='flight').exists()

    def test_validation_error_is_readable(self, owner_mcp_client, aircraft):
        message = tool_error(owner_mcp_client, 'create_flight_log', {
            'aircraft_id': str(aircraft.id),
            'date': 'not-a-date',
            'tach_time': 1.0,
        })
        assert 'date' in message

    def test_feature_gated(self, owner_mcp_client, aircraft):
        AircraftFeature.objects.create(
            aircraft=aircraft, feature='flight_tracking', enabled=False)
        message = tool_error(owner_mcp_client, 'create_flight_log', {
            'aircraft_id': str(aircraft.id),
            'date': datetime.date.today().isoformat(),
            'tach_time': 1.0,
        })
        assert 'disabled' in message
        assert FlightLog.objects.count() == 0

    def test_grounded_blocked(self, owner_mcp_client, aircraft):
        Squawk.objects.create(aircraft=aircraft, priority=0, issue_reported='Engine fire')
        message = tool_error(owner_mcp_client, 'create_flight_log', {
            'aircraft_id': str(aircraft.id),
            'date': datetime.date.today().isoformat(),
            'tach_time': 1.0,
        })
        assert 'grounded' in message
        assert FlightLog.objects.count() == 0
        aircraft.refresh_from_db()
        assert float(aircraft.tach_time) == 100.0


class TestCreateSquawkNoteConsumable:
    def test_create_squawk(self, pilot_mcp_client, aircraft_with_pilot):
        payload = tool_payload(pilot_mcp_client, 'create_squawk', {
            'aircraft_id': str(aircraft_with_pilot.id),
            'issue_reported': 'Mag drop 200 RPM',
            'priority': 1,
        })
        assert payload['issue_reported'] == 'Mag drop 200 RPM'
        squawk = Squawk.objects.get(aircraft=aircraft_with_pilot)
        assert squawk.priority == 1
        assert AircraftEvent.objects.filter(
            aircraft=aircraft_with_pilot, category='squawk').exists()

    def test_add_note(self, owner_mcp_client, aircraft, owner_user):
        payload = tool_payload(owner_mcp_client, 'add_note', {
            'aircraft_id': str(aircraft.id),
            'text': 'Left main tire looks worn',
        })
        assert payload['text'] == 'Left main tire looks worn'
        note = aircraft.notes.get()
        assert note.added_by == owner_user
        assert note.public is False

    def test_add_consumable_record_defaults_flight_hours(self, owner_mcp_client, aircraft):
        payload = tool_payload(owner_mcp_client, 'add_consumable_record', {
            'aircraft_id': str(aircraft.id),
            'type': 'oil',
            'date': datetime.date.today().isoformat(),
            'quantity_added': 1,
        })
        record = ConsumableRecord.objects.get(aircraft=aircraft)
        assert record.record_type == 'oil'
        assert record.flight_hours == Decimal('100.0')
        assert payload['quantity_added'] == '1.00'
        assert AircraftEvent.objects.filter(aircraft=aircraft, category='oil').exists()

    def test_add_consumable_feature_gated(self, owner_mcp_client, aircraft):
        AircraftFeature.objects.create(
            aircraft=aircraft, feature='fuel_consumption', enabled=False)
        message = tool_error(owner_mcp_client, 'add_consumable_record', {
            'aircraft_id': str(aircraft.id),
            'type': 'fuel',
            'date': datetime.date.today().isoformat(),
            'quantity_added': 10,
        })
        assert 'disabled' in message

    def test_write_tools_not_found_for_other_user(self, other_mcp_client, aircraft):
        for name, extra in [
            ('create_squawk', {'issue_reported': 'x'}),
            ('add_note', {'text': 'x'}),
            ('add_consumable_record', {'type': 'oil', 'date': '2026-01-01', 'quantity_added': 1}),
        ]:
            args = {'aircraft_id': str(aircraft.id), **extra}
            assert tool_error(other_mcp_client, name, args) == 'Aircraft not found'


class TestSquawkAttributionAndResolution:
    def test_create_squawk_sets_reported_by(self, pilot_mcp_client, aircraft_with_pilot, pilot_user):
        payload = tool_payload(pilot_mcp_client, 'create_squawk', {
            'aircraft_id': str(aircraft_with_pilot.id),
            'issue_reported': 'Attitude indicator sluggish',
        })
        squawk = Squawk.objects.get(id=payload['id'])
        assert squawk.reported_by == pilot_user

    def test_owner_resolves_squawk(self, owner_mcp_client, aircraft, squawk):
        payload = tool_payload(owner_mcp_client, 'resolve_squawk', {
            'aircraft_id': str(aircraft.id),
            'squawk_id': str(squawk.id),
            'notes': 'Pads replaced',
        })
        assert payload['resolved'] is True
        squawk.refresh_from_db()
        assert squawk.resolved is True
        assert 'Pads replaced' in squawk.notes
        assert AircraftEvent.objects.filter(
            aircraft=aircraft, category='squawk',
            event_name__startswith='Squawk resolved').exists()

    def test_resolving_p0_squawk_ungrounds(self, owner_mcp_client, aircraft):
        grounding = Squawk.objects.create(
            aircraft=aircraft, priority=0, issue_reported='Engine fire')
        tool_payload(owner_mcp_client, 'resolve_squawk', {
            'aircraft_id': str(aircraft.id), 'squawk_id': str(grounding.id),
        })
        status = tool_payload(owner_mcp_client, 'get_airworthiness',
                              {'aircraft_id': str(aircraft.id)})
        assert status['can_fly'] is True

    def test_pilot_cannot_resolve(self, pilot_mcp_client, aircraft_with_pilot, squawk):
        message = tool_error(pilot_mcp_client, 'resolve_squawk', {
            'aircraft_id': str(aircraft_with_pilot.id),
            'squawk_id': str(squawk.id),
        })
        assert 'owner role' in message
        squawk.refresh_from_db()
        assert squawk.resolved is False

    def test_unknown_squawk_not_found(self, owner_mcp_client, aircraft):
        assert tool_error(owner_mcp_client, 'resolve_squawk', {
            'aircraft_id': str(aircraft.id),
            'squawk_id': '00000000-0000-0000-0000-000000000000',
        }) == 'Squawk not found'


class TestFlightConsumableEvents:
    def test_flight_oil_fuel_emit_events(self, owner_mcp_client, aircraft):
        tool_payload(owner_mcp_client, 'create_flight_log', {
            'aircraft_id': str(aircraft.id),
            'date': datetime.date.today().isoformat(),
            'tach_time': 1.0,
            'oil_added': 1,
            'fuel_added': 15,
        })
        assert AircraftEvent.objects.filter(aircraft=aircraft, category='flight').count() == 1
        assert AircraftEvent.objects.filter(
            aircraft=aircraft, category='oil', event_name__startswith='Oil added').count() == 1
        assert AircraftEvent.objects.filter(
            aircraft=aircraft, category='fuel', event_name__startswith='Fuel added').count() == 1
