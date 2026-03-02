"""
Tests for aircraft ZIP export (core/export.py and ExportView).
"""
import io
import json
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from core.export import (
    _str,
    _date,
    _decimal,
    _username,
    _file_path,
    build_manifest,
    export_aircraft_zip,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Django session clients for LoginRequiredMixin views (ExportView uses Django
# auth, not DRF token auth — APIClient.force_authenticate won't work here).
# ---------------------------------------------------------------------------

@pytest.fixture
def session_owner(owner_user):
    from django.test import Client
    c = Client()
    c.force_login(owner_user)
    return c

@pytest.fixture
def session_pilot(pilot_user):
    from django.test import Client
    c = Client()
    c.force_login(pilot_user)
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
# Field converter: _str
# ---------------------------------------------------------------------------

class TestStrConverter:
    def test_str_with_string(self):
        assert _str('hello') == 'hello'

    def test_str_with_none(self):
        assert _str(None) is None

    def test_str_with_int(self):
        assert _str(42) == '42'

    def test_str_with_uuid(self):
        import uuid
        u = uuid.uuid4()
        assert _str(u) == str(u)


# ---------------------------------------------------------------------------
# Field converter: _date
# ---------------------------------------------------------------------------

class TestDateConverter:
    def test_date_with_none(self):
        assert _date(None) is None

    def test_date_with_date_object(self):
        d = date(2024, 6, 15)
        result = _date(d)
        assert result == '2024-06-15'

    def test_date_with_datetime_object(self):
        from datetime import datetime
        dt = datetime(2024, 6, 15, 12, 0, 0)
        result = _date(dt)
        assert '2024-06-15' in result


# ---------------------------------------------------------------------------
# Field converter: _decimal
# ---------------------------------------------------------------------------

class TestDecimalConverter:
    def test_decimal_with_none(self):
        assert _decimal(None) is None

    def test_decimal_with_decimal(self):
        d = Decimal('123.45')
        result = _decimal(d)
        assert result == '123.45'

    def test_decimal_is_string(self):
        # _decimal returns string to avoid float precision loss
        result = _decimal(Decimal('0.1'))
        assert isinstance(result, str)

    def test_decimal_large_value(self):
        result = _decimal(Decimal('9999.9'))
        assert result == '9999.9'


# ---------------------------------------------------------------------------
# Field converter: _username
# ---------------------------------------------------------------------------

class TestUsernameConverter:
    def test_username_with_none(self):
        assert _username(None) is None

    def test_username_with_user(self, owner_user):
        result = _username(owner_user)
        assert result == 'owner'


# ---------------------------------------------------------------------------
# Field converter: _file_path
# ---------------------------------------------------------------------------

class TestFilePathConverter:
    def test_file_path_with_none_field(self):
        # An empty/falsy FileField returns None
        # Simulate with a mock-like object
        class FakeField:
            def __bool__(self):
                return False
            name = ''

        result = _file_path(FakeField())
        assert result is None

    def test_file_path_with_valid_field(self):
        class FakeField:
            def __bool__(self):
                return True
            name = 'health/documents/abc123.jpg'

        result = _file_path(FakeField())
        assert result == 'attachments/health/documents/abc123.jpg'

    def test_file_path_prefix(self):
        class FakeField:
            def __bool__(self):
                return True
            name = 'squawks/image.png'

        result = _file_path(FakeField())
        assert result.startswith('attachments/')


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------

class TestBuildManifest:
    def test_returns_dict(self, aircraft):
        manifest = build_manifest(aircraft)
        assert isinstance(manifest, dict)

    def test_has_schema_version(self, aircraft):
        manifest = build_manifest(aircraft)
        assert 'schema_version' in manifest
        assert manifest['schema_version'] == 2

    def test_has_aircraft_section(self, aircraft):
        manifest = build_manifest(aircraft)
        assert 'aircraft' in manifest
        aircraft_data = manifest['aircraft']
        assert aircraft_data['tail_number'] == 'N12345'

    def test_aircraft_section_has_tach_time(self, aircraft):
        manifest = build_manifest(aircraft)
        aircraft_data = manifest['aircraft']
        assert 'tach_time' in aircraft_data
        # _decimal returns a string
        assert aircraft_data['tach_time'] == str(aircraft.tach_time)

    def test_has_all_required_sections(self, aircraft):
        manifest = build_manifest(aircraft)
        required_sections = [
            'schema_version', 'exported_at', 'source_instance', 'aircraft',
            'component_types', 'components', 'document_collections', 'documents',
            'document_images', 'logbook_entries', 'squawks', 'inspection_types',
            'inspection_records', 'ads', 'ad_compliances', 'consumable_records',
            'major_records', 'notes', 'oil_analysis_reports', 'flight_logs',
        ]
        for key in required_sections:
            assert key in manifest, f"Missing key: {key}"

    def test_empty_aircraft_has_empty_list_sections(self, aircraft):
        manifest = build_manifest(aircraft)
        assert manifest['components'] == []
        assert manifest['squawks'] == []
        assert manifest['logbook_entries'] == []

    def test_manifest_with_component(self, aircraft, component):
        manifest = build_manifest(aircraft)
        assert len(manifest['components']) == 1
        comp_data = manifest['components'][0]
        assert comp_data['status'] == 'IN-USE'
        assert comp_data['manufacturer'] == 'Lycoming'

    def test_manifest_with_squawk(self, aircraft, squawk):
        manifest = build_manifest(aircraft)
        assert len(manifest['squawks']) == 1
        sq_data = manifest['squawks'][0]
        assert sq_data['issue_reported'] == 'Brake squeak'
        assert sq_data['priority'] == 1

    def test_manifest_with_logbook_entry(self, aircraft, logbook_entry):
        manifest = build_manifest(aircraft)
        assert len(manifest['logbook_entries']) == 1
        entry_data = manifest['logbook_entries'][0]
        assert entry_data['log_type'] == 'AC'

    def test_manifest_is_json_serializable(self, aircraft, component, squawk, logbook_entry):
        manifest = build_manifest(aircraft)
        # Should not raise
        result = json.dumps(manifest)
        assert isinstance(result, str)

    def test_manifest_aircraft_id_is_string(self, aircraft):
        manifest = build_manifest(aircraft)
        # UUIDs are serialized as strings
        assert isinstance(manifest['aircraft']['id'], str)

    def test_manifest_with_ad(self, aircraft, ad):
        manifest = build_manifest(aircraft)
        assert len(manifest['ads']) >= 1
        ad_data = manifest['ads'][0]
        assert ad_data['name'] == 'AD 2020-01-01'

    def test_manifest_with_inspection_type(self, aircraft, inspection_type):
        manifest = build_manifest(aircraft)
        assert len(manifest['inspection_types']) >= 1


# ---------------------------------------------------------------------------
# export_aircraft_zip
# ---------------------------------------------------------------------------

class TestExportAircraftZip:
    def test_returns_bytes(self, aircraft):
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)
        assert isinstance(buf.read(), bytes)

    def test_output_is_valid_zip(self, aircraft):
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)
        assert zipfile.is_zipfile(buf)

    def test_zip_contains_manifest_json(self, aircraft):
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            assert 'manifest.json' in zf.namelist()

    def test_manifest_json_content_matches_build_manifest(self, aircraft):
        expected = build_manifest(aircraft)
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            manifest_bytes = zf.read('manifest.json')
        actual = json.loads(manifest_bytes.decode('utf-8'))
        # Core fields should match
        assert actual['schema_version'] == expected['schema_version']
        assert actual['aircraft']['tail_number'] == expected['aircraft']['tail_number']

    def test_zip_created_without_error_for_empty_aircraft(self, aircraft):
        # No media files — should not raise FileNotFoundError
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)  # Should not raise

    def test_zip_schema_version_is_2(self, aircraft):
        buf = io.BytesIO()
        export_aircraft_zip(aircraft, buf)
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
        assert manifest['schema_version'] == 2


