"""
Management command: export_aircraft

Usage:
    python manage.py export_aircraft <tail_number> [-o OUTPUT_FILE]

Exports all data for the given aircraft to a .sam.zip archive.
"""

import io
import os
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from core.models import Aircraft
from core.export import export_aircraft_zip


class Command(BaseCommand):
    help = "Export aircraft data to a .sam.zip archive."

    def add_arguments(self, parser):
        parser.add_argument(
            'tail_number',
            help="Tail number of the aircraft to export.",
        )
        parser.add_argument(
            '-o', '--output',
            dest='output',
            default=None,
            help="Output file path (default: ./<tail_number>_<YYYYMMDD>.sam.zip).",
        )

    def handle(self, *args, **options):
        tail_number = options['tail_number'].strip()

        try:
            aircraft = Aircraft.objects.get(tail_number=tail_number)
        except Aircraft.DoesNotExist:
            raise CommandError(f"Aircraft with tail number '{tail_number}' not found.")
        except Aircraft.MultipleObjectsReturned:
            raise CommandError(
                f"Multiple aircraft with tail number '{tail_number}'. "
                "Use the admin interface to export by ID."
            )

        output_path = options['output'] or f"{tail_number}_{date.today().strftime('%Y%m%d')}.sam.zip"

        self.stdout.write(f"Exporting {aircraft} to {output_path}…")

        try:
            with open(output_path, 'wb') as fh:
                export_aircraft_zip(aircraft, fh)
        except OSError as exc:
            raise CommandError(f"Could not write to '{output_path}': {exc}")

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete: {output_path} ({size_mb:.1f} MB)"
            )
        )
