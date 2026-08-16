"""Smoke tests for desktop URL routing.

The desktop URLs are picked up by the project's SAM-plugin URL discovery
loop (in ``simple_aircraft_manager/urls.py``) — gated by
``DesktopConfig.url_prefix``, which returns ``"desktop"`` only when
``settings.SAM_DESKTOP`` is true. These tests verify both the local
url_conf shape and the plugin-system gating.
"""

from __future__ import annotations

from unittest import mock


def test_desktop_urlpatterns_resolve_expected_names():
    from desktop import urls as desktop_urls

    names = {p.name for p in desktop_urls.urlpatterns if p.name}
    assert names == {"desktop-setup", "desktop-setup-status", "desktop-media"}


def test_desktop_media_view_requires_login():
    from desktop import urls as desktop_urls

    media = next(p for p in desktop_urls.urlpatterns if p.name == "desktop-media")
    # login_required attaches a wrapped view; the wrapper carries the original
    # callable on `__wrapped__` (functools.wraps) — its presence is the cheapest
    # way to confirm the decorator was applied.
    assert hasattr(media.callback, "__wrapped__")


def test_desktop_config_url_prefix_off_by_default(settings):
    """When SAM_DESKTOP is unset (dev/prod/test base settings), the plugin
    discovery loop sees ``url_prefix=None`` and skips registering the
    desktop URLs entirely."""
    from django.apps import apps

    cfg = apps.get_app_config("desktop")
    settings.SAM_DESKTOP = False
    assert cfg.url_prefix is None


def test_desktop_config_url_prefix_on_in_desktop_mode(settings):
    """When SAM_DESKTOP is true, the plugin loop mounts the desktop URLs
    under ``/desktop/``."""
    from django.apps import apps

    cfg = apps.get_app_config("desktop")
    settings.SAM_DESKTOP = True
    try:
        assert cfg.url_prefix == "desktop"
    finally:
        settings.SAM_DESKTOP = False
