#!/usr/bin/env bash
echo "Dang tat toan bo bot tren dien thoai..."
tmux kill-session -t bot 2>/dev/null
pkill -9 -f "run_multi.py" 2>/dev/null
pkill -9 -f "run_local.py" 2>/dev/null
proot-distro login ubuntu -- bash -c 'pkill -9 -f "run_multi.py" 2>/dev/null; pkill -9 -f "run_local.py" 2>/dev/null' 2>/dev/null
echo "[thanh cong] da tat sach toan bo tien trinh bot tren dien thoai!"
