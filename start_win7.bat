@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -c "import tkinter, serial, esptool"
if errorlevel 1 goto missing
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
exit /b
:missing
echo Please install Python 3.8.10 and run install_win7.bat first.
pause
exit /b 1
