# One-time setup of a Windows VM for building the SAM desktop installer.
# Installs Python 3.12, Git, and Inno Setup 6; adds them to the system PATH;
# creates the build directory; and adds a Defender exclusion so Inno Setup
# can write the output exe without file-locking interference.
#
# Safe to re-run — every step is idempotent (skips if already done).
# Must be run as Administrator.
#
# Usage (from an elevated PowerShell prompt):
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\desktop\setup-build-vm.ps1

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$PythonVersion = "3.12.9"
$BuildDir      = "C:\build"

# ── helpers ──────────────────────────────────────────────────────────────────

function Write-Step { param([string]$Msg) Write-Host "`n=== $Msg ===" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  [ok]   $Msg" -ForegroundColor Green }
function Write-Skip { param([string]$Msg) Write-Host "  [skip] $Msg" -ForegroundColor DarkGray }

function Get-RemoteFile {
    param([string]$Url, [string]$Dest)
    if (Test-Path $Dest) { return }
    Write-Host "  Downloading $([System.IO.Path]::GetFileName($Dest))..."
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

function Install-Silently {
    # Runs a GUI installer as a subprocess and throws on non-zero exit.
    # Using Start-Process -Wait avoids PowerShell's NativeCommandError
    # and gives us a clean ExitCode instead of $LASTEXITCODE.
    # Note: parameter must NOT be named $Args — that shadows PowerShell's
    # automatic $args variable and comes through null.
    param([string]$Label, [string]$Exe, [string]$Switches)
    Write-Host "  Installing $Label..."
    $proc = Start-Process $Exe -ArgumentList $Switches -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "$Label installer exited $($proc.ExitCode)" }
}

function Add-ToSystemPath {
    param([string]$Dir)
    $current = [System.Environment]::GetEnvironmentVariable("Path", "Machine") -split ";"
    if ($current -contains $Dir) {
        Write-Skip "PATH: $Dir"
        return
    }
    $joined = ($current + $Dir) -join ";"
    [System.Environment]::SetEnvironmentVariable("Path", $joined, "Machine")
    Write-OK "Added to system PATH: $Dir"
}

# ── 1. Python 3.12 ───────────────────────────────────────────────────────────

Write-Step "Python $PythonVersion"

$PyExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (Test-Path $PyExe) {
    $pyVer = & $PyExe --version 2>&1
    Write-Skip "Python already installed ($pyVer)"
} else {
    $installer = "$env:TEMP\python-$PythonVersion-amd64.exe"
    Get-RemoteFile "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" $installer
    Install-Silently "Python $PythonVersion" $installer `
        "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1"
    if (-not (Test-Path $PyExe)) { throw "Python install succeeded but exe not found at $PyExe" }
    Write-OK "Python $PythonVersion installed"
}

# ── 2. Git for Windows ───────────────────────────────────────────────────────

Write-Step "Git for Windows"

$GitExe = "C:\Program Files\Git\cmd\git.exe"
if (Test-Path $GitExe) {
    $gitVer = & $GitExe --version
    Write-Skip "Git already installed ($gitVer)"
} else {
    Write-Host "  Fetching latest Git for Windows release from GitHub..."
    $rel    = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest"
    $gitUrl = ($rel.assets | Where-Object { $_.name -like "*64-bit.exe" }).browser_download_url
    $installer = "$env:TEMP\git-windows.exe"
    Get-RemoteFile $gitUrl $installer
    Install-Silently "Git for Windows" $installer `
        "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL /SP- /COMPONENTS=assoc,assoc_sh"
    if (-not (Test-Path $GitExe)) { throw "Git install succeeded but exe not found at $GitExe" }
    Write-OK "Git $($rel.tag_name) installed"
}
Add-ToSystemPath "C:\Program Files\Git\cmd"

# ── 3. Inno Setup 6 ──────────────────────────────────────────────────────────

Write-Step "Inno Setup 6"

$IsccExe = "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
if (Test-Path $IsccExe) {
    Write-Skip "Inno Setup 6 already installed"
} else {
    $installer = "$env:TEMP\innosetup.exe"
    # jrsoftware.org/download.php/is.exe redirects to the current stable release.
    Get-RemoteFile "https://jrsoftware.org/download.php/is.exe" $installer
    Install-Silently "Inno Setup 6" $installer "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
    if (-not (Test-Path $IsccExe)) { throw "Inno Setup install succeeded but iscc.exe not found" }
    Write-OK "Inno Setup 6 installed"
}
Add-ToSystemPath "C:\Program Files (x86)\Inno Setup 6"

# ── 4. Build directory ───────────────────────────────────────────────────────

Write-Step "Build directory ($BuildDir)"

if (Test-Path $BuildDir) {
    Write-Skip "$BuildDir already exists"
} else {
    New-Item -ItemType Directory -Path $BuildDir | Out-Null
    Write-OK "Created $BuildDir"
}

# ── 5. Windows Defender exclusions ───────────────────────────────────────────

Write-Step "Windows Defender exclusions"

# Without these, Defender locks partially-written exe files and causes
# Inno Setup to fail with "file in use" errors during the build.
$ExcludePaths = @(
    $BuildDir,
    "C:\Program Files (x86)\Inno Setup 6"
)
$existing = (Get-MpPreference).ExclusionPath
foreach ($path in $ExcludePaths) {
    if ($existing -contains $path) {
        Write-Skip "Defender exclusion: $path"
    } else {
        Add-MpPreference -ExclusionPath $path
        Write-OK "Defender exclusion added: $path"
    }
}

# ── summary ──────────────────────────────────────────────────────────────────

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Tools installed:"
Write-Host "  Python 3.12  $(& $PyExe --version 2>&1)"
Write-Host "  Git          $(& $GitExe --version)"
Write-Host "  Inno Setup 6 $IsccExe"
Write-Host ""
Write-Host "Next: open a NEW terminal (to pick up the updated PATH) then:"
Write-Host "  cd $BuildDir"
Write-Host "  git clone https://github.com/marbindrakon/simple-aircraft-manager.git"
Write-Host "  cd simple-aircraft-manager"
Write-Host "  git checkout feat/desktop-installer-poc"
Write-Host "  .\desktop\build-windows.ps1"
