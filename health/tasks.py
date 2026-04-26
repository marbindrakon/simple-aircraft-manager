from pathlib import Path

from django.contrib.auth import get_user_model
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app


NO_AUTOMATIC_RETRY = RetryStrategy(max_attempts=1)


@app.task(retry=NO_AUTOMATIC_RETRY)
def import_logbook_task(job_id, tmpdir, image_paths, **kwargs):
    from health.logbook_import import run_import_job

    run_import_job(job_id, tmpdir, image_paths, **kwargs)


@app.task(retry=NO_AUTOMATIC_RETRY)
def import_aircraft_task(job_id, zip_path, owner_user_id, tail_number_override=None):
    from core.import_export import run_aircraft_import_job

    owner_user = get_user_model().objects.get(pk=owner_user_id)
    run_aircraft_import_job(
        job_id,
        zip_path,
        owner_user,
        tail_number_override=tail_number_override,
    )


@app.task(retry=NO_AUTOMATIC_RETRY)
def import_oil_analysis_task(job_id, pdf_path):
    from health.oil_analysis_import import run_oil_analysis_job

    run_oil_analysis_job(job_id, Path(pdf_path))
