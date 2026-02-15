"""
Core logbook import logic, shared by the management command and web view.

The main entry point is run_import(), a generator function that:
  1. Optionally calls the Anthropic API to extract LogbookEntry records from images
  2. Creates DocumentCollection, Document, DocumentImage, and LogbookEntry records
  3. Yields progress event dicts throughout so callers can stream or display progress

Each yielded dict has at minimum: {'type': str, 'message': str}
Event types:
  'info'    — normal progress message
  'warning' — non-fatal issue (entry skipped, low confidence, etc.)
  'error'   — batch-level error (Claude API failure, bad JSON, etc.)
  'batch'   — Claude batch started; also has 'batch' and 'total_batches' keys
  'image'   — image uploaded; also has 'filename', 'page', 'total_pages', 'tags' keys
  'entry'   — logbook entry created; also has 'date', 'log_type', 'entry_type',
              'signoff', 'confidence' keys
  'complete' — final event; also has 'entries_created', 'entries_skipped',
               'collection_id', 'document_id' keys
"""

import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Set

from django.core.files import File
from django.db import transaction

from health.models import Document, DocumentCollection, DocumentImage, LogbookEntry


SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}

VALID_LOG_TYPES = {'AC', 'ENG', 'PROP', 'OTHER'}
VALID_ENTRY_TYPES = {'FLIGHT', 'MAINTENANCE', 'INSPECTION', 'HOURS_UPDATE', 'OTHER'}

EXTRACT_SYSTEM_PROMPT = """\
You are an expert aviation maintenance logbook analyst with deep knowledge of FAA regulations,
aircraft maintenance records, and standard logbook formats.

I will provide numbered images of aircraft logbook pages. Extract every logbook entry visible.

IMPORTANT RULES:
- A single entry may span two consecutive pages (look for "continued" or entries that cut off mid-sentence)
- Multiple separate entries may appear on one page (separated by dates, rules, or spacing)
- Some pages are NOT logbook entries: FAA Form 337 (major repair/alteration), yellow tags (8130-3),
  weight and balance records, equipment lists, AD lists, or other administrative forms
- Dates: convert MM/DD/YYYY, MM/DD/YY, or written dates to YYYY-MM-DD; if year is ambiguous
  use context from surrounding entries
- Signoffs: include mechanic name, certificate number (e.g. "A&P #123456"), IA certificate
  number, or repair station number

ENTRY TYPE CLASSIFICATION:
- MAINTENANCE: repairs, part replacements, AD compliance, alterations, STCs, 337s referenced
- INSPECTION: annual, 100-hour, phase checks, pre-buy, progressive, conditional inspections
- FLIGHT: test flights, ferry flights, return-to-service flights
- HOURS_UPDATE: hours log entry with no specific work described
- OTHER: administrative, continued entries, certifications

Field guidelines:
- date: ISO 8601 (YYYY-MM-DD), or null if truly unreadable
- log_type: one of AC (airframe), ENG (engine), PROP (propeller), OTHER
- entry_type: one of MAINTENANCE, INSPECTION, FLIGHT, HOURS_UPDATE, OTHER
- text: verbatim or close paraphrase of entry text; use [?] for illegible words
- signoff_person / signoff_location: string or null (not empty string)
- page_start / page_end: 0-based indices of images in THIS request (not absolute)
- confidence: "high" (clearly legible), "medium" (some guesswork), "low" (mostly illegible)
- non_logbook_pages: 0-based indices of pages that are forms, tags, or non-entry pages
- unparseable_pages: 0-based indices of pages too illegible to extract anything useful
"""

