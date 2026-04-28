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


def test_run_start_ui_failure_shows_friendly_error(
    fake_user_data_dir, callables, monkeypatch,
):
    """If start_ui raises (e.g., WebView2 runtime missing), surface a
    friendly error pointing at the Microsoft download URL, run shutdown,
    and exit non-zero."""
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")
    callables["start_ui"].side_effect = RuntimeError("simulated webview2 missing")

    exit_code = launcher.run(
        create_server=callables["create_server"],
        start_ui=callables["start_ui"],
        wait_ready=callables["wait_ready"],
        show_message=callables["show_message"],
    )

    assert exit_code == 1
    callables["start_ui"].assert_called_once()
    callables["show_message"].assert_called_once()
    msg = callables["show_message"].call_args.args[0]
    assert "WebView2" in msg
    assert "go.microsoft.com" in msg

    # Shutdown still ran: server was closed.
    fake_server_obj = callables["create_server"].return_value
    fake_server_obj.close.assert_called_once()


def test_run_happy_path_shuts_down_cleanly(
    fake_user_data_dir, callables, monkeypatch,
):
    """start_ui returns normally (window closed by user); shutdown runs,
    no error message is shown, exit code 0."""
    paths.config_ini_path().write_text("[auth]\nmode = disabled\n")

    exit_code = launcher.run(
        create_server=callables["create_server"],
        start_ui=callables["start_ui"],
        wait_ready=callables["wait_ready"],
        show_message=callables["show_message"],
    )

    assert exit_code == 0
    callables["start_ui"].assert_called_once()
    url = callables["start_ui"].call_args.args[0]
    assert url.startswith("http://127.0.0.1:")
    callables["show_message"].assert_not_called()

    fake_server_obj = callables["create_server"].return_value
    fake_server_obj.close.assert_called_once()
