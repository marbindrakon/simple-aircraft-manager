"""
Anonymize oil-analysis lab PDFs for use as parser-test fixtures.

The replacement specs (which contain PII strings as keys) live in
`test-pdfs/anonymize_config.py` — that path is gitignored, so the actual PII
never enters version control. This file is just the engine.

Replacements operate on Tj/TJ text-showing operators in each page's content
stream. When PII is split across a Tj literal followed by a TJ array (e.g.,
'609' + ['1', kern, '15A'] for engine S/N "609115A"), the script collapses the
involved ops into a single Tj with the dummy text. Visual layout shifts
slightly but the parser's coordinate-band logic still finds the right tokens
because the replacement is anchored at the original Tj's position.

Usage:

    python scripts/anonymize_oil_pdfs.py

Reads `test-pdfs/<src>` -> writes `tests/fixtures/oil_pdfs/<dst>`.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ByteStringObject, ContentStream, NameObject


REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIR = REPO_ROOT / "test-pdfs"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "oil_pdfs"
CONFIG_PATH = PRIVATE_DIR / "anonymize_config.py"


@dataclass
class PdfSpec:
    src: str
    dst: str
    tj_replacements: dict[str, str] = field(default_factory=dict)
    merged_spans: list[tuple[int, int, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "PdfSpec":
        return cls(
            src=d["src"],
            dst=d["dst"],
            tj_replacements=dict(d.get("tj_replacements", {})),
            merged_spans=[tuple(s) for s in d.get("merged_spans", [])],
        )


def _load_specs() -> list[PdfSpec]:
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}", file=sys.stderr)
        print("Create it with a SPECS list — see scripts/anonymize_oil_pdfs.py docstring.",
              file=sys.stderr)
        sys.exit(1)
    spec_obj = importlib.util.spec_from_file_location("anonymize_config", CONFIG_PATH)
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)
    return [PdfSpec.from_dict(d) for d in mod.SPECS]


def _decode_str(s) -> str:
    if isinstance(s, bytes):
        return s.decode("latin-1", errors="replace")
    return str(s)


def _encode_text(s: str) -> ByteStringObject:
    return ByteStringObject(s.encode("latin-1", errors="replace"))


def _apply_replacements(content_stream: ContentStream, spec: PdfSpec) -> int:
    """Mutate operations in place. Returns count of edits applied."""
    edits = 0

    spans_by_start: dict[int, tuple[int, str]] = {
        start: (end, dummy) for start, end, dummy in spec.merged_spans
    }
    to_delete: set[int] = set()
    new_ops = []
    i = 0
    while i < len(content_stream.operations):
        if i in spans_by_start:
            end, dummy = spans_by_start[i]
            new_ops.append(([_encode_text(dummy)], b"Tj"))
            for j in range(i + 1, end + 1):
                to_delete.add(j)
            edits += 1
            i = end + 1
            continue
        if i in to_delete:
            i += 1
            continue
        new_ops.append(content_stream.operations[i])
        i += 1

    final_ops = []
    for operands, op in new_ops:
        if op == b"Tj" and operands:
            s_str = _decode_str(operands[0])
            if s_str in spec.tj_replacements:
                final_ops.append(([_encode_text(spec.tj_replacements[s_str])], b"Tj"))
                edits += 1
                continue
        final_ops.append((operands, op))

    content_stream.operations = final_ops
    return edits


def anonymize(spec: PdfSpec) -> None:
    src = PRIVATE_DIR / spec.src
    dst = FIXTURE_DIR / spec.dst
    if not src.exists():
        print(f"  SKIP {spec.src}: source not found at {src}", file=sys.stderr)
        return

    reader = PdfReader(str(src))
    writer = PdfWriter()
    total_edits = 0
    for page in reader.pages:
        content = page.get("/Contents")
        if content is not None:
            cs = ContentStream(content.get_object(), reader)
            total_edits += _apply_replacements(cs, spec)
            page[NameObject("/Contents")] = cs
        writer.add_page(page)

    # Strip metadata that may contain identifying info.
    writer.add_metadata({"/Producer": "anonymized", "/Creator": "anonymized"})

    with open(dst, "wb") as fp:
        writer.write(fp)
    print(f"  {spec.src} -> {dst.relative_to(REPO_ROOT)}  ({total_edits} edits)")


def main() -> int:
    if not PRIVATE_DIR.exists():
        print(f"Private originals dir not found: {PRIVATE_DIR}", file=sys.stderr)
        return 1
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    specs = _load_specs()
    print(f"Anonymizing {len(specs)} PDF(s) from {PRIVATE_DIR} -> {FIXTURE_DIR}")
    for spec in specs:
        anonymize(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
