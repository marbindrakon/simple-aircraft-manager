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
import io
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Set

from django.core.files import File
from django.db import transaction

from health.models import Document, DocumentCollection, DocumentImage, ImportJob, LogbookEntry


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

OVERLAP PAGE HANDLING:
The first page in this batch may overlap with the last page of the previous batch.
When "Previously extracted entries" context is provided in the user message, use it
to avoid duplicates:
- SKIP any entry marked Status: COMPLETE that matches by date, signoff, and substantially
  the same text — do not extract it again.
- COMPLETE any entry marked Status: CONTINUES. Extract the full combined entry:
  incorporate the text from the context block for the portion before these pages,
  then append what you read from the current pages. Set page_start to 0 (the overlap
  page in this request).
- EXTRACT normally any entry not represented in the context block at all.
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
    model: str = 'claude-sonnet-4-6',
    provider: str = 'anthropic',
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
    if provider == 'anthropic':
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            yield _ev('error', 'ANTHROPIC_API_KEY environment variable is not set')
            return

        try:
            import anthropic
        except ImportError:
            yield _ev('error', "The 'anthropic' package is not installed (pip install anthropic)")
            return

        provider_client = anthropic.Anthropic(api_key=api_key)
    elif provider == 'ollama':
        from django.conf import settings as django_settings
        provider_client = getattr(django_settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
    else:
        yield _ev('error', f"Unknown provider: {provider}")
        return

    yield _ev('info', f"Extracting entries using model: {model} (provider: {provider})")

    all_entries: list = []
    non_logbook_pages: Set[int] = set()
    unparseable_pages: Set[int] = set()

    yield from _extract_all_entries(
        provider, provider_client, image_paths, model, batch_size,
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

_MAX_TOKENS = 16384

# Rate-limit / overload retry settings
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # seconds
_MAX_BACKOFF = 60.0  # seconds

# If output_tokens exceeds this fraction of max_tokens, proactively shrink
_OUTPUT_PRESSURE_THRESHOLD = 0.80


def _ev(kind: str, message: str) -> dict:
    return {'type': kind, 'message': message}


def _get_image_bytes(path: Path, max_px: int = 1568) -> bytes:
    """
    Read an image file and return bytes suitable for base64 encoding.

    If the longest side exceeds max_px, resize proportionally using LANCZOS
    resampling. Output format:
      - PNG input  → PNG output (preserves any transparency)
      - Everything else → JPEG (avoids TIFF/BMP/GIF encoding edge cases and
        reduces payload size)

    Returns original file bytes unchanged if no resize is needed AND the
    format is already JPEG or PNG (avoids re-encoding overhead).
    """
    from PIL import Image

    suffix = path.suffix.lower()
    is_png = suffix == '.png'

    with Image.open(path) as img:
        w, h = img.size
        longest = max(w, h)

        needs_resize = longest > max_px
        needs_encode = needs_resize or suffix not in ('.jpg', '.jpeg', '.png')

        if not needs_encode:
            with open(path, 'rb') as fh:
                return fh.read()

        if needs_resize:
            scale = max_px / longest
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if is_png:
            img.save(buf, format='PNG')
        else:
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=85, optimize=True)

        return buf.getvalue()


def _format_prior_context(entries: list, overlap_page_idx: int) -> str:
    """
    Format recently extracted entries as carry-forward context for the next batch.

    overlap_page_idx: absolute index of the prior batch's last page. Entries whose
    page_end >= this index are marked CONTINUES (may be cut off at batch boundary);
    others are marked COMPLETE.
    """
    if not entries:
        return ''

    lines = ['Previously extracted entries from the last overlap page:']
    for i, e in enumerate(entries, 1):
        date = e.get('date') or 'unknown date'
        log_type = e.get('log_type') or '?'
        entry_type = e.get('entry_type') or '?'
        signoff = e.get('signoff_person') or ''
        text = (e.get('text') or '').strip()

        header = f"  {i}. [{date}] {log_type}/{entry_type}"
        if signoff:
            header += f" — signed by {signoff}"
        lines.append(header)
        lines.append(f"     Text: {text}")

        status = 'CONTINUES' if (e.get('page_end') or 0) >= overlap_page_idx else 'COMPLETE'
        lines.append(f"     Status: {status}")

    return '\n'.join(lines)


def _extract_all_entries(
    provider, provider_client, image_paths, model, batch_size,
    all_entries, non_logbook_pages, unparseable_pages,
):
    """Generator: yields progress events while filling all_entries / page sets.

    Handles output truncation adaptively: if a batch is truncated, it is split
    into smaller sub-batches and retried.  Also monitors output token pressure
    and proactively shrinks future batch sizes when approaching the limit.
    """
    log = logging.getLogger(__name__)
    seen_key_index: dict = {}       # key → index in all_entries (for keep-longer dedup)
    prior_context_text: Optional[str] = None   # carry-forward for next batch

    # Work queue: list of (batch_offset, batch_files, is_split) to process.
    # Starts with the initial batches, but truncated batches get split
    # and re-queued with is_split=True.
    work_queue = [(off, files, False) for off, files in _make_batches(image_paths, batch_size)]
    batch_num = 0
    total_estimate = len(work_queue)

    while work_queue:
        batch_offset, batch_files, is_split_batch = work_queue.pop(0)
        batch_num += 1

        yield {
            'type': 'batch',
            'message': (
                f"Batch {batch_num}/{total_estimate}: pages {batch_offset}–"
                f"{batch_offset + len(batch_files) - 1} ({len(batch_files)} images)"
            ),
            'batch': batch_num,
            'total_batches': total_estimate,
        }

        try:
            ctx = prior_context_text if not is_split_batch else None
            result = _call_model(provider, provider_client, batch_files, model,
                                 prior_context_text=ctx)
        except Exception:
            log.exception("AI API error in batch %d (provider: %s)", batch_num, provider)
            yield _ev('error', f"AI API error in batch {batch_num}. See server logs for details.")
            for j in range(len(batch_files)):
                unparseable_pages.add(batch_offset + j)
            continue

        # -- Handle truncation by splitting the batch -----------------
        if result['truncated']:
            if len(batch_files) <= 1:
                yield _ev('warning',
                          f"Single-page batch {batch_num} truncated — marking page as unparseable")
                unparseable_pages.add(batch_offset)
                continue

            half = max(1, len(batch_files) // 2)
            sub_b_start = half - 1
            sub_a = (batch_offset, batch_files[:half], True)
            sub_b = (batch_offset + sub_b_start, batch_files[sub_b_start:], True)

            yield _ev('warning',
                      f"Batch {batch_num} truncated ({len(batch_files)} images) — "
                      f"splitting into sub-batches of {len(sub_a[1])} and {len(sub_b[1])}")

            # Insert sub-batches at front of work queue
            work_queue.insert(0, sub_b)
            work_queue.insert(0, sub_a)
            total_estimate += 1  # one batch became two
            continue

        # -- Proactive batch-size shrink for remaining work -----------
        output_tokens = result['output_tokens']
        if (output_tokens > _OUTPUT_PRESSURE_THRESHOLD * _MAX_TOKENS
                and len(batch_files) > 1
                and work_queue):
            new_size = max(1, len(batch_files) // 2)
            yield _ev('info',
                      f"  Output tokens {output_tokens}/{_MAX_TOKENS} "
                      f"(>{_OUTPUT_PRESSURE_THRESHOLD:.0%}) — "
                      f"shrinking remaining batches to {new_size} images")
            # Re-batch the remaining images from the work queue
            remaining_offsets_files = []
            for off, files, _ in work_queue:
                for i, f in enumerate(files):
                    remaining_offsets_files.append((off + i, f))
            # Deduplicate by offset (overlap pages may appear twice)
            seen_offsets: set = set()
            deduped: List[tuple] = []
            for off, f in remaining_offsets_files:
                if off not in seen_offsets:
                    seen_offsets.add(off)
                    deduped.append((off, f))
            deduped.sort(key=lambda x: x[0])
            # Re-batch with the new smaller size
            new_queue = []
            for i in range(0, len(deduped), new_size):
                chunk = deduped[i:i + new_size]
                chunk_offset = chunk[0][0]
                chunk_files = [f for _, f in chunk]
                new_queue.append((chunk_offset, chunk_files, False))
            work_queue = new_queue
            total_estimate = batch_num + len(work_queue)

        # -- Collect results ------------------------------------------
        data = result['data']
        entries = data.get('entries') or []
        yield _ev('info', f"  → {len(entries)} entries extracted from batch {batch_num}")

        batch_entries_added = []

        for entry in entries:
            ps = entry.get('page_start', 0)
            pe = entry.get('page_end', ps)
            entry['page_start'] = batch_offset + ps
            entry['page_end'] = batch_offset + pe

            key = (entry.get('date'), (entry.get('text') or '')[:80].strip())
            new_text_len = len((entry.get('text') or '').strip())

            if key in seen_key_index:
                existing_idx = seen_key_index[key]
                existing_text_len = len((all_entries[existing_idx].get('text') or '').strip())
                if new_text_len > existing_text_len:
                    all_entries[existing_idx] = entry
                continue

            seen_key_index[key] = len(all_entries)
            all_entries.append(entry)
            batch_entries_added.append(entry)

        for local_idx in data.get('non_logbook_pages') or []:
            non_logbook_pages.add(batch_offset + local_idx)
        for local_idx in data.get('unparseable_pages') or []:
            unparseable_pages.add(batch_offset + local_idx)

        # Update carry-forward context for the next non-split batch
        if not is_split_batch and batch_entries_added:
            overlap_page_idx = batch_offset + len(batch_files) - 1
            n_ctx = min(3, len(batch_entries_added))
            prior_context_text = _format_prior_context(
                batch_entries_added[-n_ctx:], overlap_page_idx
            )


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
        # Overlap by 1 page to catch cross-page entries, but only when
        # batch_size > 1 (otherwise i would never advance).
        i = end - 1 if batch_size > 1 else end
    return batches


def _call_model(
    provider: str,
    provider_client,
    batch_files: List[Path],
    model: str,
    prior_context_text: Optional[str] = None,
) -> dict:
    """
    Dispatch to the correct provider function.
    Returns dict with keys: 'data', 'truncated', 'output_tokens'.
    """
    if provider == 'anthropic':
        return _call_anthropic(provider_client, batch_files, model,
                               prior_context_text=prior_context_text)
    elif provider == 'ollama':
        return _call_ollama(provider_client, batch_files, model,
                            prior_context_text=prior_context_text)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_anthropic(
    client,
    batch_files: List[Path],
    model: str,
    prior_context_text: Optional[str] = None,
) -> dict:
    """
    Send a batch of images to the Anthropic API; return dict with keys:
      'data'          — parsed JSON response
      'truncated'     — True if stop_reason was max_tokens
      'output_tokens' — number of output tokens used
    Raises anthropic.APIStatusError / anthropic.RateLimitError on
    unrecoverable API errors (rate-limit retries are handled here).
    """
    import anthropic

    content = []

    if prior_context_text:
        content.append({'type': 'text', 'text': prior_context_text})

    for local_idx, image_path in enumerate(batch_files):
        content.append({'type': 'text', 'text': f"Page {local_idx} ({image_path.name}):"})
        image_bytes = _get_image_bytes(image_path)
        image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')
        media_type = 'image/png' if image_path.suffix.lower() == '.png' else 'image/jpeg'
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

    log = logging.getLogger(__name__)
    request_kwargs = dict(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': content}],
        output_config={
            'format': {
                'type': 'json_schema',
                'schema': EXTRACT_OUTPUT_SCHEMA,
            },
        },
    )

    backoff = _INITIAL_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.messages.create(**request_kwargs)
            break
        except anthropic.RateLimitError as exc:
            if attempt == _MAX_RETRIES:
                raise
            wait = _retry_after(exc, backoff)
            log.warning("Rate limited (attempt %d/%d), waiting %.1fs",
                        attempt, _MAX_RETRIES, wait)
            time.sleep(wait)
            backoff = min(backoff * 2, _MAX_BACKOFF)
        except anthropic.APIStatusError as exc:
            if exc.status_code == 529 and attempt < _MAX_RETRIES:
                wait = _retry_after(exc, backoff)
                log.warning("API overloaded (attempt %d/%d), waiting %.1fs",
                            attempt, _MAX_RETRIES, wait)
                time.sleep(wait)
                backoff = min(backoff * 2, _MAX_BACKOFF)
            else:
                raise

    truncated = response.stop_reason == 'max_tokens'
    output_tokens = getattr(response.usage, 'output_tokens', 0)

    data = {}
    if not truncated:
        data = json.loads(response.content[0].text)

    return {
        'data': data,
        'truncated': truncated,
        'output_tokens': output_tokens,
    }


def _call_ollama(
    base_url: str,
    batch_files: List[Path],
    model: str,
    prior_context_text: Optional[str] = None,
) -> dict:
    """
    Send a batch of images to a local Ollama instance; return dict with keys:
      'data'          — parsed JSON response
      'truncated'     — True if done_reason was 'length'
      'output_tokens' — number of output tokens used (eval_count)
    """
    import requests

    log = logging.getLogger(__name__)

    images = []
    image_labels = []
    for local_idx, image_path in enumerate(batch_files):
        image_bytes = _get_image_bytes(image_path)
        image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')
        images.append(image_b64)
        image_labels.append(f"Page {local_idx} ({image_path.name})")

    base_instruction = (
        f"These are {len(batch_files)} logbook page image(s), "
        f"indexed 0\u2013{len(batch_files) - 1}. "
        f"Page labels: {', '.join(image_labels)}. "
        "Extract all logbook entries and return the JSON as specified."
    )
    if prior_context_text:
        user_text = f"{prior_context_text}\n\n{base_instruction}"
    else:
        user_text = base_instruction

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_text,
                "images": images,
            },
        ],
        "format": EXTRACT_OUTPUT_SCHEMA,
        "stream": False,
    }

    from django.conf import settings as django_settings
    timeout = getattr(django_settings, 'OLLAMA_TIMEOUT', 1200)

    resp = requests.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    result = resp.json()

    truncated = result.get('done_reason') == 'length'
    output_tokens = result.get('eval_count', 0)

    data = {}
    if not truncated:
        raw_content = result.get('message', {}).get('content', '{}')
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            log.warning("Ollama returned invalid JSON: %s", raw_content[:200])
            data = {'entries': [], 'non_logbook_pages': [], 'unparseable_pages': []}

    return {
        'data': data,
        'truncated': truncated,
        'output_tokens': output_tokens,
    }


