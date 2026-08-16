"""URL routes for the desktop launcher.

Mounted under ``/desktop/`` by the project's plugin URL discovery loop
(in ``simple_aircraft_manager/urls.py``) when ``DesktopConfig.url_prefix``
returns ``"desktop"`` — which it does only when ``settings.SAM_DESKTOP``
is true. In dev and prod the loop skips this module entirely.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.urls import path, re_path
from django.views.static import serve as _static_serve

from desktop.setup_view import DesktopSetupView, setup_status


@login_required
def _desktop_media(request, path):  # noqa: F811 — `path` is a route param name
    from django.conf import settings
    return _static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("setup/", DesktopSetupView.as_view(), name="desktop-setup"),
    path("setup/status/", setup_status, name="desktop-setup-status"),
    re_path(r"^media/(?P<path>.*)$", _desktop_media, name="desktop-media"),
]
