@echo off
cd /d "%~dp0"
py -c "import flask, requests" >nul 2>&1
if errorlevel 1 (
  echo Installing required Python packages...
  py -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Could not install the required packages.
    echo Run: py -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
py server.py
pause
