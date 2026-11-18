# TikTok Auto-Streak Flame Bot 

Tool tự động thắp lửa và giữ chuỗi (streak) TikTok hàng ngày cho bạn bè, hỗ trợ chạy mượt mà trên cả **Windows** và **Android Termux (Ubuntu PRoot)**.

- **Tác giả:** Lê Kim Lâm (@lkimlam_165 / lkimlamdev)
- **Mục đích:** Tự động gửi chuỗi tin nhắn thắp lửa (🔥) cho danh sách bạn bè theo lịch hẹn cố định hàng ngày hoặc gửi ngay lập tức. Không làm phiền, không tự động rep tin nhắn người lạ.

---

## Tính Năng Nổi Bật

1. **Nhận Diện Thông Minh 100%:**
   - Tự động tìm kiếm cuộc hội thoại qua 3 phương pháp liên hoàn: Danh sách hội thoại gần đây, Thanh tìm kiếm tin nhắn, và Trang cá nhân người dùng.
   - Hỗ trợ đa dạng selector cho nút **Tin nhắn** / **Message** (tiếng Việt, tiếng Anh, icon SVG, role button).
2. **Cơ Chế Hẹn Giờ Chuẩn Xác:**
   - Tự động kích hoạt khi đến giờ hẹn trong ngày (ví dụ: `00:30` hàng ngày).
   - Đảm bảo tất cả các session đều gửi đủ chuỗi cho toàn bộ danh sách `targets.txt`.
   - Tránh gửi trùng lặp nhờ hệ thống ghi nhật ký `streak_history.json`.
3. **Bảo Mật & An Toàn:**
   - Tự động nhận diện CAPTCHA và tạm dừng thông minh để người dùng thao tác bằng tay trực tiếp trên trình duyệt.
   - Cookie phiên đăng nhập được mã hóa và lưu trữ cục bộ, không đẩy thông tin nhạy cảm lên GitHub.
4. **Hỗ Trợ Termux Android Chuyên Dụng:**
   - Chạy ẩn 100% (Headless) tiết kiệm pin và RAM.
   - Tự động giữ nguồn CPU (`termux-wake-lock`) và duy trì SSH 24/7.

---

## Cấu Trúc Dự Án

```
├── CHAY_BOT_PC.bat          # Bảng điều khiển chính trên máy tính Windows
├── menu.sh / menu.py        # Menu điều khiển trực quan trên điện thoại Termux
├── run_local.py             # Nhân xử lý tự động hóa trình duyệt (Playwright)
├── run_multi.py             # Bộ điều phối chạy đa tài khoản song song
├── hen_gio.py               # Công cụ cài đặt giờ hẹn thắp lửa
├── targets.txt              # Danh sách tài khoản bạn bè cần giữ chuỗi
├── streak_config.json       # Cấu hình giờ hẹn hàng ngày
└── time_api_config.json     # Cấu hình đồng bộ giờ chuẩn Việt Nam qua API
```

---

## Hướng Dẫn Sử Dụng

### 1. Trên Máy Tính (Windows)
1. Mở file `CHAY_BOT_PC.bat`.
2. Chọn `[4] Chay truc tiep tren may tinh`:
   - Chọn `[1] BAN STREAK CHO TARGETS NGAY LAP TUC`: Gửi chuỗi ngay cho bạn bè rồi tắt.
   - Chọn `[2] CHAY HEN GIO HANG NGAY`: Để bot chạy ngầm, đến đúng giờ hẹn sẽ tự động gửi.

### 2. Trên Điện Thoại (Termux Android)
1. Mở Termux và chạy lệnh:
   ```bash
   cd ~/tiktok_bot && ./menu.sh
   ```
2. Giao diện menu terminal sẽ xuất hiện:
   - Phím `1`, `2`, `3`: Bắn streak ngay lập tức cho các session.
   - Phím `4`: Chạy ngầm hẹn giờ hàng ngày (tắt màn hình bot vẫn chạy).
   - Phím `5`: Chỉnh sửa giờ hẹn thắp lửa.
