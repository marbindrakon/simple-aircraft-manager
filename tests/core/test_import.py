"""
Tests for aircraft ZIP import (core/import_export.py, ImportView, ImportJobStatusView).
"""
import io
import json
import os
import tempfile
import unittest.mock
import uuid
import zipfile

import pytest

from core.export import build_manifest
from core.import_export import validate_archive_quick, run_aircraft_import_job
from health.models import ImportJob

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Django session clients for LoginRequiredMixin views (ImportView/ImportJobStatusView)
# ---------------------------------------------------------------------------

@pytest.fixture
def session_owner(owner_user):
    from django.test import Client
    c = Client()
    c.force_login(owner_user)
    return c

@pytest.fixture
def session_other(other_user):
    from django.test import Client
    c = Client()
    c.force_login(other_user)
    return c

@pytest.fixture
def session_admin(admin_user):
    from django.test import Client
    c = Client()
    c.force_login(admin_user)
    return c


# ---------------------------------------------------------------------------
# Helper: build a valid in-memory ZIP
# ---------------------------------------------------------------------------

def make_import_zip(manifest_dict, extra_files=None):
    """
    Create a valid in-memory ZIP containing manifest.json.
    Returns raw bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('manifest.json', json.dumps(manifest_dict))
        if extra_files:
            for name, data in extra_files.items():
                zf.writestr(name, data)
    buf.seek(0)
    return buf.read()


def write_zip_to_tempfile(zip_bytes):
    """Write zip_bytes to a NamedTemporaryFile; returns (path, file_obj)."""
    tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    tmp.write(zip_bytes)
    tmp.flush()
    tmp.close()
    return tmp.name


def make_minimal_manifest(tail_number='N99999'):
    """Build the minimal valid manifest dict required by validate_archive_quick."""
    return {
        'schema_version': 2,
        'exported_at': '2024-01-01T00:00:00+00:00',
        'source_instance': 'test',
        'aircraft': {
            'id': str(uuid.uuid4()),
            'tail_number': tail_number,
            'make': 'Cessna',
            'model': '172',
            'serial_number': '',
            'description': '',
            'purchased': None,
            'status': 'AVAILABLE',
            'tach_time': '100.0',
            'tach_time_offset': '0.0',
            'hobbs_time': '100.0',
            'hobbs_time_offset': '0.0',
            'picture': None,
        },
        'component_types': [],
        'components': [],
        'document_collections': [],
        'documents': [],
        'document_images': [],
        'logbook_entries': [],
        'squawks': [],
        'inspection_types': [],
        'inspection_records': [],
        'ads': [],
        'ad_compliances': [],
        'consumable_records': [],
        'major_records': [],
        'notes': [],
        'oil_analysis_reports': [],
        'flight_logs': [],
    }


# ---------------------------------------------------------------------------
# validate_archive_quick
# ---------------------------------------------------------------------------

class TestValidateArchiveQuick:
    def test_valid_zip_returns_manifest(self):
        manifest = make_minimal_manifest('N00001')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is None
            assert result_manifest is not None
            assert effective_tail == 'N00001'
        finally:
            os.unlink(path)

    def test_non_zip_bytes_returns_error(self):
        path = write_zip_to_tempfile(b'not a zip file at all')
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert result_manifest is None
        finally:
            os.unlink(path)

    def test_zip_missing_manifest_returns_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('other.txt', 'hello')
        buf.seek(0)
        path = write_zip_to_tempfile(buf.read())
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert 'manifest.json' in error
        finally:
            os.unlink(path)

    def test_wrong_schema_version_returns_error(self):
        manifest = make_minimal_manifest('N00002')
        manifest['schema_version'] = 999  # Future unsupported version
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert '999' in error or 'schema' in error.lower()
        finally:
            os.unlink(path)

    def test_unknown_manifest_keys_return_error(self):
        manifest = make_minimal_manifest('N00003')
        manifest['unknown_future_key'] = 'some value'
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert 'unknown' in error.lower() or 'unknown_future_key' in error
        finally:
            os.unlink(path)

    def test_tail_number_conflict_returns_conflict(self, aircraft):
        # aircraft fixture has tail_number='N12345'
        manifest = make_minimal_manifest('N12345')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error == 'CONFLICT'
            assert effective_tail == 'N12345'
        finally:
            os.unlink(path)

    def test_tail_number_override_bypasses_conflict(self, aircraft):
        # aircraft has N12345; override with N99998 which doesn't exist
        manifest = make_minimal_manifest('N12345')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(
                path, tail_number_override='N99998'
            )
            assert error is None
            assert effective_tail == 'N99998'
        finally:
            os.unlink(path)

    def test_manifest_missing_tail_number_returns_error(self):
        manifest = make_minimal_manifest('N00004')
        del manifest['aircraft']['tail_number']
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert result_manifest is None
        finally:
            os.unlink(path)

    def test_missing_required_manifest_keys_returns_error(self):
        manifest = make_minimal_manifest('N00005')
        del manifest['components']  # Remove a required key
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert result_manifest is None
        finally:
            os.unlink(path)

    def test_zip_bomb_detected(self):
        """ZIP with compression ratio > 100:1 should be rejected."""
        # Use a large block of repeated bytes (highly compressible)
        # 1 MB of 'a' bytes should compress to well under 10 KB → ratio > 100:1
        big_data = b'a' * (1024 * 1024)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('manifest.json', big_data)
        buf.seek(0)
        raw = buf.read()

        # First verify the ratio is actually > 100:1 in this environment
        with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
            info = zf.getinfo('manifest.json')
            compressed_size = info.compress_size
            uncompressed_size = info.file_size

        if compressed_size == 0:
            pytest.skip("Cannot create zip bomb test: compressed size is 0")
        if uncompressed_size / compressed_size <= 100:
            pytest.skip(
                f"Compression ratio {uncompressed_size / compressed_size:.1f}:1 "
                f"does not exceed 100:1 — cannot test zip bomb detection"
            )

        path = write_zip_to_tempfile(raw)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert 'bomb' in error.lower() or 'ratio' in error.lower()
        finally:
            os.unlink(path)

    def test_path_traversal_rejected(self):
        """ZIP entry with path traversal component should be rejected."""
        manifest = make_minimal_manifest('N00006')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('manifest.json', json.dumps(manifest))
            zf.writestr('../evil.txt', 'malicious content')
        buf.seek(0)
        path = write_zip_to_tempfile(buf.read())
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is not None
            assert result_manifest is None
        finally:
            os.unlink(path)

    def test_v1_schema_accepted(self):
        """Schema version 1 manifests should be accepted (backward compat)."""
        manifest = make_minimal_manifest('N00007')
        manifest['schema_version'] = 1
        # v1 manifests omit 'flight_logs'
        del manifest['flight_logs']
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is None
            assert result_manifest is not None
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# run_aircraft_import_job
# ---------------------------------------------------------------------------

class TestRunAircraftImportJob:
    def test_import_creates_aircraft(self, owner_user):
        manifest = make_minimal_manifest('N88001')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.status == 'completed'

    def test_import_sets_aircraft_on_job(self, owner_user):
        from core.models import Aircraft
        manifest = make_minimal_manifest('N88002')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.aircraft is not None
        assert job.aircraft.tail_number == 'N88002'

    def test_import_creates_owner_role(self, owner_user):
        from core.models import Aircraft, AircraftRole
        manifest = make_minimal_manifest('N88003')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.aircraft is not None
        role = AircraftRole.objects.filter(
            aircraft=job.aircraft, user=owner_user, role='owner'
        ).first()
        assert role is not None

    def test_import_aircraft_exists_in_db(self, owner_user):
        from core.models import Aircraft
        manifest = make_minimal_manifest('N88004')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        assert Aircraft.objects.filter(tail_number='N88004').exists()

    def test_import_with_tail_number_override(self, owner_user):
        from core.models import Aircraft
        # Manifest tail_number is 'N11111', but override to 'N88005'
        manifest = make_minimal_manifest('N11111')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user, tail_number_override='N88005')
        finally:
            if os.path.exists(path):
                os.unlink(path)

        # The override tail number should be used, not the manifest one
        assert Aircraft.objects.filter(tail_number='N88005').exists()
        assert not Aircraft.objects.filter(tail_number='N11111').exists()

    def test_import_sets_result_on_job(self, owner_user):
        manifest = make_minimal_manifest('N88006')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.result is not None
        assert 'aircraft_id' in job.result
        assert job.result['tail_number'] == 'N88006'

    def test_import_cleans_up_zip_file(self, owner_user):
        manifest = make_minimal_manifest('N88007')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        run_aircraft_import_job(job.id, path, owner_user)
        # The job should have deleted the staged zip
        assert not os.path.exists(path)

    def test_import_nonexistent_job_id(self, owner_user):
        """run_aircraft_import_job with invalid job_id should return without error."""
        fake_id = uuid.uuid4()
        manifest = make_minimal_manifest('N88008')
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            # Should not raise
            run_aircraft_import_job(fake_id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_import_from_build_manifest(self, aircraft, owner_user):
        """Import an export of the fixture aircraft using build_manifest output."""
        from core.models import Aircraft
        manifest = build_manifest(aircraft)
        # Must use a different tail number to avoid conflict
        manifest['aircraft']['tail_number'] = 'N88009'
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.status == 'completed'
        assert Aircraft.objects.filter(tail_number='N88009').exists()


# ---------------------------------------------------------------------------
# v1 backward compatibility (flight_time → tach_time)
# ---------------------------------------------------------------------------

class TestV1BackwardCompatibility:
    def test_v1_manifest_with_flight_time_imports(self, owner_user):
        """v1 manifests use 'flight_time'; import should handle it correctly."""
        from core.models import Aircraft
        manifest = make_minimal_manifest('N77001')
        manifest['schema_version'] = 1
        del manifest['flight_logs']  # v1 omits flight_logs
        # Replace tach_time with flight_time (v1 field name)
        del manifest['aircraft']['tach_time']
        manifest['aircraft']['flight_time'] = '150.0'

        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        job = ImportJob.objects.create(status='pending', user=owner_user)
        try:
            run_aircraft_import_job(job.id, path, owner_user)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        job.refresh_from_db()
        assert job.status == 'completed'
        ac = Aircraft.objects.get(tail_number='N77001')
        from decimal import Decimal
        assert ac.tach_time == Decimal('150.0')

    def test_v1_manifest_validates_successfully(self):
        """Schema version 1 passes validate_archive_quick."""
        manifest = make_minimal_manifest('N77002')
        manifest['schema_version'] = 1
        del manifest['flight_logs']
        zip_bytes = make_import_zip(manifest)
        path = write_zip_to_tempfile(zip_bytes)
        try:
            result_manifest, effective_tail, error = validate_archive_quick(path)
            assert error is None
            assert result_manifest['schema_version'] == 1
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# ImportView — POST /api/aircraft/import/
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_import_worker():
    """Prevent the background import thread from accessing the test DB.

    ImportView spawns a daemon thread that calls run_aircraft_import_job.
    In the test environment the SQLite DB is inside a transaction, so the
    thread gets a 'database table is locked' or 'Database access not allowed'
    error and emits PytestUnhandledThreadExceptionWarning.  These view tests
    only care about HTTP response shape, not the job outcome, so we mock the
    worker out entirely.
    """
    with unittest.mock.patch('core.import_export.run_aircraft_import_job'):
        yield


@pytest.mark.usefixtures('mock_import_worker')
class TestImportView:
    # ImportView uses LoginRequiredMixin (Django session auth) — use session_* fixtures.

    def test_owner_can_post_archive(self, session_owner):
        manifest = make_minimal_manifest('N55001')
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        resp = session_owner.post('/api/aircraft/import/', {'archive': zip_file})
        assert resp.status_code == 202

    def test_successful_import_returns_job_id(self, session_owner):
        manifest = make_minimal_manifest('N55002')
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        resp = session_owner.post('/api/aircraft/import/', {'archive': zip_file})
        assert resp.status_code == 202
        data = resp.json()
        assert 'job_id' in data
        uuid.UUID(data['job_id'])

    def test_import_creates_importjob(self, session_owner):
        manifest = make_minimal_manifest('N55003')
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        before_count = ImportJob.objects.count()
        resp = session_owner.post('/api/aircraft/import/', {'archive': zip_file})
        assert resp.status_code == 202
        assert ImportJob.objects.count() == before_count + 1

    def test_no_file_returns_400(self, session_owner):
        resp = session_owner.post('/api/aircraft/import/', {})
        assert resp.status_code == 400

    def test_invalid_zip_returns_400(self, session_owner):
        bad_file = io.BytesIO(b'this is not a zip')
        bad_file.name = 'bad.zip'
        resp = session_owner.post('/api/aircraft/import/', {'archive': bad_file})
        assert resp.status_code == 400

    def test_tail_number_conflict_returns_409(self, aircraft, session_owner):
        """Importing an archive with an existing tail number returns 409."""
        manifest = make_minimal_manifest('N12345')
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        resp = session_owner.post('/api/aircraft/import/', {'archive': zip_file})
        assert resp.status_code == 409
        data = resp.json()
        assert data['error'] == 'tail_number_conflict'
        assert 'staged_id' in data

    def test_unauthenticated_cannot_import(self):
        from django.test import Client
        anon = Client()
        manifest = make_minimal_manifest('N55004')
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        resp = anon.post('/api/aircraft/import/', {'archive': zip_file})
        # LoginRequiredMixin redirects unauthenticated users to login
        assert resp.status_code in (302, 403)


# ---------------------------------------------------------------------------
# ImportJobStatusView — GET /api/aircraft/import/{job_id}/
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures('mock_import_worker')
class TestImportJobStatusView:
    # ImportJobStatusView uses LoginRequiredMixin — use session_* fixtures.

    def _submit_import(self, client, tail_number):
        """Helper: POST a valid archive using a Django session client, return response."""
        manifest = make_minimal_manifest(tail_number)
        zip_bytes = make_import_zip(manifest)
        zip_file = io.BytesIO(zip_bytes)
        zip_file.name = 'test.zip'
        return client.post('/api/aircraft/import/', {'archive': zip_file})

    def test_status_endpoint_returns_job_data(self, session_owner):
        submit_resp = self._submit_import(session_owner, 'N66001')
        assert submit_resp.status_code == 202
        job_id = submit_resp.json()['job_id']

        status_resp = session_owner.get(f'/api/aircraft/import/{job_id}/')
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert 'status' in data

    def test_status_has_events_field(self, session_owner):
        submit_resp = self._submit_import(session_owner, 'N66002')
        job_id = submit_resp.json()['job_id']

        status_resp = session_owner.get(f'/api/aircraft/import/{job_id}/')
        data = status_resp.json()
        assert 'events' in data

    def test_status_has_result_field(self, session_owner):
        submit_resp = self._submit_import(session_owner, 'N66003')
        job_id = submit_resp.json()['job_id']

        status_resp = session_owner.get(f'/api/aircraft/import/{job_id}/')
        data = status_resp.json()
        assert 'result' in data

    def test_other_user_cannot_see_job(self, session_owner, session_other):
        submit_resp = self._submit_import(session_owner, 'N66004')
        job_id = submit_resp.json()['job_id']

        status_resp = session_other.get(f'/api/aircraft/import/{job_id}/')
        assert status_resp.status_code == 404

    def test_nonexistent_job_returns_404(self, session_owner):
        fake_id = uuid.uuid4()
        resp = session_owner.get(f'/api/aircraft/import/{fake_id}/')
        assert resp.status_code == 404

    def test_admin_can_see_any_job(self, session_owner, session_admin):
        submit_resp = self._submit_import(session_owner, 'N66005')
        job_id = submit_resp.json()['job_id']

        status_resp = session_admin.get(f'/api/aircraft/import/{job_id}/')
        assert status_resp.status_code == 200