# ---------------------------------------------------------------------------
# ExportView — API endpoint tests
# ---------------------------------------------------------------------------

class TestExportView:
    # ExportView uses LoginRequiredMixin (Django session auth) — use session_* fixtures.

    def test_owner_can_export(self, aircraft, session_owner):
        resp = session_owner.get(f'/api/aircraft/{aircraft.id}/export/')
        assert resp.status_code == 200

    def test_owner_gets_zip_content_type(self, aircraft, session_owner):
        resp = session_owner.get(f'/api/aircraft/{aircraft.id}/export/')
        content_type = resp.get('Content-Type', '')
        assert 'zip' in content_type or 'octet-stream' in content_type

    def test_owner_response_has_content_disposition(self, aircraft, session_owner):
        resp = session_owner.get(f'/api/aircraft/{aircraft.id}/export/')
        assert resp.status_code == 200
        disposition = resp.get('Content-Disposition', '')
        assert 'attachment' in disposition

    def test_owner_response_filename_contains_tail_number(self, aircraft, session_owner):
        resp = session_owner.get(f'/api/aircraft/{aircraft.id}/export/')
        disposition = resp.get('Content-Disposition', '')
        assert 'N12345' in disposition

    def test_owner_response_filename_contains_zip_extension(self, aircraft, session_owner):
        resp = session_owner.get(f'/api/aircraft/{aircraft.id}/export/')
        disposition = resp.get('Content-Disposition', '')
        assert '.zip' in disposition

    def test_pilot_cannot_export(self, aircraft_with_pilot, session_pilot):
        resp = session_pilot.get(f'/api/aircraft/{aircraft_with_pilot.id}/export/')
        assert resp.status_code == 403

    def test_other_user_gets_403(self, aircraft, session_other):
        # other_user is authenticated but has no role on the aircraft
        resp = session_other.get(f'/api/aircraft/{aircraft.id}/export/')
        assert resp.status_code == 403

    def test_admin_can_export(self, aircraft, session_admin):
        resp = session_admin.get(f'/api/aircraft/{aircraft.id}/export/')
        assert resp.status_code == 200

    def test_nonexistent_aircraft_returns_404(self, session_owner):
        import uuid
        fake_id = uuid.uuid4()
        resp = session_owner.get(f'/api/aircraft/{fake_id}/export/')
        assert resp.status_code == 404
