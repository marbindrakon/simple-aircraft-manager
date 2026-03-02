import io
import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from health.models import DocumentCollection, Document, DocumentImage

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures local to this module
# ---------------------------------------------------------------------------

@pytest.fixture
def doc_collection(aircraft):
    return DocumentCollection.objects.create(
        aircraft=aircraft,
        name='Test Collection',
    )


@pytest.fixture
def document(aircraft, doc_collection):
    return Document.objects.create(
        aircraft=aircraft,
        name='Test Document',
        doc_type='OTHER',
        collection=doc_collection,
    )


# ---------------------------------------------------------------------------
# DocumentCollectionViewSet
# ---------------------------------------------------------------------------

class TestDocumentCollectionViewSet:
    def test_owner_sees_their_collections(self, owner_client, doc_collection):
        resp = owner_client.get('/api/document-collections/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(doc_collection.id) in ids

    def test_other_client_gets_empty(self, other_client, doc_collection):
        resp = other_client.get('/api/document-collections/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_owner_can_create_collection(self, owner_client, aircraft):
        # DocumentCollectionSerializer uses HyperlinkedRelatedField — aircraft must be a URL
        resp = owner_client.post(
            '/api/document-collections/',
            {
                'aircraft': f'http://testserver/api/aircraft/{aircraft.id}/',
                'name': 'New Collection',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == 'New Collection'

    def test_pilot_cannot_delete_collection(self, pilot_client, aircraft_with_pilot, doc_collection):
        # check_object_permissions restricts pilots from deleting non-PILOT_WRITABLE_MODELS
        resp = pilot_client.delete(f'/api/document-collections/{doc_collection.id}/')
        assert resp.status_code == 403

    def test_other_client_gets_404_on_detail(self, other_client, doc_collection):
        resp = other_client.get(f'/api/document-collections/{doc_collection.id}/')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DocumentViewSet
# ---------------------------------------------------------------------------

class TestDocumentViewSet:
    def test_owner_sees_their_documents(self, owner_client, document):
        resp = owner_client.get('/api/documents/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(document.id) in ids

    def test_other_client_gets_empty(self, other_client, document):
        resp = other_client.get('/api/documents/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_owner_can_create_document(self, owner_client, aircraft):
        # DocumentSerializer uses HyperlinkedRelatedField — aircraft must be a URL
        resp = owner_client.post(
            '/api/documents/',
            {
                'aircraft': f'http://testserver/api/aircraft/{aircraft.id}/',
                'name': 'New Document',
                'doc_type': 'LOG',
            },
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == 'New Document'

    def test_pilot_cannot_delete_document(self, pilot_client, aircraft_with_pilot, document):
        # check_object_permissions restricts pilots from deleting non-PILOT_WRITABLE_MODELS
        resp = pilot_client.delete(f'/api/documents/{document.id}/')
        assert resp.status_code == 403

    def test_owner_can_delete_document(self, owner_client, document):
        doc_id = document.id
        resp = owner_client.delete(f'/api/documents/{doc_id}/')
        assert resp.status_code == 204
        assert not Document.objects.filter(id=doc_id).exists()

    def test_pilot_cannot_delete_document(self, pilot_client, aircraft_with_pilot, document):
        resp = pilot_client.delete(f'/api/documents/{document.id}/')
        assert resp.status_code == 403

    def test_other_client_gets_404_on_detail(self, other_client, document):
        resp = other_client.get(f'/api/documents/{document.id}/')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DocumentImageViewSet
# ---------------------------------------------------------------------------

class TestDocumentImageViewSet:
    def test_owner_sees_their_images(self, owner_client, document):
        # Create an image via direct model creation (skip file validation)
        image_file = SimpleUploadedFile(
            'test.jpg', b'\xff\xd8\xff\xe0test', content_type='image/jpeg'
        )
        img = DocumentImage.objects.create(document=document, image=image_file)
        resp = owner_client.get('/api/document-images/')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data]
        assert str(img.id) in ids

    def test_other_client_sees_nothing(self, other_client, document):
        image_file = SimpleUploadedFile(
            'test.jpg', b'\xff\xd8\xff\xe0test', content_type='image/jpeg'
        )
        DocumentImage.objects.create(document=document, image=image_file)
        resp = other_client.get('/api/document-images/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_owner_can_create_image_via_upload(self, owner_client, document):
        # DocumentImageSerializer uses HyperlinkedRelatedField — document must be a URL
        image_file = SimpleUploadedFile(
            'upload.jpg', b'\xff\xd8\xff\xe0' + b'A' * 100, content_type='image/jpeg'
        )
        resp = owner_client.post(
            '/api/document-images/',
            {'document': f'http://testserver/api/documents/{document.id}/', 'image': image_file},
            format='multipart',
        )
        assert resp.status_code == 201

    def test_pilot_cannot_delete_document_image(self, pilot_client, aircraft_with_pilot, document):
        # check_object_permissions restricts pilots from deleting non-PILOT_WRITABLE_MODELS
        image_file = SimpleUploadedFile(
            'img.jpg', b'\xff\xd8\xff\xe0' + b'C' * 50, content_type='image/jpeg'
        )
        img = DocumentImage.objects.create(document=document, image=image_file)
        resp = pilot_client.delete(f'/api/document-images/{img.id}/')
        assert resp.status_code == 403
