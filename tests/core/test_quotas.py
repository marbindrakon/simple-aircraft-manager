import pytest
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from health.models import Document, DocumentCollection


@pytest.mark.django_db
class TestAircraftQuota:
    def test_create_aircraft_within_quota(self, owner_client):
        """Creating aircraft within quota limit should succeed."""
        with override_settings(SAM_MAX_AIRCRAFT=5):
            response = owner_client.post(
                "/api/aircraft/",
                {
                    "tail_number": "N12345",
                    "make": "Cessna",
                    "model": "172",
                },
                format="json",
            )
            assert response.status_code == status.HTTP_201_CREATED

    def test_create_aircraft_at_quota_limit(self, owner_client, owner_user, aircraft_factory):
        """Creating aircraft when at quota limit should fail with 403."""
        with override_settings(SAM_MAX_AIRCRAFT=2):
            aircraft_factory(owner=owner_user)
            aircraft_factory(owner=owner_user)

            response = owner_client.post(
                "/api/aircraft/",
                {
                    "tail_number": "N99999",
                    "make": "Piper",
                    "model": "Cherokee",
                },
                format="json",
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Aircraft limit reached" in response.data["detail"]

    def test_create_aircraft_unlimited_when_unset(self, owner_client):
        """When SAM_MAX_AIRCRAFT is not set, no limit is enforced."""
        with override_settings(SAM_MAX_AIRCRAFT=None):
            response = owner_client.post(
                "/api/aircraft/",
                {
                    "tail_number": "N12345",
                    "make": "Cessna",
                    "model": "172",
                },
                format="json",
            )
            assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestStorageQuota:
    def test_upload_within_quota(self, owner_client, aircraft):
        """File upload within storage quota should succeed."""
        collection = DocumentCollection.objects.create(aircraft=aircraft, name="Test Collection")
        document = Document.objects.create(
            aircraft=aircraft,
            name="Test Doc",
            doc_type="OTHER",
            collection=collection,
        )
        image_file = SimpleUploadedFile(
            "upload.jpg", b"\xff\xd8\xff\xe0" + b"A" * 100, content_type="image/jpeg"
        )
        # Simulate 0 bytes used so even the smallest quota passes
        with override_settings(SAM_STORAGE_QUOTA_GB=1):
            with patch("health.serializers.dir_size", return_value=0):
                resp = owner_client.post(
                    "/api/document-images/",
                    {
                        "document": f"http://testserver/api/documents/{document.id}/",
                        "image": image_file,
                    },
                    format="multipart",
                )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_upload_exceeding_quota(self, owner_client, aircraft, owner_user):
        """File upload that would exceed storage quota should fail with 400."""
        collection = DocumentCollection.objects.create(aircraft=aircraft, name="Test Collection 2")
        document = Document.objects.create(
            aircraft=aircraft,
            name="Test Doc 2",
            doc_type="OTHER",
            collection=collection,
        )
        image_file = SimpleUploadedFile(
            "big.jpg", b"\xff\xd8\xff\xe0" + b"B" * 100, content_type="image/jpeg"
        )

        # Simulate that 1 GB is already used against a 1 GB quota — any upload will exceed it.
        used_bytes = 1 * 1024 * 1024 * 1024  # 1 GB already used
        quota_gb = 1  # 1 GB quota

        with override_settings(SAM_STORAGE_QUOTA_GB=quota_gb):
            with patch("health.serializers.dir_size", return_value=used_bytes):
                resp = owner_client.post(
                    "/api/document-images/",
                    {
                        "document": f"http://testserver/api/documents/{document.id}/",
                        "image": image_file,
                    },
                    format="multipart",
                )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # The error message should mention storage quota
        error_text = str(resp.data)
        assert "quota" in error_text.lower() or "Storage quota" in error_text
