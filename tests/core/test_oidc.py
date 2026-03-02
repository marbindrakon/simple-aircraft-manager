"""
Tests for core/oidc.py — CustomOIDCAuthenticationBackend and provider_logout.

Covers:
- generate_username: basic extraction, special char stripping, empty/invalid email, counter uniqueness
- get_username: preferred_username (happy path + sanitization + all-special falls through),
  email fallback, sub fallback, no claims
- filter_users_by_claims: lookup by sub, username fallback (no sub), no match, sub claim absent
- create_user: happy path, missing username returns None, IntegrityError recovery, sub stored
- update_user: syncs email/first_name/last_name, stores sub in UserProfile, updates existing profile
- provider_logout: uses OIDC_OP_LOGOUT_ENDPOINT when set, falls back to discovery URL,
  includes id_token_hint from session, omits hint when absent, returns None when no config
"""

import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from core.models import UserProfile
from core.oidc import CustomOIDCAuthenticationBackend, generate_username

pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def oidc_settings(settings):
    """Supply the minimum OIDC settings required by OIDCAuthenticationBackend.__init__."""
    settings.OIDC_OP_TOKEN_ENDPOINT = 'https://example.com/token'
    settings.OIDC_OP_USER_ENDPOINT = 'https://example.com/userinfo'
    settings.OIDC_RP_CLIENT_ID = 'test-client'
    settings.OIDC_RP_CLIENT_SECRET = 'test-secret'
    settings.OIDC_OP_JWKS_ENDPOINT = 'https://example.com/jwks'
    settings.OIDC_OP_AUTHORIZATION_ENDPOINT = 'https://example.com/auth'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_backend():
    """Return a backend instance."""
    backend = CustomOIDCAuthenticationBackend()
    return backend


def make_request(session=None, absolute_uri='/'):
    """Return a mock request."""
    request = MagicMock()
    request.session = session or {}
    request.build_absolute_uri.return_value = absolute_uri
    return request


# ---------------------------------------------------------------------------
# generate_username
# ---------------------------------------------------------------------------

class TestGenerateUsername:
    def test_basic_extraction(self):
        username = generate_username('alice@example.com')
        assert username == 'alice'

    def test_special_chars_stripped(self):
        username = generate_username('alice.smith+tag@example.com')
        # '.' and '+' are not alphanumeric, '_', or '-' so they are removed
        assert username == 'alicesmithtag'

    def test_hyphen_and_underscore_preserved(self):
        username = generate_username('alice_smith-x@example.com')
        assert username == 'alice_smith-x'

    def test_empty_email_returns_none(self):
        assert generate_username('') is None

    def test_no_at_sign_returns_none(self):
        assert generate_username('notanemail') is None

    def test_all_special_chars_local_part(self):
        # local part becomes empty after stripping
        assert generate_username('...@example.com') is None

    def test_uniqueness_counter(self):
        User.objects.create_user(username='bob', password='x')
        User.objects.create_user(username='bob1', password='x')
        username = generate_username('bob@example.com')
        assert username == 'bob2'

    def test_first_available_returned(self):
        # No collision — should get base username
        username = generate_username('carol@example.com')
        assert username == 'carol'


# ---------------------------------------------------------------------------
# get_username
# ---------------------------------------------------------------------------

class TestGetUsername:
    def setup_method(self):
        self.backend = make_backend()

    def test_preferred_username_returned(self):
        claims = {'preferred_username': 'alice', 'sub': 'sub-123'}
        assert self.backend.get_username(claims) == 'alice'

    def test_preferred_username_sanitized(self):
        claims = {'preferred_username': 'alice.smith@domain', 'sub': 'sub-123'}
        result = self.backend.get_username(claims)
        # dots and @ stripped
        assert result == 'alicesmithdomain'

    def test_preferred_username_all_special_falls_through_to_email(self):
        User.objects.create_user(username='alice', password='x')
        claims = {
            'preferred_username': '...',
            'email': 'alice@example.com',
            'sub': 'sub-123',
        }
        result = self.backend.get_username(claims)
        # 'alice' already taken, so generate_username returns 'alice1'
        assert result == 'alice1'

    def test_email_fallback_when_no_preferred_username(self):
        claims = {'email': 'bob@example.com', 'sub': 'sub-456'}
        assert self.backend.get_username(claims) == 'bob'

    def test_sub_fallback_when_no_preferred_username_or_email(self):
        claims = {'sub': 'unique-sub-uuid'}
        assert self.backend.get_username(claims) == 'unique-sub-uuid'

    def test_no_claims_returns_none(self):
        assert self.backend.get_username({}) is None


