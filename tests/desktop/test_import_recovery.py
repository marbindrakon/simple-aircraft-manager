import pytest

from desktop import import_recovery
from health.models import ImportJob

pytestmark = pytest.mark.django_db


def test_running_jobs_are_marked_failed_with_note():
    job = ImportJob.objects.create(status="running", events=[])

    count = import_recovery.mark_orphan_running_jobs_failed()

    assert count == 1
    job.refresh_from_db()
    assert job.status == "failed"
    assert any("interrupted by app shutdown" in str(e).lower() for e in job.events)


def test_pending_jobs_are_left_alone():
    job = ImportJob.objects.create(status="pending", events=[])

    import_recovery.mark_orphan_running_jobs_failed()

    job.refresh_from_db()
    assert job.status == "pending"


def test_completed_jobs_are_left_alone():
    job = ImportJob.objects.create(status="completed", events=[])

    import_recovery.mark_orphan_running_jobs_failed()

    job.refresh_from_db()
    assert job.status == "completed"


def test_returns_zero_when_no_orphans():
    assert import_recovery.mark_orphan_running_jobs_failed() == 0
