#!/usr/bin/env bash
# script khoi dong bot trong tmux native termux
SESS="${1:-1 2}"
MODE="${2:-both}"

termux-wake-lock 2>/dev/null
pgrep -x sshd > /dev/null || sshd 2>/dev/null

# dong bo file sang thu muc ubuntu proot
proot-distro login ubuntu -- bash -c "mkdir -p /root/tiktok_bot && cp -rf /data/data/com.termux/files/home/tiktok_bot/* /root/tiktok_bot/ 2>/dev/null" 2>/dev/null

# tao lenh khoi dong trong script con de tranh loi quote
cat << 'RUNNER' > "$HOME/tiktok_bot/.runner.sh"
#!/usr/bin/env bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf 2>/dev/null
echo "nameserver 1.1.1.1" >> /etc/resolv.conf 2>/dev/null
rm -f /usr/bin/chromium-browser 2>/dev/null
cd /root/tiktok_bot || exit 1
python3 run_multi.py --sessions "$1" --headless --mode "$2"
RUNNER
chmod +x "$HOME/tiktok_bot/.runner.sh"
proot-distro login ubuntu -- bash -c "cp -f /data/data/com.termux/files/home/tiktok_bot/.runner.sh /root/tiktok_bot/.runner.sh && chmod +x /root/tiktok_bot/.runner.sh" 2>/dev/null

# khoi dong tmux native termux
tmux kill-session -t bot 2>/dev/null
tmux new-session -d -s bot "proot-distro login ubuntu -- bash /root/tiktok_bot/.runner.sh '$SESS' '$MODE'"

echo "[thanh cong] da khoi dong bot trong tmux phien 'bot' tren termux!"