# ---------------------------------------------------------------------------
# filter_users_by_claims
# ---------------------------------------------------------------------------

class TestFilterUsersByClaims:
    def setup_method(self):
        self.backend = make_backend()

    def test_lookup_by_sub(self):
        user = User.objects.create_user(username='alice', password='x')
        UserProfile.objects.create(user=user, oidc_sub='sub-abc')

        claims = {'sub': 'sub-abc', 'preferred_username': 'alice'}
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == [user]

    def test_sub_lookup_ignores_username_collision(self):
        """If sub matches a different user than username would, sub wins."""
        user_real = User.objects.create_user(username='real_user', password='x')
        user_impostor = User.objects.create_user(username='alice', password='x')
        UserProfile.objects.create(user=user_real, oidc_sub='sub-real')

        claims = {
            'sub': 'sub-real',
            'preferred_username': 'alice',  # would match user_impostor by username
        }
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == [user_real]

    def test_username_fallback_when_no_sub_profile(self):
        """No UserProfile with matching sub → fall back to username."""
        user = User.objects.create_user(username='charlie', password='x')

        claims = {'preferred_username': 'charlie', 'sub': 'sub-xyz'}
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == [user]

    def test_no_match_returns_empty(self):
        claims = {'preferred_username': 'nobody', 'sub': 'sub-nobody'}
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == []

    def test_sub_claim_absent_falls_back_to_username(self):
        user = User.objects.create_user(username='dave', password='x')
        claims = {'preferred_username': 'dave'}  # no 'sub' key
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == [user]

    def test_no_username_and_no_sub_returns_empty(self):
        claims = {}
        qs = self.backend.filter_users_by_claims(claims)
        assert list(qs) == []


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    def setup_method(self):
        self.backend = make_backend()

    def test_creates_user(self):
        claims = {
            'preferred_username': 'newuser',
            'email': 'newuser@example.com',
            'sub': 'sub-new',
            'given_name': 'New',
            'family_name': 'User',
        }
        user = self.backend.create_user(claims)
        assert user is not None
        assert user.username == 'newuser'
        assert user.email == 'newuser@example.com'
        assert user.first_name == 'New'

    def test_sub_stored_after_create(self):
        claims = {
            'preferred_username': 'subuser',
            'email': 'subuser@example.com',
            'sub': 'sub-stored',
        }
        user = self.backend.create_user(claims)
        profile = UserProfile.objects.get(user=user)
        assert profile.oidc_sub == 'sub-stored'

    def test_missing_username_returns_none(self):
        claims = {}  # no preferred_username, email, or sub
        user = self.backend.create_user(claims)
        assert user is None

    def test_integrity_error_recovery_retrieves_existing_user(self):
        """Concurrent signup: create_user gets IntegrityError, recovers by fetching existing."""
        existing = User.objects.create_user(username='concurrent', password='x')
        claims = {
            'preferred_username': 'concurrent',
            'email': 'concurrent@example.com',
            'sub': 'sub-concurrent',
        }
        with patch('core.oidc.User.objects.create_user', side_effect=IntegrityError):
            user = self.backend.create_user(claims)
        assert user == existing

    def test_integrity_error_with_vanished_user_returns_none(self):
        """IntegrityError but user also doesn't exist → return None."""
        claims = {
            'preferred_username': 'ghost',
            'email': 'ghost@example.com',
            'sub': 'sub-ghost',
        }
        with patch('core.oidc.User.objects.create_user', side_effect=IntegrityError):
            user = self.backend.create_user(claims)
        assert user is None


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------

