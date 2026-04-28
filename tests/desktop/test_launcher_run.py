"""Tests for launcher.run() — the orchestration wrapper around startup_sequence,
start_ui, and shutdown. Injectable start_ui and show_message let us assert on
user-facing failure paths without driving a real GUI."""
from unittest.mock import MagicMock

import pytest

from desktop import launcher, paths

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def fake_server():
    server = MagicMock()
    server.run = MagicMock()
    server.close = MagicMock()
    return server


@pytest.fixture
def callables(fake_server, monkeypatch):
    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: None)

    return {
        "create_server": MagicMock(return_value=fake_server),
        "start_ui": MagicMock(),
        "wait_ready": MagicMock(return_value=True),
        "show_message": MagicMock(),
    }


def test_run_second_instance_shows_already_running_message(
    fake_user_data_dir, callables, monkeypatch,
):
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    paths.instance_port_path().write_text("9999")
    import os
    paths.instance_lock_path().write_text(f"{os.getpid()}\n2026-04-27T00:00:00")

    from desktop import instance
    monkeypatch.setattr(instance, "_pid_is_alive", lambda pid: True)

    exit_code = launcher.run(
        create_server=callables["create_server"],
        start_ui=callables["start_ui"],
        wait_ready=callables["wait_ready"],
        show_message=callables["show_message"],
    )

    assert exit_code == 0
    callables["start_ui"].assert_not_called()
    callables["create_server"].assert_not_called()
    callables["show_message"].assert_called_once()
    msg = callables["show_message"].call_args.args[0]
    assert "already running" in msg.lower()
