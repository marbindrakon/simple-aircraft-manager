"""End-to-end test of launcher.startup_sequence() with waitress and pystray stubbed."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model

from desktop import launcher, paths

pytestmark = pytest.mark.django_db(transaction=True)


def test_launcher_import_does_not_require_django_settings():
    env = os.environ.copy()
    env.pop("DJANGO_SETTINGS_MODULE", None)
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-c", "import desktop.launcher"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.fixture
def stubs(monkeypatch):
    """Replace external IO so the test runs offline and synchronously."""
    fake_server = MagicMock()
    fake_server.run = MagicMock()
    fake_server.close = MagicMock()
    create_server = MagicMock(return_value=fake_server)

    start_ui = MagicMock()
    wait_ready = MagicMock(return_value=True)

    return {
        "create_server": create_server,
        "fake_server": fake_server,
        "start_ui": start_ui,
        "wait_ready": wait_ready,
    }


def test_no_auth_mode_first_launch(fake_user_data_dir, stubs, monkeypatch):
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")

    # Mock keyring so we never touch the real OS keystore.
    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    result = launcher.startup_sequence(
        create_server=stubs["create_server"],
        start_ui=stubs["start_ui"],
        wait_ready=stubs["wait_ready"],
    )

    User = get_user_model()
    assert User.objects.filter(username="desktop").exists()
    assert paths.desktop_user_path().exists()
    assert paths.db_path().exists()

    # Server was created and started.
    stubs["create_server"].assert_called_once()
    args, kwargs = stubs["create_server"].call_args
    assert kwargs["host"] == "127.0.0.1"
    assert isinstance(kwargs["port"], int)

    assert result.port == kwargs["port"]
    assert result.lock_handle is not None


def test_required_mode_treats_setup_as_already_done(fake_user_data_dir, stubs, monkeypatch):
    """In required-auth mode the setup view has already created the
    superuser by the time the launcher reads config.ini. The launcher
    must NOT recreate the placeholder ``desktop`` user, because that user
    doesn't exist in required-auth installs."""
    paths.config_ini_path().write_text("[auth]\nmode = required\n")

    # Simulate the setup view's previous run.
    User = get_user_model()
    User.objects.create_superuser(username="owner", email="", password="hunter22hunter22")

    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    launcher.startup_sequence(
        create_server=stubs["create_server"],
        start_ui=stubs["start_ui"],
        wait_ready=stubs["wait_ready"],
    )

    assert User.objects.filter(username="owner", is_superuser=True).exists()
    # The placeholder no-auth user must NOT have been created.
    assert not User.objects.filter(username="desktop").exists()
    assert not paths.desktop_user_path().exists()


def test_setup_mode_when_config_ini_missing(fake_user_data_dir, stubs, monkeypatch):
    """First-ever launch: no config.ini exists. startup_sequence must:
    - skip config.load_into_env (would raise on the missing file)
    - skip bootstrap.ensure_initial_user (no auth mode chosen yet)
    - still bring up the server so /desktop/setup/ can render
    """
    assert not paths.config_ini_path().exists()

    # Confirm we never touch keyring or bootstrap helpers in setup mode.
    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    bootstrap_called = MagicMock()
    monkeypatch.setattr(
        "desktop.bootstrap.ensure_initial_user",
        lambda **kw: bootstrap_called(**kw),
    )

    result = launcher.startup_sequence(
        create_server=stubs["create_server"],
        start_ui=stubs["start_ui"],
        wait_ready=stubs["wait_ready"],
    )

    bootstrap_called.assert_not_called()

    # Server was started; the launcher returns a real StartupResult so the UI
    # can open and render the setup form.
    stubs["create_server"].assert_called_once()
    assert result is not None
    assert result.port

    User = get_user_model()
    assert not User.objects.filter(username="desktop").exists()
    assert not paths.config_ini_path().exists()


def test_second_instance_returns_none(fake_user_data_dir, stubs, monkeypatch):
    """If another instance holds the lock, startup_sequence returns None and
    does not start the UI. The 'already running' user-facing message lives at
    the run() level, not here."""
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    paths.instance_port_path().write_text("9999")

    import os
    paths.instance_lock_path().write_text(f"{os.getpid()}\n2026-04-27T00:00:00")

    from desktop import instance
    monkeypatch.setattr(instance, "_pid_is_alive", lambda pid: True)

    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    result = launcher.startup_sequence(
        create_server=stubs["create_server"],
        start_ui=stubs["start_ui"],
        wait_ready=stubs["wait_ready"],
    )

    assert result is None
    stubs["create_server"].assert_not_called()
    stubs["start_ui"].assert_not_called()
