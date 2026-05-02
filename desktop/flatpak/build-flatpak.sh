#!/usr/bin/env bash
# Build the Linux Flatpak bundle.
# Run from the repo root on a Linux host (or Linux VM) with:
#   - flatpak
#   - flatpak-builder
#   - org.gnome.Platform//47 + org.gnome.Sdk//47 installed from Flathub
#   - ImageMagick `convert` (only on first build, to extract icon-256.png
#     from the existing desktop/icon.ico — once committed, this step is a no-op)
#
# Output:
#   SimpleAircraftManager-<version>.flatpak  (in repo root)
#
# Mirrors build-macos.sh / build-windows.ps1 — manual build, no CI yet.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

VERSION="${SAM_BUILD_VERSION:-0.1.0-poc}"
APP_ID="app.simpleaircraft.Manager"
MANIFEST="desktop/flatpak/${APP_ID}.yml"
BUILD_DIR="build/flatpak"
REPO_DIR="build/flatpak-repo"
BUNDLE_OUT="SimpleAircraftManager-${VERSION}.flatpak"

log() { printf '\n=== %s ===\n' "$*"; }

# --- Preflight -------------------------------------------------------------

for tool in flatpak flatpak-builder; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: $tool not found on PATH." >&2
        echo "Install with your distro's package manager (e.g. apt install $tool)." >&2
        exit 1
    fi
done

# --- Icon ------------------------------------------------------------------

ICON_PNG="desktop/flatpak/icon-256.png"
if [ ! -f "$ICON_PNG" ]; then
    log "Generating $ICON_PNG from desktop/icon.ico"
    if ! command -v convert >/dev/null 2>&1; then
        cat >&2 <<EOF
ERROR: $ICON_PNG missing and ImageMagick 'convert' not on PATH.
Either install ImageMagick (apt install imagemagick) or supply a 256x256
PNG at desktop/flatpak/icon-256.png and re-run.
EOF
        exit 1
    fi
    # icon.ico contains multiple sizes; pick the largest (typically 256).
    convert "desktop/icon.ico" -resize 256x256 "$ICON_PNG"
fi

# --- Runtime check ---------------------------------------------------------

if ! flatpak info org.gnome.Platform//47 >/dev/null 2>&1; then
    log "Installing GNOME Platform 47 + SDK from Flathub"
    flatpak install --user --noninteractive flathub \
        org.gnome.Platform//47 org.gnome.Sdk//47
fi

# --- Build -----------------------------------------------------------------

log "Step 1/3: Clean previous build"
rm -rf "$BUILD_DIR" "$REPO_DIR"
rm -f "$BUNDLE_OUT"

log "Step 2/3: flatpak-builder"
# --force-clean: wipe any prior $BUILD_DIR
# --repo: write the result into an OSTree repo so we can `bundle` it next
flatpak-builder \
    --force-clean \
    --repo="$REPO_DIR" \
    --user \
    --install-deps-from=flathub \
    "$BUILD_DIR" \
    "$MANIFEST"

log "Step 3/3: Bundle to single .flatpak file"
flatpak build-bundle "$REPO_DIR" "$BUNDLE_OUT" "$APP_ID"

echo
echo "=== Build complete ==="
echo "Bundle: $BUNDLE_OUT"
echo
echo "Install with:"
echo "  flatpak install --user $BUNDLE_OUT"
echo "Run with:"
echo "  flatpak run $APP_ID"
