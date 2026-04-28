; Inno Setup script for Simple Aircraft Manager
; Compile with: iscc desktop\installer.iss
; Produces: Output\SimpleAircraftManagerSetup-<version>.exe

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
var
  AuthPage: TInputOptionWizardPage;
  CredsPage: TInputQueryWizardPage;
  ApiKeyPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  AuthPage := CreateInputOptionPage(
    wpWelcome,
    'Authentication',
    'How do you want to sign in?',
    'Choose whether the app should require a username and password.',
    True, False);
  AuthPage.Add('Require username and password (recommended)');
  AuthPage.Add('No login (single-user trusted-device mode)');
  AuthPage.Values[0] := True;

  CredsPage := CreateInputQueryPage(
    AuthPage.ID,
    'Initial Login',
    'Choose your username and password',
    'These credentials will be created on first launch. You can change the password later from inside the app.');
  CredsPage.Add('Username:', False);
  CredsPage.Add('Password:', True);
  CredsPage.Add('Confirm password:', True);

  ApiKeyPage := CreateInputQueryPage(
    CredsPage.ID,
    'AI Features (optional)',
    'Anthropic API key',
    'Paste your API key here to enable AI-powered logbook import. Leave blank to skip; you can add a key later via Windows Credential Manager. The key is stored encrypted using Windows Credential Manager (DPAPI).');
  ApiKeyPage.Add('API key:', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = CredsPage.ID then
    Result := AuthPage.Values[1];  { skip creds page when "no login" selected }
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Username, Password, Confirm: string;
begin
  Result := True;
  if CurPageID = CredsPage.ID then begin
    Username := Trim(CredsPage.Values[0]);
    Password := CredsPage.Values[1];
    Confirm := CredsPage.Values[2];
    if Length(Username) < 3 then begin
      MsgBox('Username must be at least 3 characters.', mbError, MB_OK);
      Result := False;
      exit;
    end;
    if Length(Password) < 8 then begin
      MsgBox('Password must be at least 8 characters.', mbError, MB_OK);
      Result := False;
      exit;
    end;
    if Password <> Confirm then begin
      MsgBox('Passwords do not match.', mbError, MB_OK);
      Result := False;
      exit;
    end;
  end;
end;

function GetUserDataDir(): string;
begin
  Result := ExpandConstant('{localappdata}\SimpleAircraftManager');
end;

function JsonEscape(Value: string): string;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure WriteConfigIni(AuthMode: string);
var
  Path, Content: string;
begin
  Path := AddBackslash(GetUserDataDir()) + 'config.ini';
  Content := '[auth]' + #13#10 + 'mode = ' + AuthMode + #13#10;
  if not SaveStringToFile(Path, Content, False) then
    MsgBox('Could not write config.ini at ' + Path, mbError, MB_OK);
end;

procedure WriteBootstrapJson(Username, Password: string);
var
  Path, Content: string;
  EscUser, EscPass: string;
begin
  EscUser := JsonEscape(Username);
  EscPass := JsonEscape(Password);
  Path := AddBackslash(GetUserDataDir()) + 'bootstrap.json';
  Content := '{"username": "' + EscUser + '", "password": "' + EscPass + '"}';
  if not SaveStringToFile(Path, Content, False) then
    MsgBox('Could not write bootstrap.json at ' + Path, mbError, MB_OK);
end;

procedure WriteApiKeySeed(ApiKey: string);
var
  Path: string;
begin
  if Trim(ApiKey) = '' then exit;
  Path := AddBackslash(GetUserDataDir()) + 'api_key_seed.txt';
  if not SaveStringToFile(Path, Trim(ApiKey), False) then
    MsgBox('Could not write API key seed at ' + Path, mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AuthMode: string;
begin
  if CurStep = ssPostInstall then begin
    ForceDirectories(GetUserDataDir());

    if AuthPage.Values[0] then begin
      AuthMode := 'required';
      WriteBootstrapJson(Trim(CredsPage.Values[0]), CredsPage.Values[1]);
    end else begin
      AuthMode := 'disabled';
    end;

    WriteConfigIni(AuthMode);
    WriteApiKeySeed(ApiKeyPage.Values[0]);
  end;
end;
