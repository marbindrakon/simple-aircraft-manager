# Build the Windows desktop bundle and Inno Setup installer.
# Run from the repo root in PowerShell on Windows 11 with Python 3.12 and
# Inno Setup 6 installed (iscc.exe in PATH).

# Stop on PowerShell cmdlet errors, but check native-command exit codes
# explicitly — $ErrorActionPreference = "Stop" treats any native-command
# stderr as fatal, which breaks pip and PyInstaller (they write progress to
# stderr even on success).
$ErrorActionPreference = "Stop"

function Invoke-Native {
    # Native tools (pip, PyInstaller, iscc) write progress to stderr.
    # $ErrorActionPreference = Stop misreads that as a fatal NativeCommandError.
    # Setting it to Continue inside this function is local to this scope and
    # its children — it doesn't affect the outer script's Stop preference.
    param([string]$Label, [scriptblock]$Cmd)
    $ErrorActionPreference = "Continue"
    & $Cmd 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

Write-Host "=== Step 1/5: Create venv (if missing) ==="
if (-not (Test-Path ".\venv")) {
    Invoke-Native "venv creation" { py -3.12 -m venv venv }
}
.\venv\Scripts\Activate.ps1

Write-Host "=== Step 2/5: Install dependencies ==="
Invoke-Native "pip upgrade"                  { python -m pip install --upgrade pip }
Invoke-Native "pip install requirements"     { python -m pip install -r requirements.txt }
Invoke-Native "pip install requirements-desktop" { python -m pip install -r requirements-desktop.txt }

Write-Host "=== Step 3/5: Collect static assets ==="
$env:DJANGO_SETTINGS_MODULE = "simple_aircraft_manager.settings_desktop"
$env:SAM_DESKTOP_AUTH_MODE = "disabled"
$env:SAM_BUILD_STATIC_ROOT = "$RepoRoot\build\staticfiles"
if (Test-Path $env:SAM_BUILD_STATIC_ROOT) {
    Remove-Item -Recurse -Force $env:SAM_BUILD_STATIC_ROOT
}
Invoke-Native "collectstatic" {
    python -c "
import os, django
os.environ['STATIC_ROOT_OVERRIDE'] = os.environ['SAM_BUILD_STATIC_ROOT']
django.setup()
from django.conf import settings
settings.STATIC_ROOT = os.environ['STATIC_ROOT_OVERRIDE']
from django.core.management import call_command
call_command('collectstatic', interactive=False, verbosity=1)
"
}

Write-Host "=== Step 4/5: Run PyInstaller ==="
if (Test-Path ".\dist\SimpleAircraftManager") {
    Remove-Item -Recurse -Force .\dist\SimpleAircraftManager
}
Invoke-Native "PyInstaller" { python -m PyInstaller desktop\sam-windows.spec --noconfirm }

Write-Host "=== Step 5/5: Run Inno Setup ==="
if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) {
    throw "iscc.exe (Inno Setup 6) not on PATH. Install from https://jrsoftware.org/isinfo.php and add to PATH."
}
Invoke-Native "Inno Setup" { iscc desktop\installer.iss }

$Installer = Get-ChildItem -Path .\desktop\Output\SimpleAircraftManagerSetup*.exe | Select-Object -First 1
Write-Host "=== Build complete ==="
Write-Host "Installer: $($Installer.FullName)"
