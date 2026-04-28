"""Top-level entry point for the desktop launcher.

Two layers:
- startup_sequence(): dependency-injected orchestration; testable on Linux.
- main(): wires the real waitress + pystray + webbrowser callables and runs
          the tray event loop. Called by the PyInstaller bundle's entry point.
"""

from __future__ import annotations

import dataclasses
import http.client
import logging
import logging.handlers
import os
import threading
import time
import webbrowser
from typing import Any, Callable, Optional

from desktop import (
    bootstrap,
    config,
    db_backup,
    import_recovery,
    instance,
    paths,
    preflight,
)

LOG = logging.getLogger(__name__)

PREFERRED_PORT = 8765
SERVER_READY_TIMEOUT_S = 5.0
SERVER_READY_POLL_S = 0.1


@dataclasses.dataclass
class StartupResult:
    """Returned by startup_sequence on success. None means a second instance
    was detected and the caller should exit."""

    port: int
    server: Any
    server_thread: threading.Thread
    lock_handle: object


def configure_logging() -> None:
    paths.ensure_dirs()
    handler = logging.handlers.RotatingFileHandler(
        paths.log_dir() / "launcher.log",
        maxBytes=1 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def startup_sequence(
    *,
    create_server: Callable[..., Any],
    start_ui: Callable[[str], Any],
    wait_ready: Callable[[int, float], bool],
) -> Optional[StartupResult]:
    """Run every startup step up to "server running and ready."

    Returns None if a second instance was detected.
    """
    paths.ensure_dirs()

    lock_handle = instance.acquire()
    if lock_handle is None:
        return None

    try:
        config.load_into_env()
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "simple_aircraft_manager.settings_desktop",
        )

        preflight.check_data_dir_writable(paths.user_data_dir())

        import django  # local import: settings module must be set first
        django.setup()

        # Ensure the SQLite database file exists at paths.db_path() before
        # backup or migrate. In production, Django settings_desktop points
        # DATABASES['default']['NAME'] here, so migrate creates it. In test
        # environments Django may already be configured against a different
        # database; we guarantee the file exists regardless.
        # TODO: remove when test fixture redirects DATABASES at paths.db_path()
        # directly. This pre-touch is a test-only artifact; production migrate
        # would create the file on its own.
        if not paths.db_path().exists():
            import sqlite3 as _sqlite3
            _conn = _sqlite3.connect(str(paths.db_path()))
            _conn.close()

        db_backup.backup_and_rotate(paths.db_path(), keep=3)

        # Mark orphan running ImportJobs as failed BEFORE migrate so the recovery
        # query doesn't run against a half-migrated schema.
        try:
            import_recovery.mark_orphan_running_jobs_failed()
        except Exception:
            # On the very first launch the table doesn't exist yet; that's fine.
            LOG.info("Skipping import recovery (likely first run, ImportJob table absent)")

        from django.core.management import call_command
        call_command("migrate", verbosity=0)

        # Recovery again, after migrate, in case the first run created the table.
        import_recovery.mark_orphan_running_jobs_failed()

        auth_mode = os.environ.get("SAM_DESKTOP_AUTH_MODE", "disabled")
        bootstrap.ensure_initial_user(auth_mode=auth_mode)

        port = preflight.pick_free_port(preferred=PREFERRED_PORT)
        instance.write_running_port(port)

        from simple_aircraft_manager.wsgi import application
        server = create_server(application, host="127.0.0.1", port=port, threads=8)

        server_thread = threading.Thread(target=server.run, name="sam-waitress", daemon=True)
        server_thread.start()

        ready = wait_ready(port, SERVER_READY_TIMEOUT_S)
        if not ready:
            LOG.warning("Server slow to become ready; opening browser anyway")

        return StartupResult(
            port=port,
            server=server,
            server_thread=server_thread,
            lock_handle=lock_handle,
        )

    except Exception:
        instance.release(lock_handle)
        raise


