"""Tests for the /about/ third-party notices page."""

from pathlib import Path

import pytest
from django.test import Client


@pytest.mark.django_db
def test_about_renders_notices(settings, tmp_path):
    """About page reads THIRD-PARTY-NOTICES.txt from BASE_DIR and embeds it."""
    notices = tmp_path / "THIRD-PARTY-NOTICES.txt"
    notices.write_text("UNIQUE-MARKER-PHRASE Django BSD-3-Clause", encoding="utf-8")
    settings.BASE_DIR = tmp_path

    response = Client().get("/about/")

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "UNIQUE-MARKER-PHRASE" in body
    # Required-by-license attribution line for Font Awesome (CC BY 4.0).
    assert "Font Awesome" in body
    assert "Red Hat" in body


@pytest.mark.django_db
def test_about_handles_missing_notices_file(settings, tmp_path):
    """If the notices file is absent (e.g. dev tree without a build), don't 500."""
    settings.BASE_DIR = tmp_path  # tmp_path has no THIRD-PARTY-NOTICES.txt

    response = Client().get("/about/")

    assert response.status_code == 200
    assert b"not available in this" in response.content
    assert b"generated at build time" in response.content