class TestUpdateUser:
    def setup_method(self):
        self.backend = make_backend()

    def test_syncs_email_and_names(self):
        user = User.objects.create_user(username='alice', password='x')
        claims = {
            'email': 'alice@new.com',
            'given_name': 'Alice',
            'family_name': 'Smith',
            'sub': 'sub-alice',
        }
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        assert user.email == 'alice@new.com'
        assert user.first_name == 'Alice'
        assert user.last_name == 'Smith'

    def test_stores_sub_in_profile(self):
        user = User.objects.create_user(username='bob', password='x')
        claims = {'sub': 'sub-bob', 'email': 'bob@example.com'}
        self.backend.update_user(user, claims)
        profile = UserProfile.objects.get(user=user)
        assert profile.oidc_sub == 'sub-bob'

    def test_updates_existing_profile_sub(self):
        user = User.objects.create_user(username='carol', password='x')
        UserProfile.objects.create(user=user, oidc_sub='old-sub')
        claims = {'sub': 'new-sub', 'email': 'carol@example.com'}
        self.backend.update_user(user, claims)
        profile = UserProfile.objects.get(user=user)
        assert profile.oidc_sub == 'new-sub'

    def test_no_sub_does_not_create_profile(self):
        user = User.objects.create_user(username='dave', password='x')
        claims = {'email': 'dave@example.com'}  # no 'sub'
        self.backend.update_user(user, claims)
        assert not UserProfile.objects.filter(user=user).exists()

    def test_returns_user(self):
        user = User.objects.create_user(username='eve', password='x')
        result = self.backend.update_user(user, {'sub': 'sub-eve'})
        assert result == user


# ---------------------------------------------------------------------------
# provider_logout
# ---------------------------------------------------------------------------

class TestProviderLogout:
    def test_uses_oidc_op_logout_endpoint_setting(self, settings):
        settings.OIDC_OP_LOGOUT_ENDPOINT = 'https://auth.example.com/logout'
        settings.OIDC_OP_DISCOVERY_ENDPOINT = ''
        request = make_request(absolute_uri='https://myapp.example.com/')

        from core.oidc import provider_logout
        url = provider_logout(request)

        assert url.startswith('https://auth.example.com/logout?')
        assert 'post_logout_redirect_uri=' in url

    def test_falls_back_to_discovery_url_construction(self, settings):
        settings.OIDC_OP_LOGOUT_ENDPOINT = None
        settings.OIDC_OP_DISCOVERY_ENDPOINT = (
            'https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration'
        )
        request = make_request(absolute_uri='https://myapp.example.com/')

        from core.oidc import provider_logout
        url = provider_logout(request)

        assert url.startswith(
            'https://keycloak.example.com/realms/myrealm/protocol/openid-connect/logout?'
        )

    def test_includes_id_token_hint_when_present(self, settings):
        settings.OIDC_OP_LOGOUT_ENDPOINT = 'https://auth.example.com/logout'
        request = make_request(
            session={'oidc_id_token': 'my-id-token'},
            absolute_uri='https://myapp.example.com/',
        )

        from core.oidc import provider_logout
        url = provider_logout(request)

        assert 'id_token_hint=my-id-token' in url

    def test_omits_id_token_hint_when_absent(self, settings):
        settings.OIDC_OP_LOGOUT_ENDPOINT = 'https://auth.example.com/logout'
        request = make_request(session={}, absolute_uri='https://myapp.example.com/')

        from core.oidc import provider_logout
        url = provider_logout(request)

        assert 'id_token_hint' not in url

    def test_returns_none_when_no_config(self, settings):
        settings.OIDC_OP_LOGOUT_ENDPOINT = None
        settings.OIDC_OP_DISCOVERY_ENDPOINT = ''
        request = make_request()

        from core.oidc import provider_logout
        result = provider_logout(request)

        assert result is None
