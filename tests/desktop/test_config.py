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
