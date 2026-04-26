import logging
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from core.models import Aircraft, AircraftRole
from core.permissions import has_aircraft_permission
from health.dispatch import dispatch_import

logger = logging.getLogger(__name__)

class LogbookImportView(LoginRequiredMixin, View):
    """
    Web UI for importing scanned logbook pages.

    GET  /tools/import-logbook/                — render the form
    POST /tools/import-logbook/                — start a background import job
    GET  /tools/import-logbook/<job_id>/status/ — poll job progress
    """

    # Archive extensions we accept
    _ARCHIVE_SUFFIXES = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
    _IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}

    def get(self, request, job_id=None):
        if job_id:
            return self._job_status(request, job_id)
        # Only show aircraft the user owns (or all for admin)
        if request.user.is_staff or request.user.is_superuser:
            aircraft_list = Aircraft.objects.all().order_by('tail_number')
        else:
            owned_ids = AircraftRole.objects.filter(
                user=request.user, role='owner'
            ).values_list('aircraft_id', flat=True)
            aircraft_list = Aircraft.objects.filter(id__in=owned_ids).order_by('tail_number')
        import_models = settings.LOGBOOK_IMPORT_MODELS
        if not os.environ.get('ANTHROPIC_API_KEY'):
            import_models = [m for m in import_models if m.get('provider') != 'anthropic']
        if not getattr(settings, 'LITELLM_BASE_URL', ''):
            import_models = [m for m in import_models if m.get('provider') != 'litellm']
        default_model = settings.LOGBOOK_IMPORT_DEFAULT_MODEL
        available_ids = {m['id'] for m in import_models}
        if default_model not in available_ids:
            default_model = import_models[0]['id'] if import_models else ''
        return render(request, 'logbook_import.html', {
            'aircraft_list': aircraft_list,
            'import_models': import_models,
            'default_model': default_model,
            'ai_enabled': bool(import_models),
        })

    def post(self, request):
        tmpdir = None
        try:
            aircraft, error_response = self._resolve_aircraft(request)
            if error_response:
                return error_response

            opts = self._parse_options(request)

            append_doc_id = opts.get('append_to_document_id')
            if append_doc_id:
                from health.models import Document
                try:
                    Document.objects.get(pk=append_doc_id, aircraft=aircraft)
                except (Document.DoesNotExist, ValueError):
                    return JsonResponse(
                        {'type': 'error',
                         'message': 'Document not found or does not belong to this aircraft.'},
                        status=400,
                    )

            from health.models import ImportJob
            job = ImportJob(aircraft=aircraft, status='pending', job_type='logbook')

            staging_root = getattr(
                settings,
                'IMPORT_STAGING_DIR',
                os.path.join(settings.BASE_DIR, 'import_staging'),
            )
            tmpdir = os.path.join(staging_root, 'logbook_jobs', str(job.id))
            os.makedirs(tmpdir, exist_ok=True)

            image_paths, prep_error = self._prepare_images(request, tmpdir)
            if prep_error:
                return JsonResponse({'type': 'error', 'message': prep_error}, status=400)

            if not image_paths:
                return JsonResponse(
                    {'type': 'error', 'message': 'No supported image files found in upload.'},
                    status=400,
                )

            image_paths = [str(path.relative_to(Path(tmpdir))) for path in image_paths]
            job.save()

            # Hand tmpdir ownership to the background worker.
            _tmpdir = tmpdir
            from health.logbook_import import run_import_job

            kwargs = {
                'collection_name': opts['collection_name'],
                'doc_name': opts['doc_name'],
                'doc_type': opts['doc_type'],
                'model': opts['model'],
                'provider': opts['provider'],
                'upload_only': opts['upload_only'],
                'log_type_override': opts['log_type_override'] or None,
                'batch_size': opts['batch_size'],
                'append_to_document_id': append_doc_id,
            }
            task = None
            if apps.is_installed('procrastinate.contrib.django'):
                from health.tasks import import_logbook_task
                task = import_logbook_task

            dispatch_import(
                task,
                run_import_job,
                (str(job.id), _tmpdir, image_paths),
                fallback_kwargs=kwargs,
                job_id=str(job.id),
                tmpdir=_tmpdir,
                image_paths=image_paths,
                **kwargs,
            )
            tmpdir = None

            return JsonResponse({'job_id': str(job.id)})

        except Exception:
            logger.exception("Unhandled error in LogbookImportView.post")
            return JsonResponse({'type': 'error', 'message': 'An unexpected error occurred.'}, status=500)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    def _job_status(self, request, job_id):
        from health.models import ImportJob
        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)

        try:
            after = int(request.GET.get('after', 0))
        except (ValueError, TypeError):
            after = 0

        new_events = job.events[after:]

        return JsonResponse({
            'status': job.status,
            'events': new_events,
            'result': job.result,
        })

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_aircraft(self, request):
        aircraft_id = request.POST.get('aircraft')
        if not aircraft_id:
            return None, JsonResponse({'type': 'error', 'message': 'aircraft is required'}, status=400)
        try:
            aircraft = Aircraft.objects.get(pk=aircraft_id)
        except (Aircraft.DoesNotExist, ValueError):
            return None, JsonResponse({'type': 'error', 'message': 'Aircraft not found'}, status=404)
        if not has_aircraft_permission(request.user, aircraft, 'owner'):
            return None, JsonResponse({'type': 'error', 'message': 'Permission denied'}, status=403)
        return aircraft, None

    def _prepare_images(self, request, tmpdir: str):
        """
        Write uploaded files into tmpdir and return a sorted list of image Paths.
        Handles two upload modes:
          - file_mode='images': multiple image files in request.FILES.getlist('images')
          - file_mode='archive': single zip/tar in request.FILES['archive']
        """
        file_mode = request.POST.get('file_mode', 'images')

        if file_mode == 'archive':
            archive_file = request.FILES.get('archive')
            if not archive_file:
                return None, 'No archive file uploaded.'
            error = self._extract_archive(archive_file, tmpdir)
            if error:
                return None, error
        else:
            uploaded = request.FILES.getlist('images')
            if not uploaded:
                return None, 'No image files uploaded.'
            if len(uploaded) > self._MAX_IMAGE_COUNT:
                return None, (
                    f"Too many images uploaded ({len(uploaded)}). "
                    f"Maximum is {self._MAX_IMAGE_COUNT} per request."
                )
            for uf in uploaded:
                dest = Path(tmpdir) / uf.name
                with open(dest, 'wb') as fh:
                    for chunk in uf.chunks():
                        fh.write(chunk)

        image_paths = sorted(
            p for p in Path(tmpdir).rglob('*')
            if p.is_file() and p.suffix.lower() in self._IMAGE_SUFFIXES
        )
        return image_paths, None

    def _extract_archive(self, archive_file, tmpdir: str):
        """
        Extract a zip or tar archive into tmpdir.
        Returns an error string on failure, None on success.
        Guards against path-traversal (zip-slip) attacks.
        """
        name = archive_file.name.lower()

        # Write upload to a temp file so we can seek for format detection
        tmp_archive = os.path.join(tmpdir, '_upload_archive')
        with open(tmp_archive, 'wb') as fh:
            for chunk in archive_file.chunks():
                fh.write(chunk)

        real_tmpdir = os.path.realpath(tmpdir)

        if zipfile.is_zipfile(tmp_archive):
            try:
                with zipfile.ZipFile(tmp_archive) as zf:
                    members = [m for m in zf.infolist() if not m.filename.endswith('/')]
                    if len(members) > self._MAX_ARCHIVE_MEMBERS:
                        return (
                            f"Archive contains too many files ({len(members)}). "
                            f"Maximum is {self._MAX_ARCHIVE_MEMBERS}."
                        )
                    total_bytes = 0
                    for member in members:
                        total_bytes += member.file_size
                        if total_bytes > self._MAX_ARCHIVE_BYTES:
                            return (
                                f"Archive decompressed size exceeds the "
                                f"{self._MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit."
                            )
                        target = os.path.realpath(
                            os.path.join(real_tmpdir, member.filename)
                        )
                        if not target.startswith(real_tmpdir + os.sep):
                            continue  # skip path-traversal attempts
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with zf.open(member) as src, open(target, 'wb') as dst:
                            dst.write(src.read())
            except zipfile.BadZipFile as exc:
                return "Invalid ZIP file."
        elif tarfile.is_tarfile(tmp_archive):
            try:
                with tarfile.open(tmp_archive) as tf:
                    file_members = [m for m in tf.getmembers() if m.isfile()]
                    if len(file_members) > self._MAX_ARCHIVE_MEMBERS:
                        return (
                            f"Archive contains too many files ({len(file_members)}). "
                            f"Maximum is {self._MAX_ARCHIVE_MEMBERS}."
                        )
                    total_bytes = 0
                    for member in file_members:
                        total_bytes += member.size
                        if total_bytes > self._MAX_ARCHIVE_BYTES:
                            return (
                                f"Archive decompressed size exceeds the "
                                f"{self._MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit."
                            )
                        target = os.path.realpath(
                            os.path.join(real_tmpdir, member.name)
                        )
                        if not target.startswith(real_tmpdir + os.sep):
                            continue  # skip path-traversal attempts
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        src = tf.extractfile(member)
                        if src:
                            with open(target, 'wb') as dst:
                                dst.write(src.read())
            except tarfile.TarError as exc:
                return "Invalid archive file."
        else:
            return f"Unrecognised archive format for file: {archive_file.name}"

        os.remove(tmp_archive)
        return None

    _ALLOWED_BATCH_SIZE_MIN = 1
    _ALLOWED_BATCH_SIZE_MAX = 20

    # Max number of images accepted per request (images mode)
    _MAX_IMAGE_COUNT = 100
    # Max total decompressed bytes from an archive
    _MAX_ARCHIVE_BYTES = 2048 * 1024 * 1024  # 2048 MB
    # Max members in an archive
    _MAX_ARCHIVE_MEMBERS = 200

    @staticmethod
    def _parse_options(request):
        def _int(key, default):
            try:
                return int(request.POST.get(key, default))
            except (ValueError, TypeError):
                return default

        upload_only_raw = request.POST.get('upload_only', 'false')
        upload_only = upload_only_raw.lower() in ('true', '1', 'on', 'yes')

        collection_name = request.POST.get('collection_name', '').strip()
        doc_name = request.POST.get('doc_name', '').strip()

        # Fall back to a generic name if the client sent nothing
        if not collection_name:
            collection_name = 'Imported Logbook'
        if not doc_name:
            doc_name = collection_name

        # Validate model against settings registry
        model_registry = {m['id']: m for m in settings.LOGBOOK_IMPORT_MODELS}
        default_model = settings.LOGBOOK_IMPORT_DEFAULT_MODEL
        requested_model = request.POST.get('model', default_model)
        if requested_model not in model_registry:
            requested_model = default_model
        provider = model_registry.get(requested_model, {}).get('provider', 'anthropic')

        # Clamp batch_size to safe range server-side
        batch_size = max(
            LogbookImportView._ALLOWED_BATCH_SIZE_MIN,
            min(
                _int('batch_size', 10),
                LogbookImportView._ALLOWED_BATCH_SIZE_MAX,
            ),
        )

        return {
            'collection_name': collection_name,
            'doc_name': doc_name,
            'doc_type': request.POST.get('doc_type', 'LOG'),
            'model': requested_model,
            'provider': provider,
            'upload_only': upload_only,
            'log_type_override': request.POST.get('log_type_override', ''),
            'batch_size': batch_size,
            'append_to_document_id': request.POST.get('append_to_document_id', '').strip() or None,
        }
