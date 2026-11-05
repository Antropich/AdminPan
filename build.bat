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
if errorlevel 1 (
  echo Installing libraries failed.
  pause
  exit /b 1
)
%PY% -m PyInstaller --noconsole --onefile --uac-admin --icon assets\icon.ico --name AdminPanel admin_panel.py
if not exist "dist\AdminPanel.exe" (
  echo Build failed, dist\AdminPanel.exe was not created.
  pause
  exit /b 1
)
echo.
echo Done. The program is in the "dist" folder: dist\AdminPanel.exe
pause
