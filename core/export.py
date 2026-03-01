"""
Aircraft data export — builds a manifest.json and streams a ZIP archive.

Public API:
    export_aircraft_zip(aircraft, response_file)  — write ZIP to a file-like object
    build_manifest(aircraft)                       — return the manifest dict

Manifest schema version: 2
"""

import io
import json
import os
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone


SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Low-level field converters
# ---------------------------------------------------------------------------

def _str(v):
    """UUID / string → str (None stays None)."""
    return str(v) if v is not None else None


def _date(v):
    """date/datetime → ISO 8601 string (None stays None)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return v.isoformat()


def _decimal(v):
    """Decimal → string to avoid float precision loss (None stays None)."""
    if v is None:
        return None
    return str(v)


def _username(user):
    """User FK → display username string (None if no user)."""
    if user is None:
        return None
    return user.username


def _file_path(field_file):
    """
    FileField → archive-relative path (under attachments/).
    Returns None if the field is empty.
    """
    if not field_file:
        return None
    name = field_file.name  # e.g. "health/documents/abc123.jpg"
    return f"attachments/{name}"


# ---------------------------------------------------------------------------
# Per-model serializers
# ---------------------------------------------------------------------------

def _aircraft_dict(aircraft):
    return {
        'id': _str(aircraft.id),
        'tail_number': aircraft.tail_number,
        'make': aircraft.make,
        'model': aircraft.model,
        'serial_number': aircraft.serial_number,
        'description': aircraft.description,
        'purchased': _date(aircraft.purchased),
        'status': aircraft.status,
        'tach_time': _decimal(aircraft.tach_time),
        'tach_time_offset': _decimal(aircraft.tach_time_offset),
        'hobbs_time': _decimal(aircraft.hobbs_time),
        'hobbs_time_offset': _decimal(aircraft.hobbs_time_offset),
        'picture': _file_path(aircraft.picture),
    }


def _component_type_dict(ct):
    return {
        'id': _str(ct.id),
        'name': ct.name,
        'consumable': ct.consumable,
    }


def _component_dict(component):
    return {
        'id': _str(component.id),
        'aircraft_id': _str(component.aircraft_id),
        'parent_component_id': _str(component.parent_component_id),
        'component_type_id': _str(component.component_type_id),
        'manufacturer': component.manufacturer,
        'model': component.model,
        'serial_number': component.serial_number,
        'install_location': component.install_location,
        'notes': component.notes,
        'status': component.status,
        'date_in_service': _date(component.date_in_service),
        'hours_in_service': _decimal(component.hours_in_service),
        'hours_since_overhaul': _decimal(component.hours_since_overhaul),
        'overhaul_date': _date(component.overhaul_date),
        'tbo_hours': component.tbo_hours,
        'tbo_days': component.tbo_days,
        'inspection_hours': component.inspection_hours,
        'inspection_days': component.inspection_days,
        'replacement_hours': component.replacement_hours,
        'replacement_days': component.replacement_days,
        'tbo_critical': component.tbo_critical,
        'on_condition': component.on_condition,
        'inspection_critical': component.inspection_critical,
        'replacement_critical': component.replacement_critical,
    }


def _document_collection_dict(col):
    return {
        'id': _str(col.id),
        'aircraft_id': _str(col.aircraft_id),
        'name': col.name,
        'description': col.description,
        'visibility': col.visibility,
        'starred': col.starred,
        'components': [_str(c_id) for c_id in col.components.values_list('id', flat=True)],
    }


def _document_dict(doc):
    return {
        'id': _str(doc.id),
        'aircraft_id': _str(doc.aircraft_id),
        'collection_id': _str(doc.collection_id),
        'doc_type': doc.doc_type,
        'name': doc.name,
        'description': doc.description,
        'visibility': doc.visibility,
        'components': [_str(c_id) for c_id in doc.components.values_list('id', flat=True)],
    }


def _document_image_dict(img):
    return {
        'id': _str(img.id),
        'document_id': _str(img.document_id),
        'notes': img.notes,
        'image': _file_path(img.image),
    }


def _logbook_entry_dict(entry):
    # Remap component_hours keys (UUID strings) — they're already strings in the DB
    return {
        'id': _str(entry.id),
        'aircraft_id': _str(entry.aircraft_id),
        'log_type': entry.log_type,
        'date': _date(entry.date),
        'text': entry.text,
        'signoff_person': entry.signoff_person,
        'signoff_location': entry.signoff_location,
        'log_image_id': _str(entry.log_image_id),
        'aircraft_hours_at_entry': _decimal(entry.aircraft_hours_at_entry),
        'component_hours': entry.component_hours,
        'entry_type': entry.entry_type,
        'page_number': entry.page_number,
        'components': [_str(c_id) for c_id in entry.component.values_list('id', flat=True)],
        'related_documents': [_str(d_id) for d_id in entry.related_documents.values_list('id', flat=True)],
    }


def _squawk_dict(squawk):
    return {
        'id': _str(squawk.id),
        'aircraft_id': _str(squawk.aircraft_id),
        'component_id': _str(squawk.component_id),
        'priority': squawk.priority,
        'issue_reported': squawk.issue_reported,
        'attachment': _file_path(squawk.attachment),
        'created_at': _date(squawk.created_at),
        'reported_by_display': _username(squawk.reported_by),
        'resolved': squawk.resolved,
        'notes': squawk.notes,
        'logbook_entries': [_str(le_id) for le_id in squawk.logbook_entries.values_list('id', flat=True)],
    }


def _inspection_type_dict(it):
    return {
        'id': _str(it.id),
        'name': it.name,
        'recurring': it.recurring,
        'required': it.required,
        'recurring_hours': _decimal(it.recurring_hours),
        'recurring_days': it.recurring_days,
        'recurring_months': it.recurring_months,
        'applicable_aircraft': [_str(a_id) for a_id in it.applicable_aircraft.values_list('id', flat=True)],
        'applicable_component': [_str(c_id) for c_id in it.applicable_component.values_list('id', flat=True)],
    }


def _inspection_record_dict(rec):
    return {
        'id': _str(rec.id),
        'date': _date(rec.date),
        'aircraft_hours': _decimal(rec.aircraft_hours),
        'inspection_type_id': _str(rec.inspection_type_id),
        'logbook_entry_id': _str(rec.logbook_entry_id),
        'aircraft_id': _str(rec.aircraft_id),
        'documents': [_str(d_id) for d_id in rec.documents.values_list('id', flat=True)],
        'component': [_str(c_id) for c_id in rec.component.values_list('id', flat=True)],
    }


def _ad_dict(ad):
    return {
        'id': _str(ad.id),
        'name': ad.name,
        'short_description': ad.short_description,
        'required_action': ad.required_action,
        'compliance_type': ad.compliance_type,
        'trigger_condition': ad.trigger_condition,
        'recurring': ad.recurring,
        'recurring_hours': _decimal(ad.recurring_hours),
        'recurring_months': ad.recurring_months,
        'recurring_days': ad.recurring_days,
        'bulletin_type': ad.bulletin_type,
        'mandatory': ad.mandatory,
        'document_id': _str(ad.document_id) if ad.document_id else None,
        'on_inspection_type': [_str(it_id) for it_id in ad.on_inspection_type.values_list('id', flat=True)],
        'applicable_aircraft': [_str(a_id) for a_id in ad.applicable_aircraft.values_list('id', flat=True)],
        'applicable_component': [_str(c_id) for c_id in ad.applicable_component.values_list('id', flat=True)],
    }


def _ad_compliance_dict(c):
    return {
        'id': _str(c.id),
        'ad_id': _str(c.ad_id),
        'date_complied': _date(c.date_complied),
        'compliance_notes': c.compliance_notes,
        'permanent': c.permanent,
        'next_due_at_time': _decimal(c.next_due_at_time),
        'aircraft_hours_at_compliance': _decimal(c.aircraft_hours_at_compliance),
        'logbook_entry_id': _str(c.logbook_entry_id),
        'inspection_record_id': _str(c.inspection_record_id),
        'aircraft_id': _str(c.aircraft_id),
        'component_id': _str(c.component_id),
    }


def _consumable_record_dict(rec):
    return {
        'id': _str(rec.id),
        'record_type': rec.record_type,
        'aircraft_id': _str(rec.aircraft_id),
        'date': _date(rec.date),
        'quantity_added': _decimal(rec.quantity_added),
        'level_after': _decimal(rec.level_after),
        'consumable_type': rec.consumable_type,
        'flight_hours': _decimal(rec.flight_hours),
        'notes': rec.notes,
        'excluded_from_averages': rec.excluded_from_averages,
    }


def _major_record_dict(rec):
    return {
        'id': _str(rec.id),
        'aircraft_id': _str(rec.aircraft_id),
        'record_type': rec.record_type,
        'title': rec.title,
        'description': rec.description,
        'date_performed': _date(rec.date_performed),
        'performed_by': rec.performed_by,
        'component_id': _str(rec.component_id),
        'form_337_document_id': _str(rec.form_337_document_id),
        'stc_number': rec.stc_number,
        'stc_holder': rec.stc_holder,
        'stc_document_id': _str(rec.stc_document_id),
        'logbook_entry_id': _str(rec.logbook_entry_id),
        'aircraft_hours': _decimal(rec.aircraft_hours),
        'notes': rec.notes,
    }


def _flight_log_dict(log):
    return {
        'id': _str(log.id),
        'aircraft_id': _str(log.aircraft_id),
        'date': _date(log.date),
        'tach_time': _decimal(log.tach_time),
        'tach_out': _decimal(log.tach_out),
        'tach_in': _decimal(log.tach_in),
        'hobbs_time': _decimal(log.hobbs_time),
        'hobbs_out': _decimal(log.hobbs_out),
        'hobbs_in': _decimal(log.hobbs_in),
        'departure_location': log.departure_location,
        'destination_location': log.destination_location,
        'route': log.route,
        'oil_added': _decimal(log.oil_added),
        'oil_added_type': log.oil_added_type,
        'fuel_added': _decimal(log.fuel_added),
        'fuel_added_type': log.fuel_added_type,
        'track_log': _file_path(log.track_log),
        'notes': log.notes,
        'created_at': _date(log.created_at),
    }


def _note_dict(note):
    return {
        'id': _str(note.id),
        'aircraft_id': _str(note.aircraft_id),
        'text': note.text,
        'public': note.public,
        'added_by_display': _username(note.added_by),
        'added_timestamp': _date(note.added_timestamp),
    }


def _oil_analysis_report_dict(report):
    return {
        'id': _str(report.id),
        'aircraft_id': _str(report.aircraft_id),
        'component_id': _str(report.component_id),
        'sample_date': _date(report.sample_date),
        'analysis_date': _date(report.analysis_date),
        'lab': report.lab,
        'lab_number': report.lab_number,
        'oil_type': report.oil_type,
        'oil_hours': _decimal(report.oil_hours),
        'engine_hours': _decimal(report.engine_hours),
        'oil_added_quarts': _decimal(report.oil_added_quarts),
        'elements_ppm': report.elements_ppm,
        'oil_properties': report.oil_properties,
        'lab_comments': report.lab_comments,
        'status': report.status,
        'notes': report.notes,
        'excluded_from_averages': report.excluded_from_averages,
    }


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def build_manifest(aircraft):
    """
    Return a manifest dict for the given aircraft with all related data.
    This does not include file contents — file paths are archive-relative
    strings (e.g. "attachments/health/documents/abc.jpg").
    """
    from health.models import (
        Component, ComponentType, DocumentCollection, Document, DocumentImage,
        LogbookEntry, Squawk, InspectionType, InspectionRecord, AD, ADCompliance,
        ConsumableRecord, MajorRepairAlteration, OilAnalysisReport, FlightLog,
    )
    from core.models import AircraftNote

    # --- Fetch all related objects -----------------------------------------
    components = list(
        Component.objects.filter(aircraft=aircraft).select_related('component_type')
    )
    component_type_ids = {c.component_type_id for c in components}
    component_types = list(ComponentType.objects.filter(id__in=component_type_ids))

    doc_collections = list(
        DocumentCollection.objects.filter(aircraft=aircraft).prefetch_related('components')
    )
    documents = list(
        Document.objects.filter(aircraft=aircraft).prefetch_related('components')
    )
    document_images = list(
        DocumentImage.objects.filter(document__aircraft=aircraft)
    )
    logbook_entries = list(
        LogbookEntry.objects.filter(aircraft=aircraft)
        .prefetch_related('component', 'related_documents')
    )
    squawks = list(
        Squawk.objects.filter(aircraft=aircraft)
        .select_related('reported_by')
        .prefetch_related('logbook_entries')
    )

    component_ids = [c.id for c in components]
    inspection_records = list(
        InspectionRecord.objects.filter(aircraft=aircraft)
        .prefetch_related('documents', 'component')
    )
    # Include types linked to this aircraft/components, plus any types directly
    # referenced by existing inspection records (in case the M2M association was
    # removed after the record was created).
    referenced_type_ids = {r.inspection_type_id for r in inspection_records if r.inspection_type_id}
    inspection_types = list(
        (InspectionType.objects.filter(applicable_aircraft=aircraft) |
         InspectionType.objects.filter(applicable_component__in=component_ids) |
         InspectionType.objects.filter(id__in=referenced_type_ids)).distinct()
        .prefetch_related('applicable_aircraft', 'applicable_component')
    )

    ads = list(
        (AD.objects.filter(applicable_aircraft=aircraft) |
         AD.objects.filter(applicable_component__in=component_ids)).distinct()
        .prefetch_related('on_inspection_type', 'applicable_aircraft', 'applicable_component')
    )
    ad_compliances = list(
        ADCompliance.objects.filter(aircraft=aircraft)
    )

    consumable_records = list(ConsumableRecord.objects.filter(aircraft=aircraft))
    major_records = list(
        MajorRepairAlteration.objects.filter(aircraft=aircraft)
    )
    notes = list(
        aircraft.notes.all().select_related('added_by')
    )
    oil_analysis_reports = list(OilAnalysisReport.objects.filter(aircraft=aircraft))
    flight_logs = list(FlightLog.objects.filter(aircraft=aircraft))

    # --- Build manifest -----------------------------------------------------
    request_host = getattr(settings, 'ALLOWED_HOSTS', [''])[0] or ''

    manifest = {
        'schema_version': SCHEMA_VERSION,
        'exported_at': timezone.now().isoformat(),
        'source_instance': request_host,
        'aircraft': _aircraft_dict(aircraft),
        'component_types': [_component_type_dict(ct) for ct in component_types],
        'components': [_component_dict(c) for c in components],
        'document_collections': [_document_collection_dict(col) for col in doc_collections],
        'documents': [_document_dict(doc) for doc in documents],
        'document_images': [_document_image_dict(img) for img in document_images],
        'logbook_entries': [_logbook_entry_dict(e) for e in logbook_entries],
        'squawks': [_squawk_dict(s) for s in squawks],
        'inspection_types': [_inspection_type_dict(it) for it in inspection_types],
        'inspection_records': [_inspection_record_dict(r) for r in inspection_records],
        'ads': [_ad_dict(ad) for ad in ads],
        'ad_compliances': [_ad_compliance_dict(c) for c in ad_compliances],
        'consumable_records': [_consumable_record_dict(r) for r in consumable_records],
        'major_records': [_major_record_dict(r) for r in major_records],
        'notes': [_note_dict(n) for n in notes],
        'oil_analysis_reports': [_oil_analysis_report_dict(r) for r in oil_analysis_reports],
        'flight_logs': [_flight_log_dict(fl) for fl in flight_logs],
    }
    return manifest


# ---------------------------------------------------------------------------
# ZIP writer
# ---------------------------------------------------------------------------

def _collect_file_paths(manifest):
    """
    Walk the manifest and collect all archive-relative file paths (non-None).
    Returns a list of (manifest_path, storage_name) tuples.

    manifest_path  — the string stored in the manifest (e.g. "attachments/health/...")
    storage_name   — path relative to MEDIA_ROOT used by default_storage
    """
    paths = []

    def _add(archive_path):
        if archive_path:
            # strip the "attachments/" prefix to get the storage name
            storage_name = archive_path[len('attachments/'):]
            paths.append((archive_path, storage_name))

    _add(manifest['aircraft'].get('picture'))
    for img in manifest['document_images']:
        _add(img.get('image'))
    for sq in manifest['squawks']:
        _add(sq.get('attachment'))
    for fl in manifest.get('flight_logs', []):
        _add(fl.get('track_log'))

    return paths


def export_aircraft_zip(aircraft, dest_file):
    """
    Write a .sam.zip archive for the given aircraft to dest_file (file-like).

    dest_file must support write() and be opened in binary mode.
    This function blocks until the archive is fully written.
    """
    manifest = build_manifest(aircraft)

    # Pre-verify which files actually exist in storage
    file_paths = _collect_file_paths(manifest)
    missing_storage_names = set()
    for archive_path, storage_name in file_paths:
        if not default_storage.exists(storage_name):
            missing_storage_names.add(storage_name)

    # Mark missing files in the manifest
    def _mark_missing(field_dict, field_key):
        archive_path = field_dict.get(field_key)
        if archive_path:
            storage_name = archive_path[len('attachments/'):]
            if storage_name in missing_storage_names:
                field_dict['_missing'] = True

    _mark_missing(manifest['aircraft'], 'picture')
    for img in manifest['document_images']:
        _mark_missing(img, 'image')
    for sq in manifest['squawks']:
        _mark_missing(sq, 'attachment')
    for fl in manifest.get('flight_logs', []):
        _mark_missing(fl, 'track_log')

    manifest_bytes = json.dumps(manifest, indent=2, default=str).encode('utf-8')

    with zipfile.ZipFile(dest_file, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.writestr('manifest.json', manifest_bytes)

        for archive_path, storage_name in file_paths:
            if storage_name in missing_storage_names:
                continue
            try:
                with default_storage.open(storage_name, 'rb') as fh:
                    zf.writestr(archive_path, fh.read())
            except Exception:
                pass  # Treat unreadable files like missing files
