import json

import pytest
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


def test_attaches_desktop_user_when_pointer_file_exists(fake_user_data_dir):
    user = _seed_desktop_user(fake_user_data_dir)

    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    def get_response(req):
        return req

    middleware = DesktopAutoLoginMiddleware(get_response)
    response = middleware(request)

    assert response.user.pk == user.pk
    assert response.user.is_authenticated


def test_falls_through_to_anonymous_when_pointer_file_missing(fake_user_data_dir):
    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    middleware = DesktopAutoLoginMiddleware(lambda r: r)
    response = middleware(request)

    assert isinstance(response.user, AnonymousUser)


def test_falls_through_when_pointer_file_references_missing_user(fake_user_data_dir):
    paths.desktop_user_path().write_text(json.dumps({"user_pk": 999999}))

    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    middleware = DesktopAutoLoginMiddleware(lambda r: r)
    response = middleware(request)

    assert isinstance(response.user, AnonymousUser)


def test_caches_user_lookup_across_requests(fake_user_data_dir, django_assert_num_queries):
    user = _seed_desktop_user(fake_user_data_dir)
    middleware = DesktopAutoLoginMiddleware(lambda r: r)

    rf = RequestFactory()

    # First request: one query for the user.
    req1 = rf.get("/")
    req1.user = AnonymousUser()
    with django_assert_num_queries(1):
        middleware(req1)

    # Second request: served from cache, zero queries.
    req2 = rf.get("/")
    req2.user = AnonymousUser()
    with django_assert_num_queries(0):
        middleware(req2)
