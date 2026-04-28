"""Django settings for the Windows desktop installer.

Imports the dev settings (NOT settings_prod) and overrides paths and security
flags appropriate for plain-HTTP loopback usage. Activated by setting
DJANGO_SETTINGS_MODULE=simple_aircraft_manager.settings_desktop, which the
desktop launcher does before calling django.setup().
"""

from __future__ import annotations

import logging.config
import os
import secrets
import sys
from pathlib import Path

from desktop import paths

# Compute BASE_DIR before importing the base settings module so that the
# base settings' BASE_DIR-derived paths can be overridden cleanly below.
if getattr(sys, "frozen", False):
    # Running under PyInstaller — code lives in sys._MEIPASS.
    BASE_DIR_FROZEN = Path(sys._MEIPASS)
else:
    BASE_DIR_FROZEN = Path(__file__).resolve().parent.parent

# Ensure the user-data directory exists before any Django code touches paths.
paths.ensure_dirs()

# Pull in the dev settings as a baseline. We deliberately do NOT inherit from
# settings_prod, which forces HTTPS, HSTS, and Postgres — none of which apply
# to a plain-HTTP localhost desktop server.
from .settings import *  # noqa: E402, F401, F403

# --- Sentinel ---------------------------------------------------------------

# urls.py checks this to enable the desktop-only authenticated media route.
SAM_DESKTOP = True

# --- Core ------------------------------------------------------------------

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# --- Persistent SECRET_KEY -------------------------------------------------

def _load_or_create_secret_key() -> str:
    key_path = paths.secret_key_path()
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    new_key = secrets.token_urlsafe(64)
    key_path.write_text(new_key, encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        # On Windows os.chmod is largely a no-op; ACLs are inherited from the
        # parent dir which already lives under the user's profile.
        pass
    return new_key


SECRET_KEY = _load_or_create_secret_key()

# --- Database --------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(paths.db_path()),
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL;",
        },
    }
}

# --- Static & media --------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT_OVERRIDE", str(BASE_DIR_FROZEN / "staticfiles"))
# CompressedManifestStaticFilesStorage requires a staticfiles.json manifest
# that maps hashed URLs back to real files. That manifest only exists in
# production deployments where collectstatic has run with hashing enabled.
# For a loopback desktop server there is no CDN or aggressive caching, so
# content-hashing provides no benefit. Plain StaticFilesStorage lets
# WhiteNoise serve files directly by path with no manifest required.
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = str(paths.media_root())

# --- Middleware ------------------------------------------------------------

# Insert WhiteNoise right after SecurityMiddleware (its documented position).
# Insert DesktopAutoLoginMiddleware right after AuthenticationMiddleware,
# but only in no-auth mode.
MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405 — from settings.py
try:
    sec_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
    MIDDLEWARE.insert(sec_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
except ValueError:
    MIDDLEWARE.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")

if os.environ.get("SAM_DESKTOP_AUTH_MODE") == "disabled":
    try:
        auth_idx = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        MIDDLEWARE.insert(auth_idx + 1, "desktop.middleware.DesktopAutoLoginMiddleware")
    except ValueError:
        # AuthenticationMiddleware should always be present; if it isn't we
        # do nothing rather than guess at placement.
        pass

# --- Auth backends ---------------------------------------------------------

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
OIDC_ENABLED = False

# --- Security flags appropriate for plain HTTP loopback --------------------

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None

# --- Misc ------------------------------------------------------------------

IMPORT_STAGING_DIR = str(paths.import_staging_dir())

# base settings.py defaults PROMETHEUS_METRICS_ENABLED=True and appends
# django_prometheus to INSTALLED_APPS before this module can override the
# flag. Remove it explicitly — Prometheus scraping makes no sense for a
# loopback desktop server, and the package is not bundled by PyInstaller.
PROMETHEUS_METRICS_ENABLED = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_prometheus"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "prometheus" not in m.lower()]  # noqa: F405

# --- Logging ---------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "django_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(paths.log_dir() / "django.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "default",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["django_file"],
        "level": "INFO",
    },
}
logging.config.dictConfig(LOGGING)
