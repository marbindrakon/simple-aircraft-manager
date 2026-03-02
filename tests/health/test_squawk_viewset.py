import datetime

import pytest

from health.models import Squawk, LogbookEntry

pytestmark = pytest.mark.django_db


class TestSquawkViewSetList:
    def test_owner_sees_their_squawks(self, owner_client, squawk):
        resp = owner_client.get('/api/squawks/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(squawk.id) in ids

    def test_other_client_gets_empty(self, other_client, squawk):
        resp = other_client.get('/api/squawks/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_admin_sees_all_squawks(self, admin_client, squawk):
        resp = admin_client.get('/api/squawks/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(squawk.id) in ids


class TestSquawkViewSetDetail:
    def test_owner_gets_200(self, owner_client, squawk):
        resp = owner_client.get(f'/api/squawks/{squawk.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == str(squawk.id)

    def test_other_client_gets_404(self, other_client, squawk):
        resp = other_client.get(f'/api/squawks/{squawk.id}/')
        assert resp.status_code == 404


class TestSquawkViewSetUpdate:
    def test_owner_can_update(self, owner_client, squawk):
        resp = owner_client.patch(
            f'/api/squawks/{squawk.id}/',
            {'priority': 2, 'issue_reported': 'Updated issue'},
            format='json',
        )
        assert resp.status_code == 200
        squawk.refresh_from_db()
        assert squawk.priority == 2

    def test_pilot_can_create_squawk(self, pilot_client, aircraft_with_pilot):
        # Squawk is in PILOT_CREATABLE_MODELS — pilot can create
        resp = pilot_client.post(
            '/api/squawks/',
            {
                'aircraft': str(aircraft_with_pilot.id),
                'priority': 3,
                'issue_reported': 'Pilot squawk',
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_pilot_cannot_update_squawk(self, pilot_client, aircraft_with_pilot, squawk):
        resp = pilot_client.patch(
            f'/api/squawks/{squawk.id}/',
            {'priority': 2},
            format='json',
        )
        assert resp.status_code == 403

    def test_pilot_cannot_delete_squawk(self, pilot_client, aircraft_with_pilot, squawk):
        resp = pilot_client.delete(f'/api/squawks/{squawk.id}/')
        assert resp.status_code == 403


class TestSquawkLinkLogbook:
    def test_link_logbook_entry(self, owner_client, squawk, logbook_entry):
        resp = owner_client.post(
            f'/api/squawks/{squawk.id}/link_logbook/',
            {'logbook_entry_id': str(logbook_entry.id)},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['success'] is True
        squawk.refresh_from_db()
        assert logbook_entry in squawk.logbook_entries.all()

    def test_link_logbook_with_resolve_true(self, owner_client, squawk, logbook_entry):
        resp = owner_client.post(
            f'/api/squawks/{squawk.id}/link_logbook/',
            {'logbook_entry_id': str(logbook_entry.id), 'resolve': True},
            format='json',
        )
        assert resp.status_code == 200
        squawk.refresh_from_db()
        assert squawk.resolved is True
        assert logbook_entry in squawk.logbook_entries.all()

    def test_link_logbook_entry_from_different_aircraft_fails(
        self, owner_client, squawk, owner_user
    ):
        from core.models import Aircraft, AircraftRole
        other_aircraft = Aircraft.objects.create(
            tail_number='N99999', make='Piper', model='Cherokee', tach_time=0.0, hobbs_time=0.0
        )
        AircraftRole.objects.create(aircraft=other_aircraft, user=owner_user, role='owner')
        other_entry = LogbookEntry.objects.create(
            aircraft=other_aircraft,
            date=datetime.date.today(),
            log_type='AC',
            entry_type='MAINTENANCE',
            text='Other aircraft entry',
        )
        resp = owner_client.post(
            f'/api/squawks/{squawk.id}/link_logbook/',
            {'logbook_entry_id': str(other_entry.id)},
            format='json',
        )
        assert resp.status_code == 404


class TestSquawkFilters:
    def test_filter_by_priority(self, owner_client, aircraft, squawk):
        # squawk fixture has priority=1; create a priority-2 squawk too
        Squawk.objects.create(aircraft=aircraft, priority=2, issue_reported='Priority 2')
        resp = owner_client.get('/api/squawks/?priority=1')
        assert resp.status_code == 200
        for r in resp.data:
            assert r['priority'] == 1

    def test_filter_by_resolved_false(self, owner_client, aircraft, squawk):
        # squawk fixture resolved=False; create a resolved one
        Squawk.objects.create(aircraft=aircraft, priority=3, issue_reported='Resolved', resolved=True)
        resp = owner_client.get('/api/squawks/?resolved=false')
        assert resp.status_code == 200
        for r in resp.data:
            assert r['resolved'] is False
