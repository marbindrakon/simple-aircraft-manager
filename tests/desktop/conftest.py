import pytest


@pytest.fixture
def fake_user_data_dir(tmp_path, monkeypatch):
    """Redirect platformdirs.user_data_dir to a temp dir for the duration of the test."""
    import platformdirs

    user_data = tmp_path / "user_data"
    user_data.mkdir()

    def _fake_user_data_dir(appname, appauthor=None, **kwargs):
        return str(user_data)

    monkeypatch.setattr(platformdirs, "user_data_dir", _fake_user_data_dir)
    return user_data
