"""
Tests for:
  - core/events.py: log_event
  - core/mixins.py: EventLoggingMixin, AircraftScopedMixin
"""

import datetime

import pytest
from rest_framework.test import APIClient

from core.events import log_event
from core.models import AircraftEvent, AircraftRole
from health.models import Squawk

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# log_event
# ---------------------------------------------------------------------------

class TestLogEvent:

    def test_creates_aircraft_event_record(self, aircraft, owner_user):
        count_before = AircraftEvent.objects.count()
        log_event(aircraft, 'squawk', 'Squawk created', user=owner_user)
        assert AircraftEvent.objects.count() == count_before + 1

    def test_event_has_correct_fields(self, aircraft, owner_user):
        log_event(aircraft, 'component', 'Component updated', user=owner_user, notes='test note')
        event = AircraftEvent.objects.filter(aircraft=aircraft).latest('timestamp')
        assert event.category == 'component'
        assert event.event_name == 'Component updated'
        assert event.user == owner_user
        assert event.notes == 'test note'
        assert event.aircraft == aircraft

    def test_creates_event_with_none_user(self, aircraft):
        log_event(aircraft, 'note', 'Note created', user=None)
        event = AircraftEvent.objects.filter(aircraft=aircraft).latest('timestamp')
        assert event.user is None
        assert event.event_name == 'Note created'

    def test_event_count_increments_by_one(self, aircraft, owner_user):
        before = AircraftEvent.objects.filter(aircraft=aircraft).count()
        log_event(aircraft, 'hours', 'Hours updated', user=owner_user)
        after = AircraftEvent.objects.filter(aircraft=aircraft).count()
        assert after == before + 1

    def test_multiple_events_accumulate(self, aircraft, owner_user):
        for i in range(3):
            log_event(aircraft, 'squawk', f'Event {i}', user=owner_user)
        assert AircraftEvent.objects.filter(aircraft=aircraft).count() >= 3

    def test_unauthenticated_user_stored_as_none(self, aircraft):
        """AnonymousUser or a user where is_authenticated=False → stored as None."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        log_event(aircraft, 'aircraft', 'Anonymous event', user=anon)
        event = AircraftEvent.objects.filter(aircraft=aircraft, event_name='Anonymous event').first()
        assert event is not None
        assert event.user is None


# ---------------------------------------------------------------------------
# EventLoggingMixin via SquawkViewSet API calls
# ---------------------------------------------------------------------------

class TestEventLoggingMixinViaApi:
    """
    Test EventLoggingMixin behaviour by calling the SquawkViewSet through the
    real API client.  SquawkViewSet uses both AircraftScopedMixin and
    EventLoggingMixin, making it ideal for integration-level mixin tests.
    """

    def _owner_client(self, owner_user):
        client = APIClient()
        client.force_authenticate(user=owner_user)
        return client

    def test_create_squawk_logs_event(self, aircraft, owner_user):
        client = self._owner_client(owner_user)
        before = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        client.post(
            '/api/squawks/',
            data={
                'aircraft': str(aircraft.id),
                'priority': 3,
                'issue_reported': 'Landing light out',
            },
            format='json',
        )
        after = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        assert after == before + 1

    def test_create_event_name_uses_model_verbose_name(self, aircraft, owner_user):
        client = self._owner_client(owner_user)
        client.post(
            '/api/squawks/',
            data={
                'aircraft': str(aircraft.id),
                'priority': 3,
                'issue_reported': 'Trim tab wobble',
            },
            format='json',
        )
        event = AircraftEvent.objects.filter(
            aircraft=aircraft, category='squawk'
        ).latest('timestamp')
        assert 'created' in event.event_name.lower()

    def test_update_squawk_logs_event(self, aircraft, owner_user, squawk):
        client = self._owner_client(owner_user)
        before = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        client.patch(
            f'/api/squawks/{squawk.id}/',
            data={'issue_reported': 'Updated issue'},
            format='json',
        )
        after = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        assert after == before + 1

    def test_delete_squawk_logs_event(self, aircraft, owner_user, squawk):
        client = self._owner_client(owner_user)
        before = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        client.delete(f'/api/squawks/{squawk.id}/')
        after = AircraftEvent.objects.filter(aircraft=aircraft, category='squawk').count()
        assert after == before + 1

    def test_custom_event_name_overrides_are_used(self, aircraft, owner_user):
        """MajorRepairAlterationViewSet sets custom event_name_created — verify it's used."""
        import datetime
        client = self._owner_client(owner_user)
        client.post(
            '/api/major-records/',
            data={
                'aircraft': str(aircraft.id),
                'record_type': 'repair',
                'title': 'Longeron repair',
                'date_performed': datetime.date.today().isoformat(),
            },
            format='json',
        )
        event = AircraftEvent.objects.filter(
            aircraft=aircraft, category='major_record'
        ).latest('timestamp')
        # MajorRepairAlterationViewSet.event_name_created = 'Major record created'
        assert event.event_name == 'Major record created'


