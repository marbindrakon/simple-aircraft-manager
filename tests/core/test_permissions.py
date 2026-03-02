"""
Tests for core/permissions.py:
  - get_user_role
  - has_aircraft_permission
  - user_can_create_aircraft
  - IsAircraftOwnerOrAdmin
  - IsAircraftPilotOrAbove
  - IsAdAircraftOwnerOrAdmin
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from core.models import AircraftRole
from core.permissions import (
    PILOT_WRITE_ACTIONS,
    IsAdAircraftOwnerOrAdmin,
    IsAircraftOwnerOrAdmin,
    IsAircraftPilotOrAbove,
    get_user_role,
    has_aircraft_permission,
    user_can_create_aircraft,
)
from health.models import AD

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# get_user_role
# ---------------------------------------------------------------------------

class TestGetUserRole:

    def test_staff_user_returns_admin(self, admin_user, aircraft):
        assert get_user_role(admin_user, aircraft) == 'admin'

    def test_superuser_returns_admin(self, aircraft, db):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        su = User.objects.create_superuser(username='su2', password='pw', email='su2@test.com')
        assert get_user_role(su, aircraft) == 'admin'

    def test_owner_user_returns_owner(self, owner_user, aircraft):
        assert get_user_role(owner_user, aircraft) == 'owner'

    def test_pilot_user_returns_pilot(self, pilot_user, aircraft_with_pilot):
        assert get_user_role(pilot_user, aircraft_with_pilot) == 'pilot'

    def test_user_with_no_role_returns_none(self, other_user, aircraft):
        assert get_user_role(other_user, aircraft) is None

    def test_anonymous_user_returns_none(self, aircraft):
        anon = AnonymousUser()
        assert get_user_role(anon, aircraft) is None

    def test_none_user_returns_none(self, aircraft):
        assert get_user_role(None, aircraft) is None


# ---------------------------------------------------------------------------
# has_aircraft_permission
# ---------------------------------------------------------------------------

class TestHasAircraftPermission:

    def test_admin_can_do_owner_level(self, admin_user, aircraft):
        assert has_aircraft_permission(admin_user, aircraft, 'owner') is True

    def test_admin_can_do_pilot_level(self, admin_user, aircraft):
        assert has_aircraft_permission(admin_user, aircraft, 'pilot') is True

    def test_owner_passes_owner_check(self, owner_user, aircraft):
        assert has_aircraft_permission(owner_user, aircraft, 'owner') is True

    def test_owner_passes_pilot_check(self, owner_user, aircraft):
        assert has_aircraft_permission(owner_user, aircraft, 'pilot') is True

    def test_pilot_passes_pilot_check(self, pilot_user, aircraft_with_pilot):
        assert has_aircraft_permission(pilot_user, aircraft_with_pilot, 'pilot') is True

    def test_pilot_fails_owner_check(self, pilot_user, aircraft_with_pilot):
        assert has_aircraft_permission(pilot_user, aircraft_with_pilot, 'owner') is False

    def test_no_role_user_fails_all_checks(self, other_user, aircraft):
        assert has_aircraft_permission(other_user, aircraft, 'pilot') is False
        assert has_aircraft_permission(other_user, aircraft, 'owner') is False


# ---------------------------------------------------------------------------
# user_can_create_aircraft
# ---------------------------------------------------------------------------

class TestUserCanCreateAircraft:

    @override_settings(AIRCRAFT_CREATE_PERMISSION='any')
    def test_any_authenticated_user_can_create(self, other_user):
        assert user_can_create_aircraft(other_user) is True

    @override_settings(AIRCRAFT_CREATE_PERMISSION='any')
    def test_admin_can_always_create(self, admin_user):
        assert user_can_create_aircraft(admin_user) is True

    @override_settings(AIRCRAFT_CREATE_PERMISSION='admin')
    def test_regular_user_cannot_create_when_admin_only(self, other_user):
        assert user_can_create_aircraft(other_user) is False

    @override_settings(AIRCRAFT_CREATE_PERMISSION='admin')
    def test_admin_can_create_when_admin_only(self, admin_user):
        assert user_can_create_aircraft(admin_user) is True

    @override_settings(AIRCRAFT_CREATE_PERMISSION='owners')
    def test_owner_can_create_when_owners_only(self, owner_user, aircraft):
        # owner_user already has an owner role on `aircraft` via the fixture
        assert user_can_create_aircraft(owner_user) is True

    @override_settings(AIRCRAFT_CREATE_PERMISSION='owners')
    def test_non_owner_cannot_create_when_owners_only(self, other_user):
        assert user_can_create_aircraft(other_user) is False

    @override_settings(AIRCRAFT_CREATE_PERMISSION='owners')
    def test_admin_can_create_when_owners_only(self, admin_user):
        assert user_can_create_aircraft(admin_user) is True

    def test_unauthenticated_cannot_create(self):
        anon = AnonymousUser()
        assert user_can_create_aircraft(anon) is False

    def test_none_cannot_create(self):
        assert user_can_create_aircraft(None) is False


# ---------------------------------------------------------------------------
# IsAircraftOwnerOrAdmin permission class
# ---------------------------------------------------------------------------

class TestIsAircraftOwnerOrAdmin:

    def _make_view(self, action='list'):
        """Create a mock view with an action."""
        class MockView:
            pass
        view = MockView()
        view.action = action
        return view

    def _make_request(self, user, method='GET'):
        request = factory.generic(method, '/')
        request.user = user
        return request

    def test_owner_has_object_permission(self, owner_user, aircraft):
        perm = IsAircraftOwnerOrAdmin()
        request = self._make_request(owner_user)
        assert perm.has_object_permission(request, self._make_view(), aircraft) is True

    def test_admin_has_object_permission(self, admin_user, aircraft):
        perm = IsAircraftOwnerOrAdmin()
        request = self._make_request(admin_user)
        assert perm.has_object_permission(request, self._make_view(), aircraft) is True

    def test_pilot_does_not_have_object_permission(self, pilot_user, aircraft_with_pilot):
        perm = IsAircraftOwnerOrAdmin()
        request = self._make_request(pilot_user)
        assert perm.has_object_permission(request, self._make_view(), aircraft_with_pilot) is False

    def test_no_role_user_does_not_have_object_permission(self, other_user, aircraft):
        perm = IsAircraftOwnerOrAdmin()
        request = self._make_request(other_user)
        assert perm.has_object_permission(request, self._make_view(), aircraft) is False


# ---------------------------------------------------------------------------
# IsAircraftPilotOrAbove permission class
# ---------------------------------------------------------------------------

class TestIsAircraftPilotOrAbove:

    def _make_view(self, action='list'):
        class MockView:
            pass
        view = MockView()
        view.action = action
        return view

    def _make_request(self, user, method='GET'):
        request = factory.generic(method, '/')
        request.user = user
        return request

    def test_pilot_can_read_with_safe_method(self, pilot_user, aircraft_with_pilot):
        perm = IsAircraftPilotOrAbove()
        request = self._make_request(pilot_user, method='GET')
        assert perm.has_object_permission(request, self._make_view(), aircraft_with_pilot) is True

    def test_pilot_can_perform_pilot_write_action(self, pilot_user, aircraft_with_pilot):
        """Pilot should be allowed to perform actions in PILOT_WRITE_ACTIONS."""
        perm = IsAircraftPilotOrAbove()
        # Use a known pilot write action
        pilot_action = next(iter(PILOT_WRITE_ACTIONS))
        view = self._make_view(action=pilot_action)
        request = self._make_request(pilot_user, method='POST')
        assert perm.has_object_permission(request, view, aircraft_with_pilot) is True

    def test_pilot_cannot_perform_non_pilot_write_action(self, pilot_user, aircraft_with_pilot):
        """Pilot should be denied actions not in PILOT_WRITE_ACTIONS."""
        perm = IsAircraftPilotOrAbove()
        # Use an action not in pilot write actions
        non_pilot_action = 'destroy'
        assert non_pilot_action not in PILOT_WRITE_ACTIONS
        view = self._make_view(action=non_pilot_action)
        request = self._make_request(pilot_user, method='DELETE')
        assert perm.has_object_permission(request, view, aircraft_with_pilot) is False

    def test_owner_can_perform_non_pilot_write_action(self, owner_user, aircraft):
        """Owner should be allowed actions not in PILOT_WRITE_ACTIONS."""
        perm = IsAircraftPilotOrAbove()
        view = self._make_view(action='destroy')
        request = self._make_request(owner_user, method='DELETE')
        assert perm.has_object_permission(request, view, aircraft) is True

    def test_admin_can_perform_any_action(self, admin_user, aircraft):
        perm = IsAircraftPilotOrAbove()
        view = self._make_view(action='destroy')
        request = self._make_request(admin_user, method='DELETE')
        assert perm.has_object_permission(request, view, aircraft) is True

    def test_no_role_user_is_denied(self, other_user, aircraft):
        perm = IsAircraftPilotOrAbove()
        request = self._make_request(other_user, method='GET')
        assert perm.has_object_permission(request, self._make_view(), aircraft) is False


# ---------------------------------------------------------------------------
# IsAdAircraftOwnerOrAdmin permission class
# ---------------------------------------------------------------------------

class TestIsAdAircraftOwnerOrAdmin:

    def _make_view(self):
        class MockView:
            pass
        return MockView()

    def _make_request(self, user, method='PATCH'):
        request = factory.generic(method, '/')
        request.user = user
        return request

    def _make_ad_for_aircraft(self, aircraft):
        ad = AD.objects.create(
            name='AD-PERM-TEST',
            short_description='Permission test AD',
            mandatory=True,
            compliance_type='standard',
        )
        ad.applicable_aircraft.add(aircraft)
        return ad

    def test_admin_has_object_permission(self, admin_user, aircraft):
        ad = self._make_ad_for_aircraft(aircraft)
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(admin_user)
        assert perm.has_object_permission(request, self._make_view(), ad) is True

    def test_owner_has_object_permission_on_associated_aircraft(self, owner_user, aircraft):
        """Owner of an aircraft that uses this AD should have write access."""
        ad = self._make_ad_for_aircraft(aircraft)
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(owner_user)
        assert perm.has_object_permission(request, self._make_view(), ad) is True

    def test_pilot_does_not_have_object_permission(self, pilot_user, aircraft_with_pilot):
        """Pilot (not owner) should not be able to edit ADs."""
        ad = self._make_ad_for_aircraft(aircraft_with_pilot)
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(pilot_user)
        assert perm.has_object_permission(request, self._make_view(), ad) is False

    def test_unrelated_user_does_not_have_object_permission(self, other_user, aircraft):
        """User with no role on the associated aircraft should be denied."""
        ad = self._make_ad_for_aircraft(aircraft)
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(other_user)
        assert perm.has_object_permission(request, self._make_view(), ad) is False

    def test_has_permission_requires_authentication(self, other_user, aircraft):
        """has_permission returns True for authenticated users."""
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(other_user, method='GET')
        assert perm.has_permission(request, self._make_view()) is True

    def test_has_permission_denies_anonymous(self, aircraft):
        perm = IsAdAircraftOwnerOrAdmin()
        request = self._make_request(AnonymousUser(), method='GET')
        # AnonymousUser.is_authenticated is False
        assert perm.has_permission(request, self._make_view()) is False
