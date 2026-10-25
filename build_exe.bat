@echo off
setlocal
cd /d "%~dp0"
set "BUILD_PY=python"
if not "%~1"=="" set "BUILD_PY=%~1"
"%BUILD_PY%" -c "import sys,struct; assert sys.version_info[:3]==(3,8,10) and struct.calcsize('P')==4, 'Use official Python 3.8.10 x86'"
if errorlevel 1 goto fail
"%BUILD_PY%" -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
"%BUILD_PY%" -m PyInstaller --noconfirm --clean win7.spec
if errorlevel 1 goto fail
echo Build complete: dist\ESP32_Flasher_Win7.exe
exit /b 0
:fail
echo Build failed.
exit /b 1
