import os

import pytest

from desktop import instance, paths


def test_acquire_creates_lock_file(fake_user_data_dir):
    handle = instance.acquire()
    try:
        assert paths.instance_lock_path().exists()
        contents = paths.instance_lock_path().read_text()
        assert str(os.getpid()) in contents
    finally:
        instance.release(handle)


def test_release_removes_lock_file(fake_user_data_dir):
    handle = instance.acquire()
    instance.release(handle)
    assert not paths.instance_lock_path().exists()


def test_acquire_returns_none_when_other_live_process_holds_lock(fake_user_data_dir, monkeypatch):
    # Simulate an existing lock file owned by a live PID.
    paths.instance_lock_path().write_text(f"{os.getpid()}\n2026-04-27T00:00:00")

    monkeypatch.setattr(instance, "_pid_is_alive", lambda pid: True)
    handle = instance.acquire()
    assert handle is None


def test_acquire_breaks_stale_lock_from_dead_process(fake_user_data_dir, monkeypatch):
    paths.instance_lock_path().write_text("99999\n2026-04-27T00:00:00")

    monkeypatch.setattr(instance, "_pid_is_alive", lambda pid: False)
    handle = instance.acquire()
    try:
        assert handle is not None
        assert paths.instance_lock_path().exists()
        # New lock file contains our own PID, not the stale one.
        assert "99999" not in paths.instance_lock_path().read_text()
    finally:
        instance.release(handle)


def test_write_and_read_running_port(fake_user_data_dir):
    instance.write_running_port(12345)
    assert instance.read_running_port() == 12345


def test_read_running_port_returns_none_when_missing(fake_user_data_dir):
    assert instance.read_running_port() is None
