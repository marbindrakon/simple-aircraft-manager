"""Auto-login middleware for desktop no-auth mode.

Reads desktop_user.json once per process, caches the User instance, and
attaches it to every incoming request.user. CSRF and other middleware run
normally; this only short-circuits the "who is the user" question.

Only active when SAM_DESKTOP_AUTH_MODE=disabled, which is enforced at
settings_desktop.py middleware-list construction time. If activated in any
other mode it remains a no-op as long as desktop_user.json is absent.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth import get_user_model

from desktop import paths

LOG = logging.getLogger(__name__)


class DesktopAutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._cached_user = None
        self._cache_attempted = False

    def __call__(self, request):
        user = self._get_user()
        if user is not None:
            request.user = user
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
