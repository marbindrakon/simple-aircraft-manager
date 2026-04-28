"""Tests for the cross-platform first-run desktop setup view."""

from __future__ import annotations

import json
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory

from desktop.setup_view import (
    DesktopSetupView,
    _apply_setup,
    _validate,
    setup_status,
)
from desktop import paths

pytestmark = pytest.mark.django_db


# ---------- pure-function validation ----------------------------------------


def test_validate_rejects_missing_auth_mode():
    errors = _validate(auth_mode="", username="alice", password="hunter22pwd", confirm="hunter22pwd")
    assert "auth_mode" in errors


def test_validate_rejects_unknown_auth_mode():
    errors = _validate(auth_mode="something", username="", password="", confirm="")
    assert "auth_mode" in errors


def test_validate_required_mode_rejects_short_username():
    errors = _validate(auth_mode="required", username="ab", password="hunter22pwd", confirm="hunter22pwd")
    assert "username" in errors


def test_validate_required_mode_rejects_short_password():
    errors = _validate(auth_mode="required", username="alice", password="short", confirm="short")
    assert "password" in errors


def test_validate_required_mode_rejects_password_mismatch():
    errors = _validate(auth_mode="required", username="alice", password="hunter22pwd", confirm="differentpwd")
    assert "confirm_password" in errors


def test_validate_required_mode_accepts_clean_input():
    errors = _validate(auth_mode="required", username="alice", password="hunter22pwd", confirm="hunter22pwd")
    assert errors == {}


def test_validate_disabled_mode_ignores_username_and_password():
    errors = _validate(auth_mode="disabled", username="", password="", confirm="")
    assert errors == {}


# ---------- _apply_setup side effects ---------------------------------------


def test_apply_setup_required_mode_creates_superuser_and_writes_config(fake_user_data_dir, monkeypatch):
    UserModel = get_user_model()
    monkeypatch.setattr("desktop.setup_view.keyring.set_password", lambda *a, **kw: None)

    _apply_setup(
        auth_mode="required",
        username="alice",
        password="hunter22pwd",
        api_key="",
    )

    user = UserModel.objects.get(username="alice")
    assert user.is_superuser is True
    assert user.check_password("hunter22pwd")

    cfg = paths.config_ini_path().read_text()
    assert "mode = required" in cfg


def test_apply_setup_disabled_mode_creates_desktop_user_and_pointer(fake_user_data_dir):
    UserModel = get_user_model()

    _apply_setup(auth_mode="disabled", username="", password="", api_key="")

    user = UserModel.objects.get(username="desktop")
    assert user.has_usable_password() is False
    assert paths.desktop_user_path().exists()
    pointer = json.loads(paths.desktop_user_path().read_text())
    assert pointer["user_pk"] == user.pk
    cfg = paths.config_ini_path().read_text()
    assert "mode = disabled" in cfg


def test_apply_setup_with_api_key_calls_keyring(fake_user_data_dir, monkeypatch):
    set_password = mock.MagicMock()
    monkeypatch.setattr("desktop.setup_view.keyring.set_password", set_password)

    _apply_setup(auth_mode="disabled", username="", password="", api_key="sk-ant-test")

    set_password.assert_called_once_with("SimpleAircraftManager", "anthropic_api_key", "sk-ant-test")


def test_apply_setup_keyring_failure_does_not_block_completion(fake_user_data_dir, monkeypatch):
    def explode(*a, **kw):
        raise RuntimeError("keychain locked")

    monkeypatch.setattr("desktop.setup_view.keyring.set_password", explode)

    _apply_setup(auth_mode="disabled", username="", password="", api_key="sk-ant-x")

    # Setup still completed — config.ini was written.
    assert paths.config_ini_path().exists()


def test_apply_setup_existing_superuser_is_left_alone(fake_user_data_dir, monkeypatch):
    UserModel = get_user_model()
    UserModel.objects.create_superuser(username="alice", email="", password="originalpwd")

    monkeypatch.setattr("desktop.setup_view.keyring.set_password", lambda *a, **kw: None)

    _apply_setup(auth_mode="required", username="alice", password="hunter22pwd", api_key="")

    # Pre-existing user's password is untouched.
    user = UserModel.objects.get(username="alice")
    assert user.check_password("originalpwd")
    assert not user.check_password("hunter22pwd")


# ---------- view-level integration ------------------------------------------


class _NoCsrfFactory(RequestFactory):
    """RequestFactory variant that disables CSRF enforcement and attaches an
    AnonymousUser so our context processors don't trip on missing session
    middleware. Equivalent to Django's APIClient(enforce_csrf_checks=False).
    """

    def generic(self, *args, **kwargs):
        request = super().generic(*args, **kwargs)
        request._dont_enforce_csrf_checks = True
        request.user = AnonymousUser()
        return request


