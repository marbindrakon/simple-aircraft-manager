"""Pre-startup environment checks for the desktop launcher."""

from __future__ import annotations

import socket
import uuid
from pathlib import Path


class PreflightError(RuntimeError):
    """Raised when the runtime environment fails a startup check."""


def pick_free_port(preferred: int = 8765) -> int:
    """Return ``preferred`` if it's free, otherwise an OS-assigned ephemeral port.

    Binds to 127.0.0.1 only; we are not exposing the server on other interfaces.
    """
    if _port_is_free(preferred):
        return preferred
    return _ephemeral_port()


def _port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _ephemeral_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def check_data_dir_writable(path: Path) -> None:
    if not path.exists():
        raise PreflightError(f"User-data directory does not exist: {path}")

    probe = path / f".write-probe-{uuid.uuid4().hex}"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        raise PreflightError(f"User-data directory {path} is not writable: {e}") from e
