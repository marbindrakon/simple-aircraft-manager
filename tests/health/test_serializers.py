"""
Tests for health/serializers.py — particularly validate_uploaded_file.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers as drf_serializers

from health.serializers import validate_uploaded_file

pytestmark = pytest.mark.django_db


class TestValidateUploadedFile:
    def _make_file(self, name, content=b'content', content_type='application/pdf'):
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return f

    def test_valid_pdf_passes(self):
        f = self._make_file('report.pdf', b'%PDF-1.4', 'application/pdf')
        # Should not raise
        result = validate_uploaded_file(f)
        assert result == f

    def test_valid_jpeg_passes(self):
        f = self._make_file('photo.jpg', b'\xff\xd8\xff', 'image/jpeg')
        result = validate_uploaded_file(f)
        assert result == f

    def test_valid_png_passes(self):
        f = self._make_file('image.png', b'\x89PNG', 'image/png')
        result = validate_uploaded_file(f)
        assert result == f

    def test_invalid_extension_raises(self):
        f = self._make_file('malware.exe', b'MZ', 'application/pdf')
        with pytest.raises(drf_serializers.ValidationError):
            validate_uploaded_file(f)

    def test_invalid_content_type_raises(self):
        """A .pdf file with text/html content-type should be rejected."""
        f = self._make_file('document.pdf', b'<html>', 'text/html')
        with pytest.raises(drf_serializers.ValidationError):
            validate_uploaded_file(f)

    def test_txt_file_passes(self):
        f = self._make_file('notes.txt', b'hello', 'text/plain')
        result = validate_uploaded_file(f)
        assert result == f

    def test_kml_file_passes(self):
        f = self._make_file(
            'track.kml',
            b'<?xml version="1.0"?><kml></kml>',
            'application/vnd.google-earth.kml+xml',
        )
        result = validate_uploaded_file(f)
        assert result == f

    def test_oversized_file_raises(self):
        """File over 512 MB limit should be rejected."""
        f = self._make_file('big.pdf', b'x', 'application/pdf')
        # Fake the size attribute
        f.size = 600 * 1024 * 1024  # 600 MB
        with pytest.raises(drf_serializers.ValidationError, match='512 MB'):
            validate_uploaded_file(f)

    def test_zip_extension_rejected(self):
        f = self._make_file('archive.zip', b'PK', 'application/zip')
        with pytest.raises(drf_serializers.ValidationError):
            validate_uploaded_file(f)
