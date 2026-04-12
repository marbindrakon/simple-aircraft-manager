import pytest
from decimal import Decimal
from health.models import Squawk, DocumentImage, FlightLog


@pytest.mark.django_db
def test_squawk_has_file_size_field(aircraft):
    squawk = Squawk.objects.create(
        aircraft=aircraft,
        priority=3,
        issue_reported="Test squawk",
    )
    assert squawk.file_size == 0


@pytest.mark.django_db
def test_document_image_has_file_size_field(aircraft):
    from health.models import Document, DocumentCollection
    collection = DocumentCollection.objects.create(aircraft=aircraft, name="C")
    doc = Document.objects.create(aircraft=aircraft, name="D", doc_type="OTHER", collection=collection)
    img = DocumentImage.objects.create(document=doc)
    assert img.file_size == 0


@pytest.mark.django_db
def test_flight_log_has_file_size_field(aircraft):
    from django.utils import timezone
    log = FlightLog.objects.create(aircraft=aircraft, date=timezone.now().date(), tach_time=Decimal('100.5'))
    assert log.file_size == 0
