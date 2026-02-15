"""
Django management command to import aircraft logbook pages from a directory of images.

The core import logic lives in health/logbook_import.py and is shared with the
web-based import UI.  This command is a thin CLI wrapper around that service.

Usage:
    python manage.py import_logbook /path/to/images --aircraft N5516G
    python manage.py import_logbook /path/to/images --aircraft N5516G --model claude-haiku-4-5-20251001
    python manage.py import_logbook /path/to/images --aircraft N5516G --dry-run
    python manage.py import_logbook /path/to/images --aircraft N5516G --upload-only

Environment variables:
    ANTHROPIC_API_KEY   Required (unless --upload-only or --dry-run).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Aircraft
from health.logbook_import import SUPPORTED_EXTENSIONS, run_import


class Command(BaseCommand):
    help = (
        "Import aircraft logbook pages from a directory of images using Claude AI. "
        "Creates a DocumentCollection, Document, DocumentImages, and LogbookEntry records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            type=str,
            help="Path to directory containing logbook page images (JPEG, PNG, etc.)",
        )
        parser.add_argument(
            "--aircraft",
            required=True,
            type=str,
            metavar="TAIL_NUMBER",
            help="Aircraft tail number to associate records with (e.g. N5516G)",
        )
        parser.add_argument(
            "--model",
            default=None,
            metavar="MODEL_ID",
            help="AI model ID from LOGBOOK_IMPORT_MODELS settings (default: settings.LOGBOOK_IMPORT_DEFAULT_MODEL)",
        )
        parser.add_argument(
            "--collection-name",
            default=None,
            metavar="NAME",
            help="Name for the DocumentCollection (default: directory name)",
        )
        parser.add_argument(
            "--doc-name",
            default=None,
            metavar="NAME",
            help="Name for the Document record (default: directory name)",
        )
        parser.add_argument(
            "--doc-type",
            default="LOG",
            choices=["LOG", "ALTER", "REPORT", "ESTIMATE", "DISC", "INVOICE", "AIRCRAFT", "OTHER"],
            help="Document type (default: LOG)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            metavar="N",
            help=(
                "Images per Claude API call (default: 10). "
                "Batches overlap by 1 page to catch cross-page entries."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Extract and display entries without writing any database records.",
        )
        parser.add_argument(
            "--upload-only",
            action="store_true",
            help="Skip transcription — create collection/document/images only.",
        )
        parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Create logbook entries but skip uploading the source images.",
        )
        parser.add_argument(
            "--log-type",
            default=None,
            choices=["AC", "ENG", "PROP", "OTHER"],
            help="Override log_type for all extracted entries.",
        )

    def handle(self, *args, **options):
        directory = Path(options["directory"]).expanduser().resolve()
        if not directory.is_dir():
            raise CommandError(f"Directory does not exist: {directory}")

        image_files = sorted(
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if not image_files:
            raise CommandError(f"No supported image files found in {directory}")

        self.stdout.write(
            f"Found {len(image_files)} image(s) in: {self.style.HTTP_INFO(str(directory))}"
        )

        aircraft = self._get_aircraft(options["aircraft"])
        self.stdout.write(
            f"Aircraft: {self.style.HTTP_INFO(aircraft.tail_number)} "
            f"— {aircraft.make} {aircraft.model} (ID: {aircraft.id})"
        )

        collection_name = options["collection_name"] or directory.name
        doc_name = options["doc_name"] or directory.name

        # Resolve model and provider from settings registry
        model_id = options["model"] or settings.LOGBOOK_IMPORT_DEFAULT_MODEL
        model_registry = {m['id']: m for m in settings.LOGBOOK_IMPORT_MODELS}
        if model_id not in model_registry:
            available = [m['id'] for m in settings.LOGBOOK_IMPORT_MODELS]
            raise CommandError(
                f"Unknown model '{model_id}'. "
                f"Available models: {available}"
            )
        provider = model_registry[model_id]['provider']

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDRY RUN — no database records will be created\n"))
            self._dry_run(aircraft, image_files, options, model_id, provider)
            return

        # Consume the generator, rendering each event to the terminal
        generator = run_import(
            aircraft=aircraft,
            image_paths=image_files,
            collection_name=collection_name,
            doc_name=doc_name,
            doc_type=options["doc_type"],
            model=model_id,
            provider=provider,
            upload_only=options["upload_only"],
            log_type_override=options["log_type"],
            batch_size=options["batch_size"],
        )
        result = None
        for event in generator:
            self._render_event(event)
            if event.get("type") == "complete":
                result = event

        if result:
            self.stdout.write(f"\n  DocumentCollection ID : {result['collection_id']}")
            self.stdout.write(f"  Document ID           : {result['document_id']}")

    # -------------------------------------------------------------------------

    def _get_aircraft(self, tail_number: str) -> Aircraft:
        qs = Aircraft.objects.filter(tail_number__iexact=tail_number)
        count = qs.count()
        if count == 0:
            available = list(
                Aircraft.objects.values_list("tail_number", flat=True).order_by("tail_number")
            )
            raise CommandError(
                f"Aircraft '{tail_number}' not found. "
                f"Available: {available or '(none)'}"
            )
        if count > 1:
            ids = list(qs.values_list("id", flat=True))
            raise CommandError(
                f"Multiple aircraft found with tail number '{tail_number}': {ids}"
            )
        return qs.get()

    def _render_event(self, event: dict):
        """Map an event dict to styled terminal output."""
        kind = event.get("type", "info")
        message = event.get("message", "")

        if kind == "error":
            self.stdout.write(self.style.ERROR(f"  ✗ {message}"))
        elif kind == "warning":
            self.stdout.write(self.style.WARNING(f"  ⚠ {message}"))
        elif kind == "complete":
            self.stdout.write(self.style.SUCCESS(f"\n✓ {message}"))
        elif kind == "entry":
            conf = event.get("confidence", "high")
            conf_mark = "" if conf == "high" else f" [{conf}]"
            hours = f"  {event.get('hours')} hrs" if event.get("hours") else ""
            self.stdout.write(
                f"  + {event.get('date')} | {event.get('log_type')} | "
                f"{event.get('entry_type')}{hours}{conf_mark}"
            )
        elif kind == "image":
            tags = event.get("tags") or []
            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            self.stdout.write(
                f"  ↑ {event.get('filename')} "
                f"({event.get('page')}/{event.get('total_pages')}){tag_str}"
            )
        elif kind == "batch":
            self.stdout.write(f"\n{message}")
        else:
            self.stdout.write(f"  {message}")

    def _dry_run(self, aircraft, image_files, options, model_id, provider):
        """Extract via AI and display results without writing to DB."""
        import os

        from health.logbook_import import _extract_all_entries

        if provider == 'anthropic':
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise CommandError("ANTHROPIC_API_KEY environment variable is not set")
            try:
                import anthropic
            except ImportError:
                raise CommandError("The 'anthropic' package is not installed")
            provider_client = anthropic.Anthropic(api_key=api_key)
        elif provider == 'ollama':
            provider_client = settings.OLLAMA_BASE_URL
        else:
            raise CommandError(f"Unknown provider: {provider}")

        all_entries = []
        non_logbook_pages = set()
        unparseable_pages = set()

        for event in _extract_all_entries(
            provider, provider_client, image_files, model_id, options["batch_size"],
            all_entries, non_logbook_pages, unparseable_pages,
        ):
            self._render_event(event)

        if options["log_type"]:
            for e in all_entries:
                e["log_type"] = options["log_type"]

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"EXTRACTED ENTRIES ({len(all_entries)} total)")
        self.stdout.write("="*70)
        for i, entry in enumerate(all_entries, 1):
            ps, pe = entry.get("page_start", "?"), entry.get("page_end", "?")
            pages = f"{ps}" if ps == pe else f"{ps}–{pe}"
            conf = entry.get("confidence", "?")
            self.stdout.write(
                f"\n[{i:>3}] {entry.get('date') or 'NO DATE'}  "
                f"{entry.get('log_type')}/{entry.get('entry_type')}  "
                f"pages:{pages}  conf:{conf}"
            )
            if entry.get("aircraft_hours_at_entry"):
                self.stdout.write(f"       Hours: {entry['aircraft_hours_at_entry']}")
            if entry.get("signoff_person"):
                self.stdout.write(f"       Signoff: {entry['signoff_person']}")
            text = (entry.get("text") or "")[:300]
            for line in text.splitlines():
                self.stdout.write(f"       {line}")

        self.stdout.write(f"\nNon-logbook pages: {sorted(non_logbook_pages)}")
        self.stdout.write(f"Unparseable pages: {sorted(unparseable_pages)}")
