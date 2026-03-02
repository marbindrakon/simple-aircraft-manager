"""
Tests for public share token views.

Covers:
- PublicAircraftSummaryAPI  (GET /api/shared/<token>/)
- PublicLogbookEntriesAPI   (GET /api/shared/<token>/logbook-entries/)
- PublicAircraftView        (GET /shared/<token>/)

Token UUID field is `AircraftShareToken.token` (different from `.id`).
No authentication is required; the share token itself is the credential.
"""
import datetime

import pytest
from django.utils import timezone

from core.models import Aircraft, AircraftNote, AircraftRole, AircraftShareToken
from health.models import LogbookEntry, Squawk

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def summary_url(token_obj):
    """Build the public summary API URL for a share token."""
    return f'/api/shared/{token_obj.token}/'


def logbook_url(token_obj):
    """Build the public logbook entries API URL for a share token."""
    return f'/api/shared/{token_obj.token}/logbook-entries/'


def template_url(token_obj):
    """Build the public template view URL for a share token."""
    return f'/shared/{token_obj.token}/'


# ---------------------------------------------------------------------------
# Valid token — basic access (no auth required)
# ---------------------------------------------------------------------------

class TestValidToken:
    def test_status_token_summary_200(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        assert resp.status_code == 200

    def test_maintenance_token_summary_200(self, client, share_token_maintenance):
        resp = client.get(summary_url(share_token_maintenance))
        assert resp.status_code == 200

    def test_status_token_no_auth_required(self, share_token_status):
        """Django test client (no session) can access the summary."""
        from django.test import Client
        c = Client()
        resp = c.get(summary_url(share_token_status))
        assert resp.status_code == 200

    def test_summary_response_contains_aircraft_key(self, client, share_token_status, aircraft):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'aircraft' in data
        assert data['aircraft']['tail_number'] == aircraft.tail_number

    def test_summary_response_contains_components_key(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'components' in data

    def test_summary_response_contains_active_squawks_key(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'active_squawks' in data

    def test_summary_user_role_is_null(self, client, share_token_status):
        """Sensitive user_role field should be stripped from the aircraft data."""
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert data['aircraft'].get('user_role') is None

    def test_summary_has_share_links_stripped(self, client, share_token_status):
        """has_share_links should be stripped from the aircraft data."""
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'has_share_links' not in data.get('aircraft', {})

    def test_summary_roles_stripped(self, client, share_token_status):
        """roles field should be stripped from the aircraft data."""
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'roles' not in data.get('aircraft', {})


# ---------------------------------------------------------------------------
# Invalid / expired token
# ---------------------------------------------------------------------------

class TestInvalidToken:
    def test_nonexistent_token_404(self, client):
        resp = client.get('/api/shared/00000000-0000-0000-0000-000000000000/')
        assert resp.status_code == 404

    def test_expired_token_summary_404(self, client, aircraft, owner_user):
        expired_token = AircraftShareToken.objects.create(
            aircraft=aircraft,
            created_by=owner_user,
            label='Expired',
            privilege='status',
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        resp = client.get(summary_url(expired_token))
        assert resp.status_code == 404

    def test_expired_token_logbook_404(self, client, aircraft, owner_user):
        expired_token = AircraftShareToken.objects.create(
            aircraft=aircraft,
            created_by=owner_user,
            label='Expired maint',
            privilege='maintenance',
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        resp = client.get(logbook_url(expired_token))
        assert resp.status_code == 404

    def test_nonexistent_token_logbook_404(self, client):
        resp = client.get('/api/shared/00000000-0000-0000-0000-000000000000/logbook-entries/')
        assert resp.status_code == 404

    def test_non_uuid_token_404(self, client):
        resp = client.get('/api/shared/not-a-real-token/')
        assert resp.status_code == 404

    def test_future_expiry_token_200(self, client, aircraft, owner_user):
        """A token with an expiry date in the future should still be valid."""
        future_token = AircraftShareToken.objects.create(
            aircraft=aircraft,
            created_by=owner_user,
            label='Future expiry',
            privilege='status',
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        resp = client.get(summary_url(future_token))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Status privilege — data filtering
# ---------------------------------------------------------------------------

class TestStatusPrivilegeFiltering:
    def test_active_squawk_visible_via_status_token(
        self, client, share_token_status, aircraft
    ):
        Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Brake squeak', resolved=False)
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert len(data['active_squawks']) >= 1

    def test_resolved_squawk_not_in_active_squawks(
        self, client, share_token_status, aircraft
    ):
        Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Resolved', resolved=True)
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        # active_squawks should only contain unresolved squawks
        for sq in data['active_squawks']:
            assert sq.get('resolved') is not True

    def test_status_token_resolved_squawks_empty(
        self, client, share_token_status, aircraft
    ):
        Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Fixed squawk', resolved=True)
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        # status privilege: resolved_squawks should be an empty list
        assert data.get('resolved_squawks') == []

    def test_status_token_major_records_empty(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert data.get('major_records') == []

    def test_status_token_oil_analysis_empty(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert data.get('oil_analysis_reports') == []

    def test_status_token_has_notes_key(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'notes' in data

    def test_status_token_has_ads_key(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'ads' in data

    def test_status_token_has_inspections_key(self, client, share_token_status):
        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert 'inspections' in data


# ---------------------------------------------------------------------------
# Maintenance privilege — extras
# ---------------------------------------------------------------------------

class TestMaintenancePrivilege:
    def test_maintenance_token_logbook_entries_200(
        self, client, share_token_maintenance, logbook_entry
    ):
        resp = client.get(logbook_url(share_token_maintenance))
        assert resp.status_code == 200

    def test_maintenance_logbook_response_has_results_key(
        self, client, share_token_maintenance
    ):
        resp = client.get(logbook_url(share_token_maintenance))
        data = resp.json()
        assert 'results' in data
        assert 'count' in data

    def test_maintenance_logbook_shows_logbook_entries(
        self, client, share_token_maintenance, logbook_entry
    ):
        resp = client.get(logbook_url(share_token_maintenance))
        data = resp.json()
        assert data['count'] >= 1

    def test_maintenance_token_resolved_squawks_present(
        self, client, share_token_maintenance, aircraft
    ):
        Squawk.objects.create(aircraft=aircraft, priority=1, issue_reported='Fixed', resolved=True)
        resp = client.get(summary_url(share_token_maintenance))
        data = resp.json()
        assert len(data.get('resolved_squawks', [])) >= 1

    def test_maintenance_token_active_squawks_present(
        self, client, share_token_maintenance, aircraft
    ):
        Squawk.objects.create(aircraft=aircraft, priority=2, issue_reported='Active', resolved=False)
        resp = client.get(summary_url(share_token_maintenance))
        data = resp.json()
        assert 'active_squawks' in data


# ---------------------------------------------------------------------------
# Status token cannot access logbook entries
# ---------------------------------------------------------------------------

class TestStatusTokenLogbookDenied:
    def test_status_token_logbook_404(self, client, share_token_status):
        """A status-privilege share token must not be able to read logbook entries."""
        resp = client.get(logbook_url(share_token_status))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Public notes filtering (public=True vs public=False)
# ---------------------------------------------------------------------------

class TestPublicNotesFiltering:
    def test_only_public_notes_visible(self, client, share_token_status, aircraft, owner_user):
        AircraftNote.objects.create(aircraft=aircraft, text='Private note', public=False, added_by=owner_user)
        AircraftNote.objects.create(aircraft=aircraft, text='Public note', public=True, added_by=owner_user)

        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        notes = data.get('notes', [])

        note_texts = [n['text'] for n in notes]
        assert 'Public note' in note_texts
        assert 'Private note' not in note_texts

    def test_no_notes_visible_when_all_private(
        self, client, share_token_status, aircraft, owner_user
    ):
        AircraftNote.objects.create(aircraft=aircraft, text='Private 1', public=False, added_by=owner_user)
        AircraftNote.objects.create(aircraft=aircraft, text='Private 2', public=False, added_by=owner_user)

        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        assert data.get('notes') == []

    def test_all_public_notes_visible(
        self, client, share_token_status, aircraft, owner_user
    ):
        AircraftNote.objects.create(aircraft=aircraft, text='Pub A', public=True, added_by=owner_user)
        AircraftNote.objects.create(aircraft=aircraft, text='Pub B', public=True, added_by=owner_user)

        resp = client.get(summary_url(share_token_status))
        data = resp.json()
        note_texts = [n['text'] for n in data.get('notes', [])]
        assert 'Pub A' in note_texts
        assert 'Pub B' in note_texts


# ---------------------------------------------------------------------------
# Template view (/shared/<token>/)
# ---------------------------------------------------------------------------

class TestPublicTemplateView:
    def test_valid_status_token_200(self, client, share_token_status):
        resp = client.get(template_url(share_token_status))
        assert resp.status_code == 200

    def test_valid_maintenance_token_200(self, client, share_token_maintenance):
        resp = client.get(template_url(share_token_maintenance))
        assert resp.status_code == 200

    def test_nonexistent_token_404(self, client):
        resp = client.get('/shared/00000000-0000-0000-0000-000000000000/')
        assert resp.status_code == 404

    def test_expired_token_404(self, client, aircraft, owner_user):
        expired = AircraftShareToken.objects.create(
            aircraft=aircraft,
            created_by=owner_user,
            label='Expired',
            privilege='status',
            expires_at=timezone.now() - datetime.timedelta(seconds=1),
        )
        resp = client.get(template_url(expired))
        assert resp.status_code == 404

    def test_uses_public_base_template(self, client, share_token_status):
        resp = client.get(template_url(share_token_status))
        # The view passes base_template='base_public.html' to the template context.
        # We can confirm the response used a template chain that includes base_public.html.
        template_names = [t.name for t in resp.templates]
        assert 'base_public.html' in template_names
