#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
menu điều khiển bot tiktok (bản điện thoại android termux)
giao diện tĩnh gọn nhẹ, không màu mè, không giật màn hình
tác giả: lê kim lâm (@lkimlam_165)
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime, timedelta

# cấu hình chuẩn utf-8 trên terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREAK_CONFIG_FILE = os.path.join(BASE_DIR, "streak_config.json")
TARGETS_FILE = os.path.join(BASE_DIR, "targets.txt")

def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")

# nạp giờ việt nam từ api hoặc hệ thống
def get_vietnam_now() -> datetime:
    try:
        import run_local
        if hasattr(run_local, "DualTimeSync"):
            return run_local.DualTimeSync.now()
    except Exception:
        pass
    return datetime.now()

# nạp cấu hình giờ hẹn
def load_streak_config() -> dict:
    cfg = {"enabled": True, "streak_time": "00:30", "target_date": ""}
    for p in [STREAK_CONFIG_FILE, os.path.join(BASE_DIR, "tiktok_bot", "streak_config.json"), "/root/tiktok_bot/streak_config.json"]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
                break
            except Exception:
                pass
    return cfg

# lưu cấu hình giờ hẹn
def save_streak_config(cfg: dict) -> bool:
    paths = [STREAK_CONFIG_FILE]
    if os.path.exists("/root/tiktok_bot"):
        paths.append("/root/tiktok_bot/streak_config.json")
    saved = False
    for p in paths:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            saved = True
        except Exception:
            pass
    return saved

