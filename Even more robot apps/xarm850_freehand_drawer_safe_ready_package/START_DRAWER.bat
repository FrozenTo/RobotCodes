@echo off
cd /d "%~dp0"
py xarm850_freehand_drawer_safe_ready.py
if errorlevel 1 (
 echo.
 echo Failed to start. Confirm Python is installed and, for robot use,
 echo run: py -m pip install xarm-python-sdk
 pause
)
