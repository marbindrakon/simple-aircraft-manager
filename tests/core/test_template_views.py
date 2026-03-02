"""
Tests for template views in core/views.py
Uses Django test Client (not DRF APIClient) for HTML views.
"""
import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Local fixtures for Django test Client (not DRF APIClient)
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(owner_user):
    c = Client()
    c.force_login(owner_user)
    return c


@pytest.fixture
def admin_django_client(admin_user):
    c = Client()
    c.force_login(admin_user)
    return c


# ---------------------------------------------------------------------------
# healthz endpoint
# ---------------------------------------------------------------------------

class TestHealthzView:
    def test_healthz_returns_200_no_auth(self):
        c = Client()
        resp = c.get('/healthz/')
        assert resp.status_code == 200

    def test_healthz_returns_ok_status(self):
        import json
        c = Client()
        resp = c.get('/healthz/')
        data = json.loads(resp.content)
        assert data.get('status') == 'ok'


# ---------------------------------------------------------------------------
# DashboardView
# ---------------------------------------------------------------------------

class TestDashboardView:
    def test_authenticated_user_gets_200(self, auth_client):
        resp = auth_client.get('/dashboard/')
        assert resp.status_code == 200

    def test_unauthenticated_redirects_to_login(self):
        c = Client()
        resp = c.get('/dashboard/')
        assert resp.status_code == 302
        assert '/accounts/login' in resp['Location']


# ---------------------------------------------------------------------------
# AircraftDetailView
# ---------------------------------------------------------------------------

class TestAircraftDetailView:
    def test_owner_gets_200(self, auth_client, aircraft):
        resp = auth_client.get(f'/aircraft/{aircraft.id}/')
        assert resp.status_code == 200

    def test_unauthenticated_redirects(self, aircraft):
        c = Client()
        resp = c.get(f'/aircraft/{aircraft.id}/')
        assert resp.status_code == 302
        assert '/accounts/login' in resp['Location']


# ---------------------------------------------------------------------------
# ProfileView
# ---------------------------------------------------------------------------

class TestProfileView:
    def test_authenticated_user_gets_200(self, auth_client):
        resp = auth_client.get('/accounts/profile/')
        assert resp.status_code == 200

    def test_oidc_user_redirected_to_dashboard(self, owner_user):
        """Users without a usable password (OIDC) are redirected to dashboard."""
        owner_user.set_unusable_password()
        owner_user.save()
        c = Client()
        c.force_login(owner_user)
        resp = c.get('/accounts/profile/')
        # Should redirect (to dashboard)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# ManageInvitationsView (admin-only)
# ---------------------------------------------------------------------------

class TestManageInvitationsView:
    def test_admin_gets_200(self, admin_django_client):
        resp = admin_django_client.get('/manage/invitations/')
        assert resp.status_code == 200

    def test_non_admin_gets_403(self, auth_client):
        resp = auth_client.get('/manage/invitations/')
        assert resp.status_code == 403

    def test_unauthenticated_redirects(self):
        c = Client()
        resp = c.get('/manage/invitations/')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# ManageUsersView (admin-only)
# ---------------------------------------------------------------------------

class TestManageUsersView:
    def test_admin_gets_200(self, admin_django_client):
        resp = admin_django_client.get('/manage/users/')
        assert resp.status_code == 200

    def test_non_admin_gets_403(self, auth_client):
        resp = auth_client.get('/manage/users/')
        assert resp.status_code == 403

    def test_unauthenticated_redirects(self):
        c = Client()
        resp = c.get('/manage/users/')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# UserSearchView (API, requires auth)
# ---------------------------------------------------------------------------

class TestUserSearchView:
    def test_authenticated_user_can_search(self, auth_client, owner_user):
        # Query by owner's username
        resp = auth_client.get('/api/user-search/?q=owner')
        assert resp.status_code == 200

    def test_short_query_returns_empty_list(self, auth_client):
        # Query shorter than 2 chars returns []
        resp = auth_client.get('/api/user-search/?q=o')
        assert resp.status_code == 200
        import json
        data = json.loads(resp.content)
        assert data == []

    def test_unauthenticated_returns_401_or_403(self):
        c = Client()
        resp = c.get('/api/user-search/?q=owner')
        assert resp.status_code in (401, 403)

    def test_search_finds_matching_user(self, auth_client, owner_user):
        resp = auth_client.get(f'/api/user-search/?q={owner_user.username[:3]}')
        assert resp.status_code == 200
        import json
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data]
        assert owner_user.username in usernames
