"""Django app config for the desktop launcher.

The desktop package is registered in the base settings so its templates
and static files are discoverable, but its URLs only mount when
``settings.SAM_DESKTOP`` is true — the ``url_prefix`` property below
returns ``None`` in dev/prod, which the project's plugin URL discovery
loop in ``simple_aircraft_manager/urls.py`` interprets as "skip this
plugin's URLs."
"""

from core.plugins import SAMPluginConfig


class DesktopConfig(SAMPluginConfig):
    name = "desktop"
    verbose_name = "Simple Aircraft Manager — Desktop"
    default_auto_field = "django.db.models.BigAutoField"

    @property
    def url_prefix(self):
        from django.conf import settings
        return "desktop" if getattr(settings, "SAM_DESKTOP", False) else None
