"""First-run user setup for the desktop launcher.

The actual choice of auth mode (and creation of the initial superuser, if
required) now happens in the in-app first-run setup form (see
``desktop/setup_view.py``). This module is what the launcher calls
on every subsequent startup to make sure the user records the launcher
expects are still present:

- ``"disabled"`` (no-auth): make sure the placeholder ``desktop`` user
  exists and ``desktop_user.json`` points at it. Idempotent — running
  multiple times is safe and a no-op after the first call.
- ``"required"``: nothing to do. The setup form already created the
  superuser by the time we have a config.ini saying ``mode = required``.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth import get_user_model

from desktop import paths

LOG = logging.getLogger(__name__)

DESKTOP_USERNAME = "desktop"


class BootstrapError(RuntimeError):
    """Raised when ``auth_mode`` is unknown."""


def ensure_initial_user(auth_mode: str) -> None:
    if auth_mode == "disabled":
        _ensure_desktop_user()
    elif auth_mode == "required":
        # Nothing to do — the in-app setup form created the superuser when
        # the user picked "Require login" and submitted the form.
        return
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
