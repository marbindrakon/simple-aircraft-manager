"""
Tests for AircraftViewSet custom actions.
"""
import datetime

import pytest

from core.models import AircraftEvent, AircraftRole, AircraftShareToken
from health.models import Component, ConsumableRecord, Squawk

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# update_hours (POST /api/aircraft/{id}/update_hours/)
# ---------------------------------------------------------------------------

class TestUpdateHours:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/update_hours/'

    def test_tach_time_is_updated(self, owner_client, aircraft):
        response = owner_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        assert response.status_code == 200
        aircraft.refresh_from_db()
        assert float(aircraft.tach_time) == 110.0

    def test_in_use_component_hours_incremented(self, owner_client, aircraft, component):
        # component starts at hours_in_service=0, aircraft starts at 100.0
        response = owner_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        assert response.status_code == 200
        component.refresh_from_db()
        assert float(component.hours_in_service) == 10.0
        assert float(component.hours_since_overhaul) == 10.0

    def test_spare_component_not_updated(self, owner_client, aircraft, component_type):
        spare = Component.objects.create(
            aircraft=aircraft,
            component_type=component_type,
            status='SPARE',
            date_in_service=datetime.date.today(),
            manufacturer='Test',
            model='Spare',
            hours_in_service=0.0,
        )
        owner_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        spare.refresh_from_db()
        assert float(spare.hours_in_service) == 0.0

    def test_hobbs_time_update(self, owner_client, aircraft):
        response = owner_client.post(
            self._url(aircraft),
            {'new_tach_time': 110.0, 'new_hobbs_time': 115.0},
            format='json',
        )
        assert response.status_code == 200
        aircraft.refresh_from_db()
        assert float(aircraft.hobbs_time) == 115.0

    def test_logs_hours_event(self, owner_client, aircraft):
        owner_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        event = AircraftEvent.objects.filter(aircraft=aircraft, category='hours').first()
        assert event is not None

    def test_missing_tach_time_returns_400(self, owner_client, aircraft):
        response = owner_client.post(self._url(aircraft), {}, format='json')
        assert response.status_code == 400

    def test_response_contains_tach_time(self, owner_client, aircraft):
        response = owner_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        assert response.status_code == 200
        assert 'tach_time' in response.data
        assert response.data['tach_time'] == 110.0

    def test_component_hours_clamped_at_zero_on_correction(self, owner_client, aircraft, component):
        # Reduce hours below current (correction); component already at 0, clamp prevents negatives
        response = owner_client.post(self._url(aircraft), {'new_tach_time': 90.0}, format='json')
        assert response.status_code == 200
        component.refresh_from_db()
        assert float(component.hours_in_service) >= 0.0

    def test_pilot_can_update_hours(self, pilot_client, aircraft_with_pilot):
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/update_hours/',
            {'new_tach_time': 110.0},
            format='json',
        )
        assert response.status_code == 200

    def test_other_user_cannot_update_hours(self, other_client, aircraft):
        response = other_client.post(self._url(aircraft), {'new_tach_time': 110.0}, format='json')
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# summary (GET /api/aircraft/{id}/summary/)
# ---------------------------------------------------------------------------

