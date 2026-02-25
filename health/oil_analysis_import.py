"""
Oil analysis report extraction from PDF using AI.

Public API:
    run_extraction(pdf_path, model, provider) -> dict
        Extracts oil analysis data from a PDF. Returns the raw extracted dict
        (not saved to DB). Raises ValueError on failure.
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


def run_extraction(pdf_path: Path, model: str, provider: str) -> dict:
    """
    Extract oil analysis data from a PDF using AI.

    Returns the raw extracted dict conforming to the AircraftOilAnalysisReport schema
    (with a top-level 'samples' array). Does NOT save to DB.

    Raises ValueError on API failure or unsupported provider.
    """
    system_prompt = _load_prompt('oil_analysis_system_prompt.txt')
    output_schema = json.loads(_load_prompt('oil_analysis_schema.json'))

    if provider == 'anthropic':
        return _call_anthropic(pdf_path, model, system_prompt, output_schema)
    elif provider == 'ollama':
        return _call_ollama(pdf_path, model, system_prompt, output_schema)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_anthropic(pdf_path: Path, model: str, system_prompt: str, output_schema: dict) -> dict:
    """Send PDF to Anthropic API using native document support."""
    import os

    try:
        import anthropic
    except ImportError:
        raise ValueError("The 'anthropic' package is not installed (pip install anthropic)")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode('utf-8')

    content = [
        {
            'type': 'document',
            'source': {
                'type': 'base64',
                'media_type': 'application/pdf',
                'data': pdf_b64,
            },
        },
        {
            'type': 'text',
            'text': 'Extract all oil analysis sample data from this report and return the JSON as specified.',
        },
    ]

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

    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode('utf-8')

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Extract all oil analysis sample data from this report and return the JSON as specified.",
                "images": [pdf_b64],
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
