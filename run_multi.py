#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok Multi-Session DM Auto-Reply Bot (Chạy song song nhiều tài khoản)
Tác giả / Dev: lkimlamdev
Đặc điểm:
 - Quản lý và chạy đồng thời nhiều tài khoản TikTok trên cùng 1 trình duyệt Chromium
 - Mỗi tài khoản là 1 BrowserContext độc lập 100% (cô lập cookie, cache)
 - Tiết kiệm tối đa RAM và CPU (phù hợp cho cả PC và Android Termux)
 - Tự động quét toàn bộ file session*.json trong thư mục bot và thư mục sessions/
"""

import glob
import json
import logging
import os
import sys
import time
from playwright.sync_api import sync_playwright

import run_local

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

log = run_local.log


def discover_sessions() -> list:
    """Tự động tìm kiếm tất cả các file session cookie có trong hệ thống."""
    session_files = []
    # 1. Ưu tiên tìm trong thư mục con sessions/ nếu có file
    if os.path.exists(SESSIONS_DIR):
        for f in glob.glob(os.path.join(SESSIONS_DIR, "*.json")):
            session_files.append(os.path.abspath(f))

    # 2. Nếu thư mục sessions/ rỗng thì nạp các file session*.json ở thư mục gốc
    if not session_files:
        for f in glob.glob(os.path.join(BASE_DIR, "session*.json")):
            abs_p = os.path.abspath(f)
            if abs_p not in session_files:
                session_files.append(abs_p)

    return sorted(session_files)


def resolve_session_item(item: str) -> str:
    """Quy đổi linh hoạt giữa '1', '2', 'session1', 'acc2' thành đường dẫn file json chính xác."""
    item = item.strip().strip("'\"")
    if not item:
        return None
    if os.path.isabs(item) and os.path.exists(item):
        return item

    norm = item.lower().replace("-", "_").replace(".json", "")
    cand_names = [
        f"{item}.json" if not item.endswith(".json") else item,
        f"{norm}.json",
        f"session{norm}.json",
        f"session_{norm}.json",
        item,
    ]
    if norm in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
        cand_names.insert(0, f"session{norm}.json")
        cand_names.insert(0, f"session_{norm}.json")
    elif norm.startswith("acc"):
        num = norm.replace("acc", "").strip("_")
        cand_names.insert(0, f"session{num}.json")
        cand_names.insert(0, f"session_{norm}.json")

    for name in cand_names:
        p1 = os.path.join(SESSIONS_DIR, name)
        if os.path.exists(p1):
            return os.path.abspath(p1)
        p2 = os.path.join(BASE_DIR, name)
        if os.path.exists(p2):
            return os.path.abspath(p2)

    return None


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   TikTok Multi-Account Auto-Reply by lkimlamdevcode      ║
╚══════════════════════════════════════════════════════════╝
""")
    # Tạo thư mục sessions nếu chưa có
    os.makedirs(SESSIONS_DIR, exist_ok=True)

    # Kiểm tra tham số máy chủ remote
    remote_server_url = None
    custom_sessions = []
    bot_mode = "target"  # "target", "hen_gio"

    for idx, arg in enumerate(sys.argv):
        if arg == "--server" and idx + 1 < len(sys.argv):
            remote_server_url = sys.argv[idx + 1].strip()
        elif arg in ("--mode", "-m") and idx + 1 < len(sys.argv):
            m_val = sys.argv[idx + 1].strip().lower()
            if m_val in ("target", "now", "target_now", "send_now", "ban_ngay"):
                bot_mode = "target"
            elif m_val in ("hen_gio", "schedule", "chudong", "chu_dong", "both", "247"):
                bot_mode = "hen_gio"
        elif arg in ("--sessions", "-s") and idx + 1 < len(sys.argv):
            raw = sys.argv[idx + 1].strip()
            # Hỗ trợ phân tách bằng dấu cách, dấu phẩy hoặc chấm phẩy (ví dụ: '1 2', '1 2 3', '1,2')
            clean_tokens = raw.replace(",", " ").replace(";", " ").split()
            for token in clean_tokens:
                res = resolve_session_item(token)
                if res and res not in custom_sessions:
                    custom_sessions.append(res)
                elif not res:
                    log.warning(f"[Cảnh báo] Không tìm thấy file session cho: '{token}'")

    hub = run_local.RemoteHubSync(remote_server_url)

    # Thu thập danh sách các session
    if custom_sessions:
        session_files = custom_sessions
    else:
        session_files = discover_sessions()

    if not session_files:
        log.error("[Lỗi] Không tìm thấy file session nào!")
        log.info("Hướng dẫn: Hãy copy các file cookie (vd: session_acc1.json, session_acc2.json) vào:")
        log.info(f"   -> Thư mục: {SESSIONS_DIR}")
        return

    log.info(f"[Đa tài khoản] Phát hiện {len(session_files)} tài khoản TikTok cần chạy song song:")
    for idx, sf in enumerate(session_files, start=1):
        log.info(f"   [{idx}] {os.path.basename(sf)}")

    is_headless = "--headless" in sys.argv or (not os.environ.get("DISPLAY") and sys.platform != "win32")
    log.info(f"[Trình duyệt] Chế độ: {'Headless (Chạy nền)' if is_headless else 'Cửa sổ trực quan'}")

    # Đồng bộ Đồng hồ Kép (Internet Atomic + OS Hardware)
    run_local.DualTimeSync.sync_network_time()
    drift_str = f"{run_local.DualTimeSync._offset_seconds:+.2f}s"
    log.info(f"[Đồng hồ kép] Nguồn giờ: {run_local.DualTimeSync.source()} | Giờ chuẩn: {run_local.DualTimeSync.now().strftime('%Y-%m-%d %H:%M:%S')} (Độ lệch: {drift_str})")

    with sync_playwright() as pw:
        exec_path = None
        for candidate in ["/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/google-chrome"]:
            if os.path.exists(candidate):
                exec_path = candidate
                break

        launch_kwargs = {
            "headless": is_headless,
            "slow_mo": 20 if not is_headless else 0,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if exec_path and sys.platform != "win32":
            launch_kwargs["executable_path"] = exec_path

        browser = pw.chromium.launch(**launch_kwargs)

        # Khởi tạo từng tài khoản với Context cô lập
        accounts = []
        for sf in session_files:
            tag = os.path.splitext(os.path.basename(sf))[0]
            log.info(f"[{tag}] Đang khởi tạo phiên làm việc...")

            context = browser.new_context(
                viewport={"width": 1280, "height": 800} if is_headless else None,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="vi-VN",
            )

            # Nạp cookie
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    context.add_cookies(json.load(f))
            except Exception as e:
                log.warning(f"[{tag}] Lỗi khi nạp cookie {sf}: {e}")
                continue

            page = context.new_page()
            try:
                page.goto("https://www.tiktok.com/messages", timeout=45000)
                page.wait_for_timeout(2000)
            except Exception as e:
                log.warning(f"[{tag}] Lỗi tải trang tin nhắn: {e}")

            quota_file = os.path.join(BASE_DIR, f"user_quota_{tag}.json")
            quota_tracker = run_local.UserQuotaTracker(file_path=quota_file)

            accounts.append({
                "tag": tag,
                "session_file": sf,
                "context": context,
                "page": page,
                "quota_tracker": quota_tracker,
                "cooldown_cache": {},
            })
            log.info(f"[{tag}] Đã kết nối hộp thư thành công!")

        if not accounts:
            log.error("[Lỗi] Không có tài khoản nào đăng nhập thành công. Dừng tiến trình.")
            return

        log.info(f"\n[San sang] Da kich hoat dong thoi {len(accounts)} tai khoan. San sang giu chuoi lua...")
        if bot_mode == "hen_gio":
            cfg = run_local.load_streak_config()
            target_t = cfg.get("streak_time", "00:30")
            target_d = cfg.get("target_date", "")
            d_lbl = f" ngay {target_d}" if target_d else " (hang ngay)"
            log.info(f"[Lich hen] Da khoa gio giu chuoi luc {target_t}{d_lbl}.")
            log.info(f"   -> Che do: DUNG GIO HEN {target_t} tu dong gui chuoi lua cho targets.txt. KHONG rep tin nguoi la.")
        else:
            log.info("[Che do] BAN STREAK NGAY LAP TUC: Gui chuoi lua ngay cho targets.txt roi hoan tat.")

        cycle = 0
        while True:
            cycle += 1
            for acc in accounts:
                tag = acc["tag"]
                page = acc["page"]
                q_tracker = acc["quota_tracker"]

                try:
                    if not page.url.startswith("https://www.tiktok.com/messages"):
                        page.goto("https://www.tiktok.com/messages", timeout=30000)
                        page.wait_for_timeout(1500)

                    # Gui chuoi lua cho danh sach targets.txt
                    force_send = (bot_mode == "target")
                    run_local.check_and_send_daily_streaks(page, hub, q_tracker, force_now=force_send, session_tag=tag)
                except Exception as err:
                    log.warning(f"[{tag}] Loi trong chu ky giu chuoi: {err}")

            if bot_mode == "target":
                log.info("[Hoan tat] Da ban xong chuoi streak cho toan bo nick trong targets.txt tren tat ca tai khoan. Ket thuc!")
                break

            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Dừng] Đã tắt toàn bộ các tài khoản. Tạm biệt!")