class TestSummary:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/summary/'

    def test_returns_200(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200

    def test_contains_aircraft_data(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert 'aircraft' in response.data

    def test_contains_components(self, owner_client, aircraft, component):
        response = owner_client.get(self._url(aircraft))
        assert 'components' in response.data
        assert isinstance(response.data['components'], list)

    def test_contains_active_squawks(self, owner_client, aircraft, squawk):
        response = owner_client.get(self._url(aircraft))
        assert 'active_squawks' in response.data

    def test_contains_notes(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert 'notes' in response.data

    def test_contains_recent_logs(self, owner_client, aircraft, logbook_entry):
        response = owner_client.get(self._url(aircraft))
        assert 'recent_logs' in response.data


# ---------------------------------------------------------------------------
# squawks (GET/POST /api/aircraft/{id}/squawks/)
# ---------------------------------------------------------------------------

class TestSquawks:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/squawks/'

    def test_get_returns_squawks_list(self, owner_client, aircraft, squawk):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'squawks' in response.data
        assert len(response.data['squawks']) >= 1

    def test_post_creates_squawk(self, owner_client, aircraft):
        payload = {'priority': 2, 'issue_reported': 'Oil leak at rocker box'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201

    def test_post_squawk_linked_to_aircraft(self, owner_client, aircraft):
        payload = {'priority': 1, 'issue_reported': 'Compass deviation'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        squawk = Squawk.objects.get(id=response.data['id'])
        assert squawk.aircraft == aircraft

    def test_get_filter_resolved(self, owner_client, aircraft, squawk):
        squawk.resolved = True
        squawk.save()
        response = owner_client.get(self._url(aircraft) + '?resolved=true')
        assert response.status_code == 200
        for s in response.data['squawks']:
            assert s['resolved'] is True

    def test_pilot_can_create_squawk(self, pilot_client, aircraft_with_pilot):
        payload = {'priority': 3, 'issue_reported': 'Landing light dim'}
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/squawks/',
            payload,
            format='json',
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# notes (GET/POST /api/aircraft/{id}/notes/)
# ---------------------------------------------------------------------------

class TestNotes:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/notes/'

    def test_get_returns_notes_list(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'notes' in response.data

    def test_post_creates_note(self, owner_client, aircraft):
        payload = {'text': 'Check tire pressure before next flight'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['text'] == 'Check tire pressure before next flight'

    def test_pilot_can_create_note(self, pilot_client, aircraft_with_pilot):
        payload = {'text': 'Pilot note'}
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/notes/',
            payload,
            format='json',
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# oil_records (GET/POST /api/aircraft/{id}/oil_records/)
# ---------------------------------------------------------------------------

class TestOilRecords:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/oil_records/'

    def test_get_returns_oil_records(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'oil_records' in response.data

    def test_post_creates_oil_record(self, owner_client, aircraft):
        payload = {
            'date': str(datetime.date.today()),
            'quantity_added': '2.00',
            'flight_hours': '100.0',
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        record = ConsumableRecord.objects.get(id=response.data['id'])
        assert record.record_type == 'oil'

    def test_oil_record_filters_to_oil_type(self, owner_client, aircraft):
        # Create a fuel record to make sure it's excluded
        ConsumableRecord.objects.create(
            aircraft=aircraft,
            record_type='fuel',
            date=datetime.date.today(),
            quantity_added='10.00',
            flight_hours='100.0',
        )
        response = owner_client.get(self._url(aircraft))
        for record in response.data['oil_records']:
            assert record['record_type'] == 'oil'


# ---------------------------------------------------------------------------
# fuel_records (GET/POST /api/aircraft/{id}/fuel_records/)
# ---------------------------------------------------------------------------

class TestFuelRecords:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/fuel_records/'

    def test_get_returns_fuel_records(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'fuel_records' in response.data

    def test_post_creates_fuel_record(self, owner_client, aircraft):
        payload = {
            'date': str(datetime.date.today()),
            'quantity_added': '20.00',
            'flight_hours': '100.0',
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        record = ConsumableRecord.objects.get(id=response.data['id'])
        assert record.record_type == 'fuel'

    def test_fuel_record_filters_to_fuel_type(self, owner_client, aircraft):
        ConsumableRecord.objects.create(
            aircraft=aircraft,
            record_type='oil',
            date=datetime.date.today(),
            quantity_added='2.00',
            flight_hours='100.0',
        )
        response = owner_client.get(self._url(aircraft))
        for record in response.data['fuel_records']:
            assert record['record_type'] == 'fuel'


# ---------------------------------------------------------------------------
# components (POST /api/aircraft/{id}/components/)
# ---------------------------------------------------------------------------

class TestComponents:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/components/'

    def test_post_creates_component(self, owner_client, aircraft, component_type):
        payload = {
            'component_type': str(component_type.id),
            'manufacturer': 'Lycoming',
            'model': 'IO-540',
            'status': 'SPARE',
            'date_in_service': str(datetime.date.today()),
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['manufacturer'] == 'Lycoming'

    def test_post_links_component_to_aircraft(self, owner_client, aircraft, component_type):
        payload = {
            'component_type': str(component_type.id),
            'manufacturer': 'Continental',
            'model': 'IO-360',
            'status': 'IN-USE',
            'date_in_service': str(datetime.date.today()),
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        comp = Component.objects.get(id=response.data['id'])
        assert comp.aircraft == aircraft

    def test_pilot_cannot_create_component(self, pilot_client, aircraft_with_pilot, component_type):
        payload = {
            'component_type': str(component_type.id),
            'manufacturer': 'Test',
            'model': 'Test',
            'status': 'SPARE',
            'date_in_service': str(datetime.date.today()),
        }
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/components/',
            payload,
            format='json',
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# ads (GET/POST /api/aircraft/{id}/ads/)
# ---------------------------------------------------------------------------

class TestAds:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/ads/'

    def test_get_returns_ads(self, owner_client, aircraft, ad):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'ads' in response.data
        names = [a['name'] for a in response.data['ads']]
        assert ad.name in names

    def test_post_links_existing_ad_by_id(self, owner_client, aircraft, ad):
        # Unlink first so we can re-link
        ad.applicable_aircraft.remove(aircraft)
        payload = {'ad_id': str(ad.id)}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 200
        assert ad.applicable_aircraft.filter(id=aircraft.id).exists()

    def test_post_creates_new_ad(self, owner_client, aircraft):
        payload = {
            'name': 'AD 2024-99-99',
            'short_description': 'New test AD',
            'compliance_type': 'standard',
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['name'] == 'AD 2024-99-99'

    def test_pilot_can_get_ads(self, pilot_client, aircraft_with_pilot, ad):
        response = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/ads/')
        assert response.status_code == 200

    def test_pilot_cannot_post_ad(self, pilot_client, aircraft_with_pilot, ad):
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/ads/',
            {'ad_id': str(ad.id)},
            format='json',
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# compliance (POST /api/aircraft/{id}/compliance/)
# ---------------------------------------------------------------------------

class TestCompliance:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/compliance/'

    def test_post_creates_compliance_record(self, owner_client, aircraft, ad):
        payload = {
            'ad': str(ad.id),
            'date_complied': str(datetime.date.today()),
            'compliance_notes': 'Complied per MM section 12-10-01',
            'permanent': True,
            'next_due_at_time': '0.0',
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert str(response.data['ad']) == str(ad.id)

    def test_pilot_cannot_post_compliance(self, pilot_client, aircraft_with_pilot, ad):
        payload = {
            'ad': str(ad.id),
            'date_complied': str(datetime.date.today()),
            'compliance_notes': 'Complied',
            'permanent': True,
            'next_due_at_time': '0.0',
        }
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/compliance/',
            payload,
            format='json',
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# inspections (GET/POST /api/aircraft/{id}/inspections/)
# ---------------------------------------------------------------------------

class TestInspections:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/inspections/'

    def test_get_returns_inspection_types(self, owner_client, aircraft, inspection_type):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'inspection_types' in response.data
        names = [it['name'] for it in response.data['inspection_types']]
        assert inspection_type.name in names

    def test_post_links_existing_inspection_type(self, owner_client, aircraft, inspection_type):
        # Unlink first, then re-link via API
        inspection_type.applicable_aircraft.remove(aircraft)
        payload = {'inspection_type_id': str(inspection_type.id)}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 200
        assert inspection_type.applicable_aircraft.filter(id=aircraft.id).exists()

    def test_post_creates_inspection_record(self, owner_client, aircraft, inspection_type):
        payload = {
            'inspection_type': str(inspection_type.id),
            'date': str(datetime.date.today()),
            'aircraft': str(aircraft.id),
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201

    def test_pilot_can_get_inspections(self, pilot_client, aircraft_with_pilot, inspection_type):
        response = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/inspections/')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# major_records (GET/POST /api/aircraft/{id}/major_records/)
# ---------------------------------------------------------------------------

class TestMajorRecords:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/major_records/'

    def test_get_returns_major_records(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200

    def test_post_creates_major_record(self, owner_client, aircraft):
        payload = {
            'record_type': 'repair',
            'title': 'Longeron repair',
            'date_performed': str(datetime.date.today()),
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['title'] == 'Longeron repair'
        assert response.data['record_type'] == 'repair'

    def test_pilot_can_get_major_records(self, pilot_client, aircraft_with_pilot):
        response = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/major_records/')
        assert response.status_code == 200

    def test_pilot_cannot_post_major_record(self, pilot_client, aircraft_with_pilot):
        payload = {
            'record_type': 'alteration',
            'title': 'STC install',
            'date_performed': str(datetime.date.today()),
        }
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/major_records/',
            payload,
            format='json',
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# flight_logs (GET/POST /api/aircraft/{id}/flight_logs/)
# ---------------------------------------------------------------------------

class TestFlightLogs:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/flight_logs/'

    def test_get_returns_flight_logs(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'flight_logs' in response.data

    def test_post_creates_flight_log(self, owner_client, aircraft):
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '1.5',
        }
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201

    def test_post_advances_aircraft_tach_time(self, owner_client, aircraft):
        original_tach = float(aircraft.tach_time)
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '2.0',
        }
        owner_client.post(self._url(aircraft), payload, format='json')
        aircraft.refresh_from_db()
        assert float(aircraft.tach_time) == original_tach + 2.0

    def test_post_advances_hobbs_time(self, owner_client, aircraft):
        original_hobbs = float(aircraft.hobbs_time)
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '1.0',
            'hobbs_time': '1.2',
        }
        owner_client.post(self._url(aircraft), payload, format='json')
        aircraft.refresh_from_db()
        assert float(aircraft.hobbs_time) == original_hobbs + 1.2

    def test_post_creates_oil_consumable_record_when_oil_added(self, owner_client, aircraft):
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '1.0',
            'oil_added': '2.00',
        }
        owner_client.post(self._url(aircraft), payload, format='json')
        assert ConsumableRecord.objects.filter(aircraft=aircraft, record_type='oil').exists()

    def test_post_creates_fuel_consumable_record_when_fuel_added(self, owner_client, aircraft):
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '1.0',
            'fuel_added': '20.00',
        }
        owner_client.post(self._url(aircraft), payload, format='json')
        assert ConsumableRecord.objects.filter(aircraft=aircraft, record_type='fuel').exists()

    def test_pilot_can_create_flight_log(self, pilot_client, aircraft_with_pilot):
        payload = {
            'date': str(datetime.date.today()),
            'tach_time': '1.0',
        }
        response = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/flight_logs/',
            payload,
            format='json',
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# events (GET /api/aircraft/{id}/events/)
# ---------------------------------------------------------------------------

class TestEvents:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/events/'

    def test_get_returns_events(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'events' in response.data
        assert 'total' in response.data

    def test_limit_query_param(self, owner_client, aircraft):
        # Generate several events
        for i in range(10):
            from core.events import log_event
            log_event(aircraft, 'hours', f'Event {i}')
        response = owner_client.get(self._url(aircraft) + '?limit=5')
        assert response.status_code == 200
        assert len(response.data['events']) <= 5

    def test_category_filter(self, owner_client, aircraft):
        from core.events import log_event
        log_event(aircraft, 'hours', 'Hours update')
        log_event(aircraft, 'squawk', 'Squawk reported')
        response = owner_client.get(self._url(aircraft) + '?category=hours')
        assert response.status_code == 200
        for event in response.data['events']:
            assert event['category'] == 'hours'

    def test_invalid_category_returns_400(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft) + '?category=notacategory')
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# manage_roles (GET/POST/DELETE /api/aircraft/{id}/manage_roles/)
# ---------------------------------------------------------------------------

class TestManageRoles:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/manage_roles/'

    def test_get_returns_roles(self, owner_client, aircraft):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert 'roles' in response.data

    def test_post_adds_pilot_role(self, owner_client, aircraft, pilot_user):
        payload = {'user': pilot_user.id, 'role': 'pilot'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 200
        assert AircraftRole.objects.filter(aircraft=aircraft, user=pilot_user, role='pilot').exists()

    def test_post_returns_updated_roles_list(self, owner_client, aircraft, pilot_user):
        payload = {'user': pilot_user.id, 'role': 'pilot'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 200
        assert 'roles' in response.data

    def test_delete_removes_role(self, owner_client, aircraft, pilot_user):
        # Add pilot first
        AircraftRole.objects.get_or_create(aircraft=aircraft, user=pilot_user, defaults={'role': 'pilot'})
        payload = {'user': pilot_user.id}
        response = owner_client.delete(self._url(aircraft), payload, format='json')
        assert response.status_code == 200
        assert not AircraftRole.objects.filter(aircraft=aircraft, user=pilot_user).exists()

    def test_cannot_remove_last_owner(self, owner_client, aircraft, owner_user):
        # Only one owner — trying to remove yourself should fail
        payload = {'user': owner_user.id}
        response = owner_client.delete(self._url(aircraft), payload, format='json')
        # Owner cannot remove their own role (self-removal protection also applies)
        assert response.status_code == 400

    def test_pilot_cannot_manage_roles(self, pilot_client, aircraft_with_pilot):
        response = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/manage_roles/')
        assert response.status_code == 403

    def test_post_invalid_role_returns_400(self, owner_client, aircraft, pilot_user):
        payload = {'user': pilot_user.id, 'role': 'mechanic'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# share_tokens (GET/POST /api/aircraft/{id}/share_tokens/)
# ---------------------------------------------------------------------------

class TestShareTokens:
    def _url(self, aircraft):
        return f'/api/aircraft/{aircraft.id}/share_tokens/'

    def test_get_returns_share_tokens(self, owner_client, aircraft, share_token_status):
        response = owner_client.get(self._url(aircraft))
        assert response.status_code == 200
        assert isinstance(response.data, list)
        ids = [str(t['id']) for t in response.data]
        assert str(share_token_status.id) in ids

    def test_post_creates_token_with_label_and_privilege(self, owner_client, aircraft):
        payload = {'label': 'Mechanic access', 'privilege': 'maintenance'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['privilege'] == 'maintenance'
        assert response.data['label'] == 'Mechanic access'

    def test_post_with_expires_in_days(self, owner_client, aircraft):
        payload = {'privilege': 'status', 'expires_in_days': 30}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 201
        assert response.data['expires_at'] is not None

    def test_post_invalid_privilege_returns_400(self, owner_client, aircraft):
        payload = {'privilege': 'read-only'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 400

    def test_exceeding_10_tokens_returns_400(self, owner_client, aircraft, owner_user):
        # Create 10 tokens to hit the limit
        for i in range(10):
            AircraftShareToken.objects.create(
                aircraft=aircraft,
                label=f'Token {i}',
                privilege='status',
                created_by=owner_user,
            )
        payload = {'privilege': 'status', 'label': 'Token 11'}
        response = owner_client.post(self._url(aircraft), payload, format='json')
        assert response.status_code == 400
        assert 'Maximum' in response.data.get('error', '')

    def test_pilot_cannot_get_share_tokens(self, pilot_client, aircraft_with_pilot):
        response = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/share_tokens/')
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# delete_share_token (DELETE /api/aircraft/{id}/share_tokens/{token_id}/)
# ---------------------------------------------------------------------------

class TestDeleteShareToken:
    def test_owner_can_delete_token(self, owner_client, aircraft, share_token_status):
        url = f'/api/aircraft/{aircraft.id}/share_tokens/{share_token_status.id}/'
        response = owner_client.delete(url)
        assert response.status_code == 204
        assert not AircraftShareToken.objects.filter(id=share_token_status.id).exists()

    def test_deleting_nonexistent_token_returns_404(self, owner_client, aircraft):
        import uuid
        url = f'/api/aircraft/{aircraft.id}/share_tokens/{uuid.uuid4()}/'
        response = owner_client.delete(url)
        assert response.status_code == 404
