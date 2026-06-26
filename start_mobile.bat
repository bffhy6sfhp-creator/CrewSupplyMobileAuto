@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply Mobile Control Center
echo ========================================
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo Port 8000 is already in use. The mobile service may already be running.
  echo Open http://YOUR-LAN-IP:8000 from your phone.
  pause
  exit /b 0
)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo LAN URL candidate: http://%%a:8000
python -m uvicorn mobile_server:app --host 0.0.0.0 --port 8000
pause
