import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from health.models import Squawk, DocumentImage, FlightLog, Document, DocumentCollection


def _jpeg(name="test.jpg"):
    return SimpleUploadedFile(name, b"\xff\xd8\xff\xe0" + b"X" * 100, content_type="image/jpeg")


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
    collection = DocumentCollection.objects.create(aircraft=aircraft, name="C")
    doc = Document.objects.create(aircraft=aircraft, name="D", doc_type="OTHER", collection=collection)
    img = DocumentImage.objects.create(document=doc)
    assert img.file_size == 0


@pytest.mark.django_db
def test_flight_log_has_file_size_field(aircraft):
    from django.utils import timezone
    log = FlightLog.objects.create(aircraft=aircraft, date=timezone.now().date(), tach_time=Decimal('100.5'))
    assert log.file_size == 0


@pytest.mark.django_db
def test_squawk_file_size_set_on_save_with_attachment(aircraft):
    squawk = Squawk.objects.create(
        aircraft=aircraft, priority=3, issue_reported="test", attachment=_jpeg("s.jpg")
    )
    squawk.refresh_from_db()
    assert squawk.file_size > 0


@pytest.mark.django_db
def test_squawk_file_size_zero_when_no_attachment(aircraft):
    squawk = Squawk.objects.create(aircraft=aircraft, priority=3, issue_reported="test")
    squawk.refresh_from_db()
    assert squawk.file_size == 0


@pytest.mark.django_db
def test_squawk_file_size_cleared_when_attachment_removed(aircraft):
    squawk = Squawk.objects.create(
        aircraft=aircraft, priority=3, issue_reported="test", attachment=_jpeg("s2.jpg")
    )
    squawk.refresh_from_db()
    assert squawk.file_size > 0

    squawk.attachment.delete(save=False)
    squawk.attachment = None
    squawk.save()
    squawk.refresh_from_db()
    assert squawk.file_size == 0


@pytest.mark.django_db
def test_document_image_file_size_set_on_save(aircraft):
    collection = DocumentCollection.objects.create(aircraft=aircraft, name="C")
    doc = Document.objects.create(aircraft=aircraft, name="D", doc_type="OTHER", collection=collection)
    img = DocumentImage.objects.create(document=doc, image=_jpeg("img.jpg"))
    img.refresh_from_db()
    assert img.file_size > 0


@pytest.mark.django_db
def test_flight_log_file_size_set_on_save(aircraft):
    from django.utils import timezone
    kml = SimpleUploadedFile("track.kml", b"<kml/>", content_type="application/vnd.google-earth.kml+xml")
    log = FlightLog.objects.create(aircraft=aircraft, date=timezone.now().date(), tach_time=Decimal('100.5'), track_log=kml)
    log.refresh_from_db()
    assert log.file_size > 0


@pytest.mark.django_db
def test_get_storage_used_bytes_sums_all_models(aircraft):
    from django.utils import timezone
    from core.metrics import get_storage_used_bytes

    # Start at zero
    assert get_storage_used_bytes() == 0

    # Add a squawk with attachment
    Squawk.objects.create(
        aircraft=aircraft, priority=3, issue_reported="s",
        attachment=SimpleUploadedFile("a.jpg", b"\xff\xd8\xff\xe0" + b"Y" * 50, content_type="image/jpeg"),
    )
    used = get_storage_used_bytes()
    assert used > 0

    prev = used
    # Add a flight log with track_log
    FlightLog.objects.create(
        aircraft=aircraft, date=timezone.now().date(), tach_time=Decimal('100.5'),
        track_log=SimpleUploadedFile("t.kml", b"<kml/>", content_type="application/vnd.google-earth.kml+xml"),
    )
    assert get_storage_used_bytes() > prev