def _retry_after(exc, default_backoff: float) -> float:
    """Extract retry-after seconds from an API error, falling back to default_backoff."""
    headers = getattr(exc, 'response', None)
    if headers is not None:
        headers = getattr(headers, 'headers', {})
        retry_after = headers.get('retry-after')
        if retry_after:
            try:
                return max(float(retry_after), 0.5)
            except (ValueError, TypeError):
                pass
    return default_backoff


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

        doc_image = DocumentImage(document=document, notes=notes, order=idx)
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


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

def run_import_job(job_id, tmpdir, image_paths, **kwargs):
    """
    Run an import as a background job, writing events to ImportJob.

    Intended to be called from a daemon thread.  All kwargs are forwarded
    to run_import() (collection_name, doc_name, doc_type, model, etc.).
    """
    import shutil

    log = logging.getLogger(__name__)

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        log.error("ImportJob %s not found", job_id)
        return

    job.status = 'running'
    job.save(update_fields=['status', 'updated_at'])

    try:
        aircraft = job.aircraft
        for event in run_import(aircraft=aircraft, image_paths=image_paths, **kwargs):
            job.events.append(event)
            if event.get('type') == 'complete':
                job.result = event
            job.save(update_fields=['events', 'result', 'updated_at'])

        job.status = 'completed'
        job.save(update_fields=['status', 'updated_at'])

    except Exception:
        log.exception("ImportJob %s failed", job_id)
        error_event = _ev('error', 'An unexpected error occurred during import.')
        job.events.append(error_event)
        job.status = 'failed'
        job.save(update_fields=['events', 'status', 'updated_at'])

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
