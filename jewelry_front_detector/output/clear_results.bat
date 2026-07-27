@echo off
echo Dang xoa cac file ket qua AI tu thu muc output...

cd /d "%~dp0\output"

:: Xoa cac file ket qua (chi giu lai anh goc)
del /q "*_result.json" 2>nul
del /q "*_result.jpg" 2>nul
del /q "*_panel.png" 2>nul
del /q "*_object.png" 2>nul

:: Xoa thu muc debug neu co
if exist "debug" (
    rmdir /s /q "debug"
)

echo.
echo Da xoa thanh cong tat ca file ket qua (chi con lai anh goc)!
echo.
pause
