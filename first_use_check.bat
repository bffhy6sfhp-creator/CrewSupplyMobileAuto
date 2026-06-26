@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply 第一次使用检查
echo ========================================
set "NO_PAUSE=1"
call check_environment.bat
if errorlevel 1 goto fail
call test_local.bat
if errorlevel 1 goto fail
echo.
echo 全部检查通过。现在可以运行 start_mobile.bat。
pause
exit /b 0
:fail
echo 检查未通过，请根据上方 MISSING 或 FAILED 修复。
pause
exit /b 1
