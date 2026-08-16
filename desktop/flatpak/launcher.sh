#!/bin/sh
# Entrypoint for the Flatpak build. Installed to /app/bin/simple-aircraft-manager.
#
# Mirrors what build-macos.sh / build-windows.ps1 do via PyInstaller's frozen
# executable — except here Python and the source tree live unpacked under
# /app, so we just set the search paths and exec the launcher module.
#
# SAM_DESKTOP is a settings.py attribute (set by settings_desktop.py itself),
# not an env var, so it is not exported here.
# SAM_DESKTOP_AUTH_MODE is set at runtime by desktop.config.load_into_env()
# from config.ini — also not exported here. First-run launches without
# config.ini and the setup-redirect middleware handles it.

set -eu

export PYTHONPATH="/app/share/simple-aircraft-manager${PYTHONPATH:+:$PYTHONPATH}"
export DJANGO_SETTINGS_MODULE="simple_aircraft_manager.settings_desktop"

exec python3 -m desktop.launcher "$@"
