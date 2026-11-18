#!/usr/bin/env bash
echo "========================================================================"
echo "          KIEM TRA TRANG THAI BOT TREN DIEN THOAI TERMUX"
echo "========================================================================"

if tmux has-session -t bot 2>/dev/null; then
    echo "[TRANG THAI] BOT DANG CHAY NGAM 24/7 TRONG PHIEN TMUX (bot)"
    echo "========================================================================"
    echo "Nhat ky hoat dong moi nhat:"
    echo "------------------------------------------------------------------------"
    tmux capture-pane -pt bot 2>/dev/null | tail -n 15
    echo "------------------------------------------------------------------------"
else
    echo "[THONG BAO] Hien khong co bot nao dang chay ngam tren dien thoai."
    echo ""
    echo "Goi y: Boss man hay bam phim bat ky de quay lai menu va bam so [2] nhe!"
fi
