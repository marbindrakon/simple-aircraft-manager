import json
import os

import pytest

from desktop import config, paths


def _write_config(mode="disabled"):
    paths.config_ini_path().write_text(f"[auth]\nmode = {mode}\n")


@pytest.fixture
def mock_keyring(monkeypatch):
    """Replace keyring with an in-memory dict so tests don't touch the real OS keystore."""
    store: dict[tuple[str, str], str] = {}

    def set_password(service, username, password):
        store[(service, username)] = password

    def get_password(service, username):
        return store.get((service, username))

    def delete_password(service, username):
        store.pop((service, username), None)

    import keyring as keyring_module

    monkeypatch.setattr(keyring_module, "set_password", set_password)
    monkeypatch.setattr(keyring_module, "get_password", get_password)
    monkeypatch.setattr(keyring_module, "delete_password", delete_password)
    return store


def test_load_into_env_with_missing_config_fails_closed(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("SAM_DESKTOP_AUTH_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(config.ConfigError) as excinfo:
        config.load_into_env()

    assert "config.ini is missing" in str(excinfo.value)
    assert "SAM_DESKTOP_AUTH_MODE" not in os.environ
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_load_into_env_reads_auth_mode_from_config(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("SAM_DESKTOP_AUTH_MODE", raising=False)
    _write_config("required")

    config.load_into_env()

    assert os.environ["SAM_DESKTOP_AUTH_MODE"] == "required"


def test_load_into_env_rejects_invalid_auth_mode(fake_user_data_dir, mock_keyring):
    _write_config("bogus")

    with pytest.raises(config.ConfigError) as excinfo:
        config.load_into_env()
    assert "auth.mode" in str(excinfo.value)


def test_loads_api_key_from_keyring(fake_user_data_dir, mock_keyring, monkeypatch):
    _write_config()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_keyring[("SimpleAircraftManager", "anthropic_api_key")] = "sk-ant-stored-key"

    config.load_into_env()

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-stored-key"


def test_keyring_unavailable_does_not_raise(fake_user_data_dir, monkeypatch):
    """If the keyring backend is broken, AI features go silently absent
    rather than blocking startup."""
    _write_config()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    import keyring as keyring_module
    monkeypatch.setattr(
        keyring_module,
        "get_password",
        lambda s, u: (_ for _ in ()).throw(RuntimeError("Keychain unavailable")),
    )

    config.load_into_env()  # must not raise
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_malformed_config_ini_raises_clear_error(fake_user_data_dir, mock_keyring):
    paths.config_ini_path().write_text("not a valid ini file [unclosed")

    with pytest.raises(config.ConfigError):
        config.load_into_env()


def test_config_without_auth_mode_fails_closed(fake_user_data_dir, mock_keyring):
    paths.config_ini_path().write_text("[auth]\n")

    with pytest.raises(config.ConfigError) as excinfo:
        config.load_into_env()
    assert "[auth] mode" in str(excinfo.value)


# ---------- [ai] section --------------------------------------------------


@pytest.fixture
def clean_ai_env(monkeypatch):
    """Strip out env vars the [ai] loader writes so each test starts clean."""
    for var in (
        "LOGBOOK_IMPORT_EXTRA_MODELS",
        "LOGBOOK_IMPORT_DEFAULT_MODEL",
        "OLLAMA_BASE_URL",
        "LITELLM_BASE_URL",
        "LITELLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_ai_section_seeds_extra_models_and_default(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\nollama_model = llama3.2-vision\nollama_base_url = http://localhost:11434\n"
    )

    config.load_into_env()

    extras = json.loads(os.environ["LOGBOOK_IMPORT_EXTRA_MODELS"])
    assert extras == [{
        "id": "llama3.2-vision",
        "name": "llama3.2-vision (local)",
        "provider": "ollama",
    }]
    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "llama3.2-vision"
    assert os.environ["OLLAMA_BASE_URL"] == "http://localhost:11434"


def test_ai_section_skipped_when_absent(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")

    config.load_into_env()

    assert "LOGBOOK_IMPORT_EXTRA_MODELS" not in os.environ
    assert "LOGBOOK_IMPORT_DEFAULT_MODEL" not in os.environ
    assert "OLLAMA_BASE_URL" not in os.environ


def test_ai_section_without_model_is_noop(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n[ai]\nollama_base_url = http://localhost:11434\n"
    )

    config.load_into_env()

    assert "LOGBOOK_IMPORT_EXTRA_MODELS" not in os.environ
    assert "OLLAMA_BASE_URL" not in os.environ


def test_ai_section_without_base_url_leaves_default(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n[ai]\nollama_model = llama3.2-vision\n"
    )

    config.load_into_env()

    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "llama3.2-vision"
    # OLLAMA_BASE_URL is not overridden — settings.py default applies.
    assert "OLLAMA_BASE_URL" not in os.environ


def test_ai_section_loads_litellm_endpoint_and_keyring_key(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\nlitellm_model = gpt-4o-mini\n"
        "litellm_base_url = https://openrouter.ai/api/v1\n"
    )
    mock_keyring[("SimpleAircraftManager", "litellm_api_key")] = "sk-or-v1-test"

    config.load_into_env()

    extras = json.loads(os.environ["LOGBOOK_IMPORT_EXTRA_MODELS"])
    assert extras == [{
        "id": "gpt-4o-mini",
        "name": "gpt-4o-mini (custom endpoint)",
        "provider": "litellm",
    }]
    assert os.environ["LITELLM_BASE_URL"] == "https://openrouter.ai/api/v1"
    assert os.environ["LITELLM_API_KEY"] == "sk-or-v1-test"
    # Single LiteLLM provider with no default_provider → it's the default.
    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "gpt-4o-mini"


def test_ai_section_litellm_without_keyring_entry_skips_api_key(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\nlitellm_model = local-vllm\n"
        "litellm_base_url = http://localhost:8000/v1\n"
    )
    # No keyring entry — local vLLM doesn't need auth.

    config.load_into_env()

    assert os.environ["LITELLM_BASE_URL"] == "http://localhost:8000/v1"
    assert "LITELLM_API_KEY" not in os.environ


def test_ai_section_with_all_three_providers_default_routes(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\ndefault_provider = anthropic\n"
        "ollama_model = llama3.2-vision\n"
        "ollama_base_url = http://localhost:11434\n"
        "litellm_model = anthropic/claude-sonnet-4-6\n"
        "litellm_base_url = https://openrouter.ai/api/v1\n"
    )
    mock_keyring[("SimpleAircraftManager", "anthropic_api_key")] = "sk-ant-test"
    mock_keyring[("SimpleAircraftManager", "litellm_api_key")] = "sk-or-v1-test"

    config.load_into_env()

    extras = json.loads(os.environ["LOGBOOK_IMPORT_EXTRA_MODELS"])
    providers = {entry["provider"] for entry in extras}
    assert providers == {"ollama", "litellm"}

    # default_provider=anthropic → use the static Anthropic default model.
    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == config.ANTHROPIC_DEFAULT_MODEL
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert os.environ["LITELLM_API_KEY"] == "sk-or-v1-test"


def test_ai_section_default_provider_litellm_picks_litellm_model(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\ndefault_provider = litellm\n"
        "ollama_model = llama3.2-vision\n"
        "litellm_model = gpt-4o-mini\n"
        "litellm_base_url = https://openrouter.ai/api/v1\n"
    )

    config.load_into_env()

    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "gpt-4o-mini"


def test_ai_section_default_provider_ollama_picks_ollama_model(fake_user_data_dir, mock_keyring, clean_ai_env):
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\ndefault_provider = ollama\n"
        "ollama_model = llama3.2-vision\n"
        "litellm_model = gpt-4o-mini\n"
        "litellm_base_url = https://openrouter.ai/api/v1\n"
    )

    config.load_into_env()

    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "llama3.2-vision"


def test_ai_section_back_compat_single_provider_no_default(fake_user_data_dir, mock_keyring, clean_ai_env):
    """Old [ai] sections without default_provider still work when only one
    provider is configured."""
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n[ai]\nollama_model = llama3.2-vision\n"
    )

    config.load_into_env()

    assert os.environ["LOGBOOK_IMPORT_DEFAULT_MODEL"] == "llama3.2-vision"


def test_ai_section_two_providers_no_default_does_not_set_default(fake_user_data_dir, mock_keyring, clean_ai_env):
    """When two providers are configured but default_provider is missing
    (a config the setup form would never write — but a hand-edited
    config.ini might), don't guess; leave LOGBOOK_IMPORT_DEFAULT_MODEL
    unset so settings.py keeps its built-in default."""
    paths.config_ini_path().write_text(
        "[auth]\nmode = disabled\n\n"
        "[ai]\nollama_model = llama3.2-vision\n"
        "litellm_model = gpt-4o-mini\n"
        "litellm_base_url = https://openrouter.ai/api/v1\n"
    )

    config.load_into_env()

    extras = json.loads(os.environ["LOGBOOK_IMPORT_EXTRA_MODELS"])
    assert {e["provider"] for e in extras} == {"ollama", "litellm"}
    assert "LOGBOOK_IMPORT_DEFAULT_MODEL" not in os.environ
