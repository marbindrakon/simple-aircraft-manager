import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from health.models import DocumentImage, FlightLog, Squawk

logger = logging.getLogger(__name__)


def _file_size(field_file):
    """Return size of a FieldFile in bytes, or 0 if the field is empty or the file is missing."""
    if not field_file:
        return 0
    try:
        return field_file.size
    except (FileNotFoundError, OSError):
        logger.warning("Could not read size for %s", field_file.name)
        return 0


@receiver(post_save, sender=Squawk, dispatch_uid='health.signals.update_squawk_file_size')
def update_squawk_file_size(sender, instance, **kwargs):
    sender.objects.filter(pk=instance.pk).update(file_size=_file_size(instance.attachment))


@receiver(post_save, sender=DocumentImage, dispatch_uid='health.signals.update_document_image_file_size')
def update_document_image_file_size(sender, instance, **kwargs):
    sender.objects.filter(pk=instance.pk).update(file_size=_file_size(instance.image))


@receiver(post_save, sender=FlightLog, dispatch_uid='health.signals.update_flight_log_file_size')
def update_flight_log_file_size(sender, instance, **kwargs):
    sender.objects.filter(pk=instance.pk).update(file_size=_file_size(instance.track_log))
