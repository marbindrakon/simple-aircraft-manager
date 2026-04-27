import os

import pytest

from desktop import config, paths


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


def test_load_into_env_with_missing_config_uses_defaults(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("SAM_DESKTOP_AUTH_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config.load_into_env()

    assert os.environ["SAM_DESKTOP_AUTH_MODE"] == "disabled"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_load_into_env_reads_auth_mode_from_config(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("SAM_DESKTOP_AUTH_MODE", raising=False)
    paths.config_ini_path().write_text("[auth]\nmode = required\n")

    config.load_into_env()

    assert os.environ["SAM_DESKTOP_AUTH_MODE"] == "required"


def test_load_into_env_rejects_invalid_auth_mode(fake_user_data_dir, mock_keyring):
    paths.config_ini_path().write_text("[auth]\nmode = bogus\n")

    with pytest.raises(config.ConfigError) as excinfo:
        config.load_into_env()
    assert "auth.mode" in str(excinfo.value)


def test_seed_file_is_migrated_to_keyring_on_first_load(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    paths.api_key_seed_path().write_text("sk-ant-test-key-123")

    config.load_into_env()

    assert mock_keyring[("SimpleAircraftManager", "anthropic_api_key")] == "sk-ant-test-key-123"
    assert not paths.api_key_seed_path().exists()
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test-key-123"


def test_subsequent_loads_read_from_keyring(fake_user_data_dir, mock_keyring, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_keyring[("SimpleAircraftManager", "anthropic_api_key")] = "sk-ant-stored-key"

    config.load_into_env()

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-stored-key"


def test_seed_migration_failure_leaves_seed_in_place(fake_user_data_dir, monkeypatch):
    paths.api_key_seed_path().write_text("sk-ant-fail-key")

    def boom(service, username, password):
        raise RuntimeError("Credential Manager unavailable")

    import keyring as keyring_module
    monkeypatch.setattr(keyring_module, "set_password", boom)
    monkeypatch.setattr(keyring_module, "get_password", lambda s, u: None)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.load_into_env()  # must not raise

    assert paths.api_key_seed_path().exists()
    assert paths.api_key_seed_path().read_text() == "sk-ant-fail-key"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_empty_seed_file_is_deleted_without_writing_keyring(fake_user_data_dir, mock_keyring):
    paths.api_key_seed_path().write_text("")

    config.load_into_env()

    assert ("SimpleAircraftManager", "anthropic_api_key") not in mock_keyring
    assert not paths.api_key_seed_path().exists()


def test_malformed_config_ini_raises_clear_error(fake_user_data_dir, mock_keyring):
    paths.config_ini_path().write_text("not a valid ini file [unclosed")

    with pytest.raises(config.ConfigError):
        config.load_into_env()
