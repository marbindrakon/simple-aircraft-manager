# NOTE: do NOT set default_app_config here — it was removed in Django 5.
# Django auto-discovers WBPluginConfig from apps.py.  Because SAMPluginConfig
# is imported into apps.py (making two AppConfig subclasses visible),
# WBPluginConfig must declare `default = True` so Django picks it unambiguously.
# See apps.py for details.
