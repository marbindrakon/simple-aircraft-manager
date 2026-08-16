from pathlib import Path

import pytest

from desktop import paths


def test_user_data_dir_returns_pathlib_path(fake_user_data_dir):
    result = paths.user_data_dir()
    assert isinstance(result, Path)
    assert result == fake_user_data_dir


def test_log_dir_is_under_user_data_dir(fake_user_data_dir):
    assert paths.log_dir() == fake_user_data_dir / "logs"


def test_media_root_is_under_user_data_dir(fake_user_data_dir):
    assert paths.media_root() == fake_user_data_dir / "media"


def test_db_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.db_path() == fake_user_data_dir / "db.sqlite3"


def test_import_staging_dir_is_under_user_data_dir(fake_user_data_dir):
    assert paths.import_staging_dir() == fake_user_data_dir / "import_staging"


def test_secret_key_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.secret_key_path() == fake_user_data_dir / "secret_key"


def test_config_ini_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.config_ini_path() == fake_user_data_dir / "config.ini"


def test_desktop_user_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.desktop_user_path() == fake_user_data_dir / "desktop_user.json"


def test_instance_lock_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.instance_lock_path() == fake_user_data_dir / "instance.lock"


def test_instance_port_path_is_under_user_data_dir(fake_user_data_dir):
    assert paths.instance_port_path() == fake_user_data_dir / "instance.port"


def test_ensure_dirs_creates_subdirectories(fake_user_data_dir):
    paths.ensure_dirs()
    assert (fake_user_data_dir / "media").is_dir()
    assert (fake_user_data_dir / "import_staging").is_dir()
    assert (fake_user_data_dir / "logs").is_dir()


def test_ensure_dirs_is_idempotent(fake_user_data_dir):
    paths.ensure_dirs()
    paths.ensure_dirs()  # should not raise
    assert (fake_user_data_dir / "logs").is_dir()