def wait_for_server_ready(port: int, timeout_s: float = SERVER_READY_TIMEOUT_S) -> bool:
    """Poll http://127.0.0.1:<port>/healthz/ until 200 or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
            conn.request("GET", "/healthz/")
            resp = conn.getresponse()
            conn.close()
            if 200 <= resp.status < 500:
                return True
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(SERVER_READY_POLL_S)
    return False


def shutdown(result: StartupResult, drain_timeout_s: float = 10.0) -> None:
    LOG.info("Shutting down server")
    try:
        result.server.close()
    except Exception as e:
        LOG.warning("Error closing waitress server: %s", e)
    result.server_thread.join(timeout=drain_timeout_s)
    instance.release(result.lock_handle)
    LOG.info("Shutdown complete")


ALREADY_RUNNING_MESSAGE = (
    "Simple Aircraft Manager is already running. "
    "Check the taskbar for the existing window."
)

WEBVIEW2_MISSING_MESSAGE = (
    "Simple Aircraft Manager couldn't open its window. "
    "This usually means the Microsoft Edge WebView2 Runtime is missing.\n\n"
    "Install it from:\n"
    "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
    "Then launch Simple Aircraft Manager again."
)


def run(
    *,
    create_server: Callable[..., Any],
    start_ui: Callable[[str], Any],
    wait_ready: Callable[[int, float], bool],
    show_message: Callable[[str], Any],
) -> int:
    """Orchestrate startup -> UI -> shutdown.

    Returns a process exit code. Surfaces user-facing failures via
    show_message rather than raising. Tests target this function directly.
    """
    try:
        result = startup_sequence(
            create_server=create_server,
            start_ui=start_ui,
            wait_ready=wait_ready,
        )
    except Exception as e:
        LOG.exception("Startup failed")
        show_message(
            f"Simple Aircraft Manager couldn't start.\n\n{e}\n\n"
            f"See {paths.log_dir() / 'launcher.log'} for details."
        )
        return 1

    if result is None:
        show_message(ALREADY_RUNNING_MESSAGE)
        return 0

    try:
        start_ui(f"http://127.0.0.1:{result.port}/")
        return 0
    except Exception:
        LOG.exception("UI failed to start")
        show_message(WEBVIEW2_MISSING_MESSAGE)
        return 1
    finally:
        shutdown(result)


def main() -> int:
    """Entry point for sam.exe (PyInstaller bundle)."""
    configure_logging()

    try:
        from waitress import create_server as _create_server
    except ImportError as e:
        LOG.exception("waitress not available")
        _show_fatal_messagebox(f"Internal error: {e}")
        return 1

    try:
        result = startup_sequence(
            create_server=_create_server,
            start_ui=webbrowser.open,
            wait_ready=wait_for_server_ready,
        )
    except Exception as e:
        LOG.exception("Startup failed")
        _show_fatal_messagebox(
            f"Simple Aircraft Manager couldn't start.\n\n{e}\n\n"
            f"See {paths.log_dir() / 'launcher.log'} for details."
        )
        return 1

    if result is None:
        # Second instance — opened the browser to the existing one already.
        return 0

    try:
        _run_tray(result)
    finally:
        shutdown(result)

    return 0


def _run_tray(result: StartupResult) -> None:
    """Show the system tray icon. Blocks until the user picks Quit."""
    import pystray
    from PIL import Image

    # Locate the icon. In the PyInstaller bundle it's next to the executable;
    # in source it's under desktop/. fall back to a 1x1 image rather than crash.
    icon_path = paths.user_data_dir().parent  # placeholder; real lookup below
    try:
        # When frozen, sys._MEIPASS is the bundle's data root.
        import sys
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            icon_image = Image.open(os.path.join(bundle_root, "desktop", "icon.ico"))
        else:
            from pathlib import Path
            icon_image = Image.open(Path(__file__).parent / "icon.ico")
    except Exception:
        icon_image = Image.new("RGB", (16, 16), color=(0, 100, 200))

    def _open_browser(_icon, _item):
        webbrowser.open(f"http://127.0.0.1:{result.port}/")

    def _open_logs(_icon, _item):
        try:
            os.startfile(str(paths.log_dir()))  # Windows
        except AttributeError:
            # Non-Windows: best effort
            import subprocess
            subprocess.Popen(["xdg-open", str(paths.log_dir())])

    def _quit(icon, _item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open in Browser", _open_browser, default=True),
        pystray.MenuItem("Open Log Folder", _open_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit),
    )
    icon = pystray.Icon("SimpleAircraftManager", icon_image, "Simple Aircraft Manager", menu)
    icon.run()


def _show_fatal_messagebox(message: str) -> None:
    """Best-effort native messagebox. Falls back to stderr if unavailable."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "Simple Aircraft Manager", 0x10)
    except Exception:
        import sys
        print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
