"""
Oil analysis report extraction from PDF using AI.

Public API:
    run_extraction(pdf_path, model, provider) -> dict
        Extracts oil analysis data from a PDF. Returns the raw extracted dict
        (not saved to DB). Raises ValueError on failure.

    run_oil_analysis_job(job_id, pdf_path, model, provider)
        Background job runner. Fetches ImportJob by job_id, calls run_extraction,
        stores result or error, and cleans up the temp file. Called from a daemon thread.
"""

import base64
import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

_AI_PROMPTS_DIR = Path(__file__).parent / 'ai_prompts'

# Rate-limit / overload retry settings (shared pattern from logbook_import)
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0
_MAX_BACKOFF = 60.0


def _load_prompt(filename: str) -> str:
    return (_AI_PROMPTS_DIR / filename).read_text(encoding='utf-8')


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


def run_extraction(pdf_path: Path, model: str, provider: str = 'parser') -> dict:
    """
    Extract oil analysis data from a PDF.

    provider='parser' (default) uses deterministic lab-specific OCR parsers
    (no API key required). Supports Blackstone and AVLab report formats.

    provider='anthropic' or 'ollama' use AI extraction (legacy path).

    Returns the raw extracted dict conforming to the AircraftOilAnalysisReport schema
    (with a top-level 'samples' array). Does NOT save to DB.

    Raises ValueError on failure or unsupported provider.
    """
    if provider == 'parser':
        from health.oil_analysis_parsers import parse
        return parse(pdf_path)

    system_prompt = _load_prompt('oil_analysis_system_prompt.txt')
    output_schema = json.loads(_load_prompt('oil_analysis_schema.json'))

    if provider == 'anthropic':
        result = _call_anthropic(pdf_path, model, system_prompt, output_schema)
    elif provider == 'ollama':
        result = _call_ollama(pdf_path, model, system_prompt, output_schema)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    _normalize_elements_ppm(result)
    return result


def _normalize_elements_ppm(result: dict) -> None:
    """
    Convert elements_ppm from the AI array format [{element, ppm}, ...]
    to the dict format {element: ppm, ...} expected by the rest of the app.
    Mutates result in place.
    """
    for sample in result.get('samples', []):
        raw = sample.get('elements_ppm')
        if isinstance(raw, list):
            sample['elements_ppm'] = {
                item['element']: item.get('ppm')
                for item in raw
                if isinstance(item, dict) and 'element' in item
            }


def _pdf_to_images(pdf_path: Path, dpi: int = 150) -> list:
    """Render each page of a PDF to PNG bytes using PyMuPDF. Returns a list of bytes objects."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ValueError("The 'pymupdf' package is not installed (pip install pymupdf)")

    doc = fitz.open(str(pdf_path))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes('png'))
    doc.close()
    return images


def _call_anthropic(pdf_path: Path, model: str, system_prompt: str, output_schema: dict) -> dict:
    """Convert PDF to images and send to Anthropic API."""
    import os

    try:
        import anthropic
    except ImportError:
        raise ValueError("The 'anthropic' package is not installed (pip install anthropic)")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    pdf_images = _pdf_to_images(pdf_path)

    content = []
    for img_bytes in pdf_images:
        img_b64 = base64.standard_b64encode(img_bytes).decode('utf-8')
        content.append({
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/png',
                'data': img_b64,
            },
        })
    content.append({
        'type': 'text',
        'text': 'Extract all oil analysis sample data from this report and return the JSON as specified.',
    })

    request_kwargs = dict(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{'role': 'user', 'content': content}],
        output_config={
            'format': {
                'type': 'json_schema',
                'schema': output_schema,
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
                raise ValueError(f"Anthropic rate limit exceeded after {_MAX_RETRIES} retries") from exc
            wait = _retry_after(exc, backoff)
            log.warning("Rate limited (attempt %d/%d), waiting %.1fs", attempt, _MAX_RETRIES, wait)
            time.sleep(wait)
            backoff = min(backoff * 2, _MAX_BACKOFF)
        except anthropic.APIStatusError as exc:
            if exc.status_code == 529 and attempt < _MAX_RETRIES:
                wait = _retry_after(exc, backoff)
                log.warning("API overloaded (attempt %d/%d), waiting %.1fs", attempt, _MAX_RETRIES, wait)
                time.sleep(wait)
                backoff = min(backoff * 2, _MAX_BACKOFF)
            else:
                raise ValueError(f"Anthropic API error: {exc}") from exc

    if response.stop_reason == 'max_tokens':
        raise ValueError("Model response was truncated (max_tokens). Try a smaller PDF.")

    return json.loads(response.content[0].text)


def _call_ollama(pdf_path: Path, model: str, system_prompt: str, output_schema: dict) -> dict:
    """
    Send PDF to Ollama. Note: Ollama's PDF support depends on the model.
    Most Ollama models do NOT support native PDF input; this will likely fail
    unless the model has been specifically set up for document processing.
    """
    try:
        import requests
    except ImportError:
        raise ValueError("The 'requests' package is not installed")

    from django.conf import settings as django_settings
    base_url = getattr(django_settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
    timeout = getattr(django_settings, 'OLLAMA_TIMEOUT', 1200)

    pdf_images = _pdf_to_images(pdf_path)
    images_b64 = [base64.standard_b64encode(img).decode('utf-8') for img in pdf_images]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Extract all oil analysis sample data from this report and return the JSON as specified.",
                "images": images_b64,
            },
        ],
        "format": output_schema,
        "stream": False,
    }

    try:
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        raise ValueError(f"Ollama API error: {exc}") from exc

    result = resp.json()
    if result.get('done_reason') == 'length':
        raise ValueError("Ollama response was truncated (length). The PDF may be too large.")

    raw_content = result.get('message', {}).get('content', '{}')
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ollama returned invalid JSON: {raw_content[:200]}") from exc


def run_oil_analysis_job(job_id, pdf_path: Path, model: str, provider: str) -> None:
    """
    Background job runner for oil analysis AI extraction.
    Called from a daemon thread — do NOT call synchronously in a request.

    job_id   — UUID of an ImportJob (status='pending')
    pdf_path — Path to the temp PDF file (deleted in finally block)
    model    — AI model identifier
    provider — 'anthropic' or 'ollama'
    """
    from health.models import ImportJob

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        log.error("ImportJob %s not found", job_id)
        return

    try:
        job.status = 'running'
        job.save(update_fields=['status'])

        result = run_extraction(pdf_path, model=model, provider=provider)

        job.result = result
        job.status = 'completed'
        job.save(update_fields=['result', 'status'])
    except Exception as exc:
        log.exception("Oil analysis job %s failed", job_id)
        error_event = {'type': 'error', 'message': str(exc)}
        ImportJob.objects.filter(pk=job.pk).update(
            events=ImportJob.objects.values_list('events', flat=True).get(pk=job.pk) + [error_event]
        )
        job.status = 'failed'
        job.save(update_fields=['status'])
    finally:
        pdf_path.unlink(missing_ok=True)
