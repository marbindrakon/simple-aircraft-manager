# Build the Windows desktop bundle and Inno Setup installer.
# Run from the repo root in PowerShell on Windows 11 with Python 3.12 and
# Inno Setup 6 installed (iscc.exe in PATH).

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

Write-Host "=== Step 1/5: Create venv (if missing) ==="
if (-not (Test-Path ".\venv")) {
    py -3.12 -m venv venv
}
.\venv\Scripts\Activate.ps1

Write-Host "=== Step 2/5: Install dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-desktop.txt

Write-Host "=== Step 3/5: Collect static assets ==="
$env:DJANGO_SETTINGS_MODULE = "simple_aircraft_manager.settings_desktop"
$env:SAM_DESKTOP_AUTH_MODE = "disabled"
$env:SAM_BUILD_STATIC_ROOT = "$RepoRoot\build\staticfiles"
if (Test-Path $env:SAM_BUILD_STATIC_ROOT) {
    Remove-Item -Recurse -Force $env:SAM_BUILD_STATIC_ROOT
}
# Temporarily point STATIC_ROOT at the build dir for collectstatic.
# (settings_desktop.py defaults STATIC_ROOT to a runtime path; collectstatic
# needs a writable build path.)
python -c "
import os, django, shutil
os.environ['STATIC_ROOT_OVERRIDE'] = os.environ['SAM_BUILD_STATIC_ROOT']
django.setup()
from django.conf import settings
settings.STATIC_ROOT = os.environ['STATIC_ROOT_OVERRIDE']
from django.core.management import call_command
call_command('collectstatic', interactive=False, verbosity=1)
"

Write-Host "=== Step 4/5: Run PyInstaller ==="
if (Test-Path ".\dist\SimpleAircraftManager") {
    Remove-Item -Recurse -Force .\dist\SimpleAircraftManager
}
python -m PyInstaller desktop\sam-windows.spec --noconfirm

Write-Host "=== Step 5/5: Run Inno Setup ==="
if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) {
    Write-Error "iscc.exe (Inno Setup 6) not on PATH. Install from https://jrsoftware.org/isinfo.php and add to PATH."
}
iscc desktop\installer.iss

$Installer = Get-ChildItem -Path .\Output\SimpleAircraftManagerSetup*.exe | Select-Object -First 1
Write-Host "=== Build complete ==="
Write-Host "Installer: $($Installer.FullName)"
