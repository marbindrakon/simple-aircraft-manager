import pytest
from django.test import override_settings


@pytest.mark.django_db
def test_metrics_endpoint_returns_200(client):
    """Metrics endpoint should be accessible without authentication."""
    response = client.get("/metrics/")
    assert response.status_code == 200
    assert b"django_http_requests_total" in response.content


@pytest.mark.django_db
def test_metrics_includes_aircraft_count(client, user, aircraft_factory):
    """Custom aircraft count gauge should appear in metrics."""
    client.force_login(user)
    aircraft_factory(owner=user)
    aircraft_factory(owner=user)

    response = client.get("/metrics/")
    assert response.status_code == 200
    assert b"sam_aircraft_count" in response.content


@pytest.mark.django_db
def test_metrics_includes_quota_settings(client):
    """Quota gauge should reflect configured limits."""
    with override_settings(SAM_MAX_AIRCRAFT=10):
        response = client.get("/metrics/")
        assert b"sam_aircraft_quota" in response.content
        assert b"10.0" in response.content


@pytest.mark.django_db
def test_metrics_unlimited_quota_shows_negative_one(client):
    """When quota is not set, gauge should be -1."""
    with override_settings(SAM_MAX_AIRCRAFT=None):
        response = client.get("/metrics/")
        assert b"sam_aircraft_quota" in response.content
        assert b"-1.0" in response.content
