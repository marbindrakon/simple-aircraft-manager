"""
Management command: import_aircraft

Usage:
    python manage.py import_aircraft <archive_path> --owner <username>
        [--tail-number <value>] [--dry-run]

Imports an aircraft from a .sam.zip archive.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.import_export import validate_archive_quick

User = get_user_model()


class Command(BaseCommand):
    help = "Import aircraft data from a .sam.zip archive."

    def add_arguments(self, parser):
        parser.add_argument(
            'archive_path',
            help="Path to the .sam.zip archive to import.",
        )
        parser.add_argument(
            '--owner',
            required=True,
            help="Username of the user who will own the imported aircraft.",
        )
        parser.add_argument(
            '--tail-number',
            dest='tail_number',
            default=None,
            help="Override the tail number from the manifest (required if a conflict exists).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help="Validate the archive without creating any records.",
        )

    def handle(self, *args, **options):
        archive_path = options['archive_path']
        username = options['owner']
        tail_number_override = options.get('tail_number')
        dry_run = options['dry_run']

        # Resolve archive
        if not os.path.exists(archive_path):
            raise CommandError(f"Archive file not found: {archive_path}")

        # Resolve owner
        try:
            owner = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' not found.")

        self.stdout.write(f"Validating {archive_path}…")

        manifest, effective_tail, error = validate_archive_quick(
            archive_path, tail_number_override
        )

        if error == 'CONFLICT':
            raise CommandError(
                f"Tail number conflict: an aircraft with tail number '{effective_tail}' "
                f"already exists. Use --tail-number to specify an alternate tail number."
            )

        if error:
            raise CommandError(f"Validation failed: {error}")

        self.stdout.write(f"Archive valid. Effective tail number: {effective_tail}")

        record_counts = {
            key: len(manifest.get(key, []))
            for key in [
                'components', 'component_types', 'document_collections', 'documents',
                'document_images', 'logbook_entries', 'squawks', 'inspection_types',
                'inspection_records', 'ads', 'ad_compliances', 'consumable_records',
                'major_records', 'notes',
            ]
        }
        for key, count in record_counts.items():
            if count:
                self.stdout.write(f"  {key}: {count}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete — no records created."))
            return

        self.stdout.write(f"Importing as owner '{owner.username}'…")

        # Run import synchronously (management command context — no background thread needed)
        from core.import_export import _run_import
        from health.models import ImportJob

        job = ImportJob.objects.create(status='running', user=owner)

        events_buffer = []

        def ev(event_type, message):
            events_buffer.append({'type': event_type, 'message': message})
            if event_type == 'error':
                self.stderr.write(f"  [ERROR] {message}")
            elif event_type == 'warning':
                self.stdout.write(f"  [WARN]  {message}")
            else:
                self.stdout.write(f"  {message}")

        try:
            _run_import(job, archive_path, owner, tail_number_override, ev)
        except Exception as exc:
            job.status = 'failed'
            job.save(update_fields=['status', 'updated_at'])
            raise CommandError(f"Import failed: {exc}") from exc
        finally:
            # Persist events to the job
            job.events = events_buffer
            job.save(update_fields=['events', 'updated_at'])

        if job.status == 'failed':
            raise CommandError("Import failed. See errors above.")

        result = job.result or {}
        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete. Aircraft '{result.get('tail_number', effective_tail)}' "
                f"created (ID: {result.get('aircraft_id', '?')})."
            )
        )
        if result.get('warnings'):
            self.stdout.write(f"Warnings ({len(result['warnings'])}):")
            for w in result['warnings']:
                self.stdout.write(f"  - {w}")
