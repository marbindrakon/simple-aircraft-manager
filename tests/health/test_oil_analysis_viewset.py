import datetime
import io

import pytest

from health.models import OilAnalysisReport, ImportJob

pytestmark = pytest.mark.django_db


def _get_results(data):
    """Extract list of results from either paginated or non-paginated DRF response."""
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _make_report(aircraft, lab='Blackstone', lab_number='BSL-001'):
    return OilAnalysisReport.objects.create(
        aircraft=aircraft,
        sample_date=datetime.date.today(),
        lab=lab,
        lab_number=lab_number,
    )


class TestOilAnalysisReportList:
    def test_owner_sees_their_reports(self, owner_client, aircraft):
        report = _make_report(aircraft)
        resp = owner_client.get('/api/oil-analysis-reports/')
        assert resp.status_code == 200
        ids = [r['id'] for r in _get_results(resp.data)]
        assert str(report.id) in ids

    def test_other_client_sees_empty_list(self, other_client, aircraft):
        _make_report(aircraft)
        resp = other_client.get('/api/oil-analysis-reports/')
        assert resp.status_code == 200
        assert _get_results(resp.data) == []

    def test_admin_sees_all_reports(self, admin_client, aircraft):
        report = _make_report(aircraft)
        resp = admin_client.get('/api/oil-analysis-reports/')
        assert resp.status_code == 200
        ids = [r['id'] for r in _get_results(resp.data)]
        assert str(report.id) in ids

    def test_pilot_can_list_reports(self, pilot_client, aircraft_with_pilot):
        _make_report(aircraft_with_pilot)
        resp = pilot_client.get('/api/oil-analysis-reports/')
        assert resp.status_code == 200


class TestOilAnalysisReportCreate:
    def test_owner_can_create_report(self, owner_client, aircraft):
        payload = {
            'aircraft': str(aircraft.id),
            'sample_date': str(datetime.date.today()),
            'lab': 'Blackstone',
            'lab_number': 'BSL-123',
            'elements_ppm': {},
        }
        resp = owner_client.post('/api/oil-analysis-reports/', payload, format='json')
        assert resp.status_code == 201
        assert OilAnalysisReport.objects.filter(aircraft=aircraft).exists()

    def test_admin_can_create_report(self, admin_client, aircraft):
        payload = {
            'aircraft': str(aircraft.id),
            'sample_date': str(datetime.date.today()),
            'lab': 'AVLab',
            'lab_number': 'AV-456',
            'elements_ppm': {'iron': 5.0},
        }
        resp = admin_client.post('/api/oil-analysis-reports/', payload, format='json')
        assert resp.status_code == 201

    def test_pilot_cannot_create_report_on_unowned_aircraft(self, pilot_client, aircraft):
        """A pilot with no role on an aircraft cannot create an oil analysis report for it."""
        # pilot_client has no role on `aircraft` (only aircraft_with_pilot has pilot role)
        payload = {
            'aircraft': str(aircraft.id),
            'sample_date': str(datetime.date.today()),
            'lab': 'Blackstone',
            'lab_number': 'BSL-789',
            'elements_ppm': {},
        }
        resp = pilot_client.post('/api/oil-analysis-reports/', payload, format='json')
        assert resp.status_code == 403

    def test_pilot_with_role_cannot_create_report(self, pilot_client, aircraft_with_pilot):
        """Oil analysis reports are owner-only; a pilot with a role is still denied."""
        payload = {
            'aircraft': str(aircraft_with_pilot.id),
            'sample_date': str(datetime.date.today()),
            'lab': 'Blackstone',
            'lab_number': 'BSL-790',
            'elements_ppm': {},
        }
        resp = pilot_client.post('/api/oil-analysis-reports/', payload, format='json')
        assert resp.status_code == 403

    def test_invalid_elements_ppm_rejected(self, owner_client, aircraft):
        payload = {
            'aircraft': str(aircraft.id),
            'sample_date': str(datetime.date.today()),
            'lab': 'Blackstone',
            'lab_number': 'BSL-001',
            'elements_ppm': {'not_a_real_element': 999},
        }
        resp = owner_client.post('/api/oil-analysis-reports/', payload, format='json')
        assert resp.status_code == 400


class TestOilAnalysisReportDetail:
    def test_owner_can_get_detail(self, owner_client, aircraft):
        report = _make_report(aircraft)
        resp = owner_client.get(f'/api/oil-analysis-reports/{report.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == str(report.id)

    def test_other_client_gets_404(self, other_client, aircraft):
        report = _make_report(aircraft)
        resp = other_client.get(f'/api/oil-analysis-reports/{report.id}/')
        assert resp.status_code == 404


class TestOilAnalysisAiExtract:
    def test_missing_file_returns_400(self, owner_client, aircraft):
        resp = owner_client.post(
            f'/api/aircraft/{aircraft.id}/oil_analysis_ai_extract/',
            {},
            format='multipart',
        )
        assert resp.status_code == 400
        assert 'error' in resp.data

    def test_valid_pdf_upload_returns_202_with_job_id(self, owner_client, aircraft):
        """
        Upload a PDF to the oil_analysis_ai_extract endpoint.
        The view should accept the file, create an ImportJob, and return 202.
        We mock the background thread to avoid DB access in a background thread
        after the test transaction is torn down.
        """
        from unittest.mock import patch

        # Minimal valid PDF bytes
        pdf_bytes = (
            b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj '
            b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj '
            b'3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj '
            b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n'
            b'0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>'
            b'startxref\n190\n%%EOF'
        )
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = 'test.pdf'

        # Patch threading.Thread.start so the background job doesn't actually run
        with patch('threading.Thread.start'):
            resp = owner_client.post(
                f'/api/aircraft/{aircraft.id}/oil_analysis_ai_extract/',
                {'file': pdf_file},
                format='multipart',
            )

        # The view should accept the upload and return 202 with a job_id
        assert resp.status_code == 202
        assert 'job_id' in resp.data
        # Verify an ImportJob was created
        assert ImportJob.objects.filter(
            aircraft=aircraft, job_type='oil_analysis'
        ).exists()

    def test_invalid_file_extension_rejected(self, owner_client, aircraft):
        bad_file = io.BytesIO(b'not a pdf')
        bad_file.name = 'evil.exe'
        resp = owner_client.post(
            f'/api/aircraft/{aircraft.id}/oil_analysis_ai_extract/',
            {'file': bad_file},
            format='multipart',
        )
        assert resp.status_code == 400

    def test_pilot_cannot_use_ai_extract(self, pilot_client, aircraft_with_pilot):
        """
        The oil_analysis_ai_extract action is on AircraftViewSet; pilots only get
        IsAircraftPilotOrAbove for allowed actions. oil_analysis_ai_extract falls
        under owner-only actions in get_permissions routing.
        """
        pdf_bytes = b'%PDF-1.4\n%%EOF'
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = 'test.pdf'
        resp = pilot_client.post(
            f'/api/aircraft/{aircraft_with_pilot.id}/oil_analysis_ai_extract/',
            {'file': pdf_file},
            format='multipart',
        )
        assert resp.status_code in (403, 404)