# JSON schema for structured output — guarantees valid, parseable responses.
EXTRACT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": ["string", "null"],
                        "description": "ISO 8601 date (YYYY-MM-DD), or null if unreadable",
                    },
                    "log_type": {
                        "type": "string",
                        "enum": ["AC", "ENG", "PROP", "OTHER"],
                    },
                    "entry_type": {
                        "type": "string",
                        "enum": ["MAINTENANCE", "INSPECTION", "FLIGHT", "HOURS_UPDATE", "OTHER"],
                    },
                    "text": {
                        "type": "string",
                        "description": "Verbatim or close paraphrase of entry text",
                    },
                    "signoff_person": {
                        "type": ["string", "null"],
                        "description": "Name and/or cert number, or null",
                    },
                    "signoff_location": {
                        "type": ["string", "null"],
                        "description": "City/State or airport identifier, or null",
                    },
                    "page_start": {
                        "type": "integer",
                        "description": "0-based index of first image containing this entry",
                    },
                    "page_end": {
                        "type": "integer",
                        "description": "0-based index of last image containing this entry",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "notes": {
                        "type": ["string", "null"],
                        "description": "Parsing notes, uncertainty, or context",
                    },
                },
                "required": [
                    "date", "log_type", "entry_type", "text",
                    "signoff_person", "signoff_location",
                    "page_start", "page_end",
                    "confidence", "notes",
                ],
                "additionalProperties": False,
            },
        },
        "non_logbook_pages": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "0-based indices of non-logbook pages",
        },
        "unparseable_pages": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "0-based indices of illegible pages",
        },
    },
    "required": ["entries", "non_logbook_pages", "unparseable_pages"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_import(
    aircraft,
    image_paths: List[Path],
    collection_name: str,
    doc_name: str,
    doc_type: str = 'LOG',
    model: str = 'claude-sonnet-4-5-20250929',
    upload_only: bool = False,
    log_type_override: Optional[str] = None,
    batch_size: int = 10,
) -> Iterator[dict]:
    """
    Generator.  Yields progress event dicts and creates DB records as a side effect.
    Callers must iterate the generator fully to drive execution.

    The entire DB write is wrapped in a single transaction; if an exception
    propagates out of the generator the transaction is rolled back automatically.
    File-system side effects (uploaded images) are not rolled back on failure.
    """
    yield _ev('info', f"Found {len(image_paths)} image(s) for {aircraft.tail_number}")

    # ------------------------------------------------------------------
    # Upload-only path: no Claude API calls
    # ------------------------------------------------------------------
    if upload_only:
        yield _ev('info', 'Upload-only mode — skipping transcription')
        with transaction.atomic():
            collection, created = DocumentCollection.objects.get_or_create(
                aircraft=aircraft,
                name=collection_name,
                defaults={'description': f'Imported {len(image_paths)} images'},
            )
            yield _ev('info', f"{'Created' if created else 'Using existing'} collection: {collection.name}")

            document = Document.objects.create(
                aircraft=aircraft,
                collection=collection,
                doc_type=doc_type,
                name=doc_name,
                description=f'Imported {len(image_paths)} pages.',
            )
            yield _ev('info', f"Created document: {document.name}")

            yield _ev('info', f"Uploading {len(image_paths)} image(s)…")
            yield from _upload_images(document, image_paths, set(), set())

        yield {
            'type': 'complete',
            'message': 'Upload complete.',
            'entries_created': 0,
            'entries_skipped': 0,
            'collection_id': str(collection.id),
            'document_id': str(document.id),
        }
        return

    # ------------------------------------------------------------------
    # Full transcription path
    # ------------------------------------------------------------------
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        yield _ev('error', 'ANTHROPIC_API_KEY environment variable is not set')
        return

    try:
        import anthropic
    except ImportError:
        yield _ev('error', "The 'anthropic' package is not installed (pip install anthropic)")
        return

    client = anthropic.Anthropic(api_key=api_key)

    yield _ev('info', f"Extracting entries using model: {model}")

    all_entries: list = []
    non_logbook_pages: Set[int] = set()
    unparseable_pages: Set[int] = set()

    yield from _extract_all_entries(
        client, image_paths, model, batch_size,
        all_entries, non_logbook_pages, unparseable_pages,
    )

    if log_type_override:
        for entry in all_entries:
            entry['log_type'] = log_type_override

    yield _ev('info', f"Extraction complete: {len(all_entries)} entries found")
    if non_logbook_pages:
        yield _ev('info', f"Non-logbook pages: {sorted(non_logbook_pages)}")
    if unparseable_pages:
        yield _ev('warning', f"Unparseable pages: {sorted(unparseable_pages)}")

    with transaction.atomic():
        collection, created = DocumentCollection.objects.get_or_create(
            aircraft=aircraft,
            name=collection_name,
            defaults={'description': f'Imported {len(image_paths)} images'},
        )
        yield _ev('info', f"{'Created' if created else 'Using existing'} collection: {collection.name}")

        document = Document.objects.create(
            aircraft=aircraft,
            collection=collection,
            doc_type=doc_type,
            name=doc_name,
            description=(
                f'Imported {len(image_paths)} pages. '
                f'Contains {len(all_entries)} logbook entries.'
            ),
        )
        yield _ev('info', f"Created document: {document.name}")

        yield _ev('info', f"Uploading {len(image_paths)} image(s)…")
        yield from _upload_images(document, image_paths, non_logbook_pages, unparseable_pages)

        yield _ev('info', "Creating logbook entries…")
        entries_created = 0
        entries_skipped = 0
        for entry in all_entries:
            err = _create_single_entry(aircraft, document, entry)
            if err is None:
                entries_created += 1
                yield {
                    'type': 'entry',
                    'message': (
                        f"Entry: {entry.get('date')} | "
                        f"{entry.get('log_type')} | {entry.get('entry_type')}"
                    ),
                    'date': entry.get('date'),
                    'log_type': entry.get('log_type'),
                    'entry_type': entry.get('entry_type'),
                    'signoff': entry.get('signoff_person') or '',
                    'confidence': entry.get('confidence', 'high'),
                }
            else:
                entries_skipped += 1
                yield _ev('warning', f"Skipped entry ({entry.get('date')}): {err}")

    yield {
        'type': 'complete',
        'message': (
            f"Import complete: {entries_created} entries created, "
            f"{entries_skipped} skipped."
        ),
        'entries_created': entries_created,
        'entries_skipped': entries_skipped,
        'collection_id': str(collection.id),
        'document_id': str(document.id),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ev(kind: str, message: str) -> dict:
    return {'type': kind, 'message': message}


def _extract_all_entries(
    client, image_paths, model, batch_size,
    all_entries, non_logbook_pages, unparseable_pages,
):
    """Generator: yields progress events while filling all_entries / page sets."""
    seen_keys: Set[tuple] = set()
    batches = _make_batches(image_paths, batch_size)
    total = len(batches)

    for batch_num, (batch_offset, batch_files) in enumerate(batches, 1):
        yield {
            'type': 'batch',
            'message': (
                f"Batch {batch_num}/{total}: pages {batch_offset}–"
                f"{batch_offset + len(batch_files) - 1} ({len(batch_files)} images)"
            ),
            'batch': batch_num,
            'total_batches': total,
        }

        try:
            result = _call_claude(client, batch_files, model)
        except Exception:
            logging.getLogger(__name__).exception(
                "Claude API error in batch %d", batch_num
            )
            yield _ev('error', f"Claude API error in batch {batch_num}. See server logs for details.")
            for j in range(len(batch_files)):
                unparseable_pages.add(batch_offset + j)
            continue

        entries = result.get('entries') or []
        yield _ev('info', f"  → {len(entries)} entries extracted from batch {batch_num}")

        for entry in entries:
            ps = entry.get('page_start', 0)
            pe = entry.get('page_end', ps)
            entry['page_start'] = batch_offset + ps
            entry['page_end'] = batch_offset + pe

            key = (entry.get('date'), (entry.get('text') or '')[:80].strip())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_entries.append(entry)

        for local_idx in result.get('non_logbook_pages') or []:
            non_logbook_pages.add(batch_offset + local_idx)
        for local_idx in result.get('unparseable_pages') or []:
            unparseable_pages.add(batch_offset + local_idx)


def _make_batches(image_paths: List[Path], batch_size: int):
    """Return list of (offset, files) with 1-image overlap between batches."""
    batches = []
    i = 0
    n = len(image_paths)
    while i < n:
        end = min(i + batch_size, n)
        batches.append((i, image_paths[i:end]))
        if end >= n:
            break
        i = end - 1  # overlap by 1
    return batches


def _call_claude(client, batch_files: List[Path], model: str) -> dict:
    """Send a batch of images to Claude; return parsed JSON dict."""
    _MEDIA_TYPES = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
    }

    content = []
    for local_idx, image_path in enumerate(batch_files):
        content.append({'type': 'text', 'text': f"Page {local_idx} ({image_path.name}):"})
        with open(image_path, 'rb') as fh:
            image_b64 = base64.standard_b64encode(fh.read()).decode('utf-8')
        media_type = _MEDIA_TYPES.get(image_path.suffix.lower(), 'image/jpeg')
        content.append({
            'type': 'image',
            'source': {'type': 'base64', 'media_type': media_type, 'data': image_b64},
        })

    content.append({
        'type': 'text',
        'text': (
            f"These are {len(batch_files)} logbook page image(s), "
            f"indexed 0–{len(batch_files) - 1}. "
            "Extract all logbook entries and return the JSON as specified."
        ),
    })

    response = client.messages.create(
        model=model,
        max_tokens=16384,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': content}],
        output_config={
            'format': {
                'type': 'json_schema',
                'schema': EXTRACT_OUTPUT_SCHEMA,
            },
        },
    )

    if response.stop_reason == 'max_tokens':
        raise ValueError(
            "Response truncated (max_tokens reached) — "
            "batch may have too many entries"
        )

    return json.loads(response.content[0].text)


def _upload_images(
    document: Document,
    image_paths: List[Path],
    non_logbook_pages: Set[int],
    unparseable_pages: Set[int],
) -> Iterator[dict]:
    """Generator: uploads images and yields 'image' progress events."""
    total = len(image_paths)
    for idx, image_path in enumerate(image_paths):
        tags = []
        if idx in non_logbook_pages:
            tags.append('non-logbook')
        if idx in unparseable_pages:
            tags.append('unparseable')

        notes = f"Page {idx + 1} of {total}: {image_path.name}"
        if tags:
            notes += f" [{', '.join(tags)}]"

        doc_image = DocumentImage(document=document, notes=notes)
        with open(image_path, 'rb') as fh:
            doc_image.image.save(image_path.name, File(fh), save=True)

        yield {
            'type': 'image',
            'message': f"Uploaded: {image_path.name}",
            'filename': image_path.name,
            'page': idx + 1,
            'total_pages': total,
            'tags': tags,
        }


def _create_single_entry(aircraft, document: Document, entry: dict) -> Optional[str]:
    """
    Create one LogbookEntry from an extracted entry dict.
    Returns None on success, or an error string describing why it was skipped.
    """
    date_raw = entry.get('date')
    if not date_raw:
        return 'no date'
    try:
        date = datetime.strptime(str(date_raw), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return f"unparseable date: {date_raw!r}"

    text = (entry.get('text') or '').strip()
    if not text:
        return 'empty text'

    log_type = str(entry.get('log_type') or 'AC').upper()
    if log_type not in VALID_LOG_TYPES:
        log_type = 'AC'

    entry_type = str(entry.get('entry_type') or 'OTHER').upper()
    if entry_type not in VALID_ENTRY_TYPES:
        entry_type = 'OTHER'

    signoff_person = (entry.get('signoff_person') or '').strip()
    signoff_location = (entry.get('signoff_location') or '').strip()

    confidence = entry.get('confidence', 'high')
    notes_text = (entry.get('notes') or '').strip()
    if confidence != 'high' and notes_text:
        text = f"{text}\n[Import note ({confidence} confidence): {notes_text}]"

    # Convert 0-based page_start index to 1-based page_number
    page_number = entry.get('page_start')
    if page_number is not None:
        page_number = page_number + 1

    LogbookEntry.objects.create(
        aircraft=aircraft,
        log_type=log_type,
        entry_type=entry_type,
        date=date,
        text=text,
        signoff_person=signoff_person,
        signoff_location=signoff_location,
        log_image=document,
        page_number=page_number,
    )
    return None
