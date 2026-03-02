import datetime
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import (
    Aircraft,
    AircraftEvent,
    AircraftNote,
    AircraftRole,
    AircraftShareToken,
    InvitationCode,
    InvitationCodeAircraftRole,
    InvitationCodeRedemption,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Aircraft
# ---------------------------------------------------------------------------

class TestAircraft:
    def test_uuid_pk_generated(self):
        ac = Aircraft.objects.create(tail_number='N00001', make='Piper', model='Cherokee')
        assert ac.id is not None
        assert isinstance(ac.id, uuid.UUID)

    def test_uuid_pk_unique_per_instance(self):
        ac1 = Aircraft.objects.create(tail_number='N00001')
        ac2 = Aircraft.objects.create(tail_number='N00002')
        assert ac1.id != ac2.id

    def test_str_format(self):
        ac = Aircraft.objects.create(tail_number='N12345', make='Cessna', model='172')
        assert str(ac) == 'N12345 - Cessna 172'

    def test_str_with_empty_make_model(self):
        ac = Aircraft.objects.create(tail_number='N99999')
        assert str(ac) == 'N99999 -  '

    def test_status_default_available(self):
        ac = Aircraft.objects.create(tail_number='N00003')
        assert ac.status == 'AVAILABLE'

    def test_tach_time_decimal_default(self):
        ac = Aircraft.objects.create(tail_number='N00004')
        assert float(ac.tach_time) == 0.0

    def test_hobbs_time_decimal_default(self):
        ac = Aircraft.objects.create(tail_number='N00005')
        assert float(ac.hobbs_time) == 0.0

    def test_tach_time_offset_decimal_default(self):
        ac = Aircraft.objects.create(tail_number='N00006')
        assert float(ac.tach_time_offset) == 0.0

    def test_hobbs_time_offset_decimal_default(self):
        ac = Aircraft.objects.create(tail_number='N00007')
        assert float(ac.hobbs_time_offset) == 0.0

    def test_status_choices_mx(self):
        ac = Aircraft.objects.create(tail_number='N00008', status='MX')
        ac.refresh_from_db()
        assert ac.status == 'MX'

    def test_status_choices_ground(self):
        ac = Aircraft.objects.create(tail_number='N00009', status='GROUND')
        ac.refresh_from_db()
        assert ac.status == 'GROUND'


# ---------------------------------------------------------------------------
# AircraftNote
# ---------------------------------------------------------------------------

class TestAircraftNote:
    def test_public_default_false(self, aircraft):
        note = AircraftNote.objects.create(aircraft=aircraft, text='Test note')
        assert note.public is False

    def test_added_by_nullable(self, aircraft):
        note = AircraftNote.objects.create(aircraft=aircraft, text='Anonymous note', added_by=None)
        assert note.added_by is None

    def test_added_by_set_null_on_user_delete(self, aircraft):
        user = User.objects.create_user(username='deleteme', password='pw')
        note = AircraftNote.objects.create(aircraft=aircraft, text='User note', added_by=user)
        user.delete()
        note.refresh_from_db()
        assert note.added_by is None

    def test_str(self, aircraft):
        note = AircraftNote.objects.create(aircraft=aircraft, text='Brake squeak')
        assert str(note) == 'N12345 - Brake squeak'

    def test_cascade_delete_with_aircraft(self, owner_user):
        ac = Aircraft.objects.create(tail_number='N55555', make='Beech', model='Bonanza')
        AircraftNote.objects.create(aircraft=ac, text='Will be deleted')
        note_id = AircraftNote.objects.filter(aircraft=ac).first().id
        ac.delete()
        assert not AircraftNote.objects.filter(id=note_id).exists()

    def test_uuid_pk_generated(self, aircraft):
        note = AircraftNote.objects.create(aircraft=aircraft, text='UUID test')
        assert isinstance(note.id, uuid.UUID)


# ---------------------------------------------------------------------------
# AircraftEvent
# ---------------------------------------------------------------------------

class TestAircraftEvent:
    def test_ordering_newest_first(self, aircraft):
        e1 = AircraftEvent.objects.create(
            aircraft=aircraft,
            category='hours',
            event_name='Hours updated',
        )
        e2 = AircraftEvent.objects.create(
            aircraft=aircraft,
            category='squawk',
            event_name='Squawk filed',
        )
        events = list(AircraftEvent.objects.filter(aircraft=aircraft))
        # newest first: e2 was created after e1
        assert events[0].id == e2.id
        assert events[1].id == e1.id

    def test_category_choices_all_valid(self, aircraft):
        categories = [
            'hours', 'flight', 'component', 'squawk', 'note', 'oil', 'fuel',
            'logbook', 'ad', 'inspection', 'document', 'aircraft', 'role',
            'major_record',
        ]
        for cat in categories:
            e = AircraftEvent.objects.create(
                aircraft=aircraft, category=cat, event_name=f'{cat} event'
            )
            assert e.category == cat

    def test_str(self, aircraft):
        event = AircraftEvent.objects.create(
            aircraft=aircraft,
            category='hours',
            event_name='Hours updated',
        )
        assert str(event) == 'N12345 - Hours updated'

    def test_uuid_pk_generated(self, aircraft):
        event = AircraftEvent.objects.create(
            aircraft=aircraft, category='note', event_name='Note created'
        )
        assert isinstance(event.id, uuid.UUID)

    def test_user_nullable(self, aircraft):
        event = AircraftEvent.objects.create(
            aircraft=aircraft, category='aircraft', event_name='System event', user=None
        )
        assert event.user is None


# ---------------------------------------------------------------------------
# AircraftRole
# ---------------------------------------------------------------------------

class TestAircraftRole:
    def test_role_owner(self, aircraft, other_user):
        role = AircraftRole.objects.create(aircraft=aircraft, user=other_user, role='owner')
        assert role.role == 'owner'

    def test_role_pilot(self, aircraft, pilot_user):
        role = AircraftRole.objects.create(aircraft=aircraft, user=pilot_user, role='pilot')
        assert role.role == 'pilot'

    def test_unique_together_aircraft_user_raises(self, aircraft, owner_user):
        # owner_user already has a role on aircraft (created in the aircraft fixture)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AircraftRole.objects.create(aircraft=aircraft, user=owner_user, role='pilot')

    def test_str(self, aircraft, pilot_user):
        role = AircraftRole.objects.create(aircraft=aircraft, user=pilot_user, role='pilot')
        assert 'pilot' in str(role)
        assert aircraft.tail_number in str(role)
        assert str(pilot_user) in str(role)

    def test_uuid_pk_generated(self, aircraft, other_user):
        role = AircraftRole.objects.create(aircraft=aircraft, user=other_user, role='pilot')
        assert isinstance(role.id, uuid.UUID)


# ---------------------------------------------------------------------------
# AircraftShareToken
# ---------------------------------------------------------------------------

class TestAircraftShareToken:
    def test_uuid_token_auto_generated(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='status'
        )
        assert token.token is not None
        assert isinstance(token.token, uuid.UUID)

    def test_token_different_from_id(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='status'
        )
        assert token.token != token.id

    def test_privilege_status(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='status'
        )
        assert token.privilege == 'status'

    def test_privilege_maintenance(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='maintenance'
        )
        assert token.privilege == 'maintenance'

    def test_str_with_label(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, label='Club members', privilege='status'
        )
        assert 'N12345' in str(token)
        assert 'Club members' in str(token)

    def test_str_without_label_uses_privilege(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='maintenance'
        )
        assert 'N12345' in str(token)
        assert 'maintenance' in str(token)

    def test_uuid_pk_generated(self, aircraft, owner_user):
        token = AircraftShareToken.objects.create(
            aircraft=aircraft, created_by=owner_user, privilege='status'
        )
        assert isinstance(token.id, uuid.UUID)


# ---------------------------------------------------------------------------
# InvitationCode
# ---------------------------------------------------------------------------

class TestInvitationCode:
    def _make_code(self, **kwargs):
        defaults = dict(label='Test Invite', is_active=True)
        defaults.update(kwargs)
        return InvitationCode.objects.create(**defaults)

    def test_is_valid_active_not_expired_under_max(self):
        code = self._make_code(
            max_uses=5,
            use_count=0,
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        # manually set use_count (editable=False prevents direct .create, use update)
        InvitationCode.objects.filter(pk=code.pk).update(use_count=2)
        code.refresh_from_db()
        assert code.is_valid is True

    def test_is_valid_true_unlimited_uses(self):
        code = self._make_code(max_uses=None)
        assert code.is_valid is True

    def test_is_valid_false_when_inactive(self):
        code = self._make_code(is_active=False)
        assert code.is_valid is False

    def test_is_valid_false_when_expired(self):
        code = self._make_code(
            expires_at=timezone.now() - datetime.timedelta(seconds=1),
        )
        assert code.is_valid is False

    def test_is_valid_false_when_use_count_equals_max(self):
        code = self._make_code(max_uses=3)
        InvitationCode.objects.filter(pk=code.pk).update(use_count=3)
        code.refresh_from_db()
        assert code.is_valid is False

    def test_is_valid_false_when_use_count_exceeds_max(self):
        code = self._make_code(max_uses=3)
        InvitationCode.objects.filter(pk=code.pk).update(use_count=5)
        code.refresh_from_db()
        assert code.is_valid is False

    def test_str(self):
        code = self._make_code(label='Spring 2026 Pilots')
        assert str(code) == 'Spring 2026 Pilots'

    def test_uuid_pk_generated(self):
        code = self._make_code()
        assert isinstance(code.id, uuid.UUID)

    def test_token_auto_generated_as_uuid(self):
        code = self._make_code()
        assert isinstance(code.token, uuid.UUID)


# ---------------------------------------------------------------------------
# InvitationCodeAircraftRole
# ---------------------------------------------------------------------------

class TestInvitationCodeAircraftRole:
    def test_create(self, aircraft):
        code = InvitationCode.objects.create(label='Club code')
        icar = InvitationCodeAircraftRole.objects.create(
            invitation_code=code, aircraft=aircraft, role='pilot'
        )
        assert icar.role == 'pilot'

    def test_unique_together_raises(self, aircraft):
        code = InvitationCode.objects.create(label='Dup test')
        InvitationCodeAircraftRole.objects.create(
            invitation_code=code, aircraft=aircraft, role='pilot'
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InvitationCodeAircraftRole.objects.create(
                    invitation_code=code, aircraft=aircraft, role='owner'
                )

    def test_str(self, aircraft):
        code = InvitationCode.objects.create(label='My Club')
        icar = InvitationCodeAircraftRole.objects.create(
            invitation_code=code, aircraft=aircraft, role='pilot'
        )
        assert 'My Club' in str(icar)
        assert 'pilot' in str(icar)
        assert aircraft.tail_number in str(icar)

    def test_uuid_pk_generated(self, aircraft):
        code = InvitationCode.objects.create(label='UUID test')
        icar = InvitationCodeAircraftRole.objects.create(
            invitation_code=code, aircraft=aircraft, role='owner'
        )
        assert isinstance(icar.id, uuid.UUID)


# ---------------------------------------------------------------------------
# InvitationCodeRedemption
# ---------------------------------------------------------------------------

class TestInvitationCodeRedemption:
    def test_create_with_code_and_user(self, other_user):
        code = InvitationCode.objects.create(label='Redemption test')
        redemption = InvitationCodeRedemption.objects.create(code=code, user=other_user)
        assert redemption.code == code
        assert redemption.user == other_user

    def test_uuid_pk_generated(self, other_user):
        code = InvitationCode.objects.create(label='UUID redemption')
        redemption = InvitationCodeRedemption.objects.create(code=code, user=other_user)
        assert isinstance(redemption.id, uuid.UUID)

    def test_str(self, other_user):
        code = InvitationCode.objects.create(label='Welcome code')
        redemption = InvitationCodeRedemption.objects.create(code=code, user=other_user)
        assert str(other_user) in str(redemption)
        assert 'Welcome code' in str(redemption)

    def test_unique_together_code_user_raises(self, other_user):
        code = InvitationCode.objects.create(label='Once only')
        InvitationCodeRedemption.objects.create(code=code, user=other_user)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InvitationCodeRedemption.objects.create(code=code, user=other_user)
