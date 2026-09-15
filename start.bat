@echo off
rem cmd/PowerShell/double-click entry: forwards to Git Bash start.sh (single source of truth)
cd /d "%~dp0"
"C:\Program Files\Git\bin\bash.exe" -l ./start.sh
