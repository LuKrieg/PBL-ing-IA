@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run-docker.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] No se pudo iniciar el Mock Service en Docker ^(codigo %EXIT_CODE%^).
)
pause
exit /b %EXIT_CODE%
