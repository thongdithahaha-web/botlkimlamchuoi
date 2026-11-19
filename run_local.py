#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok DM Auto-Reply Chain Bot (Chạy 24/7 trên PC & Android Termux)
Tác giả / Dev: lkimlamdev
Đặc điểm:
 - 100% Zero-Dependency │ Không cần bất kỳ API Key nào
 - Chuỗi 3 câu thoại cố định
 - Giới hạn tối đa 10 lượt rep cho mỗi tài khoản
 - Tích hợp Bảng điều khiển từ xa ngụy trang trang 404 bảo mật tuyệt đối
   (Click 10 lần vào '404 Not Found' để mở bảng đăng nhập, mật khẩu: Lam*2025)
 - Hỗ trợ đồng bộ từ xa với Cloud Server (Render / Railway / Cloudflare Tunnel)
"""

import email.utils
import json
import logging
import os
import random
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

try:
    import server
except ImportError:
    server = None

# ══════════════════════════════════════════════════════════════════════════
#  CẤU HÌNH HỆ THỐNG
# ══════════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "session.json")
USER_QUOTA_FILE = os.path.join(BASE_DIR, "user_quota.json")
TARGETS_FILE = os.path.join(BASE_DIR, "targets.txt")
STREAK_CONFIG_FILE = os.path.join(BASE_DIR, "streak_config.json")
STREAK_HISTORY_FILE = os.path.join(BASE_DIR, "streak_history.json")
TIME_API_CONFIG_FILE = os.path.join(BASE_DIR, "time_api_config.json")

# Chuỗi tin nhắn tự động gửi liên tiếp (Chain Reply)
REPLY_CHAIN = [
    "lkimlamdevbot",
    "🔥",
    "🔥",
    "🔥",
]

# Giới hạn tối đa số lượt rep cho mỗi tài khoản TikTok (Chế độ vô hạn)
MAX_REPLIES_PER_USER = 999999

# Chu kỳ quét tin nhắn mới (giây) - quét nhanh 4 giây mỗi lần
SCAN_INTERVAL_SECONDS = 4

# Giãn cách giữa các tin trong chuỗi (giây) để vừa gửi nhanh vừa an toàn
CHAIN_DELAY_RANGE = (0.35, 0.65)

# Cooldown ngắn (giây) để vừa rep xong không bị lặp chính mình, nhưng người đó nhắn lại là rep tiếp ngay
USER_COOLDOWN_SECONDS = 8

# Cổng máy chủ ngụy trang cục bộ (nếu không kết nối qua Cloud)
LOCAL_PORT = 8080
# ══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("lkimlamdev_bot")


# ══════════════════════════════════════════════════════════════════════════
#  MODULE 0: HỆ THỐNG ĐỒNG BỘ THỜI GIAN KÉP (DUAL TIME SYNC)
# ══════════════════════════════════════════════════════════════════════════
class DualTimeSync:
    """Hệ thống đồng bộ thời gian kép với cơ chế Redundant Fallback 2 chiều:
    1. Trạm 1: Đồng hồ nguyên tử Internet (HTTPS Date Google/Cloudflare & NTP time.google.com/pool.ntp.org)
    2. Trạm 2: Đồng hồ phần cứng hệ thống (OS Hardware Clock) nội tại của điện thoại / PC
    Nếu mất mạng -> Tự động chuyển 100% sang đồng hồ máy.
    Nếu đồng hồ máy bị lệch -> Tự động đối chiếu đồng hồ mạng để bù sai lệch chuẩn xác.
    """
    _offset_seconds = 0.0
    _last_sync_time = 0.0
    _sync_interval = 1800.0  # 30 phút tự đối chiếu 1 lần
    _last_source = "Đang khởi động"

    @classmethod
    def sync_network_time(cls) -> bool:
        now_local = datetime.now()
        net_time = None

        # Ưu tiên 0: Web API riêng của Boss Man (nếu có cấu hình trong time_api_config.json)
        if os.path.exists(TIME_API_CONFIG_FILE):
            try:
                with open(TIME_API_CONFIG_FILE, "r", encoding="utf-8") as f:
                    api_cfg = json.load(f)
                custom_url = api_cfg.get("url", "").strip()
                custom_key = api_cfg.get("api_key", "").strip()
                if api_cfg.get("enabled", True) and custom_url:
                    # Cho phép thử 2 lần (đề phòng Vercel Serverless Function đang ngủ/cold-start)
                    for attempt in range(1, 3):
                        try:
                            req = urllib.request.Request(custom_url)
                            if custom_key:
                                req.add_header("X-API-Key", custom_key)
                                req.add_header("Authorization", f"Bearer {custom_key}")
                            req.add_header("User-Agent", "TikTokBot-TimeSync/1.0")
                            with urllib.request.urlopen(req, timeout=6.0) as resp:
                                body_bytes = resp.read()
                                parsed_time = None
                                # 1. Thử parse JSON
                                try:
                                    json_data = json.loads(body_bytes.decode("utf-8"))
                                    # Ưu tiên trường iso hoặc unix chính xác
                                    if "iso" in json_data and isinstance(json_data["iso"], str):
                                        parsed_time = datetime.fromisoformat(json_data["iso"]).astimezone().replace(tzinfo=None)
                                    elif "unix" in json_data and isinstance(json_data["unix"], (int, float)):
                                        parsed_time = datetime.fromtimestamp(json_data["unix"])
                                    elif "unix_ms" in json_data and isinstance(json_data["unix_ms"], (int, float)):
                                        parsed_time = datetime.fromtimestamp(json_data["unix_ms"] / 1000.0)
                                    else:
                                        for k in ["datetime", "current_time", "now", "formatted"]:
                                            if k in json_data and isinstance(json_data[k], str):
                                                raw_val = json_data[k].replace("Z", "+00:00")
                                                parsed_time = datetime.fromisoformat(raw_val).astimezone().replace(tzinfo=None)
                                                break
                                        if not parsed_time:
                                            for k in ["timestamp", "unixtime", "epoch", "time_t"]:
                                                if k in json_data and isinstance(json_data[k], (int, float)):
                                                    parsed_time = datetime.fromtimestamp(json_data[k])
                                                    break
                                except Exception:
                                    pass

                                # 2. Thử parse dạng chuỗi trực tiếp
                                if not parsed_time:
                                    raw_str = body_bytes.decode("utf-8").strip().strip('"').strip("'")
                                    try:
                                        parsed_time = datetime.fromisoformat(raw_str.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
                                    except Exception:
                                        pass

                                # 3. Dự phòng qua Header Date của response từ web boss man
                                if not parsed_time and resp.headers.get("Date"):
                                    dt = email.utils.parsedate_to_datetime(resp.headers.get("Date")).astimezone()
                                    parsed_time = dt.replace(tzinfo=None)

                                if parsed_time:
                                    net_time = parsed_time
                                    cls._last_source = f"Web API của Boss ({custom_url})"
                                    break
                        except Exception:
                            if attempt < 2:
                                time.sleep(0.5)
                                continue
            except Exception:
                pass

        # Ưu tiên 1: Lấy HTTP Date từ Google & Cloudflare (cổng 443 HTTPS không bao giờ bị chặn)
        if not net_time:
            for url in ["https://www.google.com", "https://www.cloudflare.com"]:
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    req.add_header("User-Agent", "Mozilla/5.0")
                    with urllib.request.urlopen(req, timeout=2.0) as resp:
                        date_str = resp.headers.get("Date")
                        if date_str:
                            dt = email.utils.parsedate_to_datetime(date_str).astimezone()
                            net_time = dt.replace(tzinfo=None)
                            cls._last_source = f"Internet ({url.split('//')[1]})"
                            break
                except Exception:
                    continue

        # Ưu tiên 2: Lấy qua NTP UDP socket cổng 123
        if not net_time:
            for host in ["time.google.com", "pool.ntp.org"]:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.settimeout(2.0)
                    s.sendto(b"\x1b" + 47 * b"\0", (host, 123))
                    data, _ = s.recvfrom(1024)
                    s.close()
                    if data:
                        t = struct.unpack("!12I", data[:48])[10] - 2208988800
                        net_time = datetime.fromtimestamp(t)
                        cls._last_source = f"NTP Server ({host})"
                        break
                except Exception:
                    continue

        if net_time:
            cls._offset_seconds = (net_time - now_local).total_seconds()
            cls._last_sync_time = time.time()
            return True
        else:
            cls._last_source = "Đồng hồ hệ thống (Local OS Fallback)"
            cls._last_sync_time = time.time()
            return False

    @classmethod
    def now(cls) -> datetime:
        # Nếu chưa đồng bộ lần nào hoặc đã qua chu kỳ 30 phút -> tự động sync lại
        if cls._last_sync_time == 0.0 or (time.time() - cls._last_sync_time > cls._sync_interval):
            try:
                cls.sync_network_time()
            except Exception:
                cls._last_source = "Đồng hồ hệ thống (Local OS Fallback)"
                cls._last_sync_time = time.time()
        return datetime.now() + timedelta(seconds=cls._offset_seconds)

    @classmethod
    def source(cls) -> str:
        return cls._last_source


# ══════════════════════════════════════════════════════════════════════════
#  MODULE 1: QUẢN LÝ HẠN NGẠCH 10 LƯỢT / USER
# ══════════════════════════════════════════════════════════════════════════
class UserQuotaTracker:
    def __init__(self, file_path: str = USER_QUOTA_FILE, max_allowed: int = MAX_REPLIES_PER_USER):
        self.file_path = file_path
        self.max_allowed = max_allowed
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"Lỗi khi lưu hạn ngạch: {e}")

    def get_count(self, username: str) -> int:
        with self.lock:
            return self.data.get(username, {}).get("count", 0)

    def can_reply(self, username: str) -> bool:
        """Chế độ vô hạn: Luôn sẵn sàng phản hồi mỗi khi có tin nhắn mới."""
        return True

    def record_reply(self, username: str, incoming_msg: str) -> int:
        """Ghi nhận thêm 1 lượt rep cho tài khoản."""
        with self.lock:
            user_info = self.data.setdefault(username, {
                "count": 0,
                "max_allowed": self.max_allowed,
                "first_seen": DualTimeSync.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            user_info["count"] = user_info.get("count", 0) + 1
            user_info["last_seen"] = DualTimeSync.now().strftime("%Y-%m-%d %H:%M:%S")
            user_info["last_msg"] = incoming_msg
            self._save()
            return user_info["count"]


# ══════════════════════════════════════════════════════════════════════════
#  MODULE 2: ĐỒNG BỘ TỪ XA VỚI MÁY CHỦ CLOUD (RENDER / RAILWAY / LOCAL)
# ══════════════════════════════════════════════════════════════════════════
class RemoteHubSync:
    def __init__(self, hub_url: str = None):
        self.hub_url = hub_url.rstrip("/") if hub_url else None
        self.pending_logs = []
        self.lock = threading.Lock()
        self.is_running = True
        self.bot_mode = None
        self.manual_streak_requested = False
        self.total_replies = 0

    def add_log(self, text: str):
        with self.lock:
            self.pending_logs.append(text)
            if len(self.pending_logs) > 50:
                self.pending_logs.pop(0)

    def sync(self, quota_tracker: UserQuotaTracker, session_tag: str = "default") -> bool:
        """Gửi trạng thái lên Web Hub 24/7 và đồng bộ cấu hình hai chiều."""
        global REPLY_CHAIN
        with self.lock:
            logs_to_send = list(self.pending_logs)
            self.pending_logs.clear()

        # Chế độ 1: Kết nối tới máy chủ Cloud từ xa (Render / Railway / VPS)
        if self.hub_url:
            try:
                payload = {
                    "total_replies": self.total_replies,
                    "users_quota": quota_tracker.data,
                    "new_logs": logs_to_send,
                    "session_tag": session_tag,
                }
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Linux; Android) TermuxWorker/2.0"
                }
                req = urllib.request.Request(
                    f"{self.hub_url}/api/sync",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.is_running = data.get("is_running", True)
                    if data.get("trigger_streak"):
                        self.manual_streak_requested = True
                    if data.get("bot_mode"):
                        self.bot_mode = data.get("bot_mode")

                    # Đồng bộ targets nếu có
                    w_targets = data.get("targets")
                    if w_targets and isinstance(w_targets, list):
                        try:
                            cur_t = load_targets()
                            if set(w_targets) != set(cur_t):
                                with open(TARGETS_FILE, "w", encoding="utf-8") as f:
                                    f.write("# Danh sach targets dong bo tu Web Hub 24/7\n")
                                    for u in w_targets:
                                        f.write(f"{u}\n")
                        except Exception:
                            pass

                    # Đồng bộ streak config nếu có
                    w_cfg = data.get("streak_config")
                    if w_cfg and isinstance(w_cfg, dict):
                        try:
                            cur_cfg = load_streak_config()
                            if w_cfg.get("streak_time") != cur_cfg.get("streak_time") or w_cfg.get("target_date") != cur_cfg.get("target_date"):
                                with open(STREAK_CONFIG_FILE, "w", encoding="utf-8") as f:
                                    json.dump(w_cfg, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass

                    # Đồng bộ chuỗi rep tin nhắn
                    w_chain = data.get("reply_chain")
                    if w_chain and isinstance(w_chain, list) and len(w_chain) > 0:
                        if list(w_chain) != list(REPLY_CHAIN):
                            REPLY_CHAIN = list(w_chain)
                            log.info(f"[Web Hub] Da dong bo chuoi tin nhan rep moi: {REPLY_CHAIN}")

                    return self.is_running
            except Exception as e:
                err_str = str(e).lower()
                if "timed out" in err_str:
                    log.info("[Render] Dang ket noi may chu Cloud Web...")
                else:
                    log.warning(f"[Cloud Hub] Dong bo ({e})")
                return self.is_running

        # Chế độ 2: Chạy trực tiếp máy chủ ngụy trang 404 nội bộ
        else:
            if server:
                with server.STATE_LOCK:
                    server.GLOBAL_STATE["last_worker_ping"] = time.time()
                    server.GLOBAL_STATE["worker_info"] = session_tag
                    server.GLOBAL_STATE["total_replies"] = self.total_replies
                    server.GLOBAL_STATE["users_quota"] = quota_tracker.data
                    for l in logs_to_send:
                        server.GLOBAL_STATE["logs"].append(f"{datetime.now().strftime('%H:%M:%S')} │ {l}")
                        if len(server.GLOBAL_STATE["logs"]) > 100:
                            server.GLOBAL_STATE["logs"].pop(0)

                    self.is_running = server.GLOBAL_STATE["is_running"]
                    if server.GLOBAL_STATE.get("trigger_streak"):
                        self.manual_streak_requested = True
                        server.GLOBAL_STATE["trigger_streak"] = False
                    if server.GLOBAL_STATE.get("bot_mode"):
                        self.bot_mode = server.GLOBAL_STATE.get("bot_mode")

                    w_targets = server.GLOBAL_STATE.get("targets")
                    if w_targets and isinstance(w_targets, list):
                        try:
                            cur_t = load_targets()
                            if set(w_targets) != set(cur_t):
                                with open(TARGETS_FILE, "w", encoding="utf-8") as f:
                                    f.write("# Danh sach targets dong bo tu Web Hub 24/7\n")
                                    for u in w_targets:
                                        f.write(f"{u}\n")
                        except Exception:
                            pass

                    w_cfg = server.GLOBAL_STATE.get("streak_config")
                    if w_cfg and isinstance(w_cfg, dict):
                        try:
                            cur_cfg = load_streak_config()
                            if w_cfg.get("streak_time") != cur_cfg.get("streak_time") or w_cfg.get("target_date") != cur_cfg.get("target_date"):
                                with open(STREAK_CONFIG_FILE, "w", encoding="utf-8") as f:
                                    json.dump(w_cfg, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass

                    w_chain = server.GLOBAL_STATE.get("reply_chain")
                    if w_chain and isinstance(w_chain, list) and len(w_chain) > 0:
                        if list(w_chain) != list(REPLY_CHAIN):
                            REPLY_CHAIN = list(w_chain)
                            log.info(f"[Web Hub] Da dong bo chuoi tin nhan rep moi: {REPLY_CHAIN}")

                    return self.is_running
            return self.is_running


# ══════════════════════════════════════════════════════════════════════════
#  MODULE 3: GỬI CHUỖI TIN NHẮN TIKTOK
# ══════════════════════════════════════════════════════════════════════════
def human_sleep(min_sec: float, max_sec: float):
    time.sleep(random.uniform(min_sec, max_sec))


def send_chain_messages(page, username: str, hub: RemoteHubSync) -> bool:
    """Gửi lần lượt các tin nhắn trong chuỗi vào DraftEditor của TikTok."""
    total_msgs = len(REPLY_CHAIN)
    log.info(f"[Gửi tin] Bắt đầu gửi chuỗi {total_msgs} tin cho: {username}")
    hub.add_log(f"Bắt đầu gửi chuỗi {total_msgs} tin cho @{username}")

    editor_selectors = [
        "div.public-DraftEditor-content",
        'div[contenteditable="true"]',
        '[data-e2e="dm-new-chatbox"] [contenteditable="true"]',
        '[data-e2e="chat-input-textarea"]',
        'div[data-slate-editor="true"]',
    ]

    active_editor = None
    for sel in editor_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2500):
                active_editor = loc
                break
        except Exception:
            continue

    if not active_editor:
        log.error(f"[Lỗi] Không tìm thấy khung soạn thảo tin nhắn cho @{username}")
        hub.add_log(f"Lỗi: Không tìm thấy khung chat của @{username}")
        return False

    # Focus vào khung soạn thảo trước khi bắt đầu gửi
    try:
        active_editor.click(timeout=3000)
        human_sleep(0.2, 0.4)
    except Exception as e:
        log.warning(f"Lỗi focus khung chat: {e}")

    sent_count = 0
    for idx, msg in enumerate(REPLY_CHAIN, start=1):
        log.info(f"   -> [{idx}/{total_msgs}] {msg}")
        hub.add_log(f"Gui [{idx}/{total_msgs}] toi @{username}: {msg[:25]}")
        try:
            # Click nhẹ vào khung soạn thảo để đảm bảo con trỏ đang ở đúng chỗ
            try:
                active_editor.click(timeout=1000)
            except Exception:
                pass
            human_sleep(0.08, 0.15)

            # Nếu là emoji thì dùng insert_text để gửi nhanh và tránh lỗi mã hóa ký tự
            if any(ord(c) > 0xFFFF for c in msg):
                page.keyboard.insert_text(msg)
            else:
                page.keyboard.type(msg, delay=random.randint(10, 25))
            human_sleep(0.08, 0.15)
            
            page.keyboard.press("Enter")

            # Dự phòng: Bấm nút gửi nếu giao diện hiển thị nút gửi riêng
            try:
                send_btn = page.locator('[data-e2e="message-send-btn"], [aria-label*="Gửi" i], [aria-label*="Send" i]').first
                if send_btn.is_visible(timeout=300):
                    send_btn.click(timeout=800)
            except Exception:
                pass

            sent_count += 1
            human_sleep(*CHAIN_DELAY_RANGE)
        except Exception as err:
            log.warning(f"   [Cảnh báo] Lỗi khi gửi tin thứ {idx} cho @{username}: {err}")
            human_sleep(0.3, 0.6)
            continue

    if sent_count > 0:
        log.info(f"   [Thành công] Đã gửi thành công {sent_count}/{total_msgs} tin nhắn cho: {username}")
        hub.add_log(f"Hoàn tất chuỗi tin cho @{username}")
        return True
    return False


def find_next_pending_user(page, active_cooldowns: list) -> dict:
    """Quét DOM tìm một tài khoản đang chờ rep (có badge hoặc tin nhắn mới từ người xem)."""
    try:
        return page.evaluate("""(cooldownUsers) => {
            const items = document.querySelectorAll('[data-e2e="dm-new-conversation-item"]');
            for (const item of items) {
                const nameEl = item.querySelector('[data-e2e="dm-new-conversation-nickname"], [class*="PInfoNickname"]');
                const badgeEl = item.querySelector('[data-e2e="dm-new-conversation-unread"], [class*="DivAvatarBadge"] span, [class*="SpanNewMessage"]');
                const extractEl = item.querySelector('[class*="SpanInfoExtract"], [class*="Extract"]');
                
                const username = nameEl ? nameEl.textContent.trim() : '';
                if (!username) continue;
                
                // Nếu vừa rep trong 8s qua thì bỏ qua để tránh gửi đúp
                if (cooldownUsers.includes(username)) continue;
                
                const badgeText = badgeEl ? badgeEl.textContent.trim() : '';
                const snippet = extractEl ? extractEl.textContent.trim() : '';
                
                const hasBadge = badgeText && badgeText !== '0';
                // Kiểm tra tin nhắn cuối: phân biệt tin do bot gửi hay do người xem gửi
                const isFromBot = snippet.startsWith('Bạn:') || 
                                  snippet.startsWith('Bạn :') || 
                                  snippet.startsWith('Bạn đã gửi') ||
                                  snippet.startsWith('You:') || 
                                  snippet.startsWith('You :') || 
                                  snippet.startsWith('You sent') ||
                                  snippet.trim().startsWith('🔥') || 
                                  snippet.includes('lkimlamdev');
                const hasIncomingMsg = snippet && !isFromBot;
                
                if (hasBadge || hasIncomingMsg) {
                    return {
                        username: username,
                        snippet: snippet || 'Tin nhắn mới',
                        badge: badgeText
                    };
                }
            }
            return null;
        }""", active_cooldowns)
    except Exception as e:
        log.warning(f"Lỗi khi quét danh sách hội thoại: {e}")
        return None


def check_and_reply_unread(page, quota_tracker: UserQuotaTracker, hub: RemoteHubSync, cooldown_cache: dict) -> int:
    """Quét và xử lý liên hoàn TẤT CẢ các tài khoản đang có tin nhắn mới trong cùng một chu kỳ."""
    # Kiểm tra trạng thái điều khiển từ xa (Bật/Tắt)
    is_active = hub.sync(quota_tracker)
    if not is_active:
        log.info("[Tam dung tu xa] Quan tri vien da tat bot. Dang trong che do cho...")
        return 0

    processed_count = 0
    now_ts = time.time()

    # Dọn dẹp cache: chỉ giữ các user vừa rep trong 8 giây qua
    active_cooldowns = [u for u, t in cooldown_cache.items() if (now_ts - t) < USER_COOLDOWN_SECONDS]

    # Vòng lặp liên hoàn: giải quyết lần lượt TẤT CẢ người nhắn trong danh sách
    max_batch_per_cycle = 20
    while processed_count < max_batch_per_cycle:
        if not hub.is_running:
            break

        target = find_next_pending_user(page, active_cooldowns)
        if not target:
            break  # Đã xử lý sạch sẽ tất cả người có tin nhắn mới

        username = target["username"]
        incoming_message = target["snippet"]
        current_count = quota_tracker.get_count(username)

        log.info(f"[Tin moi] Phat hien tu @{username}: \"{incoming_message}\" (Da rep: {current_count} lan)")
        hub.add_log(f"Phat hien tin nhan tu @{username} (Tong rep: {current_count})")

        # Click tươi vào đúng hội thoại của user đó (tránh lỗi stale DOM handle)
        try:
            user_locator = page.locator('[data-e2e="dm-new-conversation-item"]', has_text=username).first
            user_locator.click()
            human_sleep(1.2, 2.0)
        except Exception as e:
            log.warning(f"Khong the click vao hoi thoai @{username}: {e}")
            active_cooldowns.append(username)
            continue

        # Gửi chuỗi 10 tin nhắn
        success = send_chain_messages(page, username, hub)
        if success:
            new_count = quota_tracker.record_reply(username, incoming_message)
            now_done = time.time()
            cooldown_cache[username] = now_done
            active_cooldowns.append(username)
            processed_count += 1
            hub.total_replies += 1
            hub.sync(quota_tracker)

            log.info(f"[Thanh cong] Da rep xong luot {new_count} cho @{username} (Nguoi thu {processed_count} trong dot).")
            hub.add_log(f"Hoan tat luot rep {new_count} cho @{username}")

            # Click nhẹ ra ngoài tiêu đề để nhả focus cuộc hội thoại
            try:
                page.locator('h1, h2, [class*="Header"]').first.click()
            except Exception:
                pass

            human_sleep(1.0, 2.0)
        else:
            active_cooldowns.append(username)

    return processed_count


# ══════════════════════════════════════════════════════════════════════════
#  MODULE 4: TỰ ĐỘNG CHỦ ĐỘNG GIỮ CHUỖI LỬA TIKTOK THEO GIỜ HẸN (STREAKS)
# ══════════════════════════════════════════════════════════════════════════
def load_streak_config() -> dict:
    cfg = {"enabled": True, "streak_time": "00:30"}
    if os.path.exists(STREAK_CONFIG_FILE):
        try:
            with open(STREAK_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
        except Exception:
            pass
    return cfg


def load_targets() -> list:
    targets = []
    if os.path.exists(TARGETS_FILE):
        try:
            with open(TARGETS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip().lstrip("@")
                    if u and not u.startswith("#") and u not in targets:
                        targets.append(u)
        except Exception:
            pass
    return targets


def is_captcha_present(page) -> bool:
    """Kiểm tra toàn diện tất cả các dấu hiệu CAPTCHA (hình ghép, xoay hình, 2 hình giống nhau) trên TikTok."""
    # 1. Quét nội dung văn bản và class trong DOM chính bằng JavaScript
    try:
        found_js = page.evaluate("""() => {
            const sels = [
                '#captcha-verify-image', '.captcha_verify_container', '#tiktok-verify-ele',
                '.sec-cpt-container', '[data-e2e="captcha-verify-container"]',
                '.captcha-disable-scroll', '.captcha_verify_bar', '.captcha_verify_slide',
                'div[class*="captcha_verify"]', 'div[class*="sec-cpt"]', 'div[class*="verify-container"]',
                'div[class*="Captcha"]', 'div[class*="verify-wrap"]', 'div[id*="captcha"]', 'div[id*="verify"]'
            ];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el && (el.offsetWidth > 0 || el.offsetHeight > 0 || window.getComputedStyle(el).display !== 'none')) {
                    return true;
                }
            }
            if (document.body && (
                document.body.classList.contains('captcha-disable-scroll') || 
                document.body.classList.contains('secsdk-captcha-open')
            )) {
                return true;
            }
            const bodyText = document.body ? document.body.innerText : '';
            if (bodyText.includes('Drag the slider') || 
                bodyText.includes('fit the puzzle') || 
                bodyText.includes('puzzle') || 
                bodyText.includes('Kéo thanh trượt') ||
                bodyText.includes('khớp hình ghép') ||
                bodyText.includes('hình ghép') ||
                bodyText.includes('Chọn 2 đối tượng cùng hình dạng') ||
                bodyText.includes('Select 2 objects') ||
                bodyText.includes('Verify to continue')) {
                return true;
            }
            const iframes = document.querySelectorAll('iframe[src*="captcha"], iframe[src*="verify"], iframe[id*="captcha"], iframe[src*="secsdk"]');
            if (iframes.length > 0) return true;
            return false;
        }""")
        if found_js:
            return True
    except Exception:
        pass

    # 2. Quét xuyên qua tất cả page.frames (xử lý triệt để iframe captcha ByteDance / TikTok)
    try:
        for frame in page.frames:
            f_url = (frame.url or "").lower()
            if any(k in f_url for k in ["captcha", "verify", "secsdk"]):
                return True
            try:
                f_has_text = frame.evaluate("""() => {
                    const t = document.body ? document.body.innerText : '';
                    return t.includes('Drag the slider') || 
                           t.includes('fit the puzzle') || 
                           t.includes('puzzle') || 
                           t.includes('Kéo thanh trượt') || 
                           t.includes('khớp hình ghép') || 
                           t.includes('Select 2 objects') || 
                           t.includes('Chọn 2 đối tượng') || 
                           t.includes('Verify to continue');
                }""")
                if f_has_text:
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # 3. Quét qua Playwright get_by_text (xuyên qua Shadow DOM và iframes)
    keywords = [
        "Drag the slider",
        "fit the puzzle",
        "Kéo thanh trượt",
        "khớp hình ghép",
        "Chọn 2 đối tượng",
        "Select 2 objects",
    ]
    for kw in keywords:
        try:
            if page.get_by_text(kw, exact=False).first.is_visible(timeout=100):
                return True
        except Exception:
            pass

    # 4. Quét qua Playwright locator dự phòng
    loc_selectors = [
        "#captcha-verify-image",
        ".captcha_verify_container",
        "#tiktok-verify-ele",
        ".sec-cpt-container",
        "[data-e2e='captcha-verify-container']",
        "iframe[src*='captcha']",
        "iframe[src*='verify']",
        "iframe[src*='secsdk']",
    ]
    for sel in loc_selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=100):
                return True
        except Exception:
            pass
    return False


def detect_and_wait_for_manual_captcha(page, context=None, cookie_file=None, is_headless: bool = False, max_wait: int = 300, poll_init: float = 3.0) -> bool:
    """Kiểm tra và tạm dừng hoàn toàn nếu TikTok yêu cầu giải CAPTCHA."""
    # TikTok thường mất 1-3s sau khi load trang để render bảng CAPTCHA
    start_poll = time.time()
    found = False
    while time.time() - start_poll < poll_init:
        if is_captcha_present(page):
            found = True
            break
        time.sleep(0.4)

    if not found:
        return False

    # Đã phát hiện CAPTCHA!
    print("\a", end="", flush=True)  # Kêu tiếng beep báo động trên PC
    log.warning("=" * 72)
    log.warning("  [PHÁT HIỆN CAPTCHA BẢO MẬT] TIKTOK ĐANG HIỂN THỊ MÃ XÁC THỰC!")
    log.warning("=" * 72)
    if is_headless:
        log.warning(">> Đang chạy ở chế độ ẨN (Headless) nên không thể thao tác kéo chuột.")
        log.warning(">> GIẢI PHÁP:")
        log.warning("   1. Mở file CHAY_BOT_PC.bat -> Chọn [5] -> Chọn [1] (Có cửa sổ trực quan).")
        log.warning("   2. Dùng chuột kéo khớp hình ghép 1 lần duy nhất.")
        log.warning("   3. Phiên sạch (s_v_web_id) sẽ được lưu vĩnh viễn vào session file để chạy ẩn không bao giờ bị hỏi lại.")
        log.warning("=" * 72)
        return False
    else:
        log.info(">> Boss man vui lòng dùng chuột KÉO THANH TRƯỢT / VƯỢT CAPTCHA trên cửa sổ trình duyệt.")
        log.info(">> BOT ĐÃ TẠM DỪNG HOÀN TOÀN, TUYỆT ĐỐI KHÔNG CHUYỂN TRANG / KHÔNG ĐỔI MỤC TIÊU.")
        log.info(f">> (Đang chờ boss man thao tác... tối đa {max_wait} giây)")
        log.info(">> (Mẹo: Sau khi kéo xong, boss man có thể nhấn phím ENTER tại cửa sổ này,")
        log.info(">>  hoặc bot sẽ tự động nhận diện trong 2-3 giây để tiếp tục chạy)")
        log.warning("=" * 72)

    start_wait = time.time()
    last_print = 0
    while time.time() - start_wait < max_wait:
        # 1. Kiểm tra nếu boss man nhấn phím trên console
        key_pressed = False
        if sys.platform == "win32":
            try:
                import msvcrt
                if msvcrt.kbhit():
                    msvcrt.getch()
                    key_pressed = True
            except Exception:
                pass

        if key_pressed:
            log.info("[Đã xác nhận] Boss man đã nhấn phím báo xong! Đang tiếp tục...")
            human_sleep(1.5, 2.5)
            if context and cookie_file:
                try:
                    fresh_cookies = context.cookies()
                    with open(cookie_file, "w", encoding="utf-8") as f:
                        json.dump(fresh_cookies, f, indent=2)
                    log.info(f"[Đã lưu] Đã cập nhật token sạch (s_v_web_id) vào {cookie_file}.")
                except Exception as save_err:
                    log.warning(f"Không thể lưu cookie: {save_err}")
            return True

        # 2. Tự động kiểm tra xem CAPTCHA đã biến mất hoàn toàn chưa
        if not is_captcha_present(page):
            # Chờ thêm 1.5s để chắc chắn không phải giật khung hình
            time.sleep(1.5)
            if not is_captcha_present(page):
                log.info("=" * 72)
                log.info("[Thành công] Đã xác nhận vượt qua CAPTCHA thành công! Tiếp tục tiến trình...")
                log.info("=" * 72)
                human_sleep(2.0, 3.0)

                # Cập nhật và lưu ngay cookie sạch đã xác thực vào file
                if context and cookie_file:
                    try:
                        fresh_cookies = context.cookies()
                        with open(cookie_file, "w", encoding="utf-8") as f:
                            json.dump(fresh_cookies, f, indent=2)
                        log.info(f"[Đã lưu] Đã cập nhật token sạch (s_v_web_id) vào {cookie_file}.")
                    except Exception as save_err:
                        log.warning(f"Không thể lưu cookie: {save_err}")
                return True

        elapsed = int(time.time() - start_wait)
        if elapsed - last_print >= 10:
            last_print = elapsed
            rem = max_wait - elapsed
            log.info(f"   [Đang chờ boss man kéo CAPTCHA...] Đã chờ {elapsed}s (Còn lại {rem}s | Nhấn Enter nếu đã kéo xong)")
        time.sleep(0.8)

    log.warning(f"[Hết giờ] Đã quá {max_wait} giây chờ xác minh CAPTCHA.")
    return False


def wait_for_chat_editor(page, timeout: int = 4000) -> bool:
    """Kiểm tra xem khung soạn thảo tin nhắn TikTok đã sẵn sàng nhận văn bản chưa."""
    editor_selectors = [
        "div.public-DraftEditor-content",
        'div[contenteditable="true"]',
        '[data-e2e="dm-new-chatbox"] [contenteditable="true"]',
        '[data-e2e="chat-input-textarea"]',
        'div[data-slate-editor="true"]',
    ]
    start_t = time.time()
    while (time.time() - start_t) * 1000 < timeout:
        for sel in editor_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=250):
                    return True
            except Exception:
                pass
        time.sleep(0.15)
    return False

# Giữ alias cho tương thích ngược
is_chat_editor_ready = wait_for_chat_editor


def open_conversation_with_user(page, username: str, context=None, cookie_file=None, is_headless: bool = False) -> bool:
    """
    Tìm và mở hội thoại với @username bằng 3 phương pháp liên hoàn siêu tốc:
    1. Quét ngay trong danh sách hội thoại trên /messages bằng Playwright locator chuẩn.
    2. Gõ tìm kiếm vào ô tìm kiếm tin nhắn trên /messages (nhanh, không rời trang).
    3. (Dự phòng) Truy cập trang cá nhân nếu 2 cách trên không tìm thấy. Bấm nút Tin nhắn an toàn chống crash.
    """
    clean_u = username.strip().lstrip("@")

    # Kiểm tra an toàn: Nếu trang hiện tại đang có CAPTCHA thì tuyệt đối không được chuyển trang
    if is_captcha_present(page):
        log.warning(f"[CAPTCHA] Phát hiện CAPTCHA trên màn hình trước khi mở @{clean_u}! Tạm dừng chờ giải...")
        detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

    # Đảm bảo đang ở trang /messages để tận dụng tốc độ cao và tránh bị hỏi CAPTCHA
    if not page.url.startswith("https://www.tiktok.com/messages"):
        try:
            page.goto("https://www.tiktok.com/messages", timeout=25000, wait_until="domcontentloaded")
            human_sleep(0.8, 1.2)
        except Exception:
            pass

    # Nếu có CAPTCHA xuất hiện trên trang tin nhắn thì dừng lại ngay để boss man kéo
    detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

    # ── CÁCH 1: KIỂM TRA TRONG DANH SÁCH HỘI THOẠI ĐANG MỞ TRÊN /messages ──
    try:
        user_item = page.locator(
            f'[data-e2e="dm-new-conversation-item"]:has-text("{clean_u}"), '
            f'[data-e2e="chat-list-item"]:has-text("{clean_u}"), '
            f'div[role="listitem"]:has-text("{clean_u}")'
        ).first
        if user_item.is_visible(timeout=800):
            user_item.click(timeout=3000)
            human_sleep(0.5, 0.8)
            if wait_for_chat_editor(page, timeout=3000):
                log.info(f"   -> [Cách 1] Đã mở cuộc trò chuyện có sẵn với @{clean_u}!")
                return True
    except Exception as e1:
        log.debug(f"Cách 1: {e1}")

    # ── CÁCH 2: TÌM QUA THANH TÌM KIẾM TIN NHẮN TRÊN /messages (Không rời trang) ──
    try:
        search_inputs = [
            'input[data-e2e="search-user-input"]',
            'input[data-e2e="im-search-input"]',
            'input[data-e2e="chat-search-input"]',
            'input[placeholder*="Tìm" i]',
            'input[placeholder*="Search" i]',
            'input[type="search"]',
        ]
        s_box = None
        for s_sel in search_inputs:
            try:
                loc = page.locator(s_sel).first
                if loc.is_visible(timeout=400):
                    s_box = loc
                    break
            except Exception:
                continue

        if s_box:
            s_box.click(timeout=1500)
            s_box.fill("")
            s_box.type(clean_u, delay=35)
            human_sleep(1.2, 1.8)  # Chờ API tìm kiếm TikTok trả kết quả

            result_candidates = [
                f'[data-e2e="search-user-item"]:has-text("{clean_u}")',
                f'[data-e2e="im-search-user-item"]:has-text("{clean_u}")',
                f'div[role="option"]:has-text("{clean_u}")',
                f'li:has-text("{clean_u}")',
                f'div[class*="SearchUser"]:has-text("{clean_u}")',
                '[data-e2e="search-user-item"]',
                '[data-e2e="im-search-user-item"]',
                'div[role="option"]',
            ]
            for r_sel in result_candidates:
                try:
                    r_loc = page.locator(r_sel).first
                    if r_loc.is_visible(timeout=600):
                        r_loc.click(timeout=2500)
                        human_sleep(0.6, 1.0)
                        if wait_for_chat_editor(page, timeout=4000):
                            log.info(f"   -> [Cách 2] Tìm thấy và mở hội thoại với @{clean_u} qua ô tìm kiếm!")
                            return True
                        break
                except Exception:
                    continue
    except Exception as e2:
        log.debug(f"Cách 2: {e2}")

    # ── CÁCH 3: TRUY CẬP TRỰC TIẾP TRANG CÁ NHÂN https://www.tiktok.com/@username ──
    try:
        profile_url = f"https://www.tiktok.com/@{clean_u}"
        log.info(f"   -> [Cách 3] Vào trang cá nhân của bạn bè: {profile_url}")
        try:
            page.goto(profile_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as goto_err:
            log.warning(f"   [Cảnh báo tải trang cá nhân]: {goto_err}")
        human_sleep(1.5, 2.5)

        # Kiểm tra nếu có CAPTCHA
        detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

        # Chờ header profile tải xong
        try:
            page.wait_for_selector(
                'main, [data-e2e="user-profile-header"], div[class*="Header"], div[class*="UserProfile"]',
                timeout=6000
            )
        except Exception:
            pass

        # Danh sách selector chuẩn chỉ quét trong nội dung profile (main/header), TUYỆT ĐỐI không bấm nhầm menu sidebar
        profile_msg_button_selectors = [
            # 1. Selector thuộc tính chuẩn data-e2e
            '[data-e2e="message-button"]',
            '[data-e2e="user-message-btn"]',
            '[data-e2e="chat-button"]',
            # 2. Button bên trong phần Header / Profile actions
            '[data-e2e="user-profile-header"] button:has-text("Tin nhắn")',
            '[data-e2e="user-profile-header"] button:has-text("Nhắn tin")',
            '[data-e2e="user-profile-header"] button:has-text("Message")',
            'main button:has-text("Tin nhắn")',
            'main button:has-text("Nhắn tin")',
            'main button:has-text("Message")',
            'div[class*="Header"] button:has-text("Tin nhắn")',
            'div[class*="Header"] button:has-text("Nhắn tin")',
            'div[class*="Header"] button:has-text("Message")',
            # 3. Thẻ role button bên trong main
            'main div[role="button"]:has-text("Tin nhắn")',
            'main div[role="button"]:has-text("Nhắn tin")',
            'main div[role="button"]:has-text("Message")',
            # 4. Thẻ a link bên trong header profile
            '[data-e2e="user-profile-header"] a[href*="/messages"]',
            'main a[href*="/messages"]',
        ]

        msg_btn = None
        for sel in profile_msg_button_selectors:
            try:
                btn_loc = page.locator(sel)
                if btn_loc.count() > 0 and btn_loc.first.is_visible(timeout=800):
                    msg_btn = btn_loc.first
                    break
            except Exception:
                continue

        # Phương án phụ: Tìm nút nằm cạnh nút Bạn bè / Follow trong khu vực profile actions
        if not msg_btn:
            try:
                action_btns = page.locator(
                    '[data-e2e="user-profile-actions"] button, '
                    '[data-e2e="user-profile-header"] button, '
                    'div[class*="ShareHeader"] button'
                )
                for i in range(action_btns.count()):
                    b = action_btns.nth(i)
                    b_text = (b.text_content() or "").strip().lower()
                    if any(w in b_text for w in ["follow", "theo dõi", "bạn bè"]):
                        continue
                    if b.is_visible():
                        msg_btn = b
                        break
            except Exception:
                pass

        # Nếu chưa tìm thấy nút Tin nhắn, kiểm tra xem có phải do CAPTCHA vừa xuất hiện che mất nút không
        if not msg_btn:
            if is_captcha_present(page):
                log.warning(f"   -> [Cách 3] Phát hiện CAPTCHA che nút Tin nhắn, tạm dừng chờ boss man giải...")
                solved = detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
                if solved:
                    human_sleep(2.0, 3.0)
                    for sel in profile_msg_button_selectors:
                        try:
                            btn_loc = page.locator(sel)
                            if btn_loc.count() > 0 and btn_loc.first.is_visible(timeout=1500):
                                msg_btn = btn_loc.first
                                break
                        except Exception:
                            continue

        if msg_btn:
            log.info(f"   -> [Cách 3] Đã tìm thấy nút Tin nhắn cho @{clean_u}, đang kích hoạt mở hộp thư...")
            try:
                msg_btn.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            human_sleep(0.3, 0.5)

            # Bấm nút Tin nhắn an toàn, không để ngoại lệ navigation làm sập bot
            try:
                msg_btn.click(timeout=5000)
            except Exception as click_err:
                log.debug(f"Click trigger warning: {click_err}")

            # Chờ TikTok chuyển hướng sang /messages an toàn (kể cả khi mở tab mới)
            for _ in range(16):
                human_sleep(0.3, 0.5)
                try:
                    if context and len(context.pages) > 1:
                        for p in reversed(context.pages):
                            if "tiktok.com/messages" in p.url.lower():
                                p.bring_to_front()
                                page = p
                                break
                    if "tiktok.com/messages" in page.url.lower():
                        break
                except Exception:
                    pass

            try:
                page.wait_for_load_state("domcontentloaded", timeout=6000)
            except Exception:
                pass

            if wait_for_chat_editor(page, timeout=8000):
                log.info(f"   -> [Cách 3] Đã mở thành công hộp thư với @{clean_u}!")
                return True
            else:
                log.warning(f"   -> [Cách 3] Đã bấm nút Tin nhắn nhưng khung chat chưa sẵn sàng.")
                # Kiểm tra xem có CAPTCHA xuất hiện cản trở không
                if is_captcha_present(page):
                    log.warning(f"   -> [Cách 3] CAPTCHA xuất hiện cản trở sau khi bấm Tin nhắn! Tạm dừng để giải...")
                    solved = detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
                    if solved:
                        human_sleep(2.0, 3.0)
                        if wait_for_chat_editor(page, timeout=6000):
                            log.info(f"   -> [Cách 3] Đã mở thành công hộp thư với @{clean_u} sau khi vượt CAPTCHA!")
                            return True
                        # Nếu vẫn ở trang cá nhân thì click lại nút Tin nhắn
                        for sel in profile_msg_button_selectors:
                            try:
                                btn_loc = page.locator(sel)
                                if btn_loc.count() > 0 and btn_loc.first.is_visible(timeout=1000):
                                    btn_loc.first.click(timeout=3000)
                                    break
                            except Exception:
                                continue
                        if wait_for_chat_editor(page, timeout=8000):
                            log.info(f"   -> [Cách 3] Đã bấm lại Tin nhắn và mở hộp thư với @{clean_u} thành công!")
                            return True
        else:
            log.warning(f"   [Cảnh báo] Không tìm thấy nút Tin nhắn trên trang của @{clean_u} (Nick chặn tin nhắn người lạ hoặc chưa kết bạn).")

    except Exception as e:
        log.warning(f"   [Lỗi khi mở chat với @{clean_u}]: {e}")

    # Trước khi return False, kiểm tra chắc chắn nếu CAPTCHA đang hiển thị thì phải chờ giải
    if is_captcha_present(page):
        log.warning(f"   [Cách 3] Phát hiện CAPTCHA trước khi kết thúc mở @{clean_u}! Tạm dừng...")
        detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

    return False


def check_and_send_daily_streaks(page, hub: RemoteHubSync, quota_tracker: UserQuotaTracker, force_now: bool = False, session_tag: str = "default", context=None, cookie_file: str = None, is_headless: bool = False):
    """Kiểm tra giờ hẹn hoặc kích hoạt ngay nếu force_now=True để gửi chuỗi cho targets.txt."""
    cfg = load_streak_config()
    if not cfg.get("enabled", True) and not force_now:
        return

    cur_time = DualTimeSync.now()
    streak_time = cfg.get("streak_time", "00:30").strip()
    target_date = cfg.get("target_date", "").strip()
    today_str = cur_time.strftime("%Y-%m-%d")
    record_key = f"{today_str}_{session_tag}" if session_tag else today_str

    # 1. Kiểm tra ngày hẹn (nếu có cài đặt ngày cụ thể)
    if not force_now and target_date and today_str != target_date:
        return

    # 2. Kiểm tra giờ hẹn trong ngày hôm nay:
    if not force_now:
        try:
            th, tm = map(int, streak_time.split(":"))
            scheduled_today = cur_time.replace(hour=th, minute=tm, second=0, microsecond=0)
        except Exception:
            scheduled_today = cur_time

        # Chưa đến giờ hẹn hôm nay -> Chưa chạy, chờ tiếp
        if cur_time < scheduled_today:
            return

        # Tránh gửi bù quá trễ nếu bật bot trễ hơn 2 tiếng (khi không có ngày chỉ định cụ thể)
        delta_sec = (cur_time - scheduled_today).total_seconds()
        if not target_date and delta_sec > 7200:
            return

    history = {}
    if os.path.exists(STREAK_HISTORY_FILE):
        try:
            with open(STREAK_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    sent_today = history.get(record_key, history.get(today_str, [])) if not force_now else []
    targets = load_targets()
    if not targets:
        if force_now:
            log.info(f"[{session_tag}] Danh sách targets.txt đang trống, hãy thêm nick vào targets.txt.")
        return

    pending = [u for u in targets if u not in sent_today] if not force_now else targets
    if not pending:
        return

    if force_now:
        tag_time = "NGAY LẬP TỨC"
    else:
        tag_time = f"ĐÚNG GIỜ {streak_time}"

    log.info("=" * 65)
    log.info(f"[{session_tag.upper()} - GIỮ CHUỖI LỬA - {tag_time}] Bắt đầu thắp lửa cho {len(pending)} tài khoản bạn bè ({today_str})...")
    log.info("=" * 65)
    hub.add_log(f"[{session_tag}] Kích hoạt giữ chuỗi ({tag_time}): {len(pending)} nick")

    for username in pending:
        if not hub.is_running:
            break

        log.info(f"[Giữ chuỗi] Đang gửi chuỗi cho bạn bè: @{username}")
        hub.add_log(f"Đang gửi chuỗi lửa cho @{username}")

        user_success = False
        for attempt in range(1, 4):
            if not hub.is_running:
                break

            # Kiểm tra chắc chắn không có CAPTCHA trước khi bắt đầu thử
            if is_captcha_present(page):
                detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

            try:
                found = open_conversation_with_user(page, username, context=context, cookie_file=cookie_file, is_headless=is_headless)
                if found:
                    success = send_chain_messages(page, username, hub)
                    if success:
                        quota_tracker.record_reply(username, "Giữ chuỗi lúc " + streak_time)
                        sent_today.append(username)
                        history[record_key] = sent_today
                        try:
                            with open(STREAK_HISTORY_FILE, "w", encoding="utf-8") as f:
                                json.dump(history, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                        log.info(f"[{session_tag}] Đã thắp lửa chuỗi thành công cho @{username}!")
                        hub.add_log(f"[{session_tag}] Đã thắp lửa thành công cho @{username}")
                        human_sleep(1.0, 2.0)
                        user_success = True
                        break
                    else:
                        log.warning(f"[{session_tag}] Không thể gửi trọn vẹn chuỗi tin cho @{username}")
                else:
                    # Nếu mở thất bại, kiểm tra ngay có CAPTCHA xuất hiện không
                    if is_captcha_present(page):
                        log.warning(f"[{session_tag}] Phát hiện CAPTCHA đang chặn mở hộp thư @{username}! Tạm dừng chờ boss man kéo...")
                        solved = detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
                        if solved:
                            log.info(f"[{session_tag}] Giải CAPTCHA thành công! Thử lại ngay với @{username} (không chuyển nick)...")
                            human_sleep(1.5, 2.5)
                            continue
                    log.warning(f"[{session_tag}] Mở hộp thư @{username} chưa thành công (Lần {attempt}/3)...")
            except Exception as e_user:
                log.error(f"[{session_tag}] Lỗi khi xử lý bạn bè @{username}: {e_user}")
                if is_captcha_present(page):
                    detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
                human_sleep(1.0, 2.0)

            if not user_success and attempt < 3:
                human_sleep(1.5, 2.5)

        if not user_success:
            # KHÓA AN TOÀN TUYỆT ĐỐI: Không bao giờ chuyển nick nếu CAPTCHA vẫn đang hiển thị
            while is_captcha_present(page):
                log.warning(f"[{session_tag}] CAPTCHA vẫn đang hiển thị trên màn hình! KHÔNG CHUYỂN MỤC TIÊU!")
                solved = detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
                if not solved:
                    break
            log.warning(f"[{session_tag}] Bỏ qua @{username} sau 3 lần thử, tiếp tục tài khoản kế tiếp...")

    # Đưa lại về trang tin nhắn chính sau khi hoàn thành
    if is_captcha_present(page):
        detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)
    if not page.url.startswith("https://www.tiktok.com/messages"):
        try:
            page.goto("https://www.tiktok.com/messages", timeout=30000)
            human_sleep(1.5, 2.5)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════
#  CHƯƠNG TRÌNH KHỞI ĐỘNG CHÍNH
# ══════════════════════════════════════════════════════════════════════════
def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║       Tool tự động rep chuỗi by lekimlamdevcode          ║
╚══════════════════════════════════════════════════════════╝
""")

    # Kiểm tra tham số máy chủ đồng bộ từ xa và file session
    remote_server_url = None
    cookie_file = COOKIE_FILE
    new_session_target = None
    custom_name = None
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
        elif arg in ("--name", "-n") and idx + 1 < len(sys.argv):
            custom_name = sys.argv[idx + 1].strip()
        elif arg in ("--session", "-s") and idx + 1 < len(sys.argv):
            cookie_file = sys.argv[idx + 1].strip()
        elif arg in ("--new-session", "--save-session") and idx + 1 < len(sys.argv):
            new_session_target = sys.argv[idx + 1].strip()

    # Nếu người dùng chỉ định tên gợi nhớ qua --name hoặc -n (ví dụ: -n session1, -n 2, -n acc3)
    if custom_name:
        os.makedirs(os.path.join(BASE_DIR, "sessions"), exist_ok=True)
        norm = custom_name.lower().replace("-", "_")
        cand_paths = [
            os.path.join(BASE_DIR, "sessions", f"{custom_name}.json"),
            os.path.join(BASE_DIR, "sessions", f"session_{custom_name}.json"),
            os.path.join(BASE_DIR, "sessions", f"session{custom_name}.json"),
            os.path.join(BASE_DIR, f"{custom_name}.json"),
            os.path.join(BASE_DIR, f"session_{custom_name}.json"),
        ]
        # Hỗ trợ tự động quy đổi linh hoạt giữa acc1, acc2, 1, 2, session1, session2
        if norm.startswith("acc"):
            num = norm.replace("acc", "").strip("_")
            cand_paths.insert(0, os.path.join(BASE_DIR, "sessions", f"session{num}.json"))
            cand_paths.insert(0, os.path.join(BASE_DIR, "sessions", f"session_{norm}.json"))
        elif norm in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            cand_paths.insert(0, os.path.join(BASE_DIR, "sessions", f"session{norm}.json"))

        chosen = None
        for cp in cand_paths:
            if os.path.exists(cp):
                chosen = cp
                break
        cookie_file = chosen if chosen else cand_paths[0]
        session_tag = custom_name
    else:
        session_tag = os.path.splitext(os.path.basename(cookie_file))[0]

    # Tạo file quota riêng cho từng session để không bị trùng lặp lịch sử
    quota_file = USER_QUOTA_FILE if session_tag == "session" else os.path.join(BASE_DIR, f"user_quota_{session_tag}.json")
    quota_tracker = UserQuotaTracker(file_path=quota_file)
    hub = RemoteHubSync(remote_server_url)

    # Nếu không kết nối qua Cloud Hub, tự khởi động máy chủ ngụy trang 404 nội bộ
    if not remote_server_url:
        if server:
            t = threading.Thread(target=server.run_server, daemon=True)
            t.start()
            log.info(f"[May chu] Dang chay tai: http://localhost:{LOCAL_PORT}")
            log.info("   -> Giao dien: Trang '404 Not Found' chuan Nginx.")
            log.info("   -> Nhap 10 lan vao '404 Not Found' de dang nhap.")
            log.info("   -> Mat khau: Lam*2025")
        else:
            log.info("[May chu] Chay che do doc lap.")
    else:
        log.info(f"[Cloud Hub] Dang dong bo voi may chu tu xa: {remote_server_url}")

    # Khởi động và hiệu chỉnh Đồng hồ Kép (Dual Time Sync: Internet Atomic + OS Hardware)
    DualTimeSync.sync_network_time()
    drift_str = f"{DualTimeSync._offset_seconds:+.2f}s"
    log.info(f"[Dong ho kep] Nguon gio: {DualTimeSync.source()} | Gio chuan: {DualTimeSync.now().strftime('%Y-%m-%d %H:%M:%S')} (Do lech: {drift_str})")

    # Tự động nhận diện chế độ Headless (nếu chạy trên Termux/Linux)
    is_headless = "--headless" in sys.argv or (not os.environ.get("DISPLAY") and sys.platform != "win32")
    log.info(f"[Trinh duyet] Che do: {'Headless (Chay nen)' if is_headless else 'Cua so truc quan'}")

    mode_names = {
        "target": "Ban streak ngay lap tuc (Gui chuoi ngay cho targets.txt roi hoan tat)",
        "hen_gio": "Hen gio hang ngay (Dung gio hen tu dong ban streak cho targets.txt, khong rep nguoi la)",
    }
    log.info(f"[Che do van hanh] {mode_names.get(bot_mode, bot_mode)}")

    cooldown_cache = {}

    with sync_playwright() as pw:
        # Tự động phát hiện Chromium hệ thống (Linux/Termux) để tránh lỗi thiếu file thực thi
        exec_path = None
        for candidate in ["/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/google-chrome"]:
            if os.path.exists(candidate):
                exec_path = candidate
                break

        launch_kwargs = {
            "headless": is_headless,
            "slow_mo": 10 if not is_headless else 0,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized"
            ],
            "ignore_default_args": ["--enable-automation"],
        }

        # Nếu tìm thấy Chromium hệ thống thì ưu tiên dùng ngay không cần tải thêm
        if exec_path and sys.platform != "win32":
            launch_kwargs["executable_path"] = exec_path
            log.info(f"[He thong] Phat hien Chromium tai: {exec_path}")

        try:
            browser = pw.chromium.launch(**launch_kwargs)
        except Exception as launch_err:
            if "executable_path" in launch_kwargs:
                log.warning(f"Thu lai voi trinh duyet mac dinh cua Playwright ({launch_err})...")
                launch_kwargs.pop("executable_path")
                browser = pw.chromium.launch(**launch_kwargs)
            else:
                raise launch_err

        context = browser.new_context(
            viewport=None if not is_headless else {"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.navigator.chrome = {
                runtime: {},
            };
        """)

        # Nếu người dùng muốn đăng nhập nick mới để tạo session riêng
        if new_session_target:
            save_path = new_session_target if os.path.isabs(new_session_target) else os.path.join(BASE_DIR, new_session_target)
            log.info("=" * 65)
            log.info(f"[Tao Session Moi] Vui long DANG NHAP tai khoan TikTok tren trinh duyet.")
            log.info(f"   -> Sau khi dang nhap thanh cong, quay lai day nhan phim ENTER.")
            log.info(f"   -> Cookie se duoc luu vao: {save_path}")
            log.info("=" * 65)
            page = context.new_page()
            page.goto("https://www.tiktok.com/login", timeout=60000)
            input(">> Nhan ENTER sau khi da dang nhap xong tren TikTok: ")
            cookies = context.cookies()
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            log.info(f"[Thanh cong] Da xuat va luu session vao: {save_path}")
            log.info("Boss man co the dung file nay de chay bot cho nick moi.")
            return

        # Nạp session cookie
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    context.add_cookies(json.load(f))
                log.info(f"[Phien dang nhap] Da nap session cookie tu {cookie_file}")
            except Exception as e:
                log.warning(f"Loi khi nap cookie: {e}")
        else:
            log.warning(f"[Canh bao] Khong tim thay file cookie tai {cookie_file}")

        page = context.new_page()

        # Chặn tải video stream nặng để tăng tốc độ tải trang lên 300%
        try:
            page.route("**/*", lambda route: route.abort() if route.request.resource_type == "media" else route.continue_())
        except Exception:
            pass

        # Mở trang tin nhắn TikTok
        log.info(f"[TikTok - {session_tag}] Dang truy cap hop thu tin nhan...")
        page.goto("https://www.tiktok.com/messages", timeout=45000)
        page.wait_for_timeout(3000)
        detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

        # Nếu chưa đăng nhập
        if "login" in page.url.lower() or not os.path.exists(cookie_file):
            if is_headless:
                log.error(f"[Loi] Chua co cookie hop le tai {cookie_file}! Hay chay o che do cua so de dang nhap.")
                return
            else:
                log.info("=" * 60)
                log.info(f"[Huong dan] Vui long DANG NHAP tren trinh duyet Chrome cho {session_tag}.")
                log.info("[Huong dan] Sau khi thay trang chu TikTok, quay lai day nhan ENTER.")
                log.info("=" * 60)
                input(">> Nhan ENTER khi ban da dang nhap thanh cong: ")
                cookies = context.cookies()
                with open(cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                log.info(f"[Thanh cong] Da luu session cookie vao {cookie_file}")
                page.goto("https://www.tiktok.com/messages", timeout=45000)
                page.wait_for_timeout(3000)

        log.info(f"[TikTok - {session_tag}] Da vao hop thu tin nhan! San sang giu chuoi lua...")
        if bot_mode == "hen_gio":
            cfg = load_streak_config()
            target_t = cfg.get("streak_time", "00:30")
            target_d = cfg.get("target_date", "")
            d_lbl = f" ngay {target_d}" if target_d else " (hang ngay)"
            log.info(f"[Lich hen] Da khoa gio giu chuoi luc {target_t}{d_lbl}.")
            log.info(f"   -> Che do: DUNG GIO HEN {target_t} tu dong gui chuoi lua cho targets.txt. KHONG rep tin nguoi la.")
        else:
            log.info("[Che do] BAN STREAK NGAY LAP TUC: Gui chuoi lua ngay cho targets.txt roi hoan tat.")
        print()

        cycle = 0
        while True:
            cycle += 1
            if not page.url.startswith("https://www.tiktok.com/messages"):
                log.info("[Dieu huong] Dang mo lai hop thu tin nhan...")
                page.goto("https://www.tiktok.com/messages", timeout=30000)
                page.wait_for_timeout(2000)

            # Tạm dừng chờ boss man kéo CAPTCHA nếu TikTok yêu cầu
            detect_and_wait_for_manual_captcha(page, context, cookie_file=cookie_file, is_headless=is_headless)

            # Gui chuoi lua giu chuoi cho targets.txt
            force_now = (bot_mode == "target")
            check_and_send_daily_streaks(page, hub, quota_tracker, force_now=force_now, session_tag=session_tag, context=context, cookie_file=cookie_file, is_headless=is_headless)

            if bot_mode == "target":
                log.info("[Hoan tat] Da gui xong chuoi streak cho toan bo nick trong targets.txt. Ket thuc!")
                break

            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Dung] Bot da dung theo lenh nguoi dung. Tam biet!")
