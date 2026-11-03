@echo off
cd /d "%~dp0"
title xArm 850 Shared Drawing Website
py server.py
if errorlevel 1 (
  echo.
  echo Could not start using the py launcher. Trying python...
  python server.py
)
echo.
echo The server has stopped. Press any key to close.
pause >nul