# ---------------------------------------------------------------------------
# AircraftScopedMixin queryset scoping
# ---------------------------------------------------------------------------

class TestAircraftScopedMixinQueryscoping:
    """
    Test that AircraftScopedMixin correctly scopes querysets.
    We use the /api/squawks/ endpoint which uses SquawkViewSet
    (AircraftScopedMixin + EventLoggingMixin).
    """

    def _get_ids(self, response_data):
        """Extract IDs from either a plain list or a paginated response."""
        if isinstance(response_data, dict) and 'results' in response_data:
            return [item['id'] for item in response_data['results']]
        return [item['id'] for item in response_data]

    def test_owner_can_see_their_aircraft_squawks(self, aircraft, owner_user, squawk):
        client = APIClient()
        client.force_authenticate(user=owner_user)
        response = client.get('/api/squawks/')
        assert response.status_code == 200
        ids = self._get_ids(response.data)
        assert str(squawk.id) in ids

    def test_pilot_can_see_aircraft_squawks(self, aircraft_with_pilot, pilot_user, squawk):
        client = APIClient()
        client.force_authenticate(user=pilot_user)
        response = client.get('/api/squawks/')
        assert response.status_code == 200
        ids = self._get_ids(response.data)
        assert str(squawk.id) in ids

    def test_user_with_no_role_cannot_see_squawks(self, aircraft, other_user, squawk):
        """User with no aircraft role gets empty queryset (not admin)."""
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.get('/api/squawks/')
        assert response.status_code == 200
        ids = self._get_ids(response.data)
        assert str(squawk.id) not in ids

    def test_admin_can_see_all_squawks(self, aircraft, admin_user, squawk):
        """Admin user bypasses scoping and sees all records."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get('/api/squawks/')
        assert response.status_code == 200
        ids = self._get_ids(response.data)
        assert str(squawk.id) in ids

    def test_owner_cannot_see_other_users_squawks(self, aircraft, squawk, db):
        """Owner of aircraft A should not see squawks from aircraft B."""
        from django.contrib.auth import get_user_model
        from core.models import Aircraft
        User = get_user_model()

        # Create a second owner and aircraft with its own squawk
        other_owner = User.objects.create_user(username='other_owner2', password='pw')
        other_aircraft = Aircraft.objects.create(
            tail_number='N99999',
            make='Piper',
            model='Cherokee',
        )
        AircraftRole.objects.create(aircraft=other_aircraft, user=other_owner, role='owner')
        other_squawk = Squawk.objects.create(
            aircraft=other_aircraft,
            priority=3,
            issue_reported='Other plane issue',
        )

        client = APIClient()
        client.force_authenticate(user=other_owner)
        response = client.get('/api/squawks/')
        assert response.status_code == 200
        ids = self._get_ids(response.data)
        # Should see their own squawk
        assert str(other_squawk.id) in ids
        # Should NOT see the original aircraft's squawk
        assert str(squawk.id) not in ids

    def test_pilot_cannot_delete_component(self, aircraft_with_pilot, pilot_user, component):
        """Pilot cannot DELETE a component — check_object_permissions requires owner+."""
        client = APIClient()
        client.force_authenticate(user=pilot_user)
        response = client.delete(f'/api/components/{component.id}/')
        assert response.status_code == 403

    def test_pilot_cannot_update_note(self, aircraft_with_pilot, pilot_user):
        """Pilot cannot PATCH a note even though they can create one."""
        from core.models import AircraftNote
        note = AircraftNote.objects.create(aircraft=aircraft_with_pilot, text='Original')
        client = APIClient()
        client.force_authenticate(user=pilot_user)
        response = client.patch(f'/api/aircraft-notes/{note.id}/', {'text': 'Changed'}, format='json')
        assert response.status_code == 403

    def test_pilot_cannot_delete_note(self, aircraft_with_pilot, pilot_user):
        """Pilot cannot DELETE a note even though they can create one."""
        from core.models import AircraftNote
        note = AircraftNote.objects.create(aircraft=aircraft_with_pilot, text='Original')
        client = APIClient()
        client.force_authenticate(user=pilot_user)
        response = client.delete(f'/api/aircraft-notes/{note.id}/')
        assert response.status_code == 403
