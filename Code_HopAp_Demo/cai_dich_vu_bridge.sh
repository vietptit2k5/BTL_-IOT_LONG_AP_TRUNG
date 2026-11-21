#!/usr/bin/env bash
# Cài cloud_bridge.py thành dịch vụ systemd "hop-ap-bridge": tự chạy khi Pi khởi động, tự chạy lại khi lỗi.
#
#   bash cai_dich_vu_bridge.sh          # cài và bật
#   bash cai_dich_vu_bridge.sh go       # gỡ
#   journalctl -u hop-ap-bridge -f      # xem nhật ký
#
# Dịch vụ chạy bằng tài khoản hiện tại (để gửi được SIGTERM cho chương trình điều khiển cùng tài khoản).
# Chương trình điều khiển (ap_trung.py) KHÔNG tự chạy: bật tải luôn cần người khởi động và theo dõi.
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
USER_NAME="$(id -un)"
UNIT=/etc/systemd/system/hop-ap-bridge.service

if [ "${1:-}" = "go" ]; then
  sudo systemctl disable --now hop-ap-bridge 2>/dev/null || true
  sudo rm -f "$UNIT"
  sudo systemctl daemon-reload
  echo "Đã gỡ dịch vụ hop-ap-bridge."
  exit 0
fi

[ -f "$DIR/firebase_bi_mat.json" ] || { echo "Thiếu $DIR/firebase_bi_mat.json"; exit 1; }
chmod 600 "$DIR/firebase_bi_mat.json"
python3 "$DIR/cloud_bridge.py" kiem-tra || { echo "kiem-tra thất bại: sửa kết nối/mật khẩu trước khi cài."; exit 1; }

sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Hop ap nhom 13 - cloud bridge (CSV -> Firebase)
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $DIR/cloud_bridge.py chay
Restart=always
RestartSec=10
# Lượt bắt đầu từ app chạy tách riêng: bridge khởi động lại KHÔNG được giết lượt đang chạy.
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hop-ap-bridge
sudo systemctl restart hop-ap-bridge   # luôn nạp code mới (enable --now không khởi động lại dịch vụ đang chạy)
sleep 3
systemctl --no-pager --lines=5 status hop-ap-bridge || true
echo
echo "Đã cài. App sẽ hiện 'Pi online' trong khoảng 10 giây. Nhật ký: journalctl -u hop-ap-bridge -f"
