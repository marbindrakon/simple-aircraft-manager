"""
Aircraft archive import — validation, record creation, background runner.

Public API:
    validate_archive_quick(zip_path, tail_number_override=None)
        → (manifest, effective_tail_number, error_str)
        Synchronous pre-flight checks (zip bomb, schema, tail-number conflict).
        Returns (manifest, tail_number, None) on success or (None, None, error_msg).

    run_aircraft_import_job(job_id, zip_path, owner_user, tail_number_override=None)
        Background thread target. Validates data, creates all records, cleans up.
"""

import io
import json
import logging
import os
import shutil
import unicodedata
import uuid
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

# Manifest top-level keys (unknown keys are rejected)
KNOWN_MANIFEST_KEYS = {
    'schema_version', 'exported_at', 'source_instance', 'aircraft',
    'component_types', 'components', 'document_collections', 'documents',
    'document_images', 'logbook_entries', 'squawks', 'inspection_types',
    'inspection_records', 'ads', 'ad_compliances', 'consumable_records',
    'major_records', 'notes',
}

# Per-entity record count limits (configurable in settings)
_DEFAULT_LIMITS = {
    'logbook_entries': 10_000,
    'document_images': 50_000,
    'components': 5_000,
    'document_collections': 5_000,
    'documents': 5_000,
    'squawks': 5_000,
    'inspection_types': 5_000,
    'inspection_records': 5_000,
    'ads': 5_000,
    'ad_compliances': 5_000,
    'consumable_records': 5_000,
    'major_records': 5_000,
    'notes': 5_000,
}

# File-type magic bytes for content validation
_MAGIC = {
    'jpg':  b'\xff\xd8\xff',
    'jpeg': b'\xff\xd8\xff',
    'png':  b'\x89PNG\r\n\x1a\n',
    'gif':  b'GIF8',
    'webp': b'RIFF',
    'bmp':  b'BM',
    'tiff': (b'II*\x00', b'MM\x00*'),
    'pdf':  b'%PDF-',
    'txt':  None,  # No magic for text; extension check sufficient
}

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'pdf', 'txt'}

MAX_UPLOAD_SIZE = 512 * 1024 * 1024  # 512 MB per file
MANIFEST_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _safe_zip_name(name):
    """
    Return a safely normalized zip entry name, or None if the name is unsafe.
    Checks: valid UTF-8, NFC normalization, no path traversal.
    """
    try:
        normalized = unicodedata.normalize('NFC', name)
    except (UnicodeDecodeError, TypeError):
        return None
    # Reject absolute paths and path traversal
    if os.path.isabs(normalized):
        return None
    parts = normalized.replace('\\', '/').split('/')
    if '..' in parts:
        return None
    return normalized


def _is_symlink_entry(info):
    """Return True if a ZipInfo entry is a symlink."""
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _validate_file_magic(data, ext):
    """
    Validate that file bytes match the expected magic for the extension.
    Returns True if valid, False if mismatch.
    """
    ext = ext.lower().lstrip('.')
    magic = _MAGIC.get(ext)
    if magic is None:
        return True  # txt — no magic check
    if isinstance(magic, tuple):
        return any(data[:len(m)] == m for m in magic)
    return data[:len(magic)] == magic


# ---------------------------------------------------------------------------
# Quick synchronous validation (runs in the view before returning job_id)
# ---------------------------------------------------------------------------

