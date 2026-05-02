"""Read config.ini and load the API key from the OS keyring into the
process environment.

Called exactly once near the top of launcher.startup_sequence(), AFTER
the launcher has confirmed config.ini exists. (First-run flow: when
config.ini is missing, the launcher skips this entirely so the user can
complete the in-app setup form.)
"""

from __future__ import annotations

import configparser
import json
import logging
import os

import keyring

from desktop import paths

LOG = logging.getLogger(__name__)

KEYRING_SERVICE = "SimpleAircraftManager"
KEYRING_USERNAME = "anthropic_api_key"
KEYRING_USERNAME_LITELLM = "litellm_api_key"

VALID_AUTH_MODES = {"disabled", "required"}
VALID_DEFAULT_PROVIDERS = {"anthropic", "ollama", "litellm"}

# Static default that ships in settings.LOGBOOK_IMPORT_MODELS — used when
# the user picks "anthropic" as default_provider but doesn't otherwise pin
# a model. Keep in sync with settings.LOGBOOK_IMPORT_DEFAULT_MODEL.
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"


class ConfigError(RuntimeError):
    """Raised when config.ini is malformed or contains invalid values."""


def load_into_env() -> None:
    """Populate os.environ from config.ini and the OS keystore.

    Side effects:
    - Sets SAM_DESKTOP_AUTH_MODE.
    - Sets ANTHROPIC_API_KEY if a key is in the keystore.
    - Sets LITELLM_API_KEY if an OpenAI-compatible key is in the keystore.
    - If [ai] configures Ollama or an OpenAI-compatible endpoint, appends
      entries to LOGBOOK_IMPORT_EXTRA_MODELS and sets
      LOGBOOK_IMPORT_DEFAULT_MODEL based on [ai] default_provider so
      settings.py picks up the user's chosen models.
    """
    parser = _read_config()
    auth_mode = _read_auth_mode(parser)
    os.environ["SAM_DESKTOP_AUTH_MODE"] = auth_mode

    api_key = _load_api_key_from_keyring(KEYRING_USERNAME)
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    _apply_ai_section(parser)


def _read_config() -> configparser.ConfigParser:
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
    return parser


def _read_auth_mode(parser: configparser.ConfigParser) -> str:
    if not parser.has_section("auth") or not parser.has_option("auth", "mode"):
        raise ConfigError(
            f"config.ini at {paths.config_ini_path()} must contain [auth] mode"
        )

    mode = parser.get("auth", "mode").strip().lower()
    if mode not in VALID_AUTH_MODES:
        raise ConfigError(
            f"config.ini at {paths.config_ini_path()}: auth.mode must be one of "
            f"{sorted(VALID_AUTH_MODES)}, got {mode!r}"
        )
    return mode


def _apply_ai_section(parser: configparser.ConfigParser) -> None:
    """Translate the optional [ai] section into env vars settings.py reads.

    Each provider in [ai] (Ollama, OpenAI-compatible/LiteLLM) becomes one
    entry in LOGBOOK_IMPORT_EXTRA_MODELS. ``default_provider`` decides
    which model becomes LOGBOOK_IMPORT_DEFAULT_MODEL. Provider base URLs
    and API keys flow into the env vars settings.py reads
    (OLLAMA_BASE_URL, LITELLM_BASE_URL, LITELLM_API_KEY).

    Back-compat: if [ai] has only one provider configured and no
    default_provider key, that provider is treated as the default.
    Section absent entirely → silent no-op (Anthropic-only setups
    unchanged).
    """
    if not parser.has_section("ai"):
        return

    ollama_model = parser.get("ai", "ollama_model", fallback="").strip()
    ollama_base_url = parser.get("ai", "ollama_base_url", fallback="").strip()
    litellm_model = parser.get("ai", "litellm_model", fallback="").strip()
    litellm_base_url = parser.get("ai", "litellm_base_url", fallback="").strip()
    raw_default = parser.get("ai", "default_provider", fallback="").strip().lower()

    extras: list[dict[str, str]] = []
    if ollama_model:
        extras.append({
            "id": ollama_model,
            "name": f"{ollama_model} (local)",
            "provider": "ollama",
        })
    if litellm_model:
        extras.append({
            "id": litellm_model,
            "name": f"{litellm_model} (custom endpoint)",
            "provider": "litellm",
        })

    if extras:
        os.environ["LOGBOOK_IMPORT_EXTRA_MODELS"] = json.dumps(extras)

    if ollama_model and ollama_base_url:
        os.environ["OLLAMA_BASE_URL"] = ollama_base_url

    if litellm_model:
        if litellm_base_url:
            os.environ["LITELLM_BASE_URL"] = litellm_base_url
        litellm_key = _load_api_key_from_keyring(KEYRING_USERNAME_LITELLM)
        if litellm_key:
            os.environ["LITELLM_API_KEY"] = litellm_key

    default_provider = _resolve_default_provider(
        raw_default, ollama_model=ollama_model, litellm_model=litellm_model
    )
    if default_provider == "ollama":
        os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] = ollama_model
    elif default_provider == "litellm":
        os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] = litellm_model
    elif default_provider == "anthropic":
        os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] = ANTHROPIC_DEFAULT_MODEL


def _resolve_default_provider(
    raw: str, *, ollama_model: str, litellm_model: str
) -> str | None:
    """Map [ai] default_provider to a concrete provider, falling back to
    inference for back-compat with [ai] sections that pre-date the radio.

    Returns None when no provider should be marked default (e.g. [ai] has
    no provider models filled in and the user didn't pick anthropic).
    """
    if raw in VALID_DEFAULT_PROVIDERS:
        return raw

    # Back-compat: only one provider configured → that's the default.
    if ollama_model and not litellm_model:
        return "ollama"
    if litellm_model and not ollama_model:
        return "litellm"
    return None


def _load_api_key_from_keyring(username: str = KEYRING_USERNAME) -> str | None:
    try:
        return keyring.get_password(KEYRING_SERVICE, username)
    except Exception as e:
        LOG.warning("Could not read %r from OS keystore: %s", username, e)
        return None
