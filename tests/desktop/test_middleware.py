import json
from importlib import import_module

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from desktop import paths
from desktop.middleware import DesktopAutoLoginMiddleware

User = get_user_model()
pytestmark = pytest.mark.django_db


def _seed_desktop_user(fake_user_data_dir, *, username="desktop"):
    user = User.objects.create_user(username=username, password="x")
    paths.desktop_user_path().write_text(json.dumps({"user_pk": user.pk}))
    return user


def _make_request(rf=None):
    """RequestFactory request with a real session attached.

    DesktopAutoLoginMiddleware calls django.contrib.auth.login() when it
    finds a desktop user; login() writes to request.session, so requests
    that exercise that path must have a SessionStore attached."""
    rf = rf or RequestFactory()
    request = rf.get("/")
    request.user = AnonymousUser()
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore()
    return request


def test_attaches_desktop_user_when_pointer_file_exists(fake_user_data_dir):
    user = _seed_desktop_user(fake_user_data_dir)

    request = _make_request()

    def get_response(req):
        return req

    middleware = DesktopAutoLoginMiddleware(get_response)
    response = middleware(request)

    assert response.user.pk == user.pk
    assert response.user.is_authenticated


def test_falls_through_to_anonymous_when_pointer_file_missing(fake_user_data_dir):
    request = _make_request()

    middleware = DesktopAutoLoginMiddleware(lambda r: r)
    response = middleware(request)

    assert isinstance(response.user, AnonymousUser)


def test_falls_through_when_pointer_file_references_missing_user(fake_user_data_dir):
    paths.desktop_user_path().write_text(json.dumps({"user_pk": 999999}))

    request = _make_request()

    middleware = DesktopAutoLoginMiddleware(lambda r: r)
    response = middleware(request)

    assert isinstance(response.user, AnonymousUser)


def test_caches_user_lookup_across_requests(fake_user_data_dir):
    """The desktop user pointer file is read once per process; subsequent
    calls to _get_user() return the cached User instance without re-reading
    the file or re-querying the database."""
    user = _seed_desktop_user(fake_user_data_dir)
    middleware = DesktopAutoLoginMiddleware(lambda r: r)

    first = middleware._get_user()
    assert first.pk == user.pk

    # Remove the pointer file and the user row: cache still serves the
    # original instance, proving neither is consulted on the second call.
    paths.desktop_user_path().unlink()
    User.objects.filter(pk=user.pk).delete()

    second = middleware._get_user()
    assert second is first
