"""Guards on the settings_desktop module.

settings_desktop has module-level side effects (creates the user-data dir,
writes a persistent SECRET_KEY, configures file logging), so it is imported
in a subprocess with platformdirs redirected to a temp dir rather than into
this test process.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_settings_desktop_strips_mcp_and_oauth_apps(tmp_path):
    """The desktop bundle must not ship the MCP/OAuth stack: the PyInstaller
    specs don't collect oauth2_provider or mcp_server, and jwcrypto (LGPL,
    via django-oauth-toolkit) must stay out of the distributable."""
    code = (
        "import platformdirs\n"
        f"platformdirs.user_data_dir = lambda *a, **k: {str(tmp_path)!r}\n"
        "from simple_aircraft_manager import settings_desktop as sd\n"
        "assert 'oauth2_provider' not in sd.INSTALLED_APPS\n"
        "assert 'mcp_server' not in sd.INSTALLED_APPS\n"
        "assert 'django_prometheus' not in sd.INSTALLED_APPS\n"
        "assert sd.MCP_ENABLED is False\n"
        "assert sd.MCP_DCR_ENABLED is False\n"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
