#define AppName "Admin Panel"
#define AppVersion "1.2.0"
#define AppPublisher "Admin Panel"
#define AppExe "AdminPanel.exe"

[Setup]
AppId={{A21A40C9-5D12-4F22-A3BC-123456789ABC}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Admin Panel
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=AdminPanel-Setup
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\AdminPanel\Assets\AdminPanel.ico

[Files]
Source: "..\publish\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Admin Panel"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\Assets\AdminPanel.ico"
Name: "{autodesktop}\Admin Panel"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\Assets\AdminPanel.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить Admin Panel"; Flags: postinstall nowait skipifsilent

[Code]
const
  RuntimeUrl = 'https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe';

function HasDesktopRuntime10(): Boolean;
var
  FindRec: TFindRec;
  RuntimePath: String;
begin
  Result := False;
  RuntimePath := ExpandConstant('{autopf}\dotnet\shared\Microsoft.WindowsDesktop.App');
  if FindFirst(RuntimePath + '\10.*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          Result := True;
          break;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  RuntimeInstaller: String;
  ResultCode: Integer;
  PowerShellArgs: String;
begin
  Result := True;
  if HasDesktopRuntime10() then
  begin
    Log('.NET 10 Desktop Runtime already installed.');
    exit;
  end;

  if MsgBox('.NET 10 Desktop Runtime не найден. Установщик скачает и установит его автоматически. Продолжить?',
      mbConfirmation, MB_YESNO) <> IDYES then
  begin
    Result := False;
    exit;
  end;

  RuntimeInstaller := ExpandConstant('{tmp}\windowsdesktop-runtime-10.exe');
  PowerShellArgs := '-NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference=''SilentlyContinue''; Invoke-WebRequest -Uri ''' +
    RuntimeUrl + ''' -OutFile ''' + RuntimeInstaller + '''"';
  if not Exec('powershell.exe', PowerShellArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox('Не удалось скачать .NET. Проверьте подключение к интернету и запустите установщик повторно.',
      mbCriticalError, MB_OK);
    Result := False;
    exit;
  end;

  if not Exec(RuntimeInstaller, '/install /quiet /norestart', '', SW_SHOW,
      ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox('Не удалось установить .NET Desktop Runtime. Код: ' + IntToStr(ResultCode),
      mbCriticalError, MB_OK);
    Result := False;
  end;
end;
