import pytest
from django.conf import settings as _django_settings
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def _install_desktop_app():
    """Inject the desktop app into INSTALLED_APPS for the duration of every
    desktop test.

    The desktop app is intentionally NOT in the base settings' INSTALLED_APPS
    — it only belongs in ``settings_desktop``. But these tests run against
    ``simple_aircraft_manager.settings`` (the configured ``DJANGO_SETTINGS_MODULE``
    in pyproject.toml), so we add it here. ``override_settings`` triggers
    Django's ``setting_changed`` signal, which re-bootstraps the apps
    registry and template loader caches — that's what makes
    ``desktop/templates/`` discoverable inside the GET tests.
    """
    if "desktop.apps.DesktopConfig" in _django_settings.INSTALLED_APPS:
        yield
        return
    new_apps = [*_django_settings.INSTALLED_APPS, "desktop.apps.DesktopConfig"]
    with override_settings(INSTALLED_APPS=new_apps):
        yield


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
