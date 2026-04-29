# License Compliance Plan — Desktop Bundle

**Status:** in progress. Resume tomorrow at Phase 2.

The desktop bundle (macOS `.app`, Windows installer, Linux Flatpak) aggregates
~60 third-party Python packages plus vendored web assets and fonts. This
document captures what's done, what's left, and the rationale for each step.
The starting audit and full license matrix lives in this conversation's
history; below is the action-oriented plan distilled out of it.

## Phase 1 — Resolve PyMuPDF (AGPL) ✅ DONE

**Outcome:** swapped to pypdfium2 (Apache-2 / BSD-3). See commits
`a12df37` and `89ef92a`. Bundle is now free of AGPL dependencies. Performance
within 6%, parser output bit-identical against four real lab PDFs (verified
via golden-fixture regression test).

The other practical option ("embrace AGPL — keep PyMuPDF, ship AGPL.txt, add
a 'Source code' link in the UI") would have been low-effort but is hostile
to a future plugin ecosystem: any in-process plugin would become part of the
covered work and have to ship under AGPL. Avoiding that constraint was worth
the day of porting.

## Phase 2 — Generate a real THIRD-PARTY-NOTICES.txt

The current 35-line [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) covers
3 packages out of ~60. Replace with a generated, comprehensive file.

**Steps:**
1. Add `pip-licenses` to a new `requirements-build.txt` (build-time only, not
   runtime; keep it out of the bundled deps).
2. Add a generation step to all three build scripts:
   - [desktop/build-macos.sh](desktop/build-macos.sh)
   - [desktop/build-windows.ps1](desktop/build-windows.ps1)
   - [desktop/flatpak/build-flatpak.sh](desktop/flatpak/build-flatpak.sh)

   Command:
   ```
   pip-licenses --format=plain-vertical --with-license-file --no-license-path \
                --with-notice-file --with-authors --with-urls \
                --output-file THIRD-PARTY-NOTICES.txt
   ```
   Run *after* `pip install` of all runtime deps (so it picks up exactly
   what's in the bundle), *before* PyInstaller runs (so it gets bundled).

3. Append a hand-written **"Web assets and fonts"** section covering items
   that pip-licenses won't see — text below is a starting template:

   ```
   --- Web assets ---

   Alpine.js 3.x — MIT
     Copyright (c) 2019-present Caleb Porzio and contributors
     https://github.com/alpinejs/alpine

   Chart.js 4 — MIT
     Copyright (c) 2014-2024 Chart.js Contributors
     https://github.com/chartjs/Chart.js

   PatternFly 5.3.1 — MIT
     Copyright (c) Red Hat, Inc.
     https://github.com/patternfly/patternfly

   --- Fonts ---

   Red Hat Display, Red Hat Text, Red Hat Mono — SIL Open Font License 1.1
     Copyright 2021 Red Hat, Inc.
     Reserved Font Name: "Red Hat"
     https://github.com/RedHatOfficial/RedHatFont

   PatternFly Icon Font (pficon) — MIT
     Copyright (c) Red Hat, Inc.

   Font Awesome 6 Free — fonts under SIL OFL 1.1, icons under CC BY 4.0
     Copyright 2024 Fonticons, Inc.
     https://fontawesome.com
   ```

4. Append the existing **WebView2 Runtime** language unchanged (it's
   bootstrapped, not bundled, so no redistribution obligation — but the user
   note belongs here for transparency).

5. Verify [desktop/sam-macos.spec:46](desktop/sam-macos.spec:46) and the
   corresponding line in [desktop/sam-windows.spec](desktop/sam-windows.spec)
   still copy `THIRD-PARTY-NOTICES.txt` into the bundle root. They do today
   (commit `492e13d`), but the path is repo-relative so the generation step
   has to run before PyInstaller.

**Done when:** `THIRD-PARTY-NOTICES.txt` in the built bundle has one entry
per `pip list` line, each with copyright + license text, plus the web-asset
and font block.

## Phase 3 — Surface notices in the UI

Required (or strongly suggested) by Apache-2.0, MIT, OFL, and CC BY 4.0 for
any user-facing application.

**Steps:**
1. Add an **About** route under `/about/` (or fold into the existing first-run
   setup screen at `desktop/setup_view.py`). Markup pattern: read
   `THIRD-PARTY-NOTICES.txt` from `STATIC_ROOT` and display in a `<pre>` block,
   plus links to the project [LICENSE](LICENSE) (Unlicense) and to the project
   GitHub URL.

2. Add a single line of attribution (CC BY 4.0 for Font Awesome icons is the
   only one that strictly demands visible attribution):

   > Icons by Font Awesome (CC BY 4.0). Fonts by Red Hat (SIL OFL 1.1).

   Either in the About screen or in the page footer.

3. The About link should be reachable from the main nav (existing aircraft-
   list page) with a one-line addition to [core/templates/base.html](core/templates/base.html).

**Done when:** clicking "About" in the desktop bundle shows the bundle's
`THIRD-PARTY-NOTICES.txt` and links to LICENSE.

## Phase 4 — Font-specific OFL packaging

OFL 1.1 requires the license text to *travel with* the font binaries.

**Steps:** create these new files (license texts copied verbatim from the
upstream font repos):

- `core/static/vendor/assets/fonts/RedHatDisplay/LICENSE-OFL.txt`
- `core/static/vendor/assets/fonts/RedHatText/LICENSE-OFL.txt`
- `core/static/vendor/assets/fonts/RedHatMono/LICENSE-OFL.txt`
- `core/static/vendor/assets/fonts/webfonts/LICENSE-OFL.txt` (Font Awesome)
- `core/static/vendor/assets/pficon/LICENSE.txt` (PatternFly MIT)

These get picked up automatically by `manage.py collectstatic` and end up in
both the Django staticfiles dir and the PyInstaller bundle (because
[desktop/sam-macos.spec:39](desktop/sam-macos.spec:39) ships
`build/staticfiles` wholesale).

**Done when:** font license texts are in the bundle next to the `.woff2`s.

## Phase 5 — Fix metadata that's drifting

1. **Flatpak metainfo** — [desktop/flatpak/app.simpleaircraft.Manager.metainfo.xml:7](desktop/flatpak/app.simpleaircraft.Manager.metainfo.xml:7)
   currently declares `<project_license>Unlicense</project_license>`. That's
   true for *our* code but misleading for the *aggregated bundle* which
   contains BSD/MIT/Apache/MPL/ZPL components. AppStream wants an SPDX
   expression. Simplest valid form:

   ```xml
   <project_license>Unlicense AND BSD-3-Clause AND MIT AND Apache-2.0 AND MPL-2.0 AND ZPL-2.1 AND OFL-1.1 AND CC-BY-4.0</project_license>
   ```

   Flathub reviewers will check this and reject if it's wrong.

2. **README** — [README.md](README.md) should add a single line under the
   license section:

   > This project's source is in the public domain (see [LICENSE](LICENSE)).
   > Distributed binaries aggregate third-party software listed in
   > [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

**Done when:** `flatpak run --command=appstream-util app.simpleaircraft.Manager validate` passes (or equivalent local check).

## Phase 6 — CI guardrail

One-line shell check that fails the build if a new dep with a copyleft license
slips in. Add to the existing GitHub Actions workflow.

**Step:**
```yaml
- name: License gate
  run: |
    pip install pip-licenses
    pip-licenses --format=csv --fail-on="GPL;LGPL;AGPL;SSPL;BUSL;CDDL;EPL"
```

The allowlist is whatever passes today (BSD, MIT, Apache-2, MPL, ZPL, OFL,
CC BY, ISC, PSF, HPND). The fail-on list catches the next AGPL surprise
before it ships.

**Done when:** CI fails on a synthetic PR that adds an AGPL dep, and passes
on `main`.

## Reference — license inventory

Captured from `pip list` + `pipdeptree` + per-package metadata. None of these
are blockers as of commit `89ef92a`; they all just need attribution.

| License family | Packages | Notes |
|---|---|---|
| MIT | anthropic, Markdown, keyring, bottle, proxy_tools, platformdirs, whitenoise, altgraph, macholib, pyobjc-* (5), h11, charset-normalizer, jaraco.classes/functools/context, more-itertools, pluggy, docstring_parser, sniffio (MIT/Apache-2), Pillow (HPND, MIT-style), pypdf | Standard MIT notice |
| BSD-2/3 | Django, djangorestframework, django-filter, asgiref, sqlparse, pywebview, httpx, httpcore, pytest-django, pypdfium2 (Apache-2 / BSD-3) | Standard BSD notice |
| Apache-2.0 | openai, requests, distro, django-prometheus, pyinstaller-hooks-contrib (dual w/ GPLv2), coverage, pypdfium2 | Include each project's NOTICE file when present (openai, requests have NOTICEs) |
| MPL-2.0 (file-level) | certifi (CA data, MPL), tqdm (MPL+MIT mix) | Ship the `.py`/`.pem` source files in the bundle as-is (PyInstaller already does); include MPL-2.0 text once |
| GPLv2 + bootloader exception | pyinstaller (bootloader binary in `dist/SimpleAircraftManager/`) | Exception explicitly permits redistribution as part of non-GPL apps. Include PyInstaller's COPYING.txt. |
| ZPL 2.1 | waitress | Permissive, ship LICENSE text |
| SIL OFL 1.1 | Red Hat Display/Text/Mono, Font Awesome 6 Free fonts | License text travels with binaries; Reserved Font Name = "Red Hat" |
| CC BY 4.0 | Font Awesome 6 Free icons | Visible attribution required |

## Reference — file paths

| Concern | Path |
|---|---|
| Project LICENSE (Unlicense) | [LICENSE](LICENSE) |
| Bundled third-party notices | [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) |
| Vendored web assets | [core/static/vendor/](core/static/vendor/) |
| Vendored fonts | `core/static/vendor/assets/fonts/` and `assets/pficon/` |
| PyInstaller specs | [desktop/sam-macos.spec](desktop/sam-macos.spec), [desktop/sam-windows.spec](desktop/sam-windows.spec) |
| Flatpak manifest | [desktop/flatpak/app.simpleaircraft.Manager.yml](desktop/flatpak/app.simpleaircraft.Manager.yml) |
| Flatpak AppStream metadata | [desktop/flatpak/app.simpleaircraft.Manager.metainfo.xml](desktop/flatpak/app.simpleaircraft.Manager.metainfo.xml) |
| Build scripts | [desktop/build-macos.sh](desktop/build-macos.sh), [desktop/build-windows.ps1](desktop/build-windows.ps1), [desktop/flatpak/build-flatpak.sh](desktop/flatpak/build-flatpak.sh) |
