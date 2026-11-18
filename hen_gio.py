#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
công cụ cài đặt ngày giờ và đếm ngược thời gian bắt đầu công việc
tác giả: lkimlamdev
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREAK_CONFIG_FILE = os.path.join(BASE_DIR, "streak_config.json")
TARGETS_FILE = os.path.join(BASE_DIR, "targets.txt")

# nạp dual time sync nếu có
try:
    import run_local
    get_now = run_local.DualTimeSync.now
    get_source = run_local.DualTimeSync.source
except Exception:
    get_now = datetime.now
    get_source = lambda: "đồng hồ hệ thống"

# bảng màu 7 sắc cầu vồng ansi
RAINBOW = [196, 208, 226, 46, 51, 39, 201]
C_RED = "\033[38;5;196m"
C_ORANGE = "\033[38;5;208m"
C_YELLOW = "\033[38;5;226m"
C_GREEN = "\033[38;5;46m"
C_CYAN = "\033[38;5;51m"
C_BLUE = "\033[38;5;39m"
C_PURPLE = "\033[38;5;201m"
C_GRAY = "\033[38;5;248m"
RESET = "\033[0m"


def rainbow_line(text: str, shift: int = 0) -> str:
    res = []
    for i, ch in enumerate(text):
        c = RAINBOW[(i + shift) % len(RAINBOW)]
        res.append(f"\033[38;5;{c}m{ch}")
    res.append(RESET)
    return "".join(res)


