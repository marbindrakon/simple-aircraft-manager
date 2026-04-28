"""Read config.ini, migrate API key from seed file to OS keystore, and export
the resulting values as environment variables for Django to pick up.

Called exactly once near the top of launcher.main(), before django.setup().
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
    - Sets ANTHROPIC_API_KEY if a key is in the keystore (or migrated this run).
    - Migrates a one-shot api_key_seed.txt into the keystore and deletes it.
    """
    auth_mode = _read_auth_mode()
    os.environ["SAM_DESKTOP_AUTH_MODE"] = auth_mode

    _migrate_seed_to_keyring()

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


def _migrate_seed_to_keyring() -> None:
    """If an api_key_seed.txt is present, copy its contents to the keystore
    and best-effort-wipe the file. On any failure, leave the seed alone and
    log; AI features will simply remain unconfigured this run.
    """
    seed_path = paths.api_key_seed_path()
    if not seed_path.exists():
        return

    try:
        value = seed_path.read_text(encoding="utf-8").strip()
    except OSError as e:
        LOG.warning("Could not read API key seed file %s: %s", seed_path, e)
        return

    if not value:
        # Empty seed file — nothing to migrate; just delete it.
        try:
            seed_path.unlink()
        except OSError as e:
            LOG.warning("Could not delete empty seed file %s: %s", seed_path, e)
        return

    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, value)
    except Exception as e:
        LOG.warning(
            "Could not save API key to OS keystore (%s); leaving seed in place "
            "for retry on next launch. AI features disabled this session.",
            e,
        )
        return

    # Best-effort wipe: overwrite then delete. Not guaranteed against SSDs,
    # journaled filesystems, AV indexers, or cloud-backup clients.
    try:
        size = len(value.encode("utf-8"))
        with open(seed_path, "wb") as f:
            f.write(b"\x00" * size)
        seed_path.unlink()
    except OSError as e:
        LOG.warning("Could not wipe seed file %s after keyring migration: %s", seed_path, e)


def _load_api_key_from_keyring() -> str | None:
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception as e:
        LOG.warning("Could not read API key from OS keystore: %s", e)
        return None
