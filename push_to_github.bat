@echo off
title CONG CU PUSH CODE LEN GITHUB - AI PTS
color 0A

:MENU
cls
echo =======================================================================
echo          CONG CU TU DONG PUSH CODE LEN GITHUB (AI PTS)
echo =======================================================================
echo.
echo  Thu muc lam viec: %CD%
echo.
echo  [1] Kiem tra trang thai Git (Git Status)
echo  [2] Push nhanh (Tu dong tao Commit theo ngay gio)
echo  [3] Push voi Commit Message tu nhap
echo  [4] Keo code moi nhat tu GitHub ve (Git Pull)
echo  [5] Kiem tra duong dan Remote (Git Remote -v)
echo  [6] Thoat
echo.
echo =======================================================================
set "choice="
set /p choice="Nhap lua chon cua ban (1-6) roi nhan Enter: "

if "%choice%"=="1" goto STATUS
if "%choice%"=="2" goto QUICK_PUSH
if "%choice%"=="3" goto CUSTOM_PUSH
if "%choice%"=="4" goto PULL
if "%choice%"=="5" goto CHECK_REMOTE
if "%choice%"=="6" goto EXIT

echo.
echo Lua chon khong hop le! Vui long chon tu 1 den 6.
echo.
pause
goto MENU

:STATUS
cls
echo =======================================================================
echo                       TRANG THAI GIT STATUS
echo =======================================================================
echo.
git status
echo.
echo =======================================================================
pause
goto MENU

:QUICK_PUSH
cls
echo =======================================================================
echo                         PUSH NHANH LEN GITHUB
echo =======================================================================
echo.
set COMMIT_MSG=Auto update code: %DATE% %TIME%

echo [+] Dang them tat ca thay doi (git add .)...
git add .
echo.
echo [+] Dang tao Commit: "%COMMIT_MSG%"...
git commit -m "%COMMIT_MSG%"
echo.
echo [+] Dang push code len GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo [!] Thu push len nhanh master...
    git push origin master
)

echo.
echo =======================================================================
if %errorlevel%==0 (
    echo [THANH CONG] Da Push code len GitHub thanh cong!
) else (
    echo [THAT BAI] Push khong thanh cong! Vui long kiem tra mang hoac xung dot.
)
echo =======================================================================
pause
goto MENU

:CUSTOM_PUSH
cls
echo =======================================================================
echo                    PUSH VOI COMMIT MESSAGE TU NHAP
echo =======================================================================
echo.
echo Cac file da thay doi:
git status -s
echo.
set "COMMIT_MSG="
set /p COMMIT_MSG="Nhap noi dung ghi chu Commit: "

if "%COMMIT_MSG%"=="" (
    echo.
    echo [!] Noi dung commit khong duoc de trong!
    echo.
    pause
    goto CUSTOM_PUSH
)

echo.
echo [+] Dang them tat ca thay doi (git add .)...
git add .
echo.
echo [+] Dang tao Commit: "%COMMIT_MSG%"...
git commit -m "%COMMIT_MSG%"
echo.
echo [+] Dang push code len GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo [!] Thu push len nhanh master...
    git push origin master
)

echo.
echo =======================================================================
if %errorlevel%==0 (
    echo [THANH CONG] Da Push code len GitHub thanh cong!
) else (
    echo [THAT BAI] Push khong thanh cong! Vui long kiem tra mang hoac xung dot.
)
echo =======================================================================
pause
goto MENU

:PULL
cls
echo =======================================================================
echo                   KEO CODE MOI NHAT TU GITHUB VE (GIT PULL)
echo =======================================================================
echo.
echo [+] Dang keo code moi tu GitHub ve...
git pull origin main
if %errorlevel% neq 0 (
    git pull origin master
)
echo.
echo =======================================================================
pause
goto MENU

:CHECK_REMOTE
cls
echo =======================================================================
echo                   DUONG DAN GITHUB REMOTE REPOSITORY
echo =======================================================================
echo.
git remote -v
echo.
echo =======================================================================
pause
goto MENU

:EXIT
cls
echo Cam on ban da su dung cong cu! Tam biet.
echo.
pause
exit
