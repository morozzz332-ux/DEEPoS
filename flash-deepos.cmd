@echo off
rem Double-click to flash DEEPoS to the unique matching SD card. UAC prompt must be accepted.
setlocal
set "DEEPOS_FLASH_SCRIPT=%~dp0flash-deepos.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $quoted = [char]34 + $env:DEEPOS_FLASH_SCRIPT + [char]34; $p = Start-Process -FilePath powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$quoted); exit $p.ExitCode } catch { Write-Error $_ -ErrorAction Continue; exit 1 }"
set "FLASH_EXIT=%ERRORLEVEL%"
echo.
echo Log: "%~dp0build\flash.log"
pause
exit /b %FLASH_EXIT%
