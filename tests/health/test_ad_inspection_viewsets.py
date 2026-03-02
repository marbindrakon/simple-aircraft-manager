import datetime

import pytest

from health.models import ComponentType, InspectionType, AD, ADCompliance, InspectionRecord

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# ComponentTypeViewSet
# ---------------------------------------------------------------------------

class TestComponentTypeViewSet:
    def test_authenticated_user_can_list(self, owner_client, component_type):
        resp = owner_client.get('/api/component-types/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(component_type.id) in ids

    def test_pilot_can_list(self, pilot_client, component_type):
        resp = pilot_client.get('/api/component-types/')
        assert resp.status_code == 200

    def test_owner_cannot_create(self, owner_client):
        resp = owner_client.post(
            '/api/component-types/',
            {'name': 'Propeller', 'consumable': False},
            format='json',
        )
        assert resp.status_code == 403

    def test_admin_can_create(self, admin_client):
        resp = admin_client.post(
            '/api/component-types/',
            {'name': 'Propeller', 'consumable': False},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == 'Propeller'

    def test_owner_cannot_delete(self, owner_client, component_type):
        resp = owner_client.delete(f'/api/component-types/{component_type.id}/')
        assert resp.status_code == 403

    def test_admin_can_delete(self, admin_client, component_type):
        ct_id = component_type.id
        resp = admin_client.delete(f'/api/component-types/{ct_id}/')
        assert resp.status_code == 204
        assert not ComponentType.objects.filter(id=ct_id).exists()


# ---------------------------------------------------------------------------
# InspectionTypeViewSet
# ---------------------------------------------------------------------------

class TestInspectionTypeViewSet:
    def test_owner_can_list(self, owner_client, inspection_type):
        resp = owner_client.get('/api/inspection-types/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(inspection_type.id) in ids

    def test_owner_cannot_create(self, owner_client):
        resp = owner_client.post(
            '/api/inspection-types/',
            {'name': 'Biennial Flight Review', 'recurring': True, 'required': True},
            format='json',
        )
        assert resp.status_code == 403

    def test_admin_can_create(self, admin_client):
        resp = admin_client.post(
            '/api/inspection-types/',
            {'name': 'Biennial Flight Review', 'recurring': True, 'required': True},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == 'Biennial Flight Review'

    def test_owner_cannot_update(self, owner_client, inspection_type):
        resp = owner_client.patch(
            f'/api/inspection-types/{inspection_type.id}/',
            {'name': 'Updated Name'},
            format='json',
        )
        assert resp.status_code == 403

    def test_admin_can_update(self, admin_client, inspection_type):
        resp = admin_client.patch(
            f'/api/inspection-types/{inspection_type.id}/',
            {'name': 'Updated Inspection'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['name'] == 'Updated Inspection'


# ---------------------------------------------------------------------------
# ADViewSet
# ---------------------------------------------------------------------------

class TestADViewSet:
    def test_owner_can_list(self, owner_client, ad):
        resp = owner_client.get('/api/ads/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(ad.id) in ids

    def test_pilot_can_list(self, pilot_client, ad):
        resp = pilot_client.get('/api/ads/')
        assert resp.status_code == 200

    def test_owner_cannot_create(self, owner_client):
        resp = owner_client.post(
            '/api/ads/',
            {
                'name': 'AD 2023-01-01',
                'short_description': 'Test AD',
                'compliance_type': 'standard',
            },
            format='json',
        )
        assert resp.status_code == 403

    def test_admin_can_create(self, admin_client):
        resp = admin_client.post(
            '/api/ads/',
            {
                'name': 'AD 2023-02-01',
                'short_description': 'New Test AD',
                'compliance_type': 'standard',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == 'AD 2023-02-01'

    def test_owner_can_update_ad_linked_to_their_aircraft(self, owner_client, ad):
        # ad fixture is linked to aircraft which owner_user owns
        resp = owner_client.patch(
            f'/api/ads/{ad.id}/',
            {'short_description': 'Updated description'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['short_description'] == 'Updated description'

    def test_owner_cannot_delete_ad(self, owner_client, ad):
        resp = owner_client.delete(f'/api/ads/{ad.id}/')
        assert resp.status_code == 403

    def test_admin_can_delete_ad(self, admin_client, ad):
        ad_id = ad.id
        resp = admin_client.delete(f'/api/ads/{ad_id}/')
        assert resp.status_code == 204
        assert not AD.objects.filter(id=ad_id).exists()


# ---------------------------------------------------------------------------
# ADComplianceViewSet
# ---------------------------------------------------------------------------

class TestADComplianceViewSet:
    def test_owner_sees_their_compliance_records(self, owner_client, aircraft, ad):
        compliance = ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date.today(),
            compliance_notes='Complied per instructions',
            permanent=True,
        )
        resp = owner_client.get('/api/ad-compliances/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(compliance.id) in ids

    def test_other_client_sees_nothing(self, other_client, aircraft, ad):
        ADCompliance.objects.create(
            ad=ad,
            aircraft=aircraft,
            date_complied=datetime.date.today(),
            compliance_notes='Notes',
            permanent=False,
        )
        resp = other_client.get('/api/ad-compliances/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_owner_can_create_ad_compliance(self, owner_client, aircraft, ad):
        resp = owner_client.post(
            '/api/ad-compliances/',
            {
                'ad': str(ad.id),
                'aircraft': str(aircraft.id),
                'date_complied': str(datetime.date.today()),
                'compliance_notes': 'Complied',
                'permanent': False,
            },
            format='json',
        )
        assert resp.status_code == 201
        assert str(ad.id) in str(resp.data['ad'])


# ---------------------------------------------------------------------------
# InspectionRecordViewSet
# ---------------------------------------------------------------------------

class TestInspectionRecordViewSet:
    def test_owner_sees_their_records(self, owner_client, aircraft, inspection_type):
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date.today(),
            aircraft_hours=100.0,
        )
        resp = owner_client.get('/api/inspections/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(record.id) in ids

    def test_other_client_sees_nothing(self, other_client, aircraft, inspection_type):
        InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft,
            date=datetime.date.today(),
            aircraft_hours=100.0,
        )
        resp = other_client.get('/api/inspections/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_owner_can_create_inspection_record(self, owner_client, aircraft, inspection_type):
        resp = owner_client.post(
            '/api/inspections/',
            {
                'inspection_type': str(inspection_type.id),
                'aircraft': str(aircraft.id),
                'date': str(datetime.date.today()),
                'aircraft_hours': '150.0',
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_pilot_cannot_update_inspection_record(self, pilot_client, aircraft_with_pilot, inspection_type):
        # check_object_permissions restricts pilots from updating non-PILOT_WRITABLE_MODELS
        record = InspectionRecord.objects.create(
            inspection_type=inspection_type,
            aircraft=aircraft_with_pilot,
            date=datetime.date.today(),
            aircraft_hours=100.0,
        )
        resp = pilot_client.patch(
            f'/api/inspections/{record.id}/',
            {'aircraft_hours': '200.0'},
            format='json',
        )
        assert resp.status_code == 403