@pytest.fixture
def request_factory():
    return _NoCsrfFactory()


def test_get_renders_setup_form_when_setup_active(fake_user_data_dir, request_factory):
    request = request_factory.get("/desktop/setup/")
    response = DesktopSetupView.as_view()(request)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Authentication" in body
    assert "name=\"auth_mode\"" in body


def test_get_returns_404_after_setup_completed(fake_user_data_dir, request_factory):
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    request = request_factory.get("/desktop/setup/")

    with pytest.raises(Http404):
        DesktopSetupView.as_view()(request)


def test_post_disabled_mode_writes_config_and_renders_done_page(fake_user_data_dir, request_factory, monkeypatch):
    monkeypatch.setattr("desktop.setup_view.keyring.set_password", lambda *a, **kw: None)

    request = request_factory.post("/desktop/setup/", {"auth_mode": "disabled"})
    response = DesktopSetupView.as_view()(request)

    assert response.status_code == 200
    assert "Setup complete" in response.content.decode("utf-8")
    assert paths.config_ini_path().exists()
    assert "mode = disabled" in paths.config_ini_path().read_text()


def test_post_required_mode_creates_superuser(fake_user_data_dir, request_factory, monkeypatch):
    monkeypatch.setattr("desktop.setup_view.keyring.set_password", lambda *a, **kw: None)

    request = request_factory.post("/desktop/setup/", {
        "auth_mode": "required",
        "username": "alice",
        "password": "hunter22pwd",
        "confirm_password": "hunter22pwd",
        "api_key": "",
    })
    response = DesktopSetupView.as_view()(request)

    assert response.status_code == 200
    UserModel = get_user_model()
    assert UserModel.objects.filter(username="alice", is_superuser=True).exists()


def test_post_validation_errors_re_render_form_with_400(fake_user_data_dir, request_factory):
    request = request_factory.post("/desktop/setup/", {
        "auth_mode": "required",
        "username": "ab",  # too short
        "password": "short",  # too short
        "confirm_password": "short",
    })
    response = DesktopSetupView.as_view()(request)

    assert response.status_code == 400
    body = response.content.decode("utf-8")
    assert "Username must be at least 3 characters" in body
    # config.ini was NOT written
    assert not paths.config_ini_path().exists()


def test_post_apply_setup_failure_returns_500(fake_user_data_dir, request_factory, monkeypatch):
    def explode(**kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr("desktop.setup_view._apply_setup", explode)

    request = request_factory.post("/desktop/setup/", {"auth_mode": "disabled"})
    response = DesktopSetupView.as_view()(request)

    assert response.status_code == 500
    # config.ini wasn't written, so setup is still active.
    assert not paths.config_ini_path().exists()


def test_setup_status_endpoint_reports_completion(fake_user_data_dir, request_factory):
    request = request_factory.get("/desktop/setup/status/")
    response = setup_status(request)
    assert response.status_code == 200
    assert json.loads(response.content) == {"setup_complete": False}

    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    response = setup_status(request)
    assert json.loads(response.content) == {"setup_complete": True}


# ---------- redirect middleware --------------------------------------------


def test_redirect_middleware_sends_root_to_setup_when_config_missing(fake_user_data_dir, request_factory):
    from desktop.middleware import DesktopSetupRedirectMiddleware

    inner = mock.MagicMock(return_value="should-not-be-called")
    mw = DesktopSetupRedirectMiddleware(inner)
    request = request_factory.get("/dashboard/")

    response = mw(request)
    assert response.status_code == 302
    assert response.url == "/desktop/setup/"
    inner.assert_not_called()


def test_redirect_middleware_passes_through_setup_path(fake_user_data_dir, request_factory):
    from desktop.middleware import DesktopSetupRedirectMiddleware

    inner = mock.MagicMock(return_value="OK")
    mw = DesktopSetupRedirectMiddleware(inner)
    request = request_factory.get("/desktop/setup/")
    assert mw(request) == "OK"


def test_redirect_middleware_passes_through_static_and_healthz(fake_user_data_dir, request_factory):
    from desktop.middleware import DesktopSetupRedirectMiddleware

    inner = mock.MagicMock(return_value="OK")
    mw = DesktopSetupRedirectMiddleware(inner)

    for path in ("/static/css/app.css", "/healthz/"):
        inner.reset_mock()
        request = request_factory.get(path)
        assert mw(request) == "OK"
        inner.assert_called_once()


def test_redirect_middleware_passes_everything_through_after_setup(fake_user_data_dir, request_factory):
    from desktop.middleware import DesktopSetupRedirectMiddleware

    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    inner = mock.MagicMock(return_value="OK")
    mw = DesktopSetupRedirectMiddleware(inner)
    request = request_factory.get("/dashboard/")
    assert mw(request) == "OK"
