#!/usr/bin/env bash
# Cài do_am.py thành dịch vụ systemd "hop-ap-do-am": đọc DHT11 liên tục, tự chạy khi Pi khởi động.
#
#   bash cai_dich_vu_do_am.sh           # cài và bật
#   bash cai_dich_vu_do_am.sh go        # gỡ
#   journalctl -u hop-ap-do-am -f       # xem từng lần đọc
#
# Khi dịch vụ chạy, GPIO17 thuộc về do_am.py: chương trình điều khiển dùng --do-am (chay_demo.sh tự thêm),
# KHÔNG dùng --dht11. Chỉ đọc cảm biến, không điều khiển bóng/quạt; không bật OLED (OLED dành cho điều khiển).
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
USER_NAME="$(id -un)"
UNIT=/etc/systemd/system/hop-ap-do-am.service
PY="$DIR/.venv/bin/python"

if [ "${1:-}" = "go" ]; then
  sudo systemctl disable --now hop-ap-do-am 2>/dev/null || true
  sudo rm -f "$UNIT"
  sudo systemctl daemon-reload
  echo "Đã gỡ dịch vụ hop-ap-do-am."
  exit 0
fi

[ -x "$PY" ] || PY=/usr/bin/python3   # Driver kernel không cần venv/thư viện Adafruit.
if ! grep -qs '^dht11' /sys/bus/iio/devices/iio:device*/name; then
  "$PY" -c "import board, adafruit_dht" || {
    echo "Chưa bật driver kernel và cũng thiếu thư viện Adafruit."
    echo "Khuyên dùng: echo 'dtoverlay=dht11,gpiopin=17' | sudo tee -a /boot/firmware/config.txt && sudo reboot"
    exit 1; }
fi
if pgrep -f "do_nhiet_hop.py.*--dht11|ap_trung.py.*--dht11|do_am.py" >/dev/null; then
  echo "Đang có chương trình khác đọc GPIO17 (--dht11 hoặc do_am.py). Dừng nó trước."; exit 1
fi

sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Hop ap nhom 13 - doc do am DHT11 (GPIO17)
After=multi-user.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PY $DIR/do_am.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hop-ap-do-am
sudo systemctl restart hop-ap-do-am   # luôn nạp code mới (enable --now không khởi động lại dịch vụ đang chạy)
sleep 8
journalctl -u hop-ap-do-am -n 4 --no-pager || true
echo
echo "Đã cài. Xem trực tiếp: journalctl -u hop-ap-do-am -f   (Ctrl+C chỉ thoát xem, dịch vụ vẫn chạy)"
