@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo Python launcher not found. Install Python and ensure py is available.
  exit /b 1
)

py -m pip install --user pyinstaller
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist-win rmdir /s /q dist-win

py -m PyInstaller --onefile --noconsole --add-data "config.json;." --name simpad-win simpad.py
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo Windows build created at dist\simpad-win.exe
pause
