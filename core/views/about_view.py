"""About / third-party notices page.

Reads the bundle's THIRD-PARTY-NOTICES.txt at request time and renders it
inside a templated layout. Required (or strongly suggested) by Apache-2.0,
MIT, OFL-1.1, and CC BY 4.0 attribution clauses for any user-facing
distribution. See COMPLIANCE_PLAN.md (Phase 3).

Path resolution:
- Dev / settings_prod: settings.BASE_DIR is the repo root.
- PyInstaller bundle: settings.py lives at <_MEIPASS>/simple_aircraft_manager/
  settings.py, so BASE_DIR == _MEIPASS — exactly where the spec files copy
  THIRD-PARTY-NOTICES.txt.
- Flatpak: code lives at /app/share/simple-aircraft-manager/, and the
  flatpak manifest installs THIRD-PARTY-NOTICES.txt next to it.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.views.generic import TemplateView


class AboutView(TemplateView):
    template_name = "about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notices_path = Path(settings.BASE_DIR) / "THIRD-PARTY-NOTICES.txt"
        try:
            context["notices_text"] = notices_path.read_text(encoding="utf-8")
            context["notices_missing"] = False
        except OSError:
            context["notices_text"] = ""
            context["notices_missing"] = True
        return context
