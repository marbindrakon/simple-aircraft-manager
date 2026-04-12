import os

from prometheus_client import Gauge

from django.conf import settings


sam_aircraft_count = Gauge(
    "sam_aircraft_count",
    "Current number of aircraft records",
)

sam_aircraft_quota = Gauge(
    "sam_aircraft_quota",
    "Configured aircraft quota (-1 if unlimited)",
)

sam_storage_used_bytes = Gauge(
    "sam_storage_used_bytes",
    "Total media storage used in bytes",
)

sam_storage_quota_bytes = Gauge(
    "sam_storage_quota_bytes",
    "Configured storage quota in bytes (-1 if unlimited)",
)


def _dir_size(path):
    """Calculate total size of a directory in bytes."""
    total = 0
    if not os.path.isdir(path):
        return 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def collect_metrics():
    """Update all custom gauges. Called by the metrics view."""
    from core.models import Aircraft

    sam_aircraft_count.set(Aircraft.objects.count())
    sam_aircraft_quota.set(
        settings.SAM_MAX_AIRCRAFT if settings.SAM_MAX_AIRCRAFT is not None else -1
    )

    media_root = getattr(settings, "MEDIA_ROOT", "")
    sam_storage_used_bytes.set(_dir_size(str(media_root)))
    sam_storage_quota_bytes.set(
        settings.SAM_STORAGE_QUOTA_GB * 1024 * 1024 * 1024
        if settings.SAM_STORAGE_QUOTA_GB is not None
        else -1
    )
