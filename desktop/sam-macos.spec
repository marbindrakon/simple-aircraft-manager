# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS desktop bundle.

Produces dist/Simple Aircraft Manager.app — a standard macOS app bundle
that contains the Python runtime, all third-party packages, collected
static assets, templates, and migrations. Drag-to-Applications via DMG
is the distribution path.

Build prereq: run `python manage.py collectstatic --noinput
--settings=simple_aircraft_manager.settings_desktop` first so STATIC_ROOT
contains the assets that get copied via `datas` below. The build-macos.sh
script does that for you.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

REPO_ROOT = Path(SPECPATH).parent  # SPECPATH is provided by PyInstaller
STATIC_BUILD_DIR = REPO_ROOT / "build" / "staticfiles"


# Resource files copied into Contents/Resources/.
datas = [
    # Django app templates (health/templates is optional — health is currently API-only)
    (str(REPO_ROOT / "core" / "templates"), "core/templates"),
    *([(str(REPO_ROOT / "health" / "templates"), "health/templates")]
      if (REPO_ROOT / "health" / "templates").exists() else []),

    # Migrations (PyInstaller's static analysis misses these).
    (str(REPO_ROOT / "core" / "migrations"), "core/migrations"),
    (str(REPO_ROOT / "health" / "migrations"), "health/migrations"),

    # Non-Python data files loaded by health.logbook_import at runtime via
    # Path(__file__).parent / 'ai_prompts' — PyInstaller's static analysis
    # doesn't follow this kind of resource read.
    (str(REPO_ROOT / "health" / "ai_prompts"), "health/ai_prompts"),

    # Collected static assets (must be built BEFORE invoking PyInstaller).
    (str(STATIC_BUILD_DIR), "staticfiles"),

    # Desktop package itself (so launcher etc. are importable from the bundle).
    # This also drags in desktop/templates/ and desktop/static/ which the
    # Django app loader and WhiteNoise need at runtime.
    (str(REPO_ROOT / "desktop"), "desktop"),
    (str(REPO_ROOT / "desktop" / "templates"), "desktop/templates"),

    # Misc resources.
    (str(REPO_ROOT / "LICENSE"), "."),
    (str(REPO_ROOT / "THIRD-PARTY-NOTICES.txt"), "."),
]

# Add Django's bundled migrations and admin templates (auth, contenttypes,
# sessions, admin, messages).
datas += collect_data_files("django.contrib.auth", subdir="migrations")
datas += collect_data_files("django.contrib.contenttypes", subdir="migrations")
datas += collect_data_files("django.contrib.sessions", subdir="migrations")
datas += collect_data_files("django.contrib.admin", subdir="migrations")
datas += collect_data_files("django.contrib.messages", subdir="migrations")
datas += collect_data_files("django.contrib.admin", subdir="templates")
datas += collect_data_files("django.contrib.auth", subdir="templates")
datas += collect_data_files("rest_framework", subdir="templates")


# Modules PyInstaller's static analysis misses.
hiddenimports = [
    "django.template.loaders.app_directories",
    "django.contrib.admin.apps",
    "django.contrib.auth.apps",
    "django.contrib.contenttypes.apps",
    "django.contrib.messages.apps",
    "django.contrib.sessions.apps",
    "django.contrib.staticfiles.apps",
    "django_filters",
    "whitenoise",
    "whitenoise.middleware",
    "whitenoise.storage",
    "PIL.Image",
    "PIL._imagingft",
    "pymupdf",
    "fitz",
    "anthropic",
    "openai",
    # macOS Keychain backend.
    "keyring.backends.macOS",
    "keyring.backends.fail",
    "waitress",
    # pywebview + WKWebView binding (macOS).
    "webview",
    "webview.platforms.cocoa",
    "objc",
    "Foundation",
    "AppKit",
    "WebKit",
]

# Pull in all submodules of our own apps so app configs and signal handlers
# aren't dropped.
hiddenimports += collect_submodules("rest_framework")
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("health")
hiddenimports += collect_submodules("simple_aircraft_manager")
hiddenimports += collect_submodules("desktop")
hiddenimports += collect_submodules("webview")


# .icns icon. Generate from a 1024x1024 PNG via:
#   mkdir icon.iconset && \
#   sips -z 16 16     icon-1024.png --out icon.iconset/icon_16x16.png && \
#   ... (and so on for 32, 64, 128, 256, 512, 1024) && \
#   iconutil -c icns icon.iconset -o desktop/icon.icns
ICON_PATH = REPO_ROOT / "desktop" / "icon.icns"
icon_kw = {"icon": str(ICON_PATH)} if ICON_PATH.exists() else {}


a = Analysis(
    [str(REPO_ROOT / "desktop" / "launcher.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",  # not used; saves ~20 MB
        "test",
        "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No Terminal window pops up at launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # Build for the host architecture (arm64 on M-series)
    codesign_identity=None,
    entitlements_file=None,
    **icon_kw,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SimpleAircraftManager",
)

# Wrap COLLECT output in a proper macOS .app bundle. PyInstaller copies the
# COLLECT result into Contents/MacOS/ and writes Info.plist with the keys
# below merged into the standard template.
app = BUNDLE(
    coll,
    name="Simple Aircraft Manager.app",
    bundle_identifier="app.simpleaircraftmanager.desktop",
    info_plist={
        "CFBundleShortVersionString": "0.1.0-poc",
        "CFBundleVersion": "0.1.0-poc",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # Allow the app to talk to its own loopback Django server. Without
        # this, ATS may block plain-HTTP requests to 127.0.0.1.
        "NSAppTransportSecurity": {
            "NSAllowsLocalNetworking": True,
        },
        # Keep the dock icon and menu bar — we are a foreground GUI app,
        # not a background agent.
        "LSUIElement": False,
    },
    **icon_kw,
)
