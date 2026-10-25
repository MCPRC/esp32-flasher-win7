@echo off
setlocal
cd /d "%~dp0"
rem Run using the same Python 3.8 architecture as the target Win7 computer.
python -c "import sys; assert sys.version_info[:2] == (3,8), 'Use Python 3.8.10'"
if errorlevel 1 goto fail
python -m pip install pip==24.3.1 setuptools==74.1.3 wheel==0.44.0
if errorlevel 1 goto fail
python -m pip wheel --wheel-dir wheelhouse -r requirements.txt pip==24.3.1 setuptools==74.1.3 wheel==0.44.0
if errorlevel 1 goto fail
echo Copy the complete folder, including wheelhouse, to the target PC.
pause
exit /b 0
:fail
echo Offline preparation failed.
pause
exit /b 1
