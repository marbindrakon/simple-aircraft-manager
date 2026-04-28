import sqlite3

import pytest

from desktop import db_backup


def _create_wal_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (val TEXT)")
    conn.execute("INSERT INTO t (val) VALUES ('hello')")
    conn.commit()
    return conn


def test_backup_copies_committed_data(tmp_path):
    db_path = tmp_path / "db.sqlite3"
    conn = _create_wal_db(db_path)
    try:
        backup_path = tmp_path / "db.sqlite3.bak.0"
        db_backup.backup_database(db_path, backup_path)

        copy = sqlite3.connect(str(backup_path))
        rows = list(copy.execute("SELECT val FROM t"))
        copy.close()
        assert rows == [("hello",)]
    finally:
        conn.close()


def test_backup_includes_data_still_in_wal(tmp_path):
    """If a write committed to WAL has not been checkpointed yet,
    sqlite3.Connection.backup() still captures it."""
    db_path = tmp_path / "db.sqlite3"
    conn = _create_wal_db(db_path)
    try:
        # Force a write that is committed but probably still in -wal.
        conn.execute("INSERT INTO t (val) VALUES ('uncheckpointed')")
        conn.commit()

        backup_path = tmp_path / "db.sqlite3.bak.0"
        db_backup.backup_database(db_path, backup_path)

        copy = sqlite3.connect(str(backup_path))
        rows = sorted(r[0] for r in copy.execute("SELECT val FROM t"))
        copy.close()
        assert rows == ["hello", "uncheckpointed"]
    finally:
        conn.close()


def test_backup_when_source_missing_is_silent_noop(tmp_path):
    db_backup.backup_database(tmp_path / "missing.sqlite3", tmp_path / "out.bak")
    assert not (tmp_path / "out.bak").exists()


def test_rotate_keeps_last_n_backups(tmp_path):
    for i in range(5):
        (tmp_path / f"db.sqlite3.bak.{i}").write_text(str(i))

    db_backup.rotate_backups(tmp_path / "db.sqlite3", keep=3)

    remaining = sorted(p.name for p in tmp_path.glob("db.sqlite3.bak.*"))
    assert remaining == ["db.sqlite3.bak.0", "db.sqlite3.bak.1", "db.sqlite3.bak.2"]


def test_backup_and_rotate_combined(tmp_path):
    db_path = tmp_path / "db.sqlite3"
    conn = _create_wal_db(db_path)
    try:
        for _ in range(4):
            db_backup.backup_and_rotate(db_path, keep=2)
    finally:
        conn.close()

    backups = sorted(p.name for p in tmp_path.glob("db.sqlite3.bak.*"))
    assert backups == ["db.sqlite3.bak.0", "db.sqlite3.bak.1"]
