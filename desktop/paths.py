"""Filesystem path resolution for the desktop launcher.

This is the single point of platform divergence. All other desktop modules
should call into this module rather than reading platform-specific environment
variables directly.
"""

from __future__ import annotations

from pathlib import Path

import platformdirs

APP_NAME = "SimpleAircraftManager"


def user_data_dir() -> Path:
    """Return the per-user data directory.

    On Windows: %LOCALAPPDATA%\\SimpleAircraftManager\\
    On macOS:   ~/Library/Application Support/SimpleAircraftManager/
    On Linux:   ~/.local/share/SimpleAircraftManager/

    The appauthor=False call form prevents platformdirs from inserting an
    extra "appauthor" component on Windows.
    """
    return Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))


def log_dir() -> Path:
    return user_data_dir() / "logs"


def media_root() -> Path:
    return user_data_dir() / "media"


def db_path() -> Path:
    return user_data_dir() / "db.sqlite3"


def import_staging_dir() -> Path:
    return user_data_dir() / "import_staging"


def secret_key_path() -> Path:
    return user_data_dir() / "secret_key"


def config_ini_path() -> Path:
    return user_data_dir() / "config.ini"


def desktop_user_path() -> Path:
    return user_data_dir() / "desktop_user.json"


def instance_lock_path() -> Path:
    return user_data_dir() / "instance.lock"


def instance_port_path() -> Path:
    return user_data_dir() / "instance.port"


def ensure_dirs() -> None:
    """Create the user-data subdirectories the app needs to write into."""
    user_data_dir().mkdir(parents=True, exist_ok=True)
    log_dir().mkdir(parents=True, exist_ok=True)
    media_root().mkdir(parents=True, exist_ok=True)
    import_staging_dir().mkdir(parents=True, exist_ok=True)
