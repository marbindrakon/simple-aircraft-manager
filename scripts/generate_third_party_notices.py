"""Generate THIRD-PARTY-NOTICES.txt and per-package license files.

Default mode (no --save-licenses):
  Writes THIRD-PARTY-NOTICES.txt — a compact attribution table (name,
  version, license, author, URL) plus the static block from
  notices_extras.txt.  No full license boilerplate.  Uses pip-licenses
  in JSON mode WITHOUT --with-license-file.

--save-licenses <dir> mode:
  Writes one <pkg>-<ver>.txt (verbatim license text) and one
  NOTICE-<pkg>-<ver>.txt (verbatim NOTICE text, Apache-2.0 packages) per
  package into <dir>/.  Skips entries where text is empty or "UNKNOWN".
  Uses pip-licenses with --with-license-file --with-notice-file.

Both modes are called from the build scripts — compact table first, then
--save-licenses so PyInstaller can bundle the individual license files.

Output path defaults to <repo>/THIRD-PARTY-NOTICES.txt, overridable via
--output.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRAS_FILE = Path(__file__).resolve().parent / "notices_extras.txt"
DEFAULT_OUTPUT = REPO_ROOT / "THIRD-PARTY-NOTICES.txt"

_PIP_LICENSES_IGNORE = [
    "--ignore-packages", "pip-licenses", "prettytable", "tomli", "wcwidth",
]

HEADER = """\
Simple Aircraft Manager — Third-Party Notices
==============================================

This bundle aggregates the Python packages, web assets, fonts, and runtime
components listed below. Each entry retains its original license; the project
itself is dedicated to the public domain (see LICENSE).

Generated automatically at build time from the bundle's runtime dependency
set. Do not hand-edit — modify scripts/notices_extras.txt or the build
scripts instead.

Full license texts for each Python package are provided in the licenses/
directory bundled alongside this file.
"""

SEP = "=" * 64


def _run_pip_licenses(extra_flags: list[str]) -> list[dict]:
    cmd = [
        sys.executable, "-m", "piplicenses",
        "--format=json",
        "--with-authors",
        "--with-urls",
        *_PIP_LICENSES_IGNORE,
        *extra_flags,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    pkgs = json.loads(result.stdout)
    return sorted(pkgs, key=lambda p: p["Name"].lower())


def run_pip_licenses_compact() -> list[dict]:
    return _run_pip_licenses([])


def run_pip_licenses_full() -> list[dict]:
    return _run_pip_licenses([
        "--with-license-file",
        "--no-license-path",
        "--with-notice-file",
    ])


def _safe_filename(name: str, version: str) -> str:
    """Sanitize a package name+version into a safe filename component."""
    safe = re.sub(r"[^\w.\-]", "_", f"{name}-{version}")
    return safe


def build_compact_notices(packages: list[dict], extras_text: str) -> str:
    parts: list[str] = [HEADER]

    parts.append(SEP)
    parts.append("Python packages")
    parts.append(SEP)
    parts.append("")

    for pkg in packages:
        name = pkg["Name"]
        version = pkg["Version"]
        license_raw = pkg.get("License", "UNKNOWN")
        author = (pkg.get("Author") or "").strip()
        url = (pkg.get("URL") or "").strip()

        parts.append(f"{name} {version}")
        parts.append(f"  License: {license_raw}")
        if author and author != "UNKNOWN":
            parts.append(f"  Author:  {author}")
        if url and url != "UNKNOWN":
            parts.append(f"  URL:     {url}")
        parts.append("")

    parts.append(extras_text)
    return "\n".join(parts)


def save_licenses(packages: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for pkg in packages:
        name = pkg["Name"]
        version = pkg["Version"]
        stem = _safe_filename(name, version)

        lic_text = (pkg.get("LicenseText") or "").strip()
        if lic_text and lic_text != "UNKNOWN":
            (output_dir / f"{stem}.txt").write_text(lic_text, encoding="utf-8")
            written += 1

        notice_text = (pkg.get("NoticeText") or "").strip()
        if notice_text and notice_text != "UNKNOWN":
            (output_dir / f"NOTICE-{stem}.txt").write_text(
                notice_text, encoding="utf-8"
            )
            written += 1

    print(f"Wrote {written} license/notice files to {output_dir}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output file for the compact table (default: %(default)s)",
    )
    parser.add_argument(
        "--save-licenses",
        metavar="DIR",
        type=Path,
        default=None,
        help="Write per-package license/notice files into DIR",
    )
    args = parser.parse_args()

    if not EXTRAS_FILE.exists():
        print(f"ERROR: extras file missing: {EXTRAS_FILE}", file=sys.stderr)
        return 1

    if args.save_licenses is not None:
        packages = run_pip_licenses_full()
        save_licenses(packages, args.save_licenses)
    else:
        packages = run_pip_licenses_compact()
        extras_text = EXTRAS_FILE.read_text(encoding="utf-8")
        content = build_compact_notices(packages, extras_text)
        args.output.write_text(content, encoding="utf-8")
        print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
