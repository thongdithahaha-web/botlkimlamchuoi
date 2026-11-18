#!/usr/bin/env bash
# ========================================================================
#  tool tự động rep chuỗi tiktok 24/7 (bản điện thoại android termux)
#  hiệu ứng sóng 7 màu truecolor 24-bit chuyển động vĩnh viễn (thuật toán lkl.py)
#  tác giả: lê kim lâm (@lkimlam_165)
# ========================================================================

# 1. tự động giữ nguồn termux không bao giờ ngủ cpu
termux-wake-lock 2>/dev/null

# 2. tự động bật sshd nếu chưa chạy để không bao giờ bị mất kết nối
pgrep -x "sshd" > /dev/null || sshd 2>/dev/null

# 3. tự động nạp vào ~/.bashrc để mỗi lần mở termux là sshd tự chạy vĩnh viễn
if [ -f "$HOME/.bashrc" ]; then
    grep -q "pgrep -x sshd" "$HOME/.bashrc" || echo -e '\n# tu dong giu nguon va bat sshd 24/7\ntermux-wake-lock 2>/dev/null\npgrep -x sshd > /dev/null || sshd 2>/dev/null' >> "$HOME/.bashrc"
else
    echo -e '# tu dong giu nguon va bat sshd 24/7\ntermux-wake-lock 2>/dev/null\npgrep -x sshd > /dev/null || sshd 2>/dev/null' > "$HOME/.bashrc"
fi

# 4. kiểm tra xem đang ở trong ubuntu proot hay termux native
IS_UBUNTU=0
if [ -f "/etc/issue" ] && grep -qi "ubuntu" /etc/issue; then
    IS_UBUNTU=1
fi

if [ "$IS_UBUNTU" -eq 1 ]; then
    # đang ở trong ubuntu proot
    cd "$HOME/tiktok_bot" 2>/dev/null || cd /root/tiktok_bot 2>/dev/null
    echo "nameserver 8.8.8.8" > /etc/resolv.conf 2>/dev/null
    echo "nameserver 1.1.1.1" >> /etc/resolv.conf 2>/dev/null
    rm -f /usr/bin/chromium-browser 2>/dev/null
    python3 menu.py "$@"
else
    # đang ở ngoài termux native: đồng bộ file và khởi chạy menu.py trong ubuntu proot
    echo -e "\033[38;5;51m[khoi dong] dang dong bo file sang ubuntu proot va chay menu...\033[0m"
    proot-distro login ubuntu -- bash -c "echo 'nameserver 8.8.8.8' > /etc/resolv.conf && echo 'nameserver 1.1.1.1' >> /etc/resolv.conf && rm -f /usr/bin/chromium-browser 2>/dev/null && mkdir -p /root/tiktok_bot && cp -rf $HOME/tiktok_bot/* /root/tiktok_bot/ 2>/dev/null && cd /root/tiktok_bot && python3 menu.py"
fi
