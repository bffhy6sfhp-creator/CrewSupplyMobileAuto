@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply 本地 ZIP 恢复（不访问网站）
echo ========================================
set /p "ZIP_PATH=请粘贴 AWB ZIP 完整路径: "
if "%ZIP_PATH%"=="" goto fail
set /p "ACCOUNT=账号名称（默认 account_YOUT）: "
if "%ACCOUNT%"=="" set "ACCOUNT=account_YOUT"
set /p "HOLD_ID=Hold Sale ID（没有则直接回车）: "
if "%HOLD_ID%"=="" (
  python -u auto_all_integrated.py --resume-zip "%ZIP_PATH%" --account "%ACCOUNT%"
) else (
  python -u auto_all_integrated.py --resume-zip "%ZIP_PATH%" --account "%ACCOUNT%" --hold-sale-id "%HOLD_ID%" --hold-error "Order on hold"
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo 恢复完成。请查看 Reports 文件夹。
) else (
  echo 恢复失败。请保留此窗口截图。
)
pause
exit /b %RC%
:fail
echo 未输入 ZIP 路径。
pause
exit /b 1
