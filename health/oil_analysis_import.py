"""
Oil analysis report extraction from PDF.

Public API:
    run_extraction(pdf_path) -> dict
        Extracts oil analysis data from a PDF using lab-specific parsers.
        Returns the raw extracted dict (not saved to DB). Raises ValueError on failure.

    run_oil_analysis_job(job_id, pdf_path)
        Background job runner. Fetches ImportJob by job_id, calls run_extraction,
        stores result or error, and cleans up the temp file. Called from a daemon thread.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def run_extraction(pdf_path: Path, **_kwargs) -> dict:
    """
    Extract oil analysis data from a PDF using deterministic lab-specific parsers.
    Supports Blackstone Laboratories and Aviation Laboratories (AvLab) report formats.

    Returns a dict conforming to the oil analysis report schema (samples: [...]).
    Does NOT save to DB. Raises ValueError on failure.

    Extra keyword arguments (model, provider) are accepted and ignored for
    backwards compatibility with callers that still pass them.
    """
    from health.oil_analysis_parsers import parse
    return parse(pdf_path)


def run_oil_analysis_job(job_id, pdf_path: Path, **_kwargs) -> None:
    """
    Background job runner for oil analysis PDF extraction.
    Called from a daemon thread — do NOT call synchronously in a request.

    job_id   — UUID of an ImportJob (status='pending')
    pdf_path — Path to the temp PDF file (deleted in finally block)

    Extra keyword arguments (model, provider) are accepted and ignored.
    """
    from health.models import ImportJob

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        log.error("ImportJob %s not found", job_id)
        return

    try:
        job.status = 'running'
        job.save(update_fields=['status'])

        result = run_extraction(pdf_path)

        job.result = result
        job.status = 'completed'
        job.save(update_fields=['result', 'status'])
    except Exception as exc:
        log.exception("Oil analysis job %s failed", job_id)
        error_event = {'type': 'error', 'message': str(exc)}
        ImportJob.objects.filter(pk=job.pk).update(
            events=ImportJob.objects.values_list('events', flat=True).get(pk=job.pk) + [error_event]
        )
        job.status = 'failed'
        job.save(update_fields=['status'])
    finally:
        pdf_path.unlink(missing_ok=True)