def validate_archive_quick(zip_path, tail_number_override=None):
    """
    Run fast pre-flight checks on a staged ZIP.

    Returns:
        (manifest, effective_tail_number, None)       — success
        (None, None, error_string)                    — validation failure
        (None, conflicting_tail_number, 'CONFLICT')   — tail number conflict
    """
    from core.models import Aircraft

    max_size = getattr(settings, 'IMPORT_MAX_ARCHIVE_SIZE', 10 * 1024 * 1024 * 1024)

    # 1. Must be a valid ZIP
    if not zipfile.is_zipfile(zip_path):
        return None, None, "Not a valid ZIP file."

    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except zipfile.BadZipFile as exc:
        return None, None, f"Invalid ZIP file: {exc}"

    with zf:
        # 2. Zip bomb: check total uncompressed size and ratio
        total_uncompressed = 0
        total_compressed = 0
        for info in zf.infolist():
            if _is_symlink_entry(info):
                return None, None, f"Archive contains symlinks, which are not allowed."
            name = _safe_zip_name(info.filename)
            if name is None:
                return None, None, f"Archive contains an entry with an unsafe path: {info.filename!r}"
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            if total_uncompressed > max_size:
                return None, None, (
                    f"Archive decompressed size exceeds the maximum allowed "
                    f"({max_size // (1024 ** 3)} GiB)."
                )
        if total_compressed > 0 and total_uncompressed / total_compressed > 100:
            return None, None, "Archive compression ratio exceeds 100:1 — possible zip bomb."

        # 3. manifest.json must exist and be ≤ 50 MB
        try:
            manifest_info = zf.getinfo('manifest.json')
        except KeyError:
            return None, None, "Archive is missing manifest.json."
        if manifest_info.file_size > MANIFEST_MAX_BYTES:
            return None, None, f"manifest.json exceeds the 50 MB size limit."

        # 4. Parse manifest
        try:
            manifest_bytes = zf.read('manifest.json')
            manifest = json.loads(manifest_bytes.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, None, f"Could not parse manifest.json: {exc}"

        if not isinstance(manifest, dict):
            return None, None, "manifest.json must be a JSON object."

        # 5. Schema version
        version = manifest.get('schema_version')
        if not isinstance(version, int) or version > CURRENT_SCHEMA_VERSION:
            return None, None, (
                f"Unsupported schema version {version!r}. "
                f"This instance supports schema_version ≤ {CURRENT_SCHEMA_VERSION}."
            )

        # 6. Required top-level keys
        missing_keys = KNOWN_MANIFEST_KEYS - set(manifest.keys())
        if missing_keys:
            return None, None, f"manifest.json is missing required keys: {sorted(missing_keys)}"
        unknown_keys = set(manifest.keys()) - KNOWN_MANIFEST_KEYS
        if unknown_keys:
            return None, None, f"manifest.json contains unknown keys: {sorted(unknown_keys)}"

        # 7. Aircraft data must be a dict with a tail_number
        aircraft_data = manifest.get('aircraft')
        if not isinstance(aircraft_data, dict):
            return None, None, "manifest.json 'aircraft' field must be an object."
        if not aircraft_data.get('tail_number'):
            return None, None, "manifest.json aircraft is missing 'tail_number'."

    # 8. Tail number conflict check
    effective_tail = tail_number_override or manifest['aircraft']['tail_number']
    if Aircraft.objects.filter(tail_number=effective_tail).exists():
        return None, effective_tail, 'CONFLICT'

    return manifest, effective_tail, None


# ---------------------------------------------------------------------------
# Background import runner
# ---------------------------------------------------------------------------

def _append_event(job, event_type, message):
    """Append an event to the job's event log and save."""
    from health.models import ImportJob
    event = {'type': event_type, 'message': message}
    # Atomic append to avoid race conditions with concurrent reads
    ImportJob.objects.filter(pk=job.pk).update(
        events=ImportJob.objects.get(pk=job.pk).events + [event]
    )
    job.refresh_from_db(fields=['events'])


def _topological_sort_components(components):
    """
    Sort components so parents come before their children.
    components is a list of dicts with 'id' and 'parent_component_id'.
    """
    id_to_comp = {c['id']: c for c in components}
    result = []
    visited = set()

    def visit(comp_id):
        if comp_id in visited:
            return
        visited.add(comp_id)
        comp = id_to_comp.get(comp_id)
        if comp is None:
            return
        parent_id = comp.get('parent_component_id')
        if parent_id and parent_id in id_to_comp:
            visit(parent_id)
        result.append(comp)

    for c in components:
        visit(c['id'])
    return result


def _extract_file_from_zip(zf, archive_path, ext, max_bytes=MAX_UPLOAD_SIZE):
    """
    Read a file from the ZIP, validate extension and magic bytes.
    Returns (data_bytes, error_str). error_str is None on success.
    """
    try:
        info = zf.getinfo(archive_path)
    except KeyError:
        return None, f"File not found in archive: {archive_path}"

    if info.file_size > max_bytes:
        return None, (
            f"File {archive_path!r} exceeds the {max_bytes // (1024 ** 2)} MB size limit."
        )

    data = zf.read(archive_path)

    # Validate magic bytes match extension
    if not _validate_file_magic(data, ext):
        return None, (
            f"File {archive_path!r} content does not match its extension .{ext}."
        )

    return data, None


def _save_file_to_storage(data, upload_to_subdir, original_ext):
    """
    Save bytes to Django default_storage with a random UUID filename.
    Returns the storage path (relative to MEDIA_ROOT).
    """
    filename = f"{uuid.uuid4().hex}.{original_ext.lower()}"
    storage_path = f"{upload_to_subdir}/{filename}"
    default_storage.save(storage_path, ContentFile(data))
    return storage_path


def _parse_date(value):
    """Parse an ISO 8601 date string to date, or return None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        return None


def _parse_decimal(value):
    """Parse a string or number to Decimal, or return None."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _remap(id_map_category, old_id):
    """Return the new UUID for old_id, or None if old_id is None."""
    if old_id is None:
        return None
    return id_map_category.get(old_id)


def run_aircraft_import_job(job_id, zip_path, owner_user, tail_number_override=None):
    """
    Background import runner. Called from a daemon thread.

    job_id         — UUID of an ImportJob (status='pending', aircraft=None)
    zip_path       — absolute path to the staged ZIP file
    owner_user     — User instance who will become aircraft owner
    tail_number_override — if set, use instead of manifest tail_number
    """
    from health.models import (
        ImportJob, Component, ComponentType, DocumentCollection, Document,
        DocumentImage, LogbookEntry, Squawk, InspectionType, InspectionRecord,
        AD, ADCompliance, ConsumableRecord, MajorRepairAlteration,
    )
    from core.models import Aircraft, AircraftNote, AircraftRole
    from core.events import log_event

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        logger.error("ImportJob %s not found", job_id)
        return

    def ev(event_type, message):
        event = {'type': event_type, 'message': message}
        ImportJob.objects.filter(pk=job.pk).update(
            events=ImportJob.objects.values_list('events', flat=True).get(pk=job.pk) + [event]
        )

    job.status = 'running'
    job.save(update_fields=['status'])
    ev('info', 'Validating archive…')

    try:
        _run_import(job, zip_path, owner_user, tail_number_override, ev)
    except Exception:
        logger.exception("Unhandled error in aircraft import job %s", job_id)
        ev('error', 'An unexpected internal error occurred. The import was aborted.')
        job.status = 'failed'
        job.save(update_fields=['status', 'updated_at'])
    finally:
        # Always clean up the staged ZIP
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except OSError as exc:
            logger.warning("Could not remove staged ZIP %s: %s", zip_path, exc)


def _run_import(job, zip_path, owner_user, tail_number_override, ev):
    """Inner implementation — raises on unexpected errors."""
    from health.models import (
        ImportJob, Component, ComponentType, DocumentCollection, Document,
        DocumentImage, LogbookEntry, Squawk, InspectionType, InspectionRecord,
        AD, ADCompliance, ConsumableRecord, MajorRepairAlteration,
    )
    from core.models import Aircraft, AircraftNote, AircraftRole
    from core.events import log_event

    max_size = getattr(settings, 'IMPORT_MAX_ARCHIVE_SIZE', 10 * 1024 * 1024 * 1024)
    limits = dict(_DEFAULT_LIMITS)
    limits.update(getattr(settings, 'IMPORT_RECORD_LIMITS', {}))

    # -----------------------------------------------------------------------
    # Re-parse manifest (we already validated it in the view, but re-do for safety)
    # -----------------------------------------------------------------------
    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except zipfile.BadZipFile as exc:
        ev('error', f"Could not open archive: {exc}")
        job.status = 'failed'
        job.save(update_fields=['status', 'updated_at'])
        return

    with zf:
        manifest_bytes = zf.read('manifest.json')
        manifest = json.loads(manifest_bytes.decode('utf-8'))

        aircraft_data = manifest['aircraft']
        effective_tail = tail_number_override or aircraft_data['tail_number']

        # -----------------------------------------------------------------------
        # Phase A: data-integrity validation
        # -----------------------------------------------------------------------
        ev('info', 'Checking data integrity…')

        warnings = []

        # Record count limits
        for entity_key, limit in limits.items():
            records = manifest.get(entity_key, [])
            if len(records) > limit:
                ev('error', f"Too many {entity_key}: {len(records)} (limit {limit}).")
                job.status = 'failed'
                job.save(update_fields=['status', 'updated_at'])
                return

        # Build sets of IDs from manifest for FK validation
        component_ids_in_manifest = {c['id'] for c in manifest.get('components', [])}
        document_ids_in_manifest = {d['id'] for d in manifest.get('documents', [])}
        doc_collection_ids_in_manifest = {c['id'] for c in manifest.get('document_collections', [])}
        logbook_entry_ids_in_manifest = {e['id'] for e in manifest.get('logbook_entries', [])}
        inspection_type_ids_in_manifest = {it['id'] for it in manifest.get('inspection_types', [])}
        inspection_record_ids_in_manifest = {r['id'] for r in manifest.get('inspection_records', [])}
        ad_ids_in_manifest = {a['id'] for a in manifest.get('ads', [])}

        # Build set of files in the archive
        archive_files = {info.filename for info in zf.infolist()}

        def _check_fk(record_type, field, value, valid_set, nullable=True):
            if value is None:
                return nullable
            return value in valid_set

        validation_errors = []

        for c in manifest.get('components', []):
            if c.get('parent_component_id') and c['parent_component_id'] not in component_ids_in_manifest:
                validation_errors.append(
                    f"Component {c['id']}: parent_component_id {c['parent_component_id']!r} not in manifest."
                )
            if not c.get('component_type_id'):
                validation_errors.append(f"Component {c['id']}: missing component_type_id.")

        for col in manifest.get('document_collections', []):
            for cid in col.get('components', []):
                if cid not in component_ids_in_manifest:
                    validation_errors.append(
                        f"DocumentCollection {col['id']}: component {cid!r} not in manifest."
                    )

        for doc in manifest.get('documents', []):
            if doc.get('collection_id') and doc['collection_id'] not in doc_collection_ids_in_manifest:
                validation_errors.append(
                    f"Document {doc['id']}: collection_id {doc['collection_id']!r} not in manifest."
                )

        for img in manifest.get('document_images', []):
            if img.get('document_id') and img['document_id'] not in document_ids_in_manifest:
                validation_errors.append(
                    f"DocumentImage {img['id']}: document_id {img['document_id']!r} not in manifest."
                )
            archive_path = img.get('image')
            if archive_path and not img.get('_missing') and archive_path not in archive_files:
                validation_errors.append(
                    f"DocumentImage {img['id']}: file {archive_path!r} not found in archive."
                )

        for entry in manifest.get('logbook_entries', []):
            if entry.get('log_image_id') and entry['log_image_id'] not in document_ids_in_manifest:
                validation_errors.append(
                    f"LogbookEntry {entry['id']}: log_image_id {entry['log_image_id']!r} not in manifest."
                )
            for cid in entry.get('components', []):
                if cid not in component_ids_in_manifest:
                    validation_errors.append(
                        f"LogbookEntry {entry['id']}: component {cid!r} not in manifest."
                    )
            for did in entry.get('related_documents', []):
                if did not in document_ids_in_manifest:
                    validation_errors.append(
                        f"LogbookEntry {entry['id']}: related_document {did!r} not in manifest."
                    )
            # Validate component_hours JSON structure
            ch = entry.get('component_hours')
            if ch is not None:
                if not isinstance(ch, dict):
                    validation_errors.append(
                        f"LogbookEntry {entry['id']}: component_hours must be a dict."
                    )
                else:
                    for k, v in ch.items():
                        if not isinstance(k, str):
                            validation_errors.append(
                                f"LogbookEntry {entry['id']}: component_hours keys must be strings."
                            )
                            break
                        if not isinstance(v, (int, float)):
                            validation_errors.append(
                                f"LogbookEntry {entry['id']}: component_hours values must be numbers."
                            )
                            break

        for sq in manifest.get('squawks', []):
            if sq.get('component_id') and sq['component_id'] not in component_ids_in_manifest:
                validation_errors.append(
                    f"Squawk {sq['id']}: component_id {sq['component_id']!r} not in manifest."
                )
            for le_id in sq.get('logbook_entries', []):
                if le_id not in logbook_entry_ids_in_manifest:
                    validation_errors.append(
                        f"Squawk {sq['id']}: logbook_entry {le_id!r} not in manifest."
                    )
            archive_path = sq.get('attachment')
            if archive_path and not sq.get('_missing') and archive_path not in archive_files:
                validation_errors.append(
                    f"Squawk {sq['id']}: attachment {archive_path!r} not found in archive."
                )

        for ir in manifest.get('inspection_records', []):
            if ir.get('inspection_type_id') and ir['inspection_type_id'] not in inspection_type_ids_in_manifest:
                validation_errors.append(
                    f"InspectionRecord {ir['id']}: inspection_type_id not in manifest."
                )
            if ir.get('logbook_entry_id') and ir['logbook_entry_id'] not in logbook_entry_ids_in_manifest:
                validation_errors.append(
                    f"InspectionRecord {ir['id']}: logbook_entry_id not in manifest."
                )

        for ac in manifest.get('ad_compliances', []):
            if ac.get('ad_id') and ac['ad_id'] not in ad_ids_in_manifest:
                validation_errors.append(
                    f"ADCompliance {ac['id']}: ad_id {ac['ad_id']!r} not in manifest."
                )
            if ac.get('logbook_entry_id') and ac['logbook_entry_id'] not in logbook_entry_ids_in_manifest:
                validation_errors.append(
                    f"ADCompliance {ac['id']}: logbook_entry_id not in manifest."
                )
            if ac.get('inspection_record_id') and ac['inspection_record_id'] not in inspection_record_ids_in_manifest:
                validation_errors.append(
                    f"ADCompliance {ac['id']}: inspection_record_id not in manifest."
                )

        for mr in manifest.get('major_records', []):
            if mr.get('component_id') and mr['component_id'] not in component_ids_in_manifest:
                validation_errors.append(
                    f"MajorRepairAlteration {mr['id']}: component_id not in manifest."
                )
            if mr.get('logbook_entry_id') and mr['logbook_entry_id'] not in logbook_entry_ids_in_manifest:
                validation_errors.append(
                    f"MajorRepairAlteration {mr['id']}: logbook_entry_id not in manifest."
                )

        if validation_errors:
            for err in validation_errors[:20]:  # cap output
                ev('error', err)
            if len(validation_errors) > 20:
                ev('error', f"… and {len(validation_errors) - 20} more errors.")
            job.status = 'failed'
            job.save(update_fields=['status', 'updated_at'])
            return

        # -----------------------------------------------------------------------
        # Phase B: record creation inside a transaction
        # -----------------------------------------------------------------------
        id_map = {
            'component_type': {},
            'component': {},
            'document_collection': {},
            'document': {},
            'document_image': {},
            'logbook_entry': {},
            'squawk': {},
            'inspection_type': {},
            'inspection_record': {},
            'ad': {},
            'ad_compliance': {},
            'major_record': {},
        }

        counts = {}
        extracted_files = []  # rollback tracking

        try:
            with transaction.atomic():
                # --- Aircraft -----------------------------------------------
                ev('info', 'Creating aircraft…')
                new_aircraft = Aircraft.objects.create(
                    tail_number=effective_tail,
                    make=aircraft_data.get('make', ''),
                    model=aircraft_data.get('model', ''),
                    serial_number=aircraft_data.get('serial_number', ''),
                    description=aircraft_data.get('description', ''),
                    purchased=_parse_date(aircraft_data.get('purchased')),
                    status=aircraft_data.get('status', 'AVAILABLE'),
                    flight_time=_parse_decimal(aircraft_data.get('flight_time')) or Decimal('0.0'),
                )
                # Aircraft picture
                picture_path = aircraft_data.get('picture')
                if picture_path and not aircraft_data.get('_missing'):
                    ext = picture_path.rsplit('.', 1)[-1].lower()
                    if ext in ALLOWED_EXTENSIONS:
                        data, err = _extract_file_from_zip(zf, picture_path, ext)
                        if data:
                            storage_path = _save_file_to_storage(data, 'aircraft_pictures', ext)
                            new_aircraft.picture = storage_path
                            new_aircraft.save(update_fields=['picture'])
                            extracted_files.append(storage_path)
                        elif err:
                            warnings.append(f"Aircraft picture: {err}")

                # Assign owner role
                AircraftRole.objects.create(aircraft=new_aircraft, user=owner_user, role='owner')

                # --- ComponentTypes -----------------------------------------
                ev('info', f"Processing {len(manifest.get('component_types', []))} component types…")
                for ct_data in manifest.get('component_types', []):
                    existing = ComponentType.objects.filter(name__iexact=ct_data['name']).first()
                    if existing:
                        if existing.consumable != ct_data.get('consumable', False):
                            warnings.append(
                                f"ComponentType '{ct_data['name']}' matched an existing record "
                                f"with a different 'consumable' value. Using existing."
                            )
                        id_map['component_type'][ct_data['id']] = str(existing.id)
                    else:
                        new_ct = ComponentType.objects.create(
                            name=ct_data['name'],
                            consumable=ct_data.get('consumable', False),
                        )
                        id_map['component_type'][ct_data['id']] = str(new_ct.id)
                counts['component_types'] = len(manifest.get('component_types', []))

                # --- Components (topological sort for parent-child) ----------
                sorted_components = _topological_sort_components(
                    manifest.get('components', [])
                )
                ev('info', f"Creating {len(sorted_components)} components…")
                for c_data in sorted_components:
                    ct_new_id = id_map['component_type'].get(c_data.get('component_type_id'))
                    if not ct_new_id:
                        warnings.append(
                            f"Component {c_data['id']}: component_type not found, skipping."
                        )
                        continue
                    parent_new_id = None
                    if c_data.get('parent_component_id'):
                        parent_new_id = id_map['component'].get(c_data['parent_component_id'])

                    new_c = Component.objects.create(
                        aircraft=new_aircraft,
                        parent_component_id=parent_new_id,
                        component_type_id=ct_new_id,
                        manufacturer=c_data.get('manufacturer', ''),
                        model=c_data.get('model', ''),
                        serial_number=c_data.get('serial_number', ''),
                        install_location=c_data.get('install_location', ''),
                        notes=c_data.get('notes', ''),
                        status=c_data.get('status', 'SPARE'),
                        date_in_service=_parse_date(c_data.get('date_in_service')) or '1900-01-01',
                        hours_in_service=_parse_decimal(c_data.get('hours_in_service')) or Decimal('0.0'),
                        hours_since_overhaul=_parse_decimal(c_data.get('hours_since_overhaul')) or Decimal('0.0'),
                        overhaul_date=_parse_date(c_data.get('overhaul_date')),
                        tbo_hours=c_data.get('tbo_hours'),
                        tbo_days=c_data.get('tbo_days'),
                        inspection_hours=c_data.get('inspection_hours'),
                        inspection_days=c_data.get('inspection_days'),
                        replacement_hours=c_data.get('replacement_hours'),
                        replacement_days=c_data.get('replacement_days'),
                        tbo_critical=c_data.get('tbo_critical', True),
                        inspection_critical=c_data.get('inspection_critical', True),
                        replacement_critical=c_data.get('replacement_critical', False),
                    )
                    id_map['component'][c_data['id']] = str(new_c.id)
                counts['components'] = len(id_map['component'])

                # --- DocumentCollections ------------------------------------
                ev('info', f"Creating {len(manifest.get('document_collections', []))} document collections…")
                for col_data in manifest.get('document_collections', []):
                    new_col = DocumentCollection.objects.create(
                        aircraft=new_aircraft,
                        name=col_data.get('name', 'Imported Collection'),
                        description=col_data.get('description', ''),
                        visibility=col_data.get('visibility', 'private'),
                        starred=col_data.get('starred', False),
                    )
                    # M2M components
                    component_m2m = [
                        id_map['component'][cid]
                        for cid in col_data.get('components', [])
                        if cid in id_map['component']
                    ]
                    if component_m2m:
                        new_col.components.set(component_m2m)
                    id_map['document_collection'][col_data['id']] = str(new_col.id)
                counts['document_collections'] = len(id_map['document_collection'])

                # --- Documents ----------------------------------------------
                ev('info', f"Creating {len(manifest.get('documents', []))} documents…")
                for doc_data in manifest.get('documents', []):
                    col_new_id = None
                    if doc_data.get('collection_id'):
                        col_new_id = id_map['document_collection'].get(doc_data['collection_id'])
                    new_doc = Document.objects.create(
                        aircraft=new_aircraft,
                        collection_id=col_new_id,
                        doc_type=doc_data.get('doc_type', 'OTHER'),
                        name=doc_data.get('name', 'Imported Document'),
                        description=doc_data.get('description', ''),
                        visibility=doc_data.get('visibility'),
                    )
                    component_m2m = [
                        id_map['component'][cid]
                        for cid in doc_data.get('components', [])
                        if cid in id_map['component']
                    ]
                    if component_m2m:
                        new_doc.components.set(component_m2m)
                    id_map['document'][doc_data['id']] = str(new_doc.id)
                counts['documents'] = len(id_map['document'])

                # --- DocumentImages -----------------------------------------
                ev('info', f"Creating {len(manifest.get('document_images', []))} document images…")
                img_count = 0
                for img_data in manifest.get('document_images', []):
                    doc_new_id = id_map['document'].get(img_data.get('document_id', ''))
                    if not doc_new_id:
                        warnings.append(f"DocumentImage {img_data['id']}: document not found, skipping.")
                        continue

                    new_img = DocumentImage(
                        document_id=doc_new_id,
                        notes=img_data.get('notes', ''),
                    )

                    archive_path = img_data.get('image')
                    if archive_path and not img_data.get('_missing'):
                        ext = archive_path.rsplit('.', 1)[-1].lower()
                        if ext in ALLOWED_EXTENSIONS:
                            data, err = _extract_file_from_zip(zf, archive_path, ext)
                            if data:
                                storage_path = _save_file_to_storage(data, 'health/documents', ext)
                                new_img.image = storage_path
                                extracted_files.append(storage_path)
                            elif err:
                                warnings.append(f"DocumentImage {img_data['id']}: {err}")
                        else:
                            warnings.append(
                                f"DocumentImage {img_data['id']}: disallowed extension .{ext}, skipping file."
                            )

                    new_img.save()
                    id_map['document_image'][img_data['id']] = str(new_img.id)
                    img_count += 1
                counts['document_images'] = img_count

                # --- LogbookEntries -----------------------------------------
                ev('info', f"Creating {len(manifest.get('logbook_entries', []))} logbook entries…")
                for entry_data in manifest.get('logbook_entries', []):
                    log_image_new_id = None
                    if entry_data.get('log_image_id'):
                        log_image_new_id = id_map['document'].get(entry_data['log_image_id'])

                    # Remap component_hours UUID keys
                    ch = entry_data.get('component_hours')
                    if ch and isinstance(ch, dict):
                        ch = {
                            id_map['component'].get(k, k): v
                            for k, v in ch.items()
                        }

                    new_entry = LogbookEntry.objects.create(
                        aircraft=new_aircraft,
                        log_type=entry_data.get('log_type', 'AC'),
                        date=_parse_date(entry_data.get('date')) or '1900-01-01',
                        text=entry_data.get('text', ''),
                        signoff_person=entry_data.get('signoff_person', ''),
                        signoff_location=entry_data.get('signoff_location', ''),
                        log_image_id=log_image_new_id,
                        aircraft_hours_at_entry=_parse_decimal(entry_data.get('aircraft_hours_at_entry')),
                        component_hours=ch,
                        entry_type=entry_data.get('entry_type', 'OTHER'),
                        page_number=entry_data.get('page_number'),
                    )
                    # M2M components
                    comp_m2m = [
                        id_map['component'][cid]
                        for cid in entry_data.get('components', [])
                        if cid in id_map['component']
                    ]
                    if comp_m2m:
                        new_entry.component.set(comp_m2m)
                    # M2M related_documents
                    doc_m2m = [
                        id_map['document'][did]
                        for did in entry_data.get('related_documents', [])
                        if did in id_map['document']
                    ]
                    if doc_m2m:
                        new_entry.related_documents.set(doc_m2m)

                    id_map['logbook_entry'][entry_data['id']] = str(new_entry.id)
                counts['logbook_entries'] = len(id_map['logbook_entry'])

                # --- Squawks ------------------------------------------------
                ev('info', f"Creating {len(manifest.get('squawks', []))} squawks…")
                for sq_data in manifest.get('squawks', []):
                    comp_new_id = None
                    if sq_data.get('component_id'):
                        comp_new_id = id_map['component'].get(sq_data['component_id'])

                    new_sq = Squawk(
                        aircraft=new_aircraft,
                        component_id=comp_new_id,
                        priority=sq_data.get('priority', 0),
                        issue_reported=sq_data.get('issue_reported', ''),
                        resolved=sq_data.get('resolved', False),
                        notes=sq_data.get('notes', ''),
                    )

                    archive_path = sq_data.get('attachment')
                    if archive_path and not sq_data.get('_missing'):
                        ext = archive_path.rsplit('.', 1)[-1].lower()
                        if ext in ALLOWED_EXTENSIONS:
                            data, err = _extract_file_from_zip(zf, archive_path, ext)
                            if data:
                                storage_path = _save_file_to_storage(data, 'health/squawks', ext)
                                new_sq.attachment = storage_path
                                extracted_files.append(storage_path)
                            elif err:
                                warnings.append(f"Squawk {sq_data['id']}: {err}")

                    new_sq.save()
                    le_m2m = [
                        id_map['logbook_entry'][le_id]
                        for le_id in sq_data.get('logbook_entries', [])
                        if le_id in id_map['logbook_entry']
                    ]
                    if le_m2m:
                        new_sq.logbook_entries.set(le_m2m)
                    id_map['squawk'][sq_data['id']] = str(new_sq.id)
                counts['squawks'] = len(id_map['squawk'])

                # --- InspectionTypes ----------------------------------------
                ev('info', f"Processing {len(manifest.get('inspection_types', []))} inspection types…")
                for it_data in manifest.get('inspection_types', []):
                    existing = InspectionType.objects.filter(name__iexact=it_data['name']).first()
                    if existing:
                        # Check for field differences
                        diffs = []
                        for field, val in [
                            ('recurring', it_data.get('recurring', False)),
                            ('required', it_data.get('required', True)),
                        ]:
                            if getattr(existing, field) != val:
                                diffs.append(field)
                        if diffs:
                            warnings.append(
                                f"InspectionType '{it_data['name']}' matched existing with different "
                                f"fields ({', '.join(diffs)}). Using existing."
                            )
                        id_map['inspection_type'][it_data['id']] = str(existing.id)
                        # Add this aircraft and its components to M2M
                        existing.applicable_aircraft.add(new_aircraft)
                        for cid in it_data.get('applicable_component', []):
                            new_cid = id_map['component'].get(cid)
                            if new_cid:
                                existing.applicable_component.add(new_cid)
                    else:
                        new_it = InspectionType.objects.create(
                            name=it_data['name'],
                            recurring=it_data.get('recurring', False),
                            required=it_data.get('required', True),
                            recurring_hours=_parse_decimal(it_data.get('recurring_hours')) or Decimal('0.0'),
                            recurring_days=it_data.get('recurring_days', 0),
                            recurring_months=it_data.get('recurring_months', 0),
                        )
                        new_it.applicable_aircraft.add(new_aircraft)
                        for cid in it_data.get('applicable_component', []):
                            new_cid = id_map['component'].get(cid)
                            if new_cid:
                                new_it.applicable_component.add(new_cid)
                        id_map['inspection_type'][it_data['id']] = str(new_it.id)
                counts['inspection_types'] = len(manifest.get('inspection_types', []))

                # --- InspectionRecords --------------------------------------
                ev('info', f"Creating {len(manifest.get('inspection_records', []))} inspection records…")
                for ir_data in manifest.get('inspection_records', []):
                    it_new_id = id_map['inspection_type'].get(ir_data.get('inspection_type_id', ''))
                    if not it_new_id:
                        warnings.append(
                            f"InspectionRecord {ir_data['id']}: inspection_type not found, skipping."
                        )
                        continue
                    le_new_id = id_map['logbook_entry'].get(ir_data.get('logbook_entry_id', ''))

                    new_ir = InspectionRecord.objects.create(
                        date=_parse_date(ir_data.get('date')) or '1900-01-01',
                        aircraft_hours=_parse_decimal(ir_data.get('aircraft_hours')),
                        inspection_type_id=it_new_id,
                        logbook_entry_id=le_new_id,
                        aircraft=new_aircraft,
                    )
                    doc_m2m = [
                        id_map['document'][did]
                        for did in ir_data.get('documents', [])
                        if did in id_map['document']
                    ]
                    if doc_m2m:
                        new_ir.documents.set(doc_m2m)
                    comp_m2m = [
                        id_map['component'][cid]
                        for cid in ir_data.get('component', [])
                        if cid in id_map['component']
                    ]
                    if comp_m2m:
                        new_ir.component.set(comp_m2m)
                    id_map['inspection_record'][ir_data['id']] = str(new_ir.id)
                counts['inspection_records'] = len(id_map['inspection_record'])

                # --- ADs ----------------------------------------------------
                ev('info', f"Processing {len(manifest.get('ads', []))} ADs…")
                for ad_data in manifest.get('ads', []):
                    existing = AD.objects.filter(name__iexact=ad_data['name']).first()
                    if existing:
                        diffs = []
                        for field, val in [
                            ('recurring', ad_data.get('recurring', False)),
                            ('compliance_type', ad_data.get('compliance_type', 'standard')),
                            ('bulletin_type', ad_data.get('bulletin_type', 'ad')),
                            ('mandatory', ad_data.get('mandatory', True)),
                        ]:
                            if getattr(existing, field) != val:
                                diffs.append(field)
                        if diffs:
                            warnings.append(
                                f"AD '{ad_data['name']}' matched existing with different "
                                f"fields ({', '.join(diffs)}). Using existing."
                            )
                        id_map['ad'][ad_data['id']] = str(existing.id)
                        existing.applicable_aircraft.add(new_aircraft)
                        for cid in ad_data.get('applicable_component', []):
                            new_cid = id_map['component'].get(cid)
                            if new_cid:
                                existing.applicable_component.add(new_cid)
                        for it_id in ad_data.get('on_inspection_type', []):
                            new_it_id = id_map['inspection_type'].get(it_id)
                            if new_it_id:
                                existing.on_inspection_type.add(new_it_id)
                    else:
                        new_ad = AD.objects.create(
                            name=ad_data['name'],
                            short_description=ad_data.get('short_description', ''),
                            required_action=ad_data.get('required_action', ''),
                            compliance_type=ad_data.get('compliance_type', 'standard'),
                            trigger_condition=ad_data.get('trigger_condition', ''),
                            recurring=ad_data.get('recurring', False),
                            recurring_hours=_parse_decimal(ad_data.get('recurring_hours')) or Decimal('0.0'),
                            recurring_months=ad_data.get('recurring_months', 0),
                            recurring_days=ad_data.get('recurring_days', 0),
                            bulletin_type=ad_data.get('bulletin_type', 'ad'),
                            mandatory=ad_data.get('mandatory', True),
                            # document FK not imported (cross-aircraft document UUIDs won't match)
                        )
                        new_ad.applicable_aircraft.add(new_aircraft)
                        for cid in ad_data.get('applicable_component', []):
                            new_cid = id_map['component'].get(cid)
                            if new_cid:
                                new_ad.applicable_component.add(new_cid)
                        for it_id in ad_data.get('on_inspection_type', []):
                            new_it_id = id_map['inspection_type'].get(it_id)
                            if new_it_id:
                                new_ad.on_inspection_type.add(new_it_id)
                        id_map['ad'][ad_data['id']] = str(new_ad.id)
                counts['ads'] = len(manifest.get('ads', []))

                # --- ADCompliances ------------------------------------------
                ev('info', f"Creating {len(manifest.get('ad_compliances', []))} AD compliance records…")
                for ac_data in manifest.get('ad_compliances', []):
                    ad_new_id = id_map['ad'].get(ac_data.get('ad_id', ''))
                    if not ad_new_id:
                        warnings.append(
                            f"ADCompliance {ac_data['id']}: AD not found, skipping."
                        )
                        continue
                    le_new_id = id_map['logbook_entry'].get(ac_data.get('logbook_entry_id', ''))
                    ir_new_id = id_map['inspection_record'].get(ac_data.get('inspection_record_id', ''))
                    comp_new_id = id_map['component'].get(ac_data.get('component_id', ''))

                    ADCompliance.objects.create(
                        ad_id=ad_new_id,
                        date_complied=_parse_date(ac_data.get('date_complied')) or '1900-01-01',
                        compliance_notes=ac_data.get('compliance_notes', ''),
                        permanent=ac_data.get('permanent', False),
                        next_due_at_time=_parse_decimal(ac_data.get('next_due_at_time')) or Decimal('0.0'),
                        aircraft_hours_at_compliance=_parse_decimal(ac_data.get('aircraft_hours_at_compliance')),
                        logbook_entry_id=le_new_id,
                        inspection_record_id=ir_new_id,
                        aircraft=new_aircraft,
                        component_id=comp_new_id,
                    )
                counts['ad_compliances'] = len(manifest.get('ad_compliances', []))

                # --- ConsumableRecords --------------------------------------
                ev('info', f"Creating {len(manifest.get('consumable_records', []))} consumable records…")
                for cr_data in manifest.get('consumable_records', []):
                    ConsumableRecord.objects.create(
                        record_type=cr_data.get('record_type', 'oil'),
                        aircraft=new_aircraft,
                        date=_parse_date(cr_data.get('date')) or '1900-01-01',
                        quantity_added=_parse_decimal(cr_data.get('quantity_added')) or Decimal('0.0'),
                        level_after=_parse_decimal(cr_data.get('level_after')),
                        consumable_type=cr_data.get('consumable_type', ''),
                        flight_hours=_parse_decimal(cr_data.get('flight_hours')) or Decimal('0.0'),
                        notes=cr_data.get('notes', ''),
                    )
                counts['consumable_records'] = len(manifest.get('consumable_records', []))

                # --- MajorRepairAlterations ---------------------------------
                ev('info', f"Creating {len(manifest.get('major_records', []))} major repair/alteration records…")
                for mr_data in manifest.get('major_records', []):
                    comp_new_id = id_map['component'].get(mr_data.get('component_id', ''))
                    form_doc_new_id = id_map['document'].get(mr_data.get('form_337_document_id', ''))
                    stc_doc_new_id = id_map['document'].get(mr_data.get('stc_document_id', ''))
                    le_new_id = id_map['logbook_entry'].get(mr_data.get('logbook_entry_id', ''))

                    MajorRepairAlteration.objects.create(
                        aircraft=new_aircraft,
                        record_type=mr_data.get('record_type', 'repair'),
                        title=mr_data.get('title', 'Imported Record'),
                        description=mr_data.get('description', ''),
                        date_performed=_parse_date(mr_data.get('date_performed')) or '1900-01-01',
                        performed_by=mr_data.get('performed_by', ''),
                        component_id=comp_new_id,
                        form_337_document_id=form_doc_new_id,
                        stc_number=mr_data.get('stc_number', ''),
                        stc_holder=mr_data.get('stc_holder', ''),
                        stc_document_id=stc_doc_new_id,
                        logbook_entry_id=le_new_id,
                        aircraft_hours=_parse_decimal(mr_data.get('aircraft_hours')),
                        notes=mr_data.get('notes', ''),
                    )
                counts['major_records'] = len(manifest.get('major_records', []))

                # --- Notes --------------------------------------------------
                ev('info', f"Creating {len(manifest.get('notes', []))} notes…")
                for note_data in manifest.get('notes', []):
                    AircraftNote.objects.create(
                        aircraft=new_aircraft,
                        text=note_data.get('text', ''),
                        public=note_data.get('public', False),
                        added_by=None,  # User FKs are not migrated across instances
                    )
                counts['notes'] = len(manifest.get('notes', []))

                # --- Log import event ---------------------------------------
                count_summary = ', '.join(f"{v} {k}" for k, v in counts.items() if v)
                log_event(
                    aircraft=new_aircraft,
                    category='aircraft',
                    event_name='Aircraft imported',
                    user=owner_user,
                    notes=f"Imported from archive. {count_summary}.",
                )

        except Exception:
            # Roll back extracted files (DB transaction already rolled back)
            for path in extracted_files:
                try:
                    default_storage.delete(path)
                except Exception:
                    pass
            raise

    # -----------------------------------------------------------------------
    # Success
    # -----------------------------------------------------------------------
    for warning in warnings:
        ev('warning', warning)

    result = {
        'aircraft_id': str(new_aircraft.id),
        'tail_number': new_aircraft.tail_number,
        'counts': counts,
        'warnings': warnings,
    }

    job.status = 'completed'
    job.aircraft = new_aircraft
    job.result = result
    job.save(update_fields=['status', 'aircraft', 'result', 'updated_at'])

    ev('complete', (
        f"Import complete. Aircraft {new_aircraft.tail_number} created "
        f"with {sum(counts.values())} total records."
    ))
