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


def test_required_mode_consumes_bootstrap_json_and_creates_superuser(fake_user_data_dir):
    paths.bootstrap_json_path().write_text(json.dumps({
        "username": "owner",
        "password": "correct horse battery staple",
    }))

    bootstrap.ensure_initial_user(auth_mode="required")

    user = User.objects.get(username="owner")
    assert user.is_superuser
    assert user.is_staff
    assert user.check_password("correct horse battery staple")
    assert not paths.bootstrap_json_path().exists()


def test_required_mode_without_bootstrap_json_is_noop(fake_user_data_dir):
    bootstrap.ensure_initial_user(auth_mode="required")

    assert User.objects.count() == 0
    assert not paths.desktop_user_path().exists()


def test_required_mode_skips_creation_if_user_already_exists(fake_user_data_dir):
    User.objects.create_superuser(username="owner", email="", password="prior")
    paths.bootstrap_json_path().write_text(json.dumps({
        "username": "owner",
        "password": "should-not-overwrite",
    }))

    bootstrap.ensure_initial_user(auth_mode="required")

    user = User.objects.get(username="owner")
    assert user.check_password("prior")  # password preserved
    assert not paths.bootstrap_json_path().exists()  # bootstrap still consumed


def test_malformed_bootstrap_json_raises(fake_user_data_dir):
    paths.bootstrap_json_path().write_text("{not valid json")

    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.ensure_initial_user(auth_mode="required")


def test_required_mode_rejects_short_password(fake_user_data_dir):
    paths.bootstrap_json_path().write_text(json.dumps({
        "username": "owner",
        "password": "short",  # < 8 chars
    }))

    with pytest.raises(bootstrap.BootstrapError, match="password"):
        bootstrap.ensure_initial_user(auth_mode="required")


def test_required_mode_rejects_short_username(fake_user_data_dir):
    paths.bootstrap_json_path().write_text(json.dumps({
        "username": "ab",  # < 3 chars
        "password": "longenough",
    }))

    with pytest.raises(bootstrap.BootstrapError, match="username"):
        bootstrap.ensure_initial_user(auth_mode="required")


def test_unknown_auth_mode_raises(fake_user_data_dir):
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.ensure_initial_user(auth_mode="bogus")
