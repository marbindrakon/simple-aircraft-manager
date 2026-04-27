"""First-run user setup for the desktop launcher.

Two modes:
- "disabled" (no-auth): create a single 'desktop' user (regular, not superuser)
  and write desktop_user.json so DesktopAutoLoginMiddleware can find it.
- "required": consume bootstrap.json (username + password from the installer
  wizard), create a SUPERUSER with those credentials, delete bootstrap.json.

Idempotent: running multiple times is safe. If the target user already exists
we leave it alone and only consume the bootstrap file if present.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth import get_user_model

from desktop import paths

LOG = logging.getLogger(__name__)

DESKTOP_USERNAME = "desktop"


class BootstrapError(RuntimeError):
    """Raised when bootstrap.json is malformed or auth_mode is unknown."""


def ensure_initial_user(auth_mode: str) -> None:
    if auth_mode == "disabled":
        _ensure_desktop_user()
    elif auth_mode == "required":
        _consume_bootstrap_json()
    else:
        raise BootstrapError(f"Unknown auth_mode {auth_mode!r}")


def _ensure_desktop_user() -> None:
    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        username=DESKTOP_USERNAME,
        defaults={"is_active": True},
    )
    if created:
        user.set_unusable_password()
        user.save()
        LOG.info("Created no-auth desktop user pk=%s", user.pk)

    pointer_path = paths.desktop_user_path()
    pointer_path.write_text(json.dumps({"user_pk": user.pk}), encoding="utf-8")


def _consume_bootstrap_json() -> None:
    bootstrap_path = paths.bootstrap_json_path()
    if not bootstrap_path.exists():
        return

    try:
        data = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        username = data["username"]
        password = data["password"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise BootstrapError(f"bootstrap.json is malformed: {e}") from e

    UserModel = get_user_model()
    if UserModel.objects.filter(username=username).exists():
        LOG.info("Bootstrap user %r already exists; consuming bootstrap.json without changes", username)
    else:
        UserModel.objects.create_superuser(username=username, email="", password=password)
        LOG.info("Created bootstrap superuser %r", username)

    try:
        bootstrap_path.unlink()
    except OSError as e:
        LOG.warning("Could not delete bootstrap.json after consumption: %s", e)
