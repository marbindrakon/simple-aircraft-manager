"""Tests for the cross-platform fatal-error messagebox."""

from __future__ import annotations

from unittest import mock

import pytest

from desktop import ui_messages


def test_show_fatal_message_macos_uses_osascript():
    with mock.patch("desktop.ui_messages.sys") as mock_sys, \
         mock.patch("desktop.ui_messages.subprocess.run") as run:
        mock_sys.platform = "darwin"
        ui_messages.show_fatal_message("Boom")

    assert run.call_count == 1
    cmd = run.call_args.args[0]
    assert cmd[0] == "osascript"
    assert cmd[1] == "-e"
    script = cmd[2]
    assert "display dialog" in script
    assert "Simple Aircraft Manager" in script
    assert "Boom" in script
    # Never raises on a non-zero osascript exit
    assert run.call_args.kwargs["check"] is False


def test_show_fatal_message_macos_escapes_quotes_and_backslashes():
    with mock.patch("desktop.ui_messages.sys") as mock_sys, \
         mock.patch("desktop.ui_messages.subprocess.run") as run:
        mock_sys.platform = "darwin"
        ui_messages.show_fatal_message('a "b" \\ c')

    script = run.call_args.args[0][2]
    # AppleScript-escaped form: backslash before " and before \
    assert '\\"b\\"' in script
    assert "\\\\" in script


def test_show_fatal_message_windows_uses_user32(monkeypatch):
    fake_user32 = mock.MagicMock()
    fake_windll = mock.MagicMock(user32=fake_user32)
    fake_ctypes = mock.MagicMock(windll=fake_windll)

    monkeypatch.setattr(ui_messages.sys, "platform", "win32", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)

    ui_messages.show_fatal_message("Boom")

    fake_user32.MessageBoxW.assert_called_once_with(0, "Boom", "Simple Aircraft Manager", 0x10)


def test_show_fatal_message_other_platform_falls_back_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(ui_messages.sys, "platform", "linux", raising=False)
    ui_messages.show_fatal_message("Boom")
    captured = capsys.readouterr()
    assert "Boom" in captured.err


def test_show_fatal_message_swallows_exceptions_from_native_call(monkeypatch, capsys):
    monkeypatch.setattr(ui_messages.sys, "platform", "darwin", raising=False)

    def explode(*a, **kw):
        raise RuntimeError("osascript exploded")

    monkeypatch.setattr(ui_messages.subprocess, "run", explode)

    # Must not raise
    ui_messages.show_fatal_message("Boom")
    captured = capsys.readouterr()
    # Falls back to stderr
    assert "Boom" in captured.err


@pytest.mark.parametrize("platform_name", ["darwin", "linux", "win32"])
def test_show_fatal_message_never_raises(monkeypatch, platform_name):
    monkeypatch.setattr(ui_messages.sys, "platform", platform_name, raising=False)

    # Force every backend to fail.
    def explode(*a, **kw):
        raise RuntimeError("nope")

    monkeypatch.setattr(ui_messages.subprocess, "run", explode)

    ui_messages.show_fatal_message("anything")
