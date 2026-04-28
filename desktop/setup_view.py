"""First-run configuration page for the desktop launcher.

When the launcher boots without a ``config.ini`` it serves these views in
"setup mode": the user picks an auth mode, optionally sets a username +
password, and optionally pastes an Anthropic API key. Submitting the form
writes ``config.ini`` to the user-data dir, creates the initial user (or
the no-auth ``desktop`` user), stores the API key in the OS keyring, and
prompts the user to restart the app.

These views are gated by:
1. The ``desktop`` app only being installed in ``settings_desktop`` —
   in dev/prod the URLs aren't registered and these views never load.
2. ``paths.config_ini_path()`` not existing — once setup has run, every
   subsequent GET/POST returns 404 so the page can't be reused to clobber
   credentials after the fact.

This is the cross-platform replacement for the Inno Setup wizard pages
that used to collect the same three pieces of data on Windows.
"""

from __future__ import annotations

import json
import logging

import keyring
from django.contrib.auth import get_user_model
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect

from desktop import paths
from desktop.bootstrap import DESKTOP_USERNAME
from desktop.config import KEYRING_SERVICE, KEYRING_USERNAME, VALID_AUTH_MODES

LOG = logging.getLogger(__name__)


def _ensure_setup_active() -> None:
    """Raise Http404 unless setup mode is genuinely active."""
    if paths.config_ini_path().exists():
        raise Http404("Setup has already been completed for this install.")


@method_decorator(csrf_protect, name="dispatch")
class DesktopSetupView(View):
    """Single-page setup form: auth mode + creds + optional API key."""

    template_name = "desktop_setup.html"

    def get(self, request, *args, **kwargs):
        _ensure_setup_active()
        return render(request, self.template_name, {"errors": {}, "values": {}})

    def post(self, request, *args, **kwargs):
        _ensure_setup_active()

        auth_mode = request.POST.get("auth_mode", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        api_key = request.POST.get("api_key", "").strip()

        errors = _validate(auth_mode, username, password, confirm)
        if errors:
            return render(
                request,
                self.template_name,
                {
                    "errors": errors,
                    "values": {"auth_mode": auth_mode, "username": username, "api_key": api_key},
                },
                status=400,
            )

        try:
            _apply_setup(auth_mode=auth_mode, username=username, password=password, api_key=api_key)
        except Exception:
            LOG.exception("Desktop setup failed")
            return render(
                request,
                self.template_name,
                {
                    "errors": {"form": "Could not save setup. Check the launcher log."},
                    "values": {"auth_mode": auth_mode, "username": username, "api_key": api_key},
                },
                status=500,
            )

        # Success page: tells the user to restart.
        return render(request, "desktop_setup_done.html", {})


def _validate(auth_mode: str, username: str, password: str, confirm: str) -> dict[str, str]:
    errors: dict[str, str] = {}

    if auth_mode not in VALID_AUTH_MODES:
        errors["auth_mode"] = "Choose an authentication mode."
        return errors

    if auth_mode == "required":
        if len(username) < 3:
            errors["username"] = "Username must be at least 3 characters."
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if password != confirm:
            errors["confirm_password"] = "Passwords do not match."

    return errors


def _apply_setup(*, auth_mode: str, username: str, password: str, api_key: str) -> None:
    """Persist the user's choices: write config.ini, create the initial
    user, and store the API key in the OS keyring. Order matters — config.ini
    is written LAST so a partial failure leaves setup mode active."""

    paths.ensure_dirs()

    UserModel = get_user_model()
    if auth_mode == "required":
        if not UserModel.objects.filter(username=username).exists():
            UserModel.objects.create_superuser(username=username, email="", password=password)
            LOG.info("Created bootstrap superuser %r via desktop setup", username)
    else:
        # No-auth mode: create the placeholder user the auto-login middleware
        # binds onto every request. Mirrors desktop.bootstrap._ensure_desktop_user.
        user, created = UserModel.objects.get_or_create(
            username=DESKTOP_USERNAME,
            defaults={"is_active": True},
        )
        if created:
            user.set_unusable_password()
            user.save()
        paths.desktop_user_path().write_text(
            json.dumps({"user_pk": user.pk}), encoding="utf-8",
        )

    if api_key:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
        except Exception as e:
            # Don't block setup completion if keyring isn't usable — the user
            # can re-add the key later via the OS credential manager.
            LOG.warning("Could not save API key to OS keystore: %s", e)

    config_path = paths.config_ini_path()
    config_path.write_text(f"[auth]\nmode = {auth_mode}\n", encoding="utf-8")


def setup_status(request):
    """Tiny JSON endpoint the success page can poll if desired."""
    return JsonResponse({"setup_complete": paths.config_ini_path().exists()})
