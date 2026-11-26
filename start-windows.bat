@echo off
REM Double-click to keep watching from this PC (checks every ~3 minutes).
cd /d "%~dp0"
py -m pip install --quiet requests
py watcher.py --loop 180
pause
