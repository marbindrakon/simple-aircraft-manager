import datetime

import pytest

from core.models import AircraftEvent
from health.models import MajorRepairAlteration

pytestmark = pytest.mark.django_db


@pytest.fixture
def major_record(aircraft):
    return MajorRepairAlteration.objects.create(
        aircraft=aircraft,
        record_type='repair',
        title='Longeron repair',
        date_performed=datetime.date.today(),
        performed_by='A&P Mechanic',
    )


class TestMajorRecordViewSetList:
    def test_owner_sees_their_records(self, owner_client, major_record):
        resp = owner_client.get('/api/major-records/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(major_record.id) in ids

    def test_other_client_gets_empty(self, other_client, major_record):
        resp = other_client.get('/api/major-records/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_admin_sees_all(self, admin_client, major_record):
        resp = admin_client.get('/api/major-records/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(major_record.id) in ids


class TestMajorRecordViewSetCreate:
    def test_owner_can_create(self, owner_client, aircraft):
        resp = owner_client.post(
            '/api/major-records/',
            {
                'aircraft': str(aircraft.id),
                'record_type': 'alteration',
                'title': 'STC installation',
                'date_performed': str(datetime.date.today()),
                'performed_by': 'IA Mechanic',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['title'] == 'STC installation'
        assert resp.data['record_type'] == 'alteration'

    def test_create_logs_aircraft_event(self, owner_client, aircraft):
        before_count = AircraftEvent.objects.filter(
            aircraft=aircraft, category='major_record'
        ).count()

        owner_client.post(
            '/api/major-records/',
            {
                'aircraft': str(aircraft.id),
                'record_type': 'repair',
                'title': 'Event test repair',
                'date_performed': str(datetime.date.today()),
                'performed_by': 'A&P',
            },
            format='json',
        )

        after_count = AircraftEvent.objects.filter(
            aircraft=aircraft, category='major_record'
        ).count()
        assert after_count == before_count + 1

    def test_created_event_has_custom_name(self, owner_client, aircraft):
        # MajorRepairAlterationViewSet sets event_name_created = 'Major record created'
        owner_client.post(
            '/api/major-records/',
            {
                'aircraft': str(aircraft.id),
                'record_type': 'repair',
                'title': 'Custom name test',
                'date_performed': str(datetime.date.today()),
                'performed_by': 'A&P',
            },
            format='json',
        )
        event = AircraftEvent.objects.filter(
            aircraft=aircraft, category='major_record'
        ).latest('timestamp')
        assert event.event_name == 'Major record created'


class TestMajorRecordViewSetDelete:
    def test_owner_can_delete(self, owner_client, major_record):
        rec_id = major_record.id
        resp = owner_client.delete(f'/api/major-records/{rec_id}/')
        assert resp.status_code == 204
        assert not MajorRepairAlteration.objects.filter(id=rec_id).exists()

    def test_delete_logs_event_with_custom_name(self, owner_client, major_record, aircraft):
        owner_client.delete(f'/api/major-records/{major_record.id}/')
        event = AircraftEvent.objects.filter(
            aircraft=aircraft, category='major_record', event_name='Major record deleted'
        ).first()
        assert event is not None

    def test_other_client_gets_404(self, other_client, major_record):
        resp = other_client.delete(f'/api/major-records/{major_record.id}/')
        assert resp.status_code == 404

    def test_pilot_cannot_delete(self, pilot_client, aircraft_with_pilot, major_record):
        resp = pilot_client.delete(f'/api/major-records/{major_record.id}/')
        assert resp.status_code == 403
