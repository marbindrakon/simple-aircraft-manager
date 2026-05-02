"""Auto-login + first-run-setup middleware for the desktop launcher.

Two pieces of middleware live here, both gated on conditions enforced at
settings_desktop.py middleware-list construction time:

- ``DesktopAutoLoginMiddleware`` — reads desktop_user.json once per
  process, caches the User instance, and attaches it to every incoming
  request.user. Only inserted when SAM_DESKTOP_AUTH_MODE=disabled.
- ``DesktopSetupRedirectMiddleware`` — when ``config.ini`` is missing
  (first-run state on macOS / freshly-zapped data dir), redirects every
  request that isn't already targeting ``/desktop/setup/`` to that page
  so the user lands on the setup form regardless of which URL they hit.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth import get_user_model, login as auth_login
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token

from desktop import paths

LOG = logging.getLogger(__name__)

SETUP_PATH = "/desktop/setup/"
# Paths the redirect middleware leaves alone while setup is incomplete:
# any /desktop/* route (the setup page itself, its status JSON, and the
# media route — though media will 404 for unauth users), healthz (so the
# launcher's wait_ready probe still works), and static assets the form needs.
_SETUP_ALLOWLIST_PREFIXES = (
    "/desktop/",
    "/healthz",
    "/static/",
)


class DesktopAutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._cached_user = None
        self._cache_attempted = False

    def __call__(self, request):
        user = self._get_user()
        if user is not None:
            if not request.user.is_authenticated:
                # First visit or session expired: call login() so the session
                # carries proper auth data (_auth_user_id, _auth_user_hash,
                # backend) and login() → rotate_token() seeds the CSRF cookie.
                # Guarded here so we pay the session-write cost only once per
                # session, not on every request.
                auth_login(request, user)
            request.user = user
            # Ensure the CSRF cookie is written even on subsequent requests
            # where the browser cookie may have been cleared independently.
            get_token(request)
        return self.get_response(request)

    def _get_user(self):
        if self._cache_attempted:
            return self._cached_user

        self._cache_attempted = True
        pointer_path = paths.desktop_user_path()
        if not pointer_path.exists():
            return None

        try:
            data = json.loads(pointer_path.read_text(encoding="utf-8"))
            pk = data["user_pk"]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            LOG.warning("desktop_user.json is malformed: %s", e)
            return None

        UserModel = get_user_model()
        try:
            self._cached_user = UserModel.objects.get(pk=pk)
        except UserModel.DoesNotExist:
            LOG.warning("desktop_user.json references missing user pk=%s", pk)
            self._cached_user = None
        return self._cached_user


class DesktopSetupRedirectMiddleware:
    """Redirect every request to the setup page until config.ini exists.

    The check runs on every request because setup completes mid-run: when
    the user submits the form we write config.ini, and immediately after
    that point we want this middleware to stop redirecting so the user
    lands on the success page rather than ping-ponging back.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._setup_needed() and not self._is_allowlisted(request.path):
            return HttpResponseRedirect(SETUP_PATH)
        return self.get_response(request)

    @staticmethod
    def _setup_needed() -> bool:
        return not paths.config_ini_path().exists()

    @staticmethod
    def _is_allowlisted(path: str) -> bool:
        return any(path.startswith(p) for p in _SETUP_ALLOWLIST_PREFIXES)
