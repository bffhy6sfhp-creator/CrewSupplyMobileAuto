@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "SOURCE=%USERPROFILE%\Desktop\CrewSupplyMobileAuto_v1"
if not exist "%SOURCE%\private" set /p "SOURCE=请粘贴旧项目文件夹完整路径: "
if not exist "%SOURCE%\private" (
  echo 未找到旧项目 private 文件夹。
  pause
  exit /b 1
)
mkdir private >nul 2>nul
copy /y "%SOURCE%\private\account_*.json" "private\" >nul
if exist "%SOURCE%\Reports" xcopy "%SOURCE%\Reports" "Reports\" /e /i /y >nul
if exist "%SOURCE%\Label" xcopy "%SOURCE%\Label" "Label\" /e /i /y >nul
if exist "%SOURCE%\data\production_run_history.json" copy /y "%SOURCE%\data\production_run_history.json" "data\production_run_history.json" >nul
if exist "%SOURCE%\assets\address.png" copy /y "%SOURCE%\assets\address.png" "assets\address.png" >nul
echo 导入完成。请运行 first_use_check.bat。
pause
