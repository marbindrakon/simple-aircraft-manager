import io
import logging
import os
import shutil
import uuid
from datetime import date

from django.apps import apps
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.views import View

from core.events import log_event
from core.export import export_aircraft_zip
from core.import_export import run_aircraft_import_job, validate_archive_quick
from core.models import Aircraft
from core.permissions import has_aircraft_permission, user_can_create_aircraft
from health.dispatch import dispatch_import
from health.models import ImportJob

logger = logging.getLogger(__name__)

class ExportView(LoginRequiredMixin, View):
    """
    GET /api/aircraft/{pk}/export/
    Streams a .sam.zip archive for the given aircraft.
    Only the aircraft owner or admin may export.
    """

    def get(self, request, pk):
        try:
            aircraft = Aircraft.objects.get(pk=pk)
        except (Aircraft.DoesNotExist, ValueError):
            raise Http404

        if not has_aircraft_permission(request.user, aircraft, 'owner'):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        filename = f"{aircraft.tail_number}_{date.today().strftime('%Y%m%d')}.sam.zip"

        # Build the ZIP into a BytesIO buffer and stream it
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)

        log_event(aircraft=aircraft, category='aircraft', event_name='Aircraft exported', user=request.user)

        response = StreamingHttpResponse(
            buf,
            content_type='application/zip',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ImportView(LoginRequiredMixin, View):
    """
    POST /api/aircraft/import/
    Stage the uploaded archive and start a background import job.
    Returns 202 with {"job_id": "..."} on acceptance.
    Returns 400 on validation failure.
    Returns 403 if the user is not permitted to create aircraft.
    Returns 409 on tail-number conflict with {"error": "tail_number_conflict", ...}.
    """

    def post(self, request):
        if not user_can_create_aircraft(request.user):
            return JsonResponse({'error': 'You do not have permission to import aircraft.'}, status=403)

        max_size = getattr(settings, 'IMPORT_MAX_ARCHIVE_SIZE', 10 * 1024 * 1024 * 1024)
        staging_dir = getattr(settings, 'IMPORT_STAGING_DIR', os.path.join(settings.BASE_DIR, 'import_staging'))
        os.makedirs(staging_dir, exist_ok=True)

        staged_id = request.POST.get('staged_id', '').strip()
        tail_number_override = request.POST.get('tail_number', '').strip() or None

        # Determine ZIP path — either from a previously staged file or a new upload
        if staged_id:
            # Retry path: archive was already staged
            try:
                uuid.UUID(staged_id)
            except ValueError:
                return JsonResponse({'error': 'Invalid staged_id.'}, status=400)
            
            # Normalize and verify zip_path
            raw_zip_path = os.path.join(staging_dir, f"{staged_id}.zip")
            zip_path = os.path.normpath(raw_zip_path)
            if not zip_path.startswith(os.path.abspath(staging_dir)):
                return JsonResponse({'error': 'Invalid staged archive path.'}, status=400)
                
            if not os.path.exists(zip_path):
                return JsonResponse({'error': 'Staged archive not found. Please re-upload the file.'}, status=400)
        else:
            archive_file = request.FILES.get('archive')
            if not archive_file:
                return JsonResponse({'error': 'No archive file provided.'}, status=400)

            # Size check
            if archive_file.size > max_size:
                return JsonResponse(
                    {'error': f"Archive exceeds the {max_size // (1024 ** 3)} GiB size limit."},
                    status=400,
                )

            # Pre-flight disk space check: need at least 2× archive size free
            try:
                free = shutil.disk_usage(staging_dir).free
                if free < 2 * archive_file.size:
                    return JsonResponse(
                        {'error': 'Insufficient disk space to stage the archive.'},
                        status=400,
                    )
            except OSError:
                pass  # Can't check; proceed anyway

            new_staged_id = str(uuid.uuid4())
            raw_zip_path = os.path.join(staging_dir, f"{new_staged_id}.zip")
            zip_path = os.path.normpath(raw_zip_path)
            if not zip_path.startswith(os.path.abspath(staging_dir)):
                # This should not happen since new_staged_id is a UUID
                return JsonResponse({'error': 'Failed to determine a safe stage path.'}, status=500)
                
            try:
                with open(zip_path, 'wb') as fh:
                    for chunk in archive_file.chunks():
                        fh.write(chunk)
            except OSError as exc:
                logger.exception("Failed to stage import archive: %s", exc)
                return JsonResponse({'error': 'Failed to stage the archive. Please try again.'}, status=500)
            staged_id = new_staged_id

        # Quick synchronous validation
        manifest, effective_tail, error = validate_archive_quick(zip_path, tail_number_override)

        if error == 'CONFLICT':
            # Return 409 with staged_id so client can retry without re-uploading
            return JsonResponse({
                'error': 'tail_number_conflict',
                'tail_number': effective_tail,
                'staged_id': staged_id,
            }, status=409)

        if error:
            # Clean up staged file on hard validation failure
            try:
                os.remove(zip_path)
            except OSError:
                pass
            return JsonResponse({'error': error}, status=400)

        # Create the ImportJob and start background work
        job = ImportJob.objects.create(status='pending', user=request.user, job_type='aircraft')

        task = None
        if apps.is_installed('procrastinate.contrib.django'):
            from health.tasks import import_aircraft_task
            task = import_aircraft_task

        dispatch_import(
            task,
            run_aircraft_import_job,
            (str(job.id), zip_path, request.user),
            fallback_kwargs={'tail_number_override': tail_number_override},
            job_id=str(job.id),
            zip_path=zip_path,
            owner_user_id=request.user.id,
            tail_number_override=tail_number_override,
        )

        return JsonResponse({'job_id': str(job.id)}, status=202)


class ImportJobStatusView(LoginRequiredMixin, View):
    """
    GET /api/aircraft/import/{job_id}/
    Poll the status of an aircraft import job.
    Only the submitting user may poll.
    """

    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)

        # Only the submitting user (or admin) may view this job
        if not request.user.is_staff and not request.user.is_superuser:
            if job.user_id != request.user.pk:
                return JsonResponse({'error': 'Job not found'}, status=404)

        try:
            after = int(request.GET.get('after', 0))
        except (ValueError, TypeError):
            after = 0

        return JsonResponse({
            'status': job.status,
            'events': job.events[after:],
            'result': job.result,
        })

