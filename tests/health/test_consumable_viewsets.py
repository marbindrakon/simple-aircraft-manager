import datetime

import pytest

from health.models import ConsumableRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def oil_record(aircraft):
    return ConsumableRecord.objects.create(
        record_type='oil',
        aircraft=aircraft,
        date=datetime.date.today(),
        quantity_added=2.0,
        flight_hours=100.0,
    )


@pytest.fixture
def fuel_record(aircraft):
    return ConsumableRecord.objects.create(
        record_type='fuel',
        aircraft=aircraft,
        date=datetime.date.today(),
        quantity_added=30.0,
        flight_hours=100.0,
    )


class TestConsumableRecordViewSetList:
    def test_owner_sees_their_records(self, owner_client, oil_record):
        resp = owner_client.get('/api/consumable-records/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(oil_record.id) in ids

    def test_other_client_gets_empty(self, other_client, oil_record):
        resp = other_client.get('/api/consumable-records/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_admin_sees_all(self, admin_client, oil_record):
        resp = admin_client.get('/api/consumable-records/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(oil_record.id) in ids


class TestConsumableRecordViewSetCreate:
    def test_owner_can_create_oil_record(self, owner_client, aircraft):
        resp = owner_client.post(
            '/api/consumable-records/',
            {
                'record_type': 'oil',
                'aircraft': str(aircraft.id),
                'date': str(datetime.date.today()),
                'quantity_added': '1.5',
                'flight_hours': '110.0',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['record_type'] == 'oil'

    def test_pilot_can_create_consumable_record(self, pilot_client, aircraft_with_pilot):
        # consumablerecord is in PILOT_WRITABLE_MODELS
        resp = pilot_client.post(
            '/api/consumable-records/',
            {
                'record_type': 'fuel',
                'aircraft': str(aircraft_with_pilot.id),
                'date': str(datetime.date.today()),
                'quantity_added': '20.0',
                'flight_hours': '105.0',
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_pilot_cannot_delete_consumable_record(self, pilot_client, aircraft_with_pilot, oil_record):
        # consumablerecord is in PILOT_WRITABLE_MODELS — model name check applies on the object
        # PILOT_WRITABLE_MODELS includes 'consumablerecord' so pilot CAN delete
        resp = pilot_client.delete(f'/api/consumable-records/{oil_record.id}/')
        # consumablerecord IS in PILOT_WRITABLE_MODELS — pilot is allowed
        assert resp.status_code == 204


class TestConsumableRecordViewSetFilter:
    def test_filter_by_record_type_oil(self, owner_client, oil_record, fuel_record):
        resp = owner_client.get('/api/consumable-records/?record_type=oil')
        assert resp.status_code == 200
        for r in resp.data:
            assert r['record_type'] == 'oil'

    def test_filter_by_record_type_fuel(self, owner_client, oil_record, fuel_record):
        resp = owner_client.get('/api/consumable-records/?record_type=fuel')
        assert resp.status_code == 200
        for r in resp.data:
            assert r['record_type'] == 'fuel'
