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


def test_required_mode_consumes_bootstrap_json(fake_user_data_dir, stubs, monkeypatch):
    paths.config_ini_path().write_text("[auth]\nmode = required\n")
    paths.bootstrap_json_path().write_text(json.dumps({
        "username": "owner",
        "password": "hunter22hunter22",
    }))

    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    launcher.startup_sequence(
        create_server=stubs["create_server"],
        start_ui=stubs["start_ui"],
        wait_ready=stubs["wait_ready"],
    )

    User = get_user_model()
    owner = User.objects.get(username="owner")
    assert owner.is_superuser
    assert not paths.bootstrap_json_path().exists()


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
