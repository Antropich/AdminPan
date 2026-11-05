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
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installing libraries failed.
  pause
  exit /b 1
)
%PY% admin_panel.py
pause
