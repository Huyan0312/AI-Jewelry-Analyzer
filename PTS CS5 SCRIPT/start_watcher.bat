@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

where pyw.exe >nul 2>&1
if not errorlevel 1 (
    start "" /b pyw.exe "%SCRIPT_DIR%ps_watcher.pyw"
    exit /b 0
)

where pythonw.exe >nul 2>&1
if not errorlevel 1 (
    start "" /b pythonw.exe "%SCRIPT_DIR%ps_watcher.pyw"
    exit /b 0
)

where py.exe >nul 2>&1
if not errorlevel 1 (
    start "" /b py.exe "%SCRIPT_DIR%ps_watcher.pyw"
    exit /b 0
)

exit /b 1
