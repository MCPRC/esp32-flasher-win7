@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD=python"
if not "%~1"=="" set "PYTHON_CMD=%~1"
"%PYTHON_CMD%" -c "import sys; assert sys.version_info[:2] == (3,8), 'Use Python 3.8.10 for Windows 7'"
if errorlevel 1 goto fail
if not exist ".venv\Scripts\python.exe" "%PYTHON_CMD%" -m venv .venv
if errorlevel 1 goto fail
if exist "wheelhouse\esptool-4.8.1-py3-none-any.whl" goto offline
".venv\Scripts\python.exe" -m pip install pip==24.3.1 setuptools==74.1.3 wheel==0.44.0
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
goto check
:offline
".venv\Scripts\python.exe" -m pip install --no-index --find-links=wheelhouse pip==24.3.1 setuptools==74.1.3 wheel==0.44.0
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --no-index --find-links=wheelhouse -r requirements.txt
:check
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import tkinter, serial, esptool; from cryptography.hazmat.primitives.ciphers import Cipher; print('Dependencies OK')"
if errorlevel 1 goto fail
echo Installation complete. Run start_win7.bat
pause
exit /b 0
:fail
echo Installation failed. See README.md. You can pass the full Python 3.8 path as argument.
pause
exit /b 1
