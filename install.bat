@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo CrewSupply Install Dependencies
echo ========================================
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo ERROR: python or py was not found.
    pause
    exit /b 1
  )
  set "PY=py"
) else (
  set "PY=python"
)
%PY% --version
%PY% -m pip --version
if errorlevel 1 goto fail
%PY% -m pip install --upgrade pip
if errorlevel 1 goto fail
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto fail
%PY% -m playwright install chromium
if errorlevel 1 goto fail
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo Tesseract OK: C:\Program Files\Tesseract-OCR\tesseract.exe
) else (
  echo WARNING: Tesseract was not found. OCR may be unavailable.
)
echo Install completed. Account login states were not modified.
pause
exit /b 0
:fail
echo ERROR: Install failed. Review the message above.
pause
exit /b 1
