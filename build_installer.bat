@echo off
cd /d "%~dp0"
set PY=
py -3 --version >nul 2>nul && set PY=py -3
if not defined PY python --version >nul 2>nul && set PY=python
if not defined PY (
  echo Python is not installed.
  echo 1. Download it from https://www.python.org/downloads/
  echo 2. In the installer tick "Add python.exe to PATH"
  echo 3. Run this file again
  pause
  exit /b 1
)
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail

echo.
echo === 1/2 Building AdminPanel.exe ===
%PY% -m PyInstaller --noconsole --onefile --uac-admin --icon assets\icon.ico --name AdminPanel admin_panel.py
if not exist "dist\AdminPanel.exe" goto fail

echo.
echo === 2/2 Building the installer ===
%PY% -m PyInstaller --noconsole --onefile --uac-admin --icon assets\icon.ico --name AdminPanel-Setup ^
  --add-data "dist\AdminPanel.exe;payload" --add-data "assets\icon.ico;payload" ^
  --distpath installer_output --workpath build_setup installer.py
if not exist "installer_output\AdminPanel-Setup.exe" goto fail

echo.
echo Done. The installer is here: installer_output\AdminPanel-Setup.exe
pause
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
