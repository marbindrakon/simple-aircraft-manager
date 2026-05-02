"""WAL-safe SQLite backup using the Online Backup API.

A naive shutil.copy of db.sqlite3 can miss data that is committed but still
sitting in db.sqlite3-wal. sqlite3.Connection.backup() copies a consistent
snapshot regardless of WAL state.

Layout:
    db.sqlite3            (live)
    db.sqlite3.bak.0      (most recent backup)
    db.sqlite3.bak.1      (previous)
    db.sqlite3.bak.2      (older)

backup_and_rotate() shifts existing .bak.N up by one, then writes a new .bak.0.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

LOG = logging.getLogger(__name__)


def backup_database(src_db: Path, dest: Path) -> None:
    """Copy a consistent snapshot of ``src_db`` to ``dest`` using the SQLite
    Online Backup API. If the source does not exist (fresh install before
    first migrate), this is a silent no-op.
    """
    if not src_db.exists():
        return

    src = sqlite3.connect(str(src_db))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def rotate_backups(src_db: Path, keep: int) -> None:
    """Delete .bak.N files where N >= keep."""
    for path in src_db.parent.glob(f"{src_db.name}.bak.*"):
        try:
            n = int(path.name.rsplit(".", 1)[-1])
        except ValueError:
            continue
        if n >= keep:
            try:
                path.unlink()
            except OSError as e:
                LOG.warning("Could not remove old backup %s: %s", path, e)


def backup_and_rotate(src_db: Path, *, keep: int = 3) -> None:
    """Shift existing backups, write a new .bak.0, and trim to ``keep`` files."""
    if not src_db.exists():
        return

    # Shift in reverse order: bak.(keep-1) first, so we don't overwrite live
    # numbered backups before they're renamed.
    for n in range(keep - 1, -1, -1):
        old = src_db.parent / f"{src_db.name}.bak.{n}"
        new = src_db.parent / f"{src_db.name}.bak.{n + 1}"
        if old.exists():
            try:
                old.replace(new)
            except OSError as e:
                LOG.warning("Could not rotate %s -> %s: %s", old, new, e)

    backup_database(src_db, src_db.parent / f"{src_db.name}.bak.0")
    rotate_backups(src_db, keep=keep)
