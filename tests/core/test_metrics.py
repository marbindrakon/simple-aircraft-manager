import pytest
from django.test import override_settings

from core.metrics import SAMCollector


@pytest.mark.django_db
def test_collector_reports_aircraft_count(aircraft_factory, user):
    """SAMCollector should yield sam_aircraft_count matching Aircraft.objects.count()."""
    aircraft_factory(owner=user)
    aircraft_factory(owner=user)
    metrics = {m.name: m for m in SAMCollector().collect()}
    assert metrics["sam_aircraft_count"].samples[0].value == 2.0


@pytest.mark.django_db
def test_collector_reports_configured_aircraft_quota():
    """sam_aircraft_quota should reflect SAM_MAX_AIRCRAFT when set."""
    with override_settings(SAM_MAX_AIRCRAFT=10):
        metrics = {m.name: m for m in SAMCollector().collect()}
        assert metrics["sam_aircraft_quota"].samples[0].value == 10.0


@pytest.mark.django_db
def test_collector_reports_unlimited_quota_as_negative_one():
    """sam_aircraft_quota should be -1.0 when SAM_MAX_AIRCRAFT is None."""
    with override_settings(SAM_MAX_AIRCRAFT=None):
        metrics = {m.name: m for m in SAMCollector().collect()}
        assert metrics["sam_aircraft_quota"].samples[0].value == -1.0


@pytest.mark.django_db
def test_collector_reports_configured_storage_quota():
    """sam_storage_quota_bytes should be SAM_STORAGE_QUOTA_GB converted to bytes."""
    with override_settings(SAM_STORAGE_QUOTA_GB=2):
        metrics = {m.name: m for m in SAMCollector().collect()}
        assert metrics["sam_storage_quota_bytes"].samples[0].value == 2 * 1024 * 1024 * 1024


@pytest.mark.django_db
def test_collector_reports_unlimited_storage_as_negative_one():
    """sam_storage_quota_bytes should be -1.0 when SAM_STORAGE_QUOTA_GB is None."""
    with override_settings(SAM_STORAGE_QUOTA_GB=None):
        metrics = {m.name: m for m in SAMCollector().collect()}
        assert metrics["sam_storage_quota_bytes"].samples[0].value == -1.0


@pytest.mark.django_db
def test_metrics_url_removed(client):
    """/metrics/ must not exist on the Django app — metrics are on port 8087."""
    response = client.get("/metrics/")
    assert response.status_code == 404
