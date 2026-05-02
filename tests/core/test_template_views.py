"""
Tests for template views in core/views.py
Uses Django test Client (not DRF APIClient) for HTML views.
"""
import json

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
# Base template assets
# ---------------------------------------------------------------------------

class TestBaseTemplateAssets:
    def test_dashboard_does_not_load_stale_fonts_css(self, auth_client):
        resp = auth_client.get('/dashboard/')
        assert resp.status_code == 200
        html = resp.content.decode()

        assert 'css/fonts.css' not in html
        assert 'overpass-webfont' not in html

    def test_vendor_assets_mode_uses_local_app_shell_assets(self, auth_client, settings):
        settings.SAM_USE_VENDOR_ASSETS = True

        resp = auth_client.get('/dashboard/')
        assert resp.status_code == 200
        html = resp.content.decode()

        assert 'vendor/patternfly.min.css' in html
        assert 'vendor/chart.umd.min.js' in html
        assert 'vendor/alpine.min.js' in html
        assert 'css/fonts.css' not in html
        assert 'unpkg.com' not in html
        assert 'cdn.jsdelivr.net' not in html


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
        data = json.loads(resp.content)
        assert data == []

    def test_unauthenticated_returns_401_or_403(self):
        c = Client()
        resp = c.get('/api/user-search/?q=owner')
        assert resp.status_code in (401, 403)

    def test_search_finds_matching_user(self, auth_client, owner_user):
        resp = auth_client.get(f'/api/user-search/?q={owner_user.username[:3]}')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data]
        assert owner_user.username in usernames


# ---------------------------------------------------------------------------
# vendor_assets_context processor
# ---------------------------------------------------------------------------

class TestVendorAssetsContextProcessor:
    def test_returns_false_by_default(self, rf):
        from core.context_processors import vendor_assets_context
        request = rf.get('/')
        result = vendor_assets_context(request)
        assert result == {'sam_use_vendor_assets': False}

    def test_returns_true_when_setting_enabled(self, rf, settings):
        from core.context_processors import vendor_assets_context
        settings.SAM_USE_VENDOR_ASSETS = True
        request = rf.get('/')
        result = vendor_assets_context(request)
        assert result == {'sam_use_vendor_assets': True}
