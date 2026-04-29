# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows desktop bundle.

Produces a one-folder bundle at dist/SimpleAircraftManager/ containing sam.exe
and an _internal/ tree with the Python runtime, all third-party packages,
collected static assets, templates, and migrations.

Build prereq: run `python manage.py collectstatic --noinput
--settings=simple_aircraft_manager.settings_desktop` first so STATIC_ROOT
contains the assets that get copied via `datas` below.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

REPO_ROOT = Path(SPECPATH).parent  # SPECPATH is provided by PyInstaller
STATIC_BUILD_DIR = REPO_ROOT / "build" / "staticfiles"


# Resource files copied into _internal/.
datas = [
    # Django app templates (health/templates is optional — health is currently API-only)
    (str(REPO_ROOT / "core" / "templates"), "core/templates"),
    *([( str(REPO_ROOT / "health" / "templates"), "health/templates")]
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

    # Misc resources Inno Setup also reads.
    (str(REPO_ROOT / "LICENSE"), "."),
    (str(REPO_ROOT / "THIRD-PARTY-NOTICES.txt"), "."),
    (str(REPO_ROOT / "desktop" / "icon.ico"), "desktop"),
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
    "pypdfium2",
    "pypdfium2_raw",
    "anthropic",
    "openai",
    "keyring.backends.Windows",
    "keyring.backends.fail",
    "waitress",
    # pywebview + Edge WebView2 binding (Windows).
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr_loader",
    "pythonnet",
]

# Pull in all submodules of our own apps so app configs and signal handlers
# aren't dropped.
hiddenimports += collect_submodules("rest_framework")
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("health")
hiddenimports += collect_submodules("simple_aircraft_manager")
hiddenimports += collect_submodules("desktop")
hiddenimports += collect_submodules("webview")


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
    console=False,  # No console window on launch
    disable_windowed_traceback=False,
    icon=str(REPO_ROOT / "desktop" / "icon.ico"),
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
