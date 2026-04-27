import os

from django.conf import settings
from prometheus_client.metrics_core import GaugeMetricFamily
from prometheus_client.registry import Collector


def dir_size(path):
    """
    Calculate total size of a directory in bytes.
    Not used in hot paths — kept for ad-hoc debugging only.
    """
    total = 0
    if not os.path.isdir(path):
        return 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp) and not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total


def get_storage_used_bytes():
    """
    Return total uploaded file bytes by summing file_size across all models with
    file upload fields. Replaces dir_size() in hot paths — three DB aggregates,
    no filesystem scan.
    """
    from health.models import DocumentImage, FlightLog, Squawk
    from django.db.models import Sum
    return (
        (Squawk.objects.aggregate(t=Sum('file_size'))['t'] or 0)
        + (DocumentImage.objects.aggregate(t=Sum('file_size'))['t'] or 0)
        + (FlightLog.objects.aggregate(t=Sum('file_size'))['t'] or 0)
    )


class SAMCollector(Collector):
    """
    Prometheus collector that queries the DB on demand when scraped.
    Registered once in gunicorn.conf.py's on_starting hook and served on port 8087.
    """

    def collect(self):
        from core.models import Aircraft
        from django.contrib.auth import get_user_model

        yield GaugeMetricFamily(
            "sam_aircraft_count",
            "Current number of aircraft records",
            value=Aircraft.objects.count(),
        )
        yield GaugeMetricFamily(
            "sam_aircraft_quota",
            "Configured aircraft quota (-1 if unlimited)",
            value=settings.SAM_MAX_AIRCRAFT if settings.SAM_MAX_AIRCRAFT is not None else -1,
        )
        yield GaugeMetricFamily(
            "sam_storage_used_bytes",
            "Total media storage used in bytes",
            value=get_storage_used_bytes(),
        )
        yield GaugeMetricFamily(
            "sam_storage_quota_bytes",
            "Configured storage quota in bytes (-1 if unlimited)",
            value=(
                settings.SAM_STORAGE_QUOTA_GB * 1024 * 1024 * 1024
                if settings.SAM_STORAGE_QUOTA_GB is not None
                else -1
            ),
        )
        yield GaugeMetricFamily(
            "sam_member_count",
            "Number of active users in this SAM instance.",
            value=get_user_model().objects.filter(is_active=True).count(),
        )
