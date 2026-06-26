@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply Local Tests - No real website access
echo ========================================
python -m py_compile auto_all_integrated.py mobile_server.py pdf_processor.py shipping_report.py save_login.py environment_check.py
if errorlevel 1 goto fail
python -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo Local simulation tests passed.
if "%NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0
:fail
echo Local simulation tests failed.
if "%NO_PAUSE%"=="1" exit /b 1
pause
exit /b 1
