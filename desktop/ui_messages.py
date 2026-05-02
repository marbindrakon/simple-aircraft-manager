"""Cross-platform fatal-error messagebox.

The launcher uses this to surface unrecoverable startup failures (server
won't bind, UI won't open, etc.) before any HTML is on screen. We dispatch
on ``sys.platform`` so the same call works on Windows, macOS, and Linux.

All branches are best-effort: if the native dialog API fails for any
reason, we fall back to writing the message to stderr so the user (or the
log harness) still sees it.
"""

from __future__ import annotations

import logging
import subprocess
import sys

LOG = logging.getLogger(__name__)

DIALOG_TITLE = "Simple Aircraft Manager"


def show_fatal_message(message: str) -> None:
    """Show ``message`` in a native modal dialog. Never raises."""
    try:
        if sys.platform == "win32":
            _show_windows(message)
            return
        if sys.platform == "darwin":
            _show_macos(message)
            return
        _show_stderr(message)
    except Exception as e:  # pragma: no cover — defensive belt-and-suspenders
        LOG.warning("Native messagebox failed (%s); falling back to stderr", e)
        _show_stderr(message)


def _show_windows(message: str) -> None:
    import ctypes

    # 0x10 = MB_ICONERROR
    ctypes.windll.user32.MessageBoxW(0, message, DIALOG_TITLE, 0x10)


def _show_macos(message: str) -> None:
    # AppleScript's `display dialog` is the simplest way to get a modal
    # window without a Python GUI toolkit. We escape backslashes and
    # double-quotes so user-supplied text (filenames, exception strings)
    # can't break out of the string literal.
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'display dialog "{safe}" '
        f'with title "{DIALOG_TITLE}" '
        f'with icon stop '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
    )


def _show_stderr(message: str) -> None:
    print(message, file=sys.stderr)
