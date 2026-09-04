"""Test-only settings.

This module must never be used to serve the application. It replaces Django's
deliberately expensive production password hashers with a fast hasher so tests
that create users do not spend most of their runtime deriving throwaway hashes.
Password creation, verification, and authentication semantics remain covered;
only the computational work factor changes.
"""

from .settings import *  # noqa: F401, F403


PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
