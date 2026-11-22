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
DefaultDirName={autopf}\BlindCue
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
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

[Run]
Filename: "{app}\BlindCue.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
