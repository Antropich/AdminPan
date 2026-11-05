@echo off
cd /d "%~dp0"
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
  echo Inno Setup 6 is not installed.
  echo Download it from https://jrsoftware.org/isdl.php and run this file again.
  pause
  exit /b 1
)
set PY=
py -3 --version >nul 2>nul && set PY=py -3
if not defined PY python --version >nul 2>nul && set PY=python
if not defined PY (
  echo Python is not installed.
  pause
  exit /b 1
)
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
%PY% -m PyInstaller --noconsole --onefile --uac-admin --name AdminPanel admin_panel.py
if not exist "dist\AdminPanel.exe" goto fail
"%ISCC%" installer.iss
if not exist "installer_output\AdminPanel-Setup.exe" goto fail
echo.
echo Done. The installer is here: installer_output\AdminPanel-Setup.exe
pause
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
