#!/usr/bin/env bash
# script khoi dong bot ben trong ubuntu proot
cd /root/tiktok_bot 2>/dev/null || cd "$HOME/tiktok_bot"
echo "nameserver 8.8.8.8" > /etc/resolv.conf 2>/dev/null
echo "nameserver 1.1.1.1" >> /etc/resolv.conf 2>/dev/null
rm -f /usr/bin/chromium-browser 2>/dev/null

SESS="${1:-1 2}"
MODE="${2:-both}"

tmux kill-session -t bot 2>/dev/null
tmux new-session -d -s bot "python3 run_multi.py --sessions \"$SESS\" --headless --mode $MODE"
echo "[thanh cong] da khoi dong bot trong tmux phien 'bot' voi session [$SESS] va che do [$MODE]!"
