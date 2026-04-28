"""Read config.ini and load the API key from the OS keyring into the
process environment.

Called exactly once near the top of launcher.startup_sequence(), AFTER
the launcher has confirmed config.ini exists. (First-run flow: when
config.ini is missing, the launcher skips this entirely so the user can
complete the in-app setup form.)
"""

from __future__ import annotations

import configparser
import logging
import os

import keyring

from desktop import paths

LOG = logging.getLogger(__name__)

KEYRING_SERVICE = "SimpleAircraftManager"
KEYRING_USERNAME = "anthropic_api_key"

VALID_AUTH_MODES = {"disabled", "required"}


class ConfigError(RuntimeError):
    """Raised when config.ini is malformed or contains invalid values."""


def load_into_env() -> None:
    """Populate os.environ from config.ini and the OS keystore.

    Side effects:
    - Sets SAM_DESKTOP_AUTH_MODE.
    - Sets ANTHROPIC_API_KEY if a key is in the keystore.
    """
    auth_mode = _read_auth_mode()
    os.environ["SAM_DESKTOP_AUTH_MODE"] = auth_mode

    api_key = _load_api_key_from_keyring()
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key


def _read_auth_mode() -> str:
    config_path = paths.config_ini_path()
    if not config_path.exists():
        raise ConfigError(
            f"config.ini is missing at {config_path}; reinstall or create it with "
            "an explicit [auth] mode."
        )

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error as e:
        raise ConfigError(f"config.ini at {config_path} is malformed: {e}") from e

    if not parser.has_section("auth") or not parser.has_option("auth", "mode"):
        raise ConfigError(f"config.ini at {config_path} must contain [auth] mode")

    mode = parser.get("auth", "mode").strip().lower()
    if mode not in VALID_AUTH_MODES:
        raise ConfigError(
            f"config.ini at {config_path}: auth.mode must be one of "
            f"{sorted(VALID_AUTH_MODES)}, got {mode!r}"
        )
    return mode


def _load_api_key_from_keyring() -> str | None:
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception as e:
        LOG.warning("Could not read API key from OS keystore: %s", e)
        return None
