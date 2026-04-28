# Build the Windows desktop bundle and Inno Setup installer.
# Run from the repo root in PowerShell on Windows 11 with Python 3.12 and
# Inno Setup 6 installed (iscc.exe in PATH).

# Stop on PowerShell cmdlet errors, but check native-command exit codes
# explicitly — $ErrorActionPreference = "Stop" treats any native-command
# stderr as fatal, which breaks pip and PyInstaller (they write progress to
# stderr even on success).
$ErrorActionPreference = "Stop"

function Assert-LastExit([string]$Label) {
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

Write-Host "=== Step 1/5: Create venv (if missing) ==="
if (-not (Test-Path ".\venv")) {
    py -3.12 -m venv venv
    Assert-LastExit "venv creation"
}
.\venv\Scripts\Activate.ps1

Write-Host "=== Step 2/5: Install dependencies ==="
# python -m pip avoids Windows file-locking when upgrading pip itself.
# 2>&1 merges pip's stderr progress into stdout so PowerShell doesn't
# misread informational notices as NativeCommandErrors.
python -m pip install --upgrade pip 2>&1 | Out-Null
python -m pip install -r requirements.txt 2>&1
Assert-LastExit "pip install requirements.txt"
python -m pip install -r requirements-desktop.txt 2>&1
Assert-LastExit "pip install requirements-desktop.txt"

Write-Host "=== Step 3/5: Collect static assets ==="
$env:DJANGO_SETTINGS_MODULE = "simple_aircraft_manager.settings_desktop"
$env:SAM_DESKTOP_AUTH_MODE = "disabled"
$env:SAM_BUILD_STATIC_ROOT = "$RepoRoot\build\staticfiles"
if (Test-Path $env:SAM_BUILD_STATIC_ROOT) {
    Remove-Item -Recurse -Force $env:SAM_BUILD_STATIC_ROOT
}
python -c "
import os, django
os.environ['STATIC_ROOT_OVERRIDE'] = os.environ['SAM_BUILD_STATIC_ROOT']
django.setup()
from django.conf import settings
settings.STATIC_ROOT = os.environ['STATIC_ROOT_OVERRIDE']
from django.core.management import call_command
call_command('collectstatic', interactive=False, verbosity=1)
" 2>&1
Assert-LastExit "collectstatic"

Write-Host "=== Step 4/5: Run PyInstaller ==="
if (Test-Path ".\dist\SimpleAircraftManager") {
    Remove-Item -Recurse -Force .\dist\SimpleAircraftManager
}
python -m PyInstaller desktop\sam-windows.spec --noconfirm 2>&1
Assert-LastExit "PyInstaller"

Write-Host "=== Step 5/5: Run Inno Setup ==="
if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) {
    throw "iscc.exe (Inno Setup 6) not on PATH. Install from https://jrsoftware.org/isinfo.php and add to PATH."
}
iscc desktop\installer.iss 2>&1
Assert-LastExit "Inno Setup"

$Installer = Get-ChildItem -Path .\Output\SimpleAircraftManagerSetup*.exe | Select-Object -First 1
Write-Host "=== Build complete ==="
Write-Host "Installer: $($Installer.FullName)"
