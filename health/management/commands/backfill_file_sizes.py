"""
Backfill file_size on Squawk, DocumentImage, and FlightLog rows created before
the file_size column was added. Safe to re-run — overwrites existing values.
"""
from django.core.management.base import BaseCommand

from health.models import DocumentImage, FlightLog, Squawk


class Command(BaseCommand):
    help = "Backfill file_size for existing Squawk, DocumentImage, and FlightLog records."

    def handle(self, *args, **options):
        self.stdout.write("Backfilling file sizes...")
        self._backfill(Squawk, "attachment")
        self._backfill(DocumentImage, "image")
        self._backfill(FlightLog, "track_log")
        self.stdout.write(self.style.SUCCESS("Done."))

    def _backfill(self, model, field_name):
        updated = 0
        for obj in model.objects.all():
            field = getattr(obj, field_name)
            if field:
                try:
                    size = field.size
                except (FileNotFoundError, OSError):
                    size = 0
            else:
                size = 0
            model.objects.filter(pk=obj.pk).update(file_size=size)
            updated += 1
        self.stdout.write(f"  {model.__name__}: {updated} records updated")
