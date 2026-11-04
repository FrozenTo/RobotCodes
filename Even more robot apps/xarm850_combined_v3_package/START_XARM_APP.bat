@echo off
cd /d "%~dp0"
py xarm850_combined_controller_drawer_v3.py
if errorlevel 1 (
  echo.
  echo The app exited with an error. If a module is missing, run:
  echo   py -m pip install -r requirements.txt
  echo.
  pause
)