def load_config() -> dict:
    cfg = {"enabled": True, "streak_time": "00:30", "target_date": ""}
    if os.path.exists(STREAK_CONFIG_FILE):
        try:
            with open(STREAK_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    try:
        with open(STREAK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"{C_RED}lỗi khi lưu cấu hình: {e}{RESET}")
        return False


def calculate_countdown(cfg: dict) -> tuple:
    streak_time = cfg.get("streak_time", "00:30").strip()
    target_date = cfg.get("target_date", "").strip()

    try:
        h, m = map(int, streak_time.split(":"))
    except Exception:
        h, m = 0, 30

    now = get_now()

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
            target_label = f"{h:02d}:{m:02d} ngày {d:02d}/{mon:02d}/{y}"
        except Exception:
            target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target_dt <= now:
                target_dt += timedelta(days=1)
            target_label = f"{streak_time} (hàng ngày)"
    else:
        target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target_dt <= now:
            target_dt += timedelta(days=1)
        target_label = f"{streak_time} (hàng ngày)"

    delta = target_dt - now
    total_sec = int(delta.total_seconds())

    if total_sec < 0:
        return target_label, "đã qua giờ hẹn", 0

    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60

    parts = []
    if days > 0:
        parts.append(f"{days} ngày")
    if hours > 0:
        parts.append(f"{hours} tiếng")
    if minutes > 0:
        parts.append(f"{minutes} phút")
    parts.append(f"{seconds} giây")

    countdown_str = "còn " + " ".join(parts) + " nữa bắt đầu công việc"
    return target_label, countdown_str, total_sec


def live_countdown_view(cfg: dict):
    print(f"\n{C_CYAN}đang theo dõi đếm ngược thời gian thực (nhấn ctrl + c hoặc enter để dừng):{RESET}")
    try:
        while True:
            target_label, countdown, sec = calculate_countdown(cfg)
            now_str = get_now().strftime("%H:%M:%S")
            sys.stdout.write(f"\r\033[K{C_YELLOW}[{now_str}]{RESET} {C_GREEN}{countdown}{RESET} {C_GRAY}(lịch: {target_label}){RESET}")
            sys.stdout.flush()
            time.sleep(1)
    except (KeyboardInterrupt, Exception):
        print("\n")


def load_targets_list() -> list:
    targets = []
    if os.path.exists(TARGETS_FILE):
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if raw and not raw.startswith("#"):
                    clean = raw.lstrip("@").strip()
                    if "/" in clean:
                        clean = clean.split("/")[-1].lstrip("@")
                    if clean and clean not in targets:
                        targets.append(clean)
    return targets


def save_targets_list(targets: list):
    try:
        with open(TARGETS_FILE, "w", encoding="utf-8") as f:
            f.write("# ========================================================================\n")
            f.write("# danh sach tai khoan ban be giu chuoi lua tiktok (targets.txt)\n")
            f.write("# tac gia: le kim lam (@lkimlam_165)\n")
            f.write("# ========================================================================\n")
            for u in targets:
                f.write(f"{u}\n")
        return True
    except Exception as e:
        print(f"{C_RED}lỗi khi lưu targets: {e}{RESET}")
        return False


def manage_targets():
    while True:
        targets = load_targets_list()
        print("\n" + rainbow_line("========================================================================"))
        print(f"       {C_YELLOW}quản lý & bổ sung danh sách bạn bè giữ chuỗi ({len(targets)} nick){RESET}")
        print(rainbow_line("========================================================================"))
        if targets:
            for idx, u in enumerate(targets, 1):
                print(f"  {C_CYAN}{idx:2d}.{RESET} @{u}")
        else:
            print(f"  {C_GRAY}(danh sách hiện tại đang trống){RESET}")
        print(rainbow_line("------------------------------------------------------------------------", 2))
        print(f"  {C_GREEN}[1]{RESET} thêm nick bạn bè mới (nhập 1 hoặc nhiều nick cách nhau bằng dấu cách/phẩy)")
        print(f"  {C_RED}[2]{RESET} xóa 1 nick khỏi danh sách (nhập số thứ tự)")
        print(f"  {C_YELLOW}[3]{RESET} mở file targets.txt (notepad trên windows / nano trên termux)")
        print(f"  {C_PURPLE}[4]{RESET} xóa toàn bộ danh sách")
        print(f"  {C_GRAY}[0]{RESET} quay lại menu")
        print(rainbow_line("========================================================================", 4))

        sub = input(f"{C_CYAN}>> chọn chức năng [0-4, mặc định 0]: {RESET}").strip()
        if sub == "1":
            raw_input_u = input(f"\n{C_CYAN}nhập username tiktok (vd: ndn_nhan hoac _devvibecode, linhbo_25): {RESET}").strip()
            if raw_input_u:
                tokens = raw_input_u.replace(",", " ").replace(";", " ").split()
                added_count = 0
                for tok in tokens:
                    clean = tok.strip().lstrip("@")
                    if "/" in clean:
                        clean = clean.split("/")[-1].lstrip("@")
                    if clean and clean not in targets:
                        targets.append(clean)
                        added_count += 1
                if added_count > 0:
                    save_targets_list(targets)
                    print(f"{C_GREEN}đã bổ sung thành công {added_count} nick vào targets.txt! (tổng: {len(targets)} nick){RESET}")
                else:
                    print(f"{C_YELLOW}nick này đã có sẵn trong danh sách!{RESET}")
            time.sleep(1.2)
        elif sub == "2":
            if not targets:
                print(f"{C_RED}danh sách đang trống!{RESET}")
                time.sleep(1)
                continue
            del_idx = input(f"{C_CYAN}nhập số thứ tự nick muốn xóa [1-{len(targets)}]: {RESET}").strip()
            if del_idx.isdigit():
                idx_int = int(del_idx)
                if 1 <= idx_int <= len(targets):
                    removed = targets.pop(idx_int - 1)
                    save_targets_list(targets)
                    print(f"{C_GREEN}đã xóa @{removed} khỏi danh sách targets!{RESET}")
                else:
                    print(f"{C_RED}số thứ tự không tồn tại!{RESET}")
            time.sleep(1.2)
        elif sub == "3":
            if sys.platform == "win32":
                os.system(f"start notepad {TARGETS_FILE}")
                print(f"{C_GREEN}đã mở file {TARGETS_FILE} bằng notepad!{RESET}")
            else:
                os.system(f"nano {TARGETS_FILE}")
            time.sleep(1.2)
        elif sub == "4":
            confirm = input(f"{C_RED}xác nhận xóa toàn bộ danh sách? (y/n): {RESET}").strip().lower()
            if confirm == "y":
                targets = []
                save_targets_list(targets)
                print(f"{C_GREEN}đã làm trống danh sách targets.txt!{RESET}")
            time.sleep(1.2)
        elif sub in ("0", ""):
            break


def main_menu():
    while True:
        cfg = load_config()
        now_dt = get_now()
        target_label, countdown, sec = calculate_countdown(cfg)

        print("\n" + rainbow_line("========================================================================"))
        print(f"       {C_YELLOW}cài đặt ngày giờ & đếm ngược bắt đầu công việc{RESET}")
        print(f"              {C_GRAY}tác giả: lkimlamdev | đồng bộ thời gian thực{RESET}")
        print(rainbow_line("========================================================================"))
        print(f"  {C_CYAN}thời gian hiện tại:{RESET} {now_dt.strftime('%H:%M:%S')} (ngày {now_dt.strftime('%d/%m/%Y')})")
        print(f"  {C_CYAN}nguồn thời gian:{RESET}    {get_source()}")
        print(f"  {C_YELLOW}lịch hẹn công việc:{RESET} {target_label}")
        print(f"  {C_GREEN}thời gian còn lại:{RESET}  \033[1m{countdown}\033[0m")
        print(rainbow_line("------------------------------------------------------------------------", 2))
        print(f"  {C_RED}[1]{RESET} chỉnh giờ phút hẹn (hiện tại: {cfg.get('streak_time', '00:30')})")
        
        cur_d = cfg.get("target_date", "")
        cur_d_label = cur_d if cur_d else "hàng ngày"
        print(f"  {C_ORANGE}[2]{RESET} chỉnh ngày tháng hẹn (hiện tại: {cur_d_label})")
        print(f"  {C_YELLOW}[3]{RESET} xem đồng hồ đếm ngược chạy từng giây thời gian thực")
        print(f"  {C_GREEN}[4]{RESET} quản lý danh sách nick bạn bè nhận chuỗi (targets.txt)")
        print(f"  {C_PURPLE}[5]{RESET} chuyển đổi bật/tắt tự động giữ chuỗi (hiện tại: {'bật' if cfg.get('enabled', True) else 'tắt'})")
        print(f"  {C_GRAY}[0]{RESET} lưu và quay lại menu chính")
        print(rainbow_line("========================================================================", 4))

        choice = input(f"{C_CYAN}>> chọn chức năng [0-5]: {RESET}").strip()

        if choice == "1":
            print(f"\n{C_YELLOW}ví dụ nhập: 00:30, 01:15, 12:00, 23:45{RESET}")
            new_t = input(f"{C_CYAN}nhập giờ phút mới (HH:MM) [mặc định: 00:30]: {RESET}").strip()
            if not new_t:
                new_t = "00:30"
            if ":" in new_t:
                try:
                    parts = new_t.split(":")
                    h, m = int(parts[0]), int(parts[1])
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        cfg["streak_time"] = f"{h:02d}:{m:02d}"
                        save_config(cfg)
                        print(f"{C_GREEN}đã cập nhật giờ hẹn thành: {cfg['streak_time']}!{RESET}")
                    else:
                        print(f"{C_RED}giờ phút không hợp lệ! (0-23:0-59){RESET}")
                except Exception:
                    print(f"{C_RED}định dạng không đúng, vui lòng nhập theo dạng HH:MM{RESET}")
            else:
                print(f"{C_RED}vui lòng nhập có dấu hai chấm : (ví dụ 00:30){RESET}")
            time.sleep(1)

        elif choice == "2":
            print(f"\n{C_YELLOW}tùy chọn ngày hẹn:{RESET}")
            print(f"  - bấm Enter hoặc nhập {C_GREEN}0{RESET} để hẹn: {C_GREEN}hàng ngày{RESET}")
            print(f"  - hoặc nhập ngày tháng cụ thể (ví dụ: {C_CYAN}17/11{RESET} hoặc {C_CYAN}17/11/2026{RESET} hoặc {C_CYAN}2026-11-17{RESET})")
            new_d = input(f"{C_CYAN}nhập ngày hẹn mới: {RESET}").strip()
            if not new_d or new_d in ("0", "all", "hang_ngay", "hang ngay"):
                cfg["target_date"] = ""
                save_config(cfg)
                print(f"{C_GREEN}đã đặt lịch chạy: hàng ngày!{RESET}")
            else:
                try:
                    if "/" in new_d:
                        p = list(map(int, new_d.split("/")))
                        if len(p) == 2:
                            d, mon = p
                            y = now_dt.year
                        else:
                            d, mon, y = p
                    elif "-" in new_d:
                        p = list(map(int, new_d.split("-")))
                        if len(p) == 3:
                            y, mon, d = p
                        else:
                            mon, d = p
                            y = now_dt.year
                    else:
                        d = int(new_d)
                        mon = now_dt.month
                        y = now_dt.year
                    formatted_d = f"{y:04d}-{mon:02d}-{d:02d}"
                    cfg["target_date"] = formatted_d
                    save_config(cfg)
                    print(f"{C_GREEN}đã đặt lịch hẹn vào ngày: {d:02d}/{mon:02d}/{y:04d}!{RESET}")
                except Exception as ex:
                    print(f"{C_RED}ngày tháng không hợp lệ: {ex}{RESET}")
            time.sleep(1.2)

        elif choice == "3":
            live_countdown_view(cfg)

        elif choice == "4":
            manage_targets()
            input(f"\n{C_GRAY}nhấn enter để quay lại...{RESET}")

        elif choice == "5":
            cfg["enabled"] = not cfg.get("enabled", True)
            save_config(cfg)
            st = f"{C_GREEN}bật{RESET}" if cfg["enabled"] else f"{C_RED}tắt{RESET}"
            print(f"\nđã chuyển trạng thái tự động giữ chuỗi sang: {st}")
            time.sleep(1)

        elif choice == "0":
            print(f"\n{C_GREEN}đã lưu toàn bộ cài đặt!{RESET}")
            break


if __name__ == "__main__":
    if any(arg in sys.argv for arg in ("--targets", "-t", "targets", "target")):
        try:
            manage_targets()
        except KeyboardInterrupt:
            print(f"\n{C_GRAY}đã thoát.{RESET}")
        sys.exit(0)
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{C_GRAY}đã thoát.{RESET}")
