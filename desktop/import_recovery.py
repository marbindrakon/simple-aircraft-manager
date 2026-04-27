"""Recover from interrupted imports on launcher startup.

The existing logbook/oil-analysis import path spawns daemon threads that get
killed when the parent process exits. On the desktop, that happens whenever
the user quits via the tray (or kills the app from Task Manager). Any
ImportJob row left in the 'running' state is necessarily orphaned by the
time the next launcher starts, because daemon threads from a previous
process are guaranteed dead.

This module marks all such rows as 'failed' with a note in their events
list so the user sees a sensible status in the UI rather than a permanent
spinner.
"""

from __future__ import annotations

import datetime as _dt
import logging

from health.models import ImportJob

LOG = logging.getLogger(__name__)


def mark_orphan_running_jobs_failed() -> int:
    """Flip every ImportJob with status='running' to 'failed', append an
    explanatory event, and return the number of rows updated.
    """
    orphans = list(ImportJob.objects.filter(status="running"))
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat()

    for job in orphans:
        events = list(job.events) if job.events else []
        events.append({
            "ts": timestamp,
            "level": "error",
            "message": "Interrupted by app shutdown",
        })
        job.events = events
        job.status = "failed"
        job.save(update_fields=["events", "status", "updated_at"])
        LOG.info("Marked orphan ImportJob %s as failed", job.id)

    return len(orphans)
