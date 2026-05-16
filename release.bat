@echo off
setlocal

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 release.py %*
) else (
    python release.py %*
)

endlocal
