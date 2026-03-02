import datetime

import pytest
from django.utils import timezone

from core.models import AircraftEvent
from health.models import Component

pytestmark = pytest.mark.django_db


class TestComponentViewSetList:
    def test_owner_sees_their_components(self, owner_client, component, aircraft):
        resp = owner_client.get('/api/components/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(component.id) in ids

    def test_other_client_sees_nothing(self, other_client, component):
        resp = other_client.get('/api/components/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_admin_sees_all_components(self, admin_client, component):
        resp = admin_client.get('/api/components/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(component.id) in ids


class TestComponentViewSetDetail:
    def test_owner_gets_200(self, owner_client, component):
        resp = owner_client.get(f'/api/components/{component.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == str(component.id)

    def test_other_client_gets_404(self, other_client, component):
        resp = other_client.get(f'/api/components/{component.id}/')
        assert resp.status_code == 404

    def test_admin_gets_200(self, admin_client, component):
        resp = admin_client.get(f'/api/components/{component.id}/')
        assert resp.status_code == 200


class TestComponentViewSetUpdate:
    def test_owner_can_update(self, owner_client, component):
        resp = owner_client.patch(f'/api/components/{component.id}/', {'notes': 'Updated note'}, format='json')
        assert resp.status_code == 200
        component.refresh_from_db()
        assert component.notes == 'Updated note'

    def test_pilot_cannot_update(self, pilot_client, aircraft_with_pilot, component):
        # component belongs to aircraft_with_pilot (same aircraft fixture)
        resp = pilot_client.patch(f'/api/components/{component.id}/', {'notes': 'Pilot change'}, format='json')
        assert resp.status_code == 403

    def test_pilot_cannot_delete(self, pilot_client, aircraft_with_pilot, component):
        resp = pilot_client.delete(f'/api/components/{component.id}/')
        assert resp.status_code == 403

    def test_owner_can_delete(self, owner_client, component):
        comp_id = component.id
        resp = owner_client.delete(f'/api/components/{comp_id}/')
        assert resp.status_code == 204
        assert not Component.objects.filter(id=comp_id).exists()


class TestComponentResetService:
    def test_reset_service_resets_overhaul_hours(self, owner_client, replacement_component):
        replacement_component.hours_since_overhaul = 25.0
        replacement_component.save()

        resp = owner_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert resp.data['new_hours'] == 0

        replacement_component.refresh_from_db()
        assert replacement_component.hours_since_overhaul == 0
        assert replacement_component.overhaul_date == timezone.now().date()

    def test_reset_service_does_not_reset_in_service_by_default(self, owner_client, replacement_component):
        replacement_component.hours_in_service = 200.0
        replacement_component.hours_since_overhaul = 25.0
        replacement_component.save()

        resp = owner_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {},
            format='json',
        )
        assert resp.status_code == 200

        replacement_component.refresh_from_db()
        assert replacement_component.hours_in_service == 200.0  # not reset

    def test_reset_service_with_reset_in_service_true(self, owner_client, replacement_component):
        replacement_component.hours_in_service = 200.0
        replacement_component.hours_since_overhaul = 25.0
        replacement_component.save()

        resp = owner_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {'reset_in_service': True},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['reset_in_service'] is True

        replacement_component.refresh_from_db()
        assert replacement_component.hours_in_service == 0
        assert replacement_component.date_in_service == timezone.now().date()

    def test_reset_service_logs_aircraft_event(self, owner_client, replacement_component, aircraft):
        before_count = AircraftEvent.objects.filter(aircraft=aircraft, category='component').count()

        owner_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {},
            format='json',
        )

        after_count = AircraftEvent.objects.filter(aircraft=aircraft, category='component').count()
        assert after_count == before_count + 1

    def test_pilot_cannot_reset_service(self, pilot_client, aircraft_with_pilot, replacement_component):
        # component belongs to aircraft_with_pilot — pilot can see it but reset_service is not pilot-writable
        resp = pilot_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {},
            format='json',
        )
        assert resp.status_code == 403

    def test_other_client_gets_404_for_reset_service(self, other_client, replacement_component):
        resp = other_client.post(
            f'/api/components/{replacement_component.id}/reset_service/',
            {},
            format='json',
        )
        assert resp.status_code == 404
