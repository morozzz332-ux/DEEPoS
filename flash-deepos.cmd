@echo off
rem Double-click to flash DEEPoS to the SD card (disk 2). UAC prompt must be accepted.
setlocal
set SCRIPT=%~dp0flash-deepos.ps1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -Wait -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%SCRIPT%')"
echo.
echo Log: %~dp0build\flash.log
pause
