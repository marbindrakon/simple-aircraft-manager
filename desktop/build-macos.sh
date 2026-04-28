#!/usr/bin/env bash
# Build the macOS desktop bundle and DMG.
# Run from the repo root on macOS 12+ with Python 3.12 and Xcode CLI tools.
# DMG packaging requires Homebrew's create-dmg:  brew install create-dmg
#
# Output:
#   dist/Simple Aircraft Manager.app
#   dist/SimpleAircraftManager-<version>.dmg
#
# The build is unsigned and un-notarized — first launch from a downloaded
# DMG will trip Gatekeeper. Right-click the app -> Open -> Open to clear
# the quarantine bit. Code signing + notarization are Day-2.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${SAM_BUILD_VERSION:-0.1.0-poc}"
APP_NAME="Simple Aircraft Manager"
APP_BUNDLE="dist/${APP_NAME}.app"
DMG_OUT="dist/SimpleAircraftManager-${VERSION}.dmg"

log() { printf '\n=== %s ===\n' "$*"; }

log "Step 0/5: Clean previous build artifacts"
rm -rf build/sam-macos build/staticfiles "${APP_BUNDLE}" dist/SimpleAircraftManager
rm -f "${DMG_OUT}"

log "Step 1/5: Create venv (if missing)"
if [ ! -d ".venv" ]; then
    python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

log "Step 2/5: Install dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt

log "Step 3/5: Collect static assets"
export DJANGO_SETTINGS_MODULE="simple_aircraft_manager.settings_desktop"
export SAM_DESKTOP_AUTH_MODE="disabled"
export SAM_BUILD_STATIC_ROOT="${REPO_ROOT}/build/staticfiles"
mkdir -p "${SAM_BUILD_STATIC_ROOT}"

# We override STATIC_ROOT at runtime so we don't pollute the user-data dir
# the launcher uses at app runtime. The same trick lives in build-windows.ps1.
STATIC_ROOT_OVERRIDE="${SAM_BUILD_STATIC_ROOT}" \
    python -c "
import os, django
django.setup()
from django.conf import settings
settings.STATIC_ROOT = os.environ['STATIC_ROOT_OVERRIDE']
from django.core.management import call_command
call_command('collectstatic', interactive=False, verbosity=1)
"

log "Step 4/5: Run PyInstaller"
python -m PyInstaller desktop/sam-macos.spec --noconfirm

if [ ! -d "${APP_BUNDLE}" ]; then
    echo "ERROR: PyInstaller didn't produce ${APP_BUNDLE}" >&2
    exit 1
fi

log "Step 5/5: Build DMG"
if ! command -v create-dmg >/dev/null 2>&1; then
    cat >&2 <<EOF
WARNING: create-dmg not found on PATH. Skipping DMG step.
Install with:  brew install create-dmg
The app bundle is still available at:
    ${APP_BUNDLE}
EOF
    exit 0
fi

create-dmg \
    --volname "${APP_NAME}" \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 150 200 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 450 200 \
    "${DMG_OUT}" \
    "${APP_BUNDLE}"

echo
echo "=== Build complete ==="
echo "App bundle: ${APP_BUNDLE}"
echo "DMG:        ${DMG_OUT}"
