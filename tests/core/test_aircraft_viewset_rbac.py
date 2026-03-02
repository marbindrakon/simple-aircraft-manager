"""
RBAC enforcement tests for AircraftViewSet.

Tests that pilots, owners, admins, and unauthenticated users get the
correct responses from every action/endpoint.
"""
import datetime

import pytest
from rest_framework.test import APIClient

from core.models import AircraftRole

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Pilot — ALLOWED
# ---------------------------------------------------------------------------

class TestPilotAllowed:
    """Pilot-role users should be allowed to read all data and write to the
    PILOT_WRITE_ACTIONS subset of endpoints."""

    def test_list_aircraft_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get('/api/aircraft/')
        assert resp.status_code == 200

    def test_retrieve_aircraft_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/')
        assert resp.status_code == 200

    def test_summary_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/summary/')
        assert resp.status_code == 200

    def test_update_hours_200(self, pilot_client, aircraft_with_pilot):
        new_tach = float(aircraft_with_pilot.tach_time) + 1.0
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/update_hours/',
            {'new_tach_time': new_tach},
            format='json',
        )
        assert resp.status_code == 200

    def test_create_squawk_201(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/squawks/',
            {'priority': 1, 'issue_reported': 'Brake squeak'},
            format='json',
        )
        assert resp.status_code == 201

    def test_create_note_201(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/notes/',
            {'text': 'Pilot note'},
            format='json',
        )
        assert resp.status_code == 201

    def test_create_oil_record_201(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/oil_records/',
            {
                'quantity_added': '1.0',
                'date': str(datetime.date.today()),
                'flight_hours': str(aircraft_with_pilot.tach_time),
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_create_fuel_record_201(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/fuel_records/',
            {
                'quantity_added': '10.0',
                'date': str(datetime.date.today()),
                'flight_hours': str(aircraft_with_pilot.tach_time),
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_get_squawks_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/squawks/')
        assert resp.status_code == 200

    def test_get_notes_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/notes/')
        assert resp.status_code == 200

    def test_get_ads_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/ads/')
        assert resp.status_code == 200

    def test_get_inspections_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/inspections/')
        assert resp.status_code == 200

    def test_get_major_records_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/major_records/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pilot — DENIED (403)
# ---------------------------------------------------------------------------

class TestPilotDenied:
    """Pilot-role users must be denied owner-level write actions."""

    def test_patch_aircraft_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.patch(
            f'/api/aircraft/{aircraft_with_pilot.id}/',
            {'tail_number': 'N99999'},
            format='json',
        )
        assert resp.status_code == 403

    def test_delete_aircraft_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.delete(f'/api/aircraft/{aircraft_with_pilot.id}/')
        assert resp.status_code == 403

    def test_post_component_403(self, pilot_client, aircraft_with_pilot, component_type):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/components/',
            {
                'component_type': str(component_type.id),
                'status': 'SPARE',
                'date_in_service': str(datetime.date.today()),
            },
            format='json',
        )
        assert resp.status_code == 403

    def test_post_ads_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/ads/',
            {
                'name': 'AD-2020-01-01',
                'short_description': 'Test AD',
                'mandatory': True,
                'compliance_type': 'standard',
            },
            format='json',
        )
        assert resp.status_code == 403

    def test_post_compliance_403(self, pilot_client, aircraft_with_pilot, ad):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/compliance/',
            {
                'ad': str(ad.id),
                'date_complied': str(datetime.date.today()),
                'permanent': True,
            },
            format='json',
        )
        assert resp.status_code == 403

    def test_post_inspections_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/inspections/',
            {'inspection_type_id': 'does-not-exist'},
            format='json',
        )
        assert resp.status_code == 403

    def test_post_major_records_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/major_records/',
            {
                'title': 'Test major repair',
                'record_type': 'repair',
                'date_performed': str(datetime.date.today()),
            },
            format='json',
        )
        assert resp.status_code == 403

    def test_get_manage_roles_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/manage_roles/')
        assert resp.status_code == 403

    def test_get_share_tokens_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/share_tokens/')
        assert resp.status_code == 403

    def test_post_share_tokens_403(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/share_tokens/',
            {'privilege': 'status'},
            format='json',
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Owner — ALLOWED (spot-check)
# ---------------------------------------------------------------------------

class TestOwnerAllowed:
    """Owner-role users can access everything including owner-only actions."""

    def test_patch_aircraft_200(self, owner_client, aircraft):
        resp = owner_client.patch(
            f'/api/aircraft/{aircraft.id}/',
            {'tail_number': 'N54321'},
            format='json',
        )
        assert resp.status_code == 200

    def test_get_manage_roles_200(self, owner_client, aircraft):
        resp = owner_client.get(f'/api/aircraft/{aircraft.id}/manage_roles/')
        assert resp.status_code == 200

    def test_get_share_tokens_200(self, owner_client, aircraft):
        resp = owner_client.get(f'/api/aircraft/{aircraft.id}/share_tokens/')
        assert resp.status_code == 200

    def test_post_share_tokens_201(self, owner_client, aircraft):
        resp = owner_client.post(
            f'/api/aircraft/{aircraft.id}/share_tokens/',
            {'privilege': 'status'},
            format='json',
        )
        assert resp.status_code == 201

    def test_update_hours_200(self, owner_client, aircraft):
        new_tach = float(aircraft.tach_time) + 2.0
        resp = owner_client.post(
            f'/api/aircraft/{aircraft.id}/update_hours/',
            {'new_tach_time': new_tach},
            format='json',
        )
        assert resp.status_code == 200

    def test_summary_200(self, owner_client, aircraft):
        resp = owner_client.get(f'/api/aircraft/{aircraft.id}/summary/')
        assert resp.status_code == 200

    def test_list_200(self, owner_client, aircraft):
        resp = owner_client.get('/api/aircraft/')
        assert resp.status_code == 200
        # The owner's aircraft should appear in the list
        ids = [item['id'] for item in resp.data]
        assert str(aircraft.id) in ids

    def test_post_note_201(self, owner_client, aircraft):
        resp = owner_client.post(
            f'/api/aircraft/{aircraft.id}/notes/',
            {'text': 'Owner note'},
            format='json',
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# No-role user (other_client) — queryset scoping returns 404
# ---------------------------------------------------------------------------

class TestNoRoleUser:
    """A user with no role on the aircraft gets 404 (not in scoped queryset)
    on all aircraft-scoped endpoints, rather than 403."""

    def test_retrieve_404(self, other_client, aircraft):
        resp = other_client.get(f'/api/aircraft/{aircraft.id}/')
        assert resp.status_code == 404

    def test_summary_404(self, other_client, aircraft):
        resp = other_client.get(f'/api/aircraft/{aircraft.id}/summary/')
        assert resp.status_code == 404

    def test_patch_404(self, other_client, aircraft):
        resp = other_client.patch(
            f'/api/aircraft/{aircraft.id}/',
            {'tail_number': 'N00000'},
            format='json',
        )
        assert resp.status_code == 404

    def test_squawks_404(self, other_client, aircraft):
        resp = other_client.get(f'/api/aircraft/{aircraft.id}/squawks/')
        assert resp.status_code == 404

    def test_update_hours_404(self, other_client, aircraft):
        resp = other_client.post(
            f'/api/aircraft/{aircraft.id}/update_hours/',
            {'new_tach_time': 200.0},
            format='json',
        )
        assert resp.status_code == 404

    def test_list_returns_empty(self, other_client, aircraft):
        """List endpoint returns 200 but the other user sees no aircraft."""
        resp = other_client.get('/api/aircraft/')
        assert resp.status_code == 200
        assert len(resp.data) == 0


# ---------------------------------------------------------------------------
# Unauthenticated — 401 or 403
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    """Unauthenticated requests must be rejected with 401 or 403."""

    def test_list_aircraft_rejected(self, aircraft):
        client = APIClient()  # no auth
        resp = client.get('/api/aircraft/')
        assert resp.status_code in (401, 403)

    def test_retrieve_aircraft_rejected(self, aircraft):
        client = APIClient()
        resp = client.get(f'/api/aircraft/{aircraft.id}/')
        assert resp.status_code in (401, 403)

    def test_update_hours_rejected(self, aircraft):
        client = APIClient()
        resp = client.post(
            f'/api/aircraft/{aircraft.id}/update_hours/',
            {'new_tach_time': 200.0},
            format='json',
        )
        assert resp.status_code in (401, 403)

    def test_summary_rejected(self, aircraft):
        client = APIClient()
        resp = client.get(f'/api/aircraft/{aircraft.id}/summary/')
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Admin — bypasses all checks
# ---------------------------------------------------------------------------

class TestAdminBypasses:
    """Admin (is_staff/is_superuser) can access every endpoint regardless of
    aircraft role assignment."""

    def test_list_200(self, admin_client, aircraft):
        resp = admin_client.get('/api/aircraft/')
        assert resp.status_code == 200

    def test_retrieve_200(self, admin_client, aircraft):
        resp = admin_client.get(f'/api/aircraft/{aircraft.id}/')
        assert resp.status_code == 200

    def test_patch_aircraft_200(self, admin_client, aircraft):
        resp = admin_client.patch(
            f'/api/aircraft/{aircraft.id}/',
            {'tail_number': 'NADMIN'},
            format='json',
        )
        assert resp.status_code == 200

    def test_delete_aircraft_204(self, admin_client, aircraft):
        resp = admin_client.delete(f'/api/aircraft/{aircraft.id}/')
        assert resp.status_code == 204

    def test_get_manage_roles_200(self, admin_client, aircraft):
        resp = admin_client.get(f'/api/aircraft/{aircraft.id}/manage_roles/')
        assert resp.status_code == 200

    def test_get_share_tokens_200(self, admin_client, aircraft):
        resp = admin_client.get(f'/api/aircraft/{aircraft.id}/share_tokens/')
        assert resp.status_code == 200

    def test_update_hours_200(self, admin_client, aircraft):
        new_tach = float(aircraft.tach_time) + 5.0
        resp = admin_client.post(
            f'/api/aircraft/{aircraft.id}/update_hours/',
            {'new_tach_time': new_tach},
            format='json',
        )
        assert resp.status_code == 200

    def test_summary_200(self, admin_client, aircraft):
        resp = admin_client.get(f'/api/aircraft/{aircraft.id}/summary/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestRbacEdgeCases:
    """Additional edge-case RBAC checks."""

    def test_pilot_can_get_oil_records_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/oil_records/')
        assert resp.status_code == 200

    def test_pilot_can_get_fuel_records_200(self, pilot_client, aircraft_with_pilot):
        resp = pilot_client.get(f'/api/aircraft/{aircraft_with_pilot.id}/fuel_records/')
        assert resp.status_code == 200

    def test_owner_can_delete_aircraft_204(self, owner_client, aircraft):
        resp = owner_client.delete(f'/api/aircraft/{aircraft.id}/')
        assert resp.status_code == 204

    def test_pilot_list_only_sees_own_aircraft(self, pilot_client, aircraft_with_pilot, owner_user):
        """Pilot can only see aircraft they have a role on."""
        # Create a second aircraft that the pilot has NO role on
        from core.models import Aircraft
        other_ac = Aircraft.objects.create(tail_number='NOTHER', make='Piper', model='PA-28')
        AircraftRole.objects.create(aircraft=other_ac, user=owner_user, role='owner')

        resp = pilot_client.get('/api/aircraft/')
        assert resp.status_code == 200
        ids = [item['id'] for item in resp.data]
        assert str(aircraft_with_pilot.id) in ids
        assert str(other_ac.id) not in ids
