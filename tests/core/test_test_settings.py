from django.conf import settings


def test_suite_uses_fast_password_hasher():
    """Prevent CI from silently falling back to expensive runtime hashers."""
    assert settings.SETTINGS_MODULE == "simple_aircraft_manager.settings_test"
    assert settings.PASSWORD_HASHERS == [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
