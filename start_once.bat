@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply 正式运行入口已统一
echo ========================================
echo 为防止重复生成 AWB，本文件不再直接运行账号。
echo.
echo 正确操作：
echo 1. 双击 start_mobile.bat
echo 2. 手机打开控制中心
echo 3. 只点击一次“开始今日发货”
echo.
echo 本地 ZIP 恢复请运行 start_recovery.bat。
pause
exit /b 0
