"""Single-instance guard for the desktop launcher.

Uses a lock file in the user-data dir. The file contains the holding process's
PID and an ISO-8601 creation timestamp. Acquire-time logic:

1. Try to create the lock file atomically and return a handle on success.
2. If it exists, read the PID. If that process is still alive, return None
   (the second instance should redirect the user to the running one).
3. If the PID is dead, the lock is stale: delete and retry once.

The lock is released by deleting the file on graceful shutdown. Crashes leave
a stale lock that the next launch breaks automatically.

Cross-process file locking via msvcrt/fcntl is intentionally NOT used. The
PID-liveness check is portable and good enough for a single-user desktop app.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import sys

from desktop import paths

LOG = logging.getLogger(__name__)


def acquire() -> object | None:
    """Acquire the single-instance lock.

    Returns an opaque handle on success, or None if another live instance
    holds it. Caller should call ``release(handle)`` on graceful shutdown.
    """
    lock_path = paths.instance_lock_path()

    for _ in range(2):
        if _write_lock_file_exclusive(lock_path):
            return lock_path

        existing_pid = _read_existing_pid(lock_path)
        if existing_pid is not None and _pid_is_alive(existing_pid):
            LOG.info("Another instance (pid=%s) holds the lock", existing_pid)
            return None
        LOG.info("Breaking stale lock (pid=%s no longer alive)", existing_pid)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            continue
        except OSError as e:
            LOG.error("Could not remove stale lock %s: %s", lock_path, e)
            return None

    LOG.error("Could not acquire instance lock %s after stale-lock retry", lock_path)
    return None


def _write_lock_file_exclusive(lock_path) -> bool:
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
    try:
        with lock_path.open("x", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{timestamp}")
    except FileExistsError:
        return False
    return True


def release(handle) -> None:
    if handle is None:
        return
    try:
        os.unlink(str(handle))
    except OSError as e:
        LOG.warning("Could not release instance lock %s: %s", handle, e)


def write_running_port(port: int) -> None:
    paths.instance_port_path().write_text(str(port), encoding="utf-8")


def read_running_port() -> int | None:
    p = paths.instance_port_path()
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _read_existing_pid(lock_path) -> int | None:
    try:
        first_line = lock_path.read_text(encoding="utf-8").splitlines()[0]
        return int(first_line.strip())
    except (OSError, ValueError, IndexError):
        return None


def _pid_is_alive(pid: int) -> bool:
    """Return True if a process with this PID exists."""
    if sys.platform == "win32":
        # Windows: use OpenProcess via ctypes.
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok) and exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    else:
        # POSIX: signal 0 probes for existence without delivering a signal.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists, we just can't signal it.
        return True
