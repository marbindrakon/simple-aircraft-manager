import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Aircraft, AircraftRole, AircraftShareToken
from health.models import AD, Component, ComponentType, InspectionType, LogbookEntry, Squawk

User = get_user_model()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin', password='pw', email='admin@test.com'
    )


@pytest.fixture
def owner_user(db):
    return User.objects.create_user(username='owner', password='pw')


@pytest.fixture
def pilot_user(db):
    return User.objects.create_user(username='pilot', password='pw')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username='other', password='pw')


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def owner_client(owner_user):
    client = APIClient()
    client.force_authenticate(user=owner_user)
    return client


@pytest.fixture
def pilot_client(pilot_user):
    client = APIClient()
    client.force_authenticate(user=pilot_user)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


# ---------------------------------------------------------------------------
# Aircraft
# ---------------------------------------------------------------------------

@pytest.fixture
def aircraft(owner_user):
    ac = Aircraft.objects.create(
        tail_number='N12345',
        make='Cessna',
        model='172',
        tach_time=100.0,
        hobbs_time=100.0,
    )
    AircraftRole.objects.create(aircraft=ac, user=owner_user, role='owner')
    return ac


@pytest.fixture
def aircraft_with_pilot(aircraft, pilot_user):
    AircraftRole.objects.create(aircraft=aircraft, user=pilot_user, role='pilot')
    return aircraft


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@pytest.fixture
def component_type(db):
    return ComponentType.objects.create(name='Engine')


@pytest.fixture
def component(aircraft, component_type):
    return Component.objects.create(
        aircraft=aircraft,
        component_type=component_type,
        status='IN-USE',
        date_in_service=datetime.date.today(),
        manufacturer='Lycoming',
        model='O-360',
    )


@pytest.fixture
def replacement_component(aircraft, component_type):
    return Component.objects.create(
        aircraft=aircraft,
        component_type=component_type,
        status='IN-USE',
        date_in_service=datetime.date.today(),
        manufacturer='Champion',
        model='Oil Filter',
        replacement_critical=True,
        replacement_hours=50.0,
    )


# ---------------------------------------------------------------------------
# Health reference data
# ---------------------------------------------------------------------------

@pytest.fixture
def inspection_type(aircraft):
    it = InspectionType.objects.create(
        name='Annual Inspection',
        recurring=True,
        required=True,
        recurring_months=12,
    )
    it.applicable_aircraft.add(aircraft)
    return it


@pytest.fixture
def ad(aircraft):
    a = AD.objects.create(
        name='AD 2020-01-01',
        short_description='Test AD',
        mandatory=True,
        compliance_type='standard',
    )
    a.applicable_aircraft.add(aircraft)
    return a


@pytest.fixture
def squawk(aircraft):
    return Squawk.objects.create(
        aircraft=aircraft,
        priority=1,
        issue_reported='Brake squeak',
    )


@pytest.fixture
def logbook_entry(aircraft):
    return LogbookEntry.objects.create(
        aircraft=aircraft,
        date=datetime.date.today(),
        log_type='AC',
        entry_type='MAINTENANCE',
        text='100-hour inspection completed',
    )


# ---------------------------------------------------------------------------
# Share tokens
# ---------------------------------------------------------------------------

@pytest.fixture
def share_token_status(aircraft, owner_user):
    return AircraftShareToken.objects.create(
        aircraft=aircraft,
        created_by=owner_user,
        label='Status share',
        privilege='status',
    )


@pytest.fixture
def share_token_maintenance(aircraft, owner_user):
    return AircraftShareToken.objects.create(
        aircraft=aircraft,
        created_by=owner_user,
        label='Maintenance share',
        privilege='maintenance',
    )
