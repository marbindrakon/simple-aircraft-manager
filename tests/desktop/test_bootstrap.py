"""Tests for the launcher's idempotent first-launch user setup.

The actual choice of auth mode + initial-superuser creation now lives in
``desktop/setup_view.py`` (covered by tests/desktop/test_setup_view.py).
This module is just the launcher's defensive 'make sure the placeholder
desktop user exists' helper for no-auth installs.
"""

import json

import pytest
from django.contrib.auth import get_user_model

from desktop import bootstrap, paths

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_no_auth_mode_creates_desktop_user_and_pointer(fake_user_data_dir):
    bootstrap.ensure_initial_user(auth_mode="disabled")

    user = User.objects.get(username="desktop")
    assert user.is_active
    assert not user.is_superuser

    pointer = json.loads(paths.desktop_user_path().read_text())
    assert pointer["user_pk"] == user.pk


def test_no_auth_mode_is_idempotent(fake_user_data_dir):
    bootstrap.ensure_initial_user(auth_mode="disabled")
    bootstrap.ensure_initial_user(auth_mode="disabled")

    assert User.objects.filter(username="desktop").count() == 1


def test_required_mode_is_a_noop(fake_user_data_dir):
    """The setup view created the superuser; the launcher has nothing more to
    do for required-auth installs. The pointer file is intentionally NOT
    written either — required-mode never uses it."""
    bootstrap.ensure_initial_user(auth_mode="required")

    assert User.objects.count() == 0
    assert not paths.desktop_user_path().exists()


def test_unknown_auth_mode_raises(fake_user_data_dir):
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.ensure_initial_user(auth_mode="bogus")
