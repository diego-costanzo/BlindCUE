; Inno Setup script for the self-contained Windows installer of BlindCue.
; Build with packaging\windows\build.ps1 - it passes AppVersion / AppVersionNum.
; Installs per user (no admin rights) into %LOCALAPPDATA%\Programs\BlindCue;
; the fixed AppId makes a newer version install over the old one.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef AppVersionNum
  #define AppVersionNum "0.0.0.0"
#endif
#define AppName "BlindCue"
#define Root "..\.."

[Setup]
AppId={{3A84585C-9E42-425F-B514-F26DF973C01C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Diego Costanzo
AppPublisherURL=https://github.com/diego-costanzo/BlindCUE
AppSupportURL=https://github.com/diego-costanzo/BlindCUE/issues
VersionInfoVersion={#AppVersionNum}
VersionInfoProductVersion={#AppVersionNum}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} {#AppVersion} setup
; Program Files, like other programs. With admin rights {autopf} is C:\Program Files, HKA is HKLM
; and the shortcuts are for all users. Older versions were installed per user in
; %LOCALAPPDATA%\Programs\BlindCue: [Code] removes that copy.
DefaultDirName={autopf}\BlindCue
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Root}\LICENSE
SetupIconFile={#Root}\setup\assets\blindcue.ico
UninstallDisplayIcon={app}\BlindCue.exe
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/normal
SolidCompression=yes
OutputDir={#Root}\dist
OutputBaseFilename=BlindCue-Setup-{#AppVersion}
CloseApplications=yes
; 5.14: a double-click on a .blindcue file opens the show
ChangesAssociations=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Root}\dist\BlindCue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\BlindCue.exe"
#if FileExists(AddBackslash(SourcePath) + Root + "\blindcue\help\manual_it.html")
Name: "{autoprograms}\{#AppName} - Manuale"; Filename: "{app}\_internal\help\manual_it.html"; Languages: italian
Name: "{autoprograms}\{#AppName} - Manual"; Filename: "{app}\_internal\help\manual_en.html"; Languages: english
Name: "{autoprograms}\{#AppName} - Instrukcja"; Filename: "{app}\_internal\help\manual_pl.html"; Languages: polish
#endif
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\BlindCue.exe"; Tasks: desktopicon

[Registry]
; 5.14: .blindcue files open in the program (HKA is HKLM with PrivilegesRequired=admin; the per-user
; keys of older versions are removed with their uninstaller, else HKCU would win over HKLM).
Root: HKA; Subkey: "Software\Classes\.blindcue"; ValueType: string; ValueName: ""; ValueData: "BlindCue.Show"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\BlindCue.Show"; ValueType: string; ValueName: ""; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\BlindCue.Show\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\BlindCue.exe,0"
Root: HKA; Subkey: "Software\Classes\BlindCue.Show\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\BlindCue.exe"" ""%1"""

[Run]
Filename: "{app}\BlindCue.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  { The same AppId as above, installed per user by the older versions. }
  PerUserUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{3A84585C-9E42-425F-B514-F26DF973C01C}_is1';

{ Remove the per-user copy before installing into Program Files: two copies would both be in the
  Start menu, and its HKCU file association would win over the new one. Settings, shows and autosave
  are not touched. Found only when the person who installed it confirms the UAC prompt. }
procedure RemovePerUserInstall();
var
  Uninstaller: String;
  ResultCode, Waited: Integer;
begin
  if not RegQueryStringValue(HKCU, PerUserUninstallKey, 'UninstallString', Uninstaller) then
    exit;
  Uninstaller := RemoveQuotes(Uninstaller);
  if not FileExists(Uninstaller) then
    exit;
  Log('Removing the per-user installation: ' + Uninstaller);
  if Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    { An Inno uninstaller hands over to a copy of itself in TEMP and returns at once: wait for its key to go. }
    Waited := 0;
    while RegKeyExists(HKCU, PerUserUninstallKey) and (Waited < 60) do
    begin
      Sleep(500);
      Waited := Waited + 1;
    end;
    Log('Per-user uninstaller code ' + IntToStr(ResultCode) + ', waited ' + IntToStr(Waited * 500) + ' ms');
  end
  else
    Log('Per-user uninstaller could not start: ' + SysErrorMessage(ResultCode));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemovePerUserInstall();
end;
