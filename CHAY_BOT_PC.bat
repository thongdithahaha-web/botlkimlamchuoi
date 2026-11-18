@echo off
title TikTok Auto-Reply Chain Bot - Ban File Sang Dien Thoai
cd /d "%~dp0\tiktok_autobot" 2>nul || cd /d "%~dp0"

:MENU
cls
echo ========================================================================
echo   TIKTOK AUTO-REPLY CHAIN BOT - CHUYEN FILE SANG DIEN THOAI
echo   Dev: lkimlamdev - Termux Android (IP: 192.168.1.76:8022)
echo ========================================================================
echo.
echo   [1] BAN TOAN BO CODE, MENU 7 MAU VA COOKIE SANG DIEN THOAI (0.5s) [Mac dinh]
echo   [2] Dang nhap va Tao file cookie session moi cho nick TikTok
echo   [3] Cai dat gio hen tren PC (Dong bo sang dien thoai)
echo   [4] Quan ly va Bo sung danh sach Target ban be (Xem danh sach, Them nick)
echo   [5] Chay truc tiep tren may tinh (Neu muon test tren PC)
echo.
echo   [0] Thoat
echo ========================================================================
echo.
set choice=
set /p choice="Nhap lua chon [1-5, 0] (Nhan Enter de ban file ngay): "
if "%choice%"=="" set choice=1
set choice=%choice: =%

if "%choice%"=="1" goto PUSH
if "%choice%"=="2" goto NEWSESSION
if "%choice%"=="3" goto STREAK_CONFIG
if "%choice%"=="4" goto MANAGE_TARGETS
if "%choice%"=="5" goto RUN_PC
if "%choice%"=="0" exit
goto PUSH

:PUSH
cls
echo ========================================================================
echo   DANG BAN TOAN BO DU LIEU SANG DIEN THOAI TERMUX...
echo ========================================================================
echo.
scp -r menu.py menu.sh CHAY_BOT_PHONE.sh hen_gio.py run_local.py run_multi.py sessions targets.txt streak_config.json time_api_config.json termux:~/tiktok_bot/
if errorlevel 1 (
    echo.
    echo [CANH BAO] Khong the ket noi toi Termux port 8022.
    echo Hay dam bao app Termux dang mo tren dien thoai va da bat sshd.
    echo.
    pause
    goto MENU
)
echo.
echo Dang dong bo du lieu vao he dieu hanh Ubuntu proot va cap quyen...
ssh termux "chmod +x ~/tiktok_bot/*.sh; proot-distro login ubuntu -- bash -c 'mkdir -p /root/tiktok_bot && cp -rf ~/tiktok_bot/* /root/tiktok_bot/ 2>/dev/null && chmod +x /root/tiktok_bot/*.sh && echo nameserver 8.8.8.8 > /etc/resolv.conf && rm -f /usr/bin/chromium-browser 2>/dev/null'"
echo.
echo ========================================================================
echo [THANH CONG] Toan bo code, menu 7 mau, cookie va lich hen da cap nhat
echo.
echo Tren dien thoai, boss man chi can mo Termux va go:
echo    ./menu.sh
echo ========================================================================
echo.
pause
goto MENU

:NEWSESSION
cls
echo ========================================================================
echo   DANG NHAP TAO COOKIE SESSION TIKTOK MOI
echo ========================================================================
echo.
set /p accname="Nhap ten goi nho cho nick nay (vi du: session4, clone1): "
if "%accname%"=="" set accname=session4
echo.
echo Dang mo trinh duyet de dang nhap TikTok cho '%accname%'...
python run_local.py --new-session "sessions\session_%accname%.json"
echo.
echo [Thong bao] Dang nhap xong hay chon muc 1 de ban nick moi sang dien thoai.
pause
goto MENU

:STREAK_CONFIG
cls
python hen_gio.py
echo.
set /p push_cfg="Ban gio hen nay sang dien thoai ngay? [y/n, mac dinh y]: "
if /i "%push_cfg%"=="n" goto MENU
scp streak_config.json termux:~/tiktok_bot/ 2>nul
ssh termux "cp -f ~/tiktok_bot/streak_config.json /root/tiktok_bot/streak_config.json 2>/dev/null" 2>nul
echo [Thanh cong] Da dong bo gio hen sang dien thoai.
pause
goto MENU

:MANAGE_TARGETS
cls
python hen_gio.py --targets
echo.
set /p push_tgt="Ban danh sach targets.txt moi nay sang dien thoai Termux ngay? [y/n, mac dinh y]: "
if /i "%push_tgt%"=="n" goto MENU
scp targets.txt termux:~/tiktok_bot/ 2>nul
ssh termux "cp -f ~/tiktok_bot/targets.txt /root/tiktok_bot/targets.txt 2>/dev/null" 2>nul
echo.
echo [Thanh cong] Da dong bo danh sach targets.txt sang dien thoai Termux!
pause
goto MENU

:RUN_PC
cls
echo ========================================================================
echo   CHAY TIKTOK BOT TRUC TIEP TREN MAY TINH
echo ========================================================================
echo.
echo   [1] Session 1 (Co cua so trinh duyet)
echo   [2] Session 1 (Chay an Headless)
echo   [3] Chay da tai khoan song song (Nhap 1, 1 2, 1 2 3...)
echo   [4] Quan ly va Bo sung danh sach Target ban be truoc khi chay
echo.
echo   [0] Quay lai Menu chinh
echo ========================================================================
echo.
set pc_opt=
set /p pc_opt="Nhap lua chon tai khoan [1-4, 0, mac dinh 1]: "
if "%pc_opt%"=="" set pc_opt=1
set pc_opt=%pc_opt: =%
if "%pc_opt%"=="0" goto MENU
if "%pc_opt%"=="4" goto MANAGE_TARGETS

set pc_sess=1
if "%pc_opt%"=="3" (
    echo.
    set /p pc_sess="Nhap danh sach session (vi du: 1 2 hoac 1 2 3, mac dinh 1 2): "
    if "%pc_sess%"=="" set pc_sess=1 2
)

cls
echo ========================================================================
echo   CHON CHE DO GIU CHUOI LUA CHO TARGETS.TXT TREN PC
echo ========================================================================
echo.
echo   [1] BAN STREAK CHO TARGETS NGAY LAP TUC (Gui chuoi ngay roi xong) [Mac dinh]
echo   [2] CHAY HEN GIO HANG NGAY (Dung gio hen tu dong ban streak, khong rep nguoi la)
echo   [3] Xem va Bo sung danh sach Target ban be truoc khi ban
echo.
echo   [0] Quay lai Menu chinh
echo ========================================================================
echo.
set mode_opt=
set /p mode_opt="Nhap che do [1-3, 0, mac dinh 1]: "
if "%mode_opt%"=="" set mode_opt=1
set mode_opt=%mode_opt: =%
if "%mode_opt%"=="0" goto MENU
if "%mode_opt%"=="3" goto MANAGE_TARGETS

set BOT_M=target
if "%mode_opt%"=="1" set BOT_M=target
if "%mode_opt%"=="2" set BOT_M=hen_gio

cls
echo ========================================================================
echo   DANG KHOI CHAY BOT TREN PC (Che do: %BOT_M%)...
echo ========================================================================
echo.

if "%pc_opt%"=="1" python run_local.py -s 1 --mode %BOT_M%
if "%pc_opt%"=="2" python run_local.py -s 1 --headless --mode %BOT_M%
if "%pc_opt%"=="3" python run_multi.py --sessions "%pc_sess%" --mode %BOT_M%
pause
goto MENU
