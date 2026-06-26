@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply Environment Check
echo ========================================
python environment_check.py
set "RC=%ERRORLEVEL%"
if "%NO_PAUSE%"=="1" exit /b %RC%
pause
exit /b %RC%
