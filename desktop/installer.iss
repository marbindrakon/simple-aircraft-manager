; Inno Setup script for Simple Aircraft Manager
; Compile with: iscc desktop\installer.iss
; Produces: Output\SimpleAircraftManagerSetup-<version>.exe
;
; The installer is intentionally minimal: it only checks for the WebView2
; runtime and copies the bundle into %LOCALAPPDATA%. The first-run setup
; wizard (auth mode, credentials, optional Anthropic API key) lives inside
; the app itself — the launcher detects a missing config.ini and serves a
; setup form at /desktop-setup/ that the user fills in and submits. The
; same setup form is the golden path on macOS and Linux too.

#define AppName "Simple Aircraft Manager"
#define AppVersion "0.1.0-poc"
#define AppPublisher "Simple Aircraft Manager"
#define AppExeName "sam.exe"

[Setup]
AppId={{E1F2A301-AAAA-4D1F-9F3C-3A8C5B6D7E8F}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\SimpleAircraftManager
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputBaseFilename=SimpleAircraftManagerSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\SimpleAircraftManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed(): Boolean;
var
  Version: string;
begin
  Result := False;
  { Per-machine 64-bit install — most common on Win10/11. }
  if RegQueryStringValue(
       HKEY_LOCAL_MACHINE,
       'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
       'pv', Version) and (Trim(Version) <> '') and (Version <> '0.0.0.0') then
  begin
    Result := True;
    exit;
  end;
  { Per-machine 32-bit (rare). }
  if RegQueryStringValue(
       HKEY_LOCAL_MACHINE,
       'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
       'pv', Version) and (Trim(Version) <> '') and (Version <> '0.0.0.0') then
  begin
    Result := True;
    exit;
  end;
  { Per-user (HKCU) install. }
  if RegQueryStringValue(
       HKEY_CURRENT_USER,
       'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
       'pv', Version) and (Trim(Version) <> '') and (Version <> '0.0.0.0') then
  begin
    Result := True;
    exit;
  end;
end;

function InitializeSetup(): Boolean;
var
  Response: Integer;
  ErrorCode: Integer;
begin
  if WebView2Installed() then begin
    Result := True;
    exit;
  end;

  Response := MsgBox(
    'Simple Aircraft Manager requires the Microsoft Edge WebView2 Runtime, ' +
    'which is not installed on this PC.' + #13#10 + #13#10 +
    'Click OK to open the Microsoft download page in your browser. ' +
    'Install the WebView2 Runtime, then run this installer again.',
    mbInformation, MB_OKCANCEL);

  if Response = IDOK then begin
    ShellExec('open',
      'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
      '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;

  Result := False;  { Abort install. }
end;
