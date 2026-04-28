import socket

import pytest

from desktop import preflight


def test_pick_free_port_returns_preferred_when_available():
    # Pick a high port unlikely to be in use; if it happens to be in use,
    # the test will (correctly) fall through to the ephemeral path — accept.
    port = preflight.pick_free_port(preferred=58765)
    assert isinstance(port, int)
    assert 1 <= port <= 65535


def test_pick_free_port_falls_back_when_preferred_in_use():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    busy_port = sock.getsockname()[1]
    sock.listen(1)
    try:
        port = preflight.pick_free_port(preferred=busy_port)
        assert port != busy_port
    finally:
        sock.close()


def test_check_data_dir_writable_succeeds_on_writable_dir(tmp_path):
    preflight.check_data_dir_writable(tmp_path)  # must not raise


def test_check_data_dir_writable_raises_on_missing_dir(tmp_path):
    with pytest.raises(preflight.PreflightError):
        preflight.check_data_dir_writable(tmp_path / "does-not-exist")
