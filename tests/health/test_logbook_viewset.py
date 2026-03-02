import datetime

import pytest

from health.models import LogbookEntry

pytestmark = pytest.mark.django_db


class TestLogbookEntryViewSetList:
    def test_owner_sees_entries(self, owner_client, logbook_entry):
        resp = owner_client.get('/api/logbook-entries/')
        assert resp.status_code == 200
        # Paginated response
        ids = [r['id'] for r in resp.data['results']]
        assert str(logbook_entry.id) in ids

    def test_other_client_gets_empty(self, other_client, logbook_entry):
        resp = other_client.get('/api/logbook-entries/')
        assert resp.status_code == 200
        assert resp.data['results'] == []

    def test_response_is_paginated(self, owner_client, logbook_entry):
        resp = owner_client.get('/api/logbook-entries/')
        assert resp.status_code == 200
        assert 'count' in resp.data
        assert 'results' in resp.data

    def test_admin_sees_entries(self, admin_client, logbook_entry):
        resp = admin_client.get('/api/logbook-entries/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data['results']]
        assert str(logbook_entry.id) in ids


class TestLogbookEntryViewSetDetail:
    def test_owner_gets_200(self, owner_client, logbook_entry):
        resp = owner_client.get(f'/api/logbook-entries/{logbook_entry.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == str(logbook_entry.id)

    def test_other_client_gets_404(self, other_client, logbook_entry):
        resp = other_client.get(f'/api/logbook-entries/{logbook_entry.id}/')
        assert resp.status_code == 404


class TestLogbookEntryViewSetCreate:
    def test_owner_can_create(self, owner_client, aircraft):
        # LogbookEntrySerializer uses HyperlinkedRelatedField — aircraft must be a URL
        resp = owner_client.post(
            '/api/logbook-entries/',
            {
                'aircraft': f'http://testserver/api/aircraft/{aircraft.id}/',
                'date': str(datetime.date.today()),
                'log_type': 'ENG',
                'entry_type': 'MAINTENANCE',
                'text': 'Oil changed',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['log_type'] == 'ENG'

    def test_pilot_cannot_create_logbook_entry(self, pilot_client, aircraft_with_pilot):
        """Logbook entry CRUD is owner-only; pilots should be denied on create."""
        resp = pilot_client.post(
            '/api/logbook-entries/',
            {
                'aircraft': f'http://testserver/api/aircraft/{aircraft_with_pilot.id}/',
                'date': str(datetime.date.today()),
                'log_type': 'AC',
                'entry_type': 'OTHER',
                'text': 'Pilot note',
            },
            format='json',
        )
        assert resp.status_code == 403


class TestLogbookEntryViewSetUpdate:
    def test_owner_can_update(self, owner_client, logbook_entry):
        resp = owner_client.patch(
            f'/api/logbook-entries/{logbook_entry.id}/',
            {'text': 'Updated text'},
            format='json',
        )
        assert resp.status_code == 200
        logbook_entry.refresh_from_db()
        assert logbook_entry.text == 'Updated text'

    def test_pilot_cannot_update(self, pilot_client, aircraft_with_pilot, logbook_entry):
        resp = pilot_client.patch(
            f'/api/logbook-entries/{logbook_entry.id}/',
            {'text': 'Pilot update'},
            format='json',
        )
        assert resp.status_code == 403


class TestLogbookEntryViewSetDelete:
    def test_owner_can_delete(self, owner_client, logbook_entry):
        entry_id = logbook_entry.id
        resp = owner_client.delete(f'/api/logbook-entries/{entry_id}/')
        assert resp.status_code == 204
        assert not LogbookEntry.objects.filter(id=entry_id).exists()


class TestLogbookEntryFilters:
    def test_filter_by_log_type(self, owner_client, aircraft, logbook_entry):
        # logbook_entry has log_type='AC'; create an ENG one
        LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            log_type='ENG',
            entry_type='OTHER',
            text='Engine entry',
        )
        resp = owner_client.get('/api/logbook-entries/?log_type=AC')
        assert resp.status_code == 200
        for r in resp.data['results']:
            assert r['log_type'] == 'AC'

    def test_filter_by_entry_type(self, owner_client, aircraft, logbook_entry):
        # logbook_entry has entry_type='MAINTENANCE'; create an OTHER one
        LogbookEntry.objects.create(
            aircraft=aircraft,
            date=datetime.date.today(),
            log_type='AC',
            entry_type='OTHER',
            text='Other entry',
        )
        resp = owner_client.get('/api/logbook-entries/?entry_type=MAINTENANCE')
        assert resp.status_code == 200
        for r in resp.data['results']:
            assert r['entry_type'] == 'MAINTENANCE'
