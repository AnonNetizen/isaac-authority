@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch_watch_out_laser.ps1" -Action install
pause
