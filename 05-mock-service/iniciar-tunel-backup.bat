@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run-tunnel.ps1" -Mode backup %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] El tunel backup termino con codigo %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