# tính toán thời gian đếm ngược
def get_countdown_info() -> tuple:
    cfg = load_streak_config()
    st_str = cfg.get("streak_time", "00:30").strip()
    target_date = cfg.get("target_date", "").strip()
    try:
        h, m = map(int, st_str.split(":"))
    except Exception:
        h, m = 0, 30

    now = get_vietnam_now()
    if target_date:
        try:
            if "-" in target_date:
                parts = list(map(int, target_date.split("-")))
                y, mon, d = parts[0], parts[1], parts[2]
            elif "/" in target_date:
                parts = list(map(int, target_date.split("/")))
                if len(parts) == 3:
                    d, mon, y = parts[0], parts[1], parts[2]
                else:
                    d, mon = parts[0], parts[1]
                    y = now.year
            else:
                y, mon, d = now.year, now.month, now.day
            target_dt = datetime(y, mon, d, h, m, 0)
            lbl = f"{h:02d}:{m:02d} ngay {d:02d}/{mon:02d}/{y}"
        except Exception:
            target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target_dt <= now:
                target_dt += timedelta(days=1)
            lbl = f"{h:02d}:{m:02d} (hang ngay)"
    else:
        target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target_dt <= now:
            target_dt += timedelta(days=1)
        lbl = f"{h:02d}:{m:02d} (hang ngay)"

    diff = target_dt - now
    total_seconds = int(diff.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    rem_h = total_seconds // 3600
    rem_m = (total_seconds % 3600) // 60
    rem_s = total_seconds % 60

    countdown_text = f"con {rem_h} tieng {rem_m} phut {rem_s} giay nua bat dau cong viec"
    return lbl, countdown_text

# kiểm tra môi trường chạy
def detect_environment() -> dict:
    is_win = (os.name == "nt")
    is_ubuntu = False
    is_termux = False

    if not is_win:
        if os.path.exists("/etc/issue"):
            try:
                with open("/etc/issue", "r") as f:
                    if "ubuntu" in f.read().lower():
                        is_ubuntu = True
            except Exception:
                pass
        if not is_ubuntu and os.path.exists("/data/data/com.termux"):
            is_termux = True

    return {
        "is_windows": is_win,
        "is_ubuntu": is_ubuntu,
        "is_termux": is_termux,
    }

# thực thi lệnh bot
def execute_bot_command(cmd: str, in_background: bool = False):
    env = detect_environment()
    print(f"\n>> dang chuan bi khoi chay: {cmd}\n")

    if env["is_windows"]:
        full_cmd = f"python {cmd}"
        if in_background:
            subprocess.Popen(full_cmd, shell=True)
            print("[thanh cong] da khoi chay ngam tren may tinh!")
        else:
            subprocess.run(full_cmd, shell=True)
        return

    # trên ubuntu proot (hoặc termux)
    bot_dir = "/root/tiktok_bot" if os.path.exists("/root/tiktok_bot") else os.getcwd()
    if in_background:
        full_cmd = f"cd {bot_dir} && nohup python3 {cmd} > bot.log 2>&1 &"
        subprocess.run(full_cmd, shell=True)
        print("[thanh cong] bot da khoi chay ngam 24/7 (file log: bot.log)!")
        print("ban co the tat man hinh hoac dong termux, bot van chay lien tuc 24/7.")
    else:
        full_cmd = f"cd {bot_dir} && python3 {cmd}"
        subprocess.run(full_cmd, shell=True)

# cài đặt ngày giờ hẹn
def sub_setting_streak_time():
    clear_screen()
    cfg = load_streak_config()
    cur_time = cfg.get("streak_time", "00:30")
    cur_date = cfg.get("target_date", "")

    print("========================================================================")
    print("          cai dat ngay gio hen chu dong bat dau cong viec")
    print("========================================================================")
    print(f"  gio hen hien tai: {cur_time}")
    print(f"  ngay hen hien tai: {cur_date if cur_date else '(hang ngay)'}\n")

    val_time = input(">> nhap gio hen moi [dinh dang hh:mm, vd: 00:30, nhan enter de giu nguyen]: ").strip()
    if val_time:
        if ":" in val_time:
            cfg["streak_time"] = val_time
        else:
            print("dinh dang khong hop le, giu nguyen gio cu!")

    val_date = input(">> nhap ngay thang [vd: 17/11/2026, hoac de trong de chay hang ngay]: ").strip()
    cfg["target_date"] = val_date
    save_streak_config(cfg)
    print(f"\n[thanh cong] da luu gio hen moi: {cfg['streak_time']} | ngay: {cfg['target_date'] or 'hang ngay'}!")
    input("\nnhan enter de quay lai menu chinh...")

# kiểm tra đồng bộ giờ và xem đếm ngược
def sub_view_countdown():
    clear_screen()
    print("========================================================================")
    print("          kiem tra dong bo gio & dem nguoc thoi gian chi tiet")
    print("========================================================================")
    
    vn_now = get_vietnam_now()
    sys_now = datetime.now()
    lbl, cd_str = get_countdown_info()

    print(f"  gio viet nam (chuan api): {vn_now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  gio dong ho thiet bi:     {sys_now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  lich hen cong viec:       {lbl}")
    print(f"  thoi gian dem nguoc:      {cd_str}\n")
    print("------------------------------------------------------------------------")
    input("nhan enter de quay lai menu chinh...")

# thiết lập termux & sshd không bao giờ tắt
def sub_setup_keep_alive():
    clear_screen()
    print("========================================================================")
    print("       thiet lap termux & sshd chay ngam vinh vien khong bao gio tat")
    print("========================================================================")

    subprocess.run("termux-wake-lock 2>/dev/null", shell=True)
    subprocess.run("pgrep -x sshd > /dev/null || sshd 2>/dev/null", shell=True)

    print("\n3 buoc cai dat tren dien thoai de may khong bao gio tu tat:")
    print("  1. cai dat pin: vao cai dat -> pin -> quan ly pin ung dung -> termux -> bat 'cho phep hoat dong duoi nen' & 'tu khoi chay'.")
    print("  2. khoa ung dung: mo danh sach da nhiem (vuot len xem cac app dang mo) -> bam icon 3 cham o tren termux -> chon 'khoa' (o khoa).")
    print("  3. wifi lien tuc: vao cai dat wifi -> nang cao -> giu wifi luon bat khi man hinh tat.")
    print("\n[ket qua] tu nay du tat man hinh dien thoai, bot van chay vinh vien 24/7!\n")
    print("------------------------------------------------------------------------")
    input("nhan enter de quay lai menu chinh...")

# kiểm tra trạng thái bot đang chạy
def sub_check_bot_status():
    clear_screen()
    print("========================================================================")
    print("                   kiem tra trang thai bot dang chay")
    print("========================================================================")

    res = subprocess.run("pgrep -af 'python3 run_' 2>/dev/null", shell=True, capture_output=True, text=True)
    if res.stdout.strip():
        print("[dang hoat dong] phat hien bot dang chay ngam 24/7:")
        print(res.stdout.strip())
        bot_log_path = "/root/tiktok_bot/bot.log"
        if os.path.exists(bot_log_path):
            print("\n--- nhat ky hoat dong moi nhat (bot.log) ---")
            subprocess.run(f"tail -n 15 {bot_log_path}", shell=True)
    else:
        print("[thong bao] hien khong co bot nao dang chay ngam.")
        print("goi y: boss man hay chon muc [4] de khoi dong chay ngam 24/7 nhe!")

    print("\n------------------------------------------------------------------------")
    input("nhan enter de quay lai menu chinh...")

# dừng tất cả bot đang chạy
def sub_stop_all_bots():
    clear_screen()
    print("========================================================================")
    print("                     dung toan bo bot dang chay ngam")
    print("========================================================================")

    subprocess.run("pkill -9 -f 'python3 run_' 2>/dev/null", shell=True)
    subprocess.run("tmux kill-session -t bot 2>/dev/null", shell=True)
    print("[thanh cong] da tat toan bo tien trinh bot dang chay tren dien thoai!")

    print("\n------------------------------------------------------------------------")
    input("nhan enter de quay lai menu chinh...")


# menu tùy chọn session và chế độ
def sub_flexible_session():
    clear_screen()
    print("========================================================================")
    print("          tuy chon session linh hoat & chon che do van hanh")
    print("========================================================================")
    print("  vi du nhap session: 1       (chay session 1)")
    print("                      1 2     (chay song song session 1 va 2)")
    print("                      1 2 3   (chay song song ca 3 session)\n")

    sess_in = input(">> nhap cac session muon chay [mac dinh: 1 2]: ").strip()
    if not sess_in:
        sess_in = "1 2"

    print("\nchon che do van hanh cho targets.txt:")
    print("  [1] ban streak ngay lap tuc cho targets.txt roi xong [mac dinh]")
    print("  [2] chay hen gio hang ngay (dung gio hen tu dong ban streak, khong rep nguoi la)")

    m_choice = input("\n>> chon che do [1-2, mac dinh 1]: ").strip()
    mode_flag = "target" if m_choice != "2" else "hen_gio"

    bg_in = input("\n>> chay ngam (tat man hinh van chay)? [y/n, mac dinh y]: ").strip().lower()
    in_bg = (bg_in != "n")

    cmd = f"run_multi.py --sessions \"{sess_in}\" --headless --mode {mode_flag}"
    execute_bot_command(cmd, in_background=in_bg)
    input("\nnhan enter de quay lai menu chinh...")

# chạy trực tiếp session đơn
def sub_run_single(sess_num: int):
    clear_screen()
    print("========================================================================")
    print(f"             chay truc tiep session {sess_num} tren man hinh")
    print("========================================================================")
    print(f"chon che do van hanh cho session {sess_num}:")
    print("  [1] ban streak ngay lap tuc cho targets.txt roi xong [mac dinh]")
    print("  [2] chay hen gio hang ngay (dung gio hen tu dong ban streak, khong rep nguoi la)")

    m_choice = input("\n>> chon che do [1-2, mac dinh 1]: ").strip()
    mode_flag = "target" if m_choice != "2" else "hen_gio" 

    cmd = f"run_local.py -s {sess_num} --headless --mode {mode_flag}"
    execute_bot_command(cmd, in_background=False)
    input("\nnhan enter de quay lai menu chinh...")

# chạy ngầm 24/7 mặc định khuyên dùng
def sub_run_background_default():
    clear_screen()
    print("========================================================================")
    print("      khoi dong chay ngam hen gio giu chuoi targets.txt (khuyen dung)")
    print("========================================================================")
    cmd = "run_multi.py --sessions \"1 2\" --headless --mode hen_gio"
    execute_bot_command(cmd, in_background=True)
    input("\nnhan enter de quay lai menu chinh...")

# quản lý danh sách targets bạn bè
def sub_manage_targets():
    try:
        import hen_gio
        hen_gio.manage_targets()
    except Exception as e:
        print(f"Lỗi khi mở quản lý targets: {e}")
        input("\nNhấn Enter để quay lại menu chính...")

# hàm vòng lặp chính của menu
def main_menu():
    env = detect_environment()
    os_name = "windows"
    if env["is_ubuntu"]:
        os_name = "ubuntu proot (root)"
    elif env["is_termux"]:
        os_name = "termux android (proot ubuntu)"

    while True:
        clear_screen()
        lbl, cd_str = get_countdown_info()

        print("========================================================================")
        print("  tool tu dong giu chuoi lua tiktok (ban dien thoai termux)")
        print("  tac gia: le kim lam (@lkimlam_165) | ho tro termux")
        print("========================================================================")
        print(f"  he dieu hanh: {os_name}")
        print("  che do hien thi: 100% chay an headless (tiet kiem pin & ram)")
        print(f"  lich hen cong viec: {lbl}")
        print(f"  dem nguoc thoi gian: {cd_str}")
        print("------------------------------------------------------------------------")
        print("  [1] chay session 1 (chay truc tiep tren man hinh)")
        print("  [2] chay session 2 (chay truc tiep tren man hinh)")
        print("  [3] tuy chon session linh hoat (1, 2, 1 2, 1 2 3) + chon che do")
        print("  [4] chay ngam hen gio giu chuoi (tu dong thap lua hang ngay - khuyen dung)")
        print("  [5] cai dat ngay gio hen ban streak hang ngay (chinh gio, phut, ngay)")
        print("  [6] xem dem nguoc thoi gian chi tiet & kiem tra dong bo gio api")
        print("  [7] kiem tra trang thai bot dang chay ngam (tien trinh & log)")
        print("  [8] dung (tat) toan bo bot dang chay ngam")
        print("  [9] thiet lap termux & sshd khong bao gio tat (chay vinh vien 24/7)")
        print("  [t] quan ly & bo sung danh sach targets.txt (xem, them, sua nick ban be)")
        print("  [0] thoat menu")
        print("========================================================================")

        try:
            choice = input(">> chon chuc nang [0-9, t]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\ntam biet boss man!\n")
            break

        if choice == "1":
            sub_run_single(1)
        elif choice == "2":
            sub_run_single(2)
        elif choice == "3":
            sub_flexible_session()
        elif choice == "4":
            sub_run_background_default()
        elif choice == "5":
            sub_setting_streak_time()
        elif choice == "6":
            sub_view_countdown()
        elif choice == "7":
            sub_check_bot_status()
        elif choice == "8":
            sub_stop_all_bots()
        elif choice == "9":
            sub_setup_keep_alive()
        elif choice in ("t", "T", "target", "targets", "10"):
            sub_manage_targets()
        elif choice in ("0", "q", "Q"):
            print("\ntam biet boss man!\n")
            break
        else:
            pass

if __name__ == "__main__":
    main_menu()
