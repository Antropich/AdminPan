; Inno Setup script. Build: build_installer.bat (or GitHub Actions, see README).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B464A112-9021-4963-834E-1B59EDDAEC2B}
AppName=Admin Panel
AppVersion={#AppVersion}
AppPublisher=Admin Panel
DefaultDirName={autopf}\Admin Panel
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=AdminPanel-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\AdminPanel.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\AdminPanel.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Admin Panel"; Filename: "{app}\AdminPanel.exe"
Name: "{autodesktop}\Admin Panel"; Filename: "{app}\AdminPanel.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AdminPanel.exe"; Description: "{cm:LaunchProgram,Admin Panel}"; Flags: nowait postinstall skipifsilent
