"""
Tests for AircraftViewSet CRUD operations.
"""
import pytest
from django.urls import reverse

from core.models import Aircraft, AircraftEvent, AircraftRole

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# List (GET /api/aircraft/)
# ---------------------------------------------------------------------------

class TestAircraftList:
    def test_owner_sees_their_aircraft(self, owner_client, aircraft):
        url = reverse('aircraft-list')
        response = owner_client.get(url)
        assert response.status_code == 200
        ids = [item['id'] for item in response.data]
        assert str(aircraft.id) in ids

    def test_pilot_sees_aircraft_they_have_role_on(self, pilot_client, aircraft_with_pilot):
        url = reverse('aircraft-list')
        response = pilot_client.get(url)
        assert response.status_code == 200
        ids = [item['id'] for item in response.data]
        assert str(aircraft_with_pilot.id) in ids

    def test_other_user_sees_empty_list(self, other_client, aircraft):
        url = reverse('aircraft-list')
        response = other_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 0

    def test_admin_sees_all_aircraft(self, admin_client, aircraft):
        # Create a second aircraft not related to admin
        ac2 = Aircraft.objects.create(tail_number='N99999', make='Piper', model='PA-28')
        url = reverse('aircraft-list')
        response = admin_client.get(url)
        assert response.status_code == 200
        ids = [item['id'] for item in response.data]
        assert str(aircraft.id) in ids
        assert str(ac2.id) in ids


# ---------------------------------------------------------------------------
# Create (POST /api/aircraft/)
# ---------------------------------------------------------------------------

class TestAircraftCreate:
    def test_owner_can_create_aircraft(self, owner_client):
        url = reverse('aircraft-list')
        payload = {
            'tail_number': 'N55555',
            'make': 'Piper',
            'model': 'Cherokee',
        }
        response = owner_client.post(url, payload, format='json')
        assert response.status_code == 201

    def test_create_auto_assigns_creator_as_owner(self, owner_user, owner_client):
        url = reverse('aircraft-list')
        payload = {'tail_number': 'N44444', 'make': 'Beechcraft', 'model': 'Bonanza'}
        response = owner_client.post(url, payload, format='json')
        assert response.status_code == 201
        ac_id = response.data['id']
        role = AircraftRole.objects.get(aircraft_id=ac_id, user=owner_user)
        assert role.role == 'owner'

    def test_create_logs_aircraft_event(self, owner_client):
        url = reverse('aircraft-list')
        payload = {'tail_number': 'N33333', 'make': 'Cirrus', 'model': 'SR22'}
        response = owner_client.post(url, payload, format='json')
        assert response.status_code == 201
        ac_id = response.data['id']
        event = AircraftEvent.objects.filter(aircraft_id=ac_id, category='aircraft').first()
        assert event is not None

    def test_create_returns_uuid_id(self, owner_client):
        url = reverse('aircraft-list')
        payload = {'tail_number': 'N22222', 'make': 'Diamond', 'model': 'DA40'}
        response = owner_client.post(url, payload, format='json')
        assert response.status_code == 201
        assert 'id' in response.data
        # UUID format: 32 hex digits + 4 dashes = 36 chars
        assert len(str(response.data['id'])) == 36


# ---------------------------------------------------------------------------
# Retrieve (GET /api/aircraft/{id}/)
# ---------------------------------------------------------------------------

class TestAircraftRetrieve:
    def test_owner_gets_200(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = owner_client.get(url)
        assert response.status_code == 200

    def test_retrieve_includes_airworthiness(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = owner_client.get(url)
        assert response.status_code == 200
        assert 'airworthiness' in response.data

    def test_retrieve_includes_user_role(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = owner_client.get(url)
        assert response.status_code == 200
        assert 'user_role' in response.data
        assert response.data['user_role'] == 'owner'

    def test_other_user_gets_404(self, other_client, aircraft):
        # AircraftViewSet scopes queryset by role, so other_user gets 404
        url = f'/api/aircraft/{aircraft.id}/'
        response = other_client.get(url)
        assert response.status_code == 404

    def test_pilot_gets_200(self, pilot_client, aircraft_with_pilot):
        url = f'/api/aircraft/{aircraft_with_pilot.id}/'
        response = pilot_client.get(url)
        assert response.status_code == 200

    def test_pilot_user_role_is_pilot(self, pilot_client, aircraft_with_pilot):
        url = f'/api/aircraft/{aircraft_with_pilot.id}/'
        response = pilot_client.get(url)
        assert response.status_code == 200
        assert response.data['user_role'] == 'pilot'


# ---------------------------------------------------------------------------
# Update (PUT/PATCH /api/aircraft/{id}/)
# ---------------------------------------------------------------------------

class TestAircraftUpdate:
    def test_owner_can_patch_tail_number(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = owner_client.patch(url, {'tail_number': 'N99100'}, format='json')
        assert response.status_code == 200
        aircraft.refresh_from_db()
        assert aircraft.tail_number == 'N99100'

    def test_pilot_cannot_patch(self, pilot_client, aircraft_with_pilot):
        url = f'/api/aircraft/{aircraft_with_pilot.id}/'
        response = pilot_client.patch(url, {'tail_number': 'N00001'}, format='json')
        assert response.status_code == 403

    def test_other_user_cannot_patch(self, other_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = other_client.patch(url, {'tail_number': 'N00002'}, format='json')
        # Scoped queryset → 404 rather than 403
        assert response.status_code in (403, 404)

    def test_owner_can_put(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        payload = {
            'tail_number': 'N11111',
            'make': 'Cessna',
            'model': '172',
            'status': 'AVAILABLE',
            'tach_time': '100.0',
            'tach_time_offset': '0.0',
            'hobbs_time': '100.0',
            'hobbs_time_offset': '0.0',
        }
        response = owner_client.put(url, payload, format='json')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Destroy (DELETE /api/aircraft/{id}/)
# ---------------------------------------------------------------------------

class TestAircraftDestroy:
    def test_owner_can_delete(self, owner_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = owner_client.delete(url)
        assert response.status_code == 204
        assert not Aircraft.objects.filter(id=aircraft.id).exists()

    def test_pilot_cannot_delete(self, pilot_client, aircraft_with_pilot):
        url = f'/api/aircraft/{aircraft_with_pilot.id}/'
        response = pilot_client.delete(url)
        assert response.status_code == 403

    def test_other_user_cannot_delete(self, other_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = other_client.delete(url)
        assert response.status_code in (403, 404)

    def test_admin_can_delete(self, admin_client, aircraft):
        url = f'/api/aircraft/{aircraft.id}/'
        response = admin_client.delete(url)
        assert response.status_code == 204
