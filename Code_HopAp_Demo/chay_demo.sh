#!/usr/bin/env bash
# Một lệnh chạy lượt ấp 3 giai đoạn trên Pi, trong tmux (rớt SSH không dừng lượt).
#
#   bash chay_demo.sh                      # RL, 30 phút, giữ ngày hiện tại của mẻ
#   bash chay_demo.sh --ngay 5             # đặt (hoặc tạo) mẻ ở ngày 5 rồi chạy
#   bash chay_demo.sh thermostat --phut 30 # lượt đối chứng
#   bash chay_demo.sh --yes                # bỏ câu hỏi xác nhận
#   Độ ẩm: nếu dịch vụ hop-ap-do-am (do_am.py) đang chạy thì tự thêm --do-am; nếu không, dùng --dht11.
#
# Ô trái: cloud bridge (bỏ qua nếu đã chạy bằng dịch vụ hop-ap-bridge). Ô phải: ap_trung.py.
# Rời tmux mà không dừng: Ctrl+B rồi D. Quay lại: tmux attach -t hopap.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

CTRL=rl
PHUT=30
NGAY=""
YES=0
EXTRA=""
SESSION=hopap

while [ $# -gt 0 ]; do
  case "$1" in
    rl|thermostat) CTRL="$1" ;;
    --phut) PHUT="$2"; shift ;;
    --ngay) NGAY="$2"; shift ;;
    --dht11) EXTRA="$EXTRA --dht11" ;;
    --khong-oled) EXTRA="$EXTRA --khong-oled" ;;
    --yes|-y) YES=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Không hiểu tham số: $1 (xem: bash chay_demo.sh --help)"; exit 2 ;;
  esac
  shift
done

command -v tmux >/dev/null || { echo "Thiếu tmux. Cài: sudo apt install -y tmux"; exit 1; }
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Đã có phiên tmux '$SESSION' (lượt trước có thể còn chạy)."
  echo "  Xem lại:   tmux attach -t $SESSION"
  echo "  Đóng hẳn:  tmux kill-session -t $SESSION   (chỉ khi chắc chắn lượt đã dừng)"
  exit 1
fi
if pgrep -f "ap_trung.py|thu_rl_du_lieu_moi.py|kiem_tra_giu_nhiet.py|do_nhiet_hop.py|khao_sat_nhiet.py" >/dev/null; then
  echo "Đang có chương trình khác dùng GPIO18/23. Dừng nó trước khi chạy lượt mới."
  exit 1
fi

if [ -n "$NGAY" ]; then
  if [ -f trang_thai_me_ap.json ]; then python3 me_ap.py dat-ngay "$NGAY"; else python3 me_ap.py bat-dau --ngay "$NGAY"; fi
fi
python3 me_ap.py xem || { echo "Chưa có mẻ ấp: chạy lại với --ngay N"; exit 1; }
"$PY" ap_trung.py --bo-dieu-khien "$CTRL" --phut "$PHUT" --dry-run

if systemctl is-active --quiet hop-ap-do-am 2>/dev/null; then
  if [[ "$EXTRA" == *--dht11* ]]; then
    echo "do_am.py đang giữ GPIO17 (dịch vụ hop-ap-do-am): bỏ --dht11, dùng --do-am thay thế."
    EXTRA="${EXTRA/ --dht11/}"
  fi
  EXTRA="$EXTRA --do-am"
fi

BRIDGE=1
if systemctl is-active --quiet hop-ap-bridge 2>/dev/null; then
  echo "Cloud bridge đang chạy bằng dịch vụ hop-ap-bridge: không mở thêm bridge."
  BRIDGE=0
elif [ ! -f firebase_bi_mat.json ]; then
  echo "CẢNH BÁO: thiếu firebase_bi_mat.json, chạy KHÔNG có đám mây/app."
  BRIDGE=0
fi

if [ "$YES" -ne 1 ]; then
  echo
  echo "Kiểm tra trước khi bật tải: hộp rỗng, nhiệt trong hộp <= 30 °C, adapter 12 V đã cắm, có người theo dõi."
  read -r -p "Gõ y rồi Enter để bắt đầu: " ok
  [ "$ok" = "y" ] || { echo "Đã hủy."; exit 0; }
fi

tmux new-session -d -s "$SESSION" -n demo
if [ "$BRIDGE" -eq 1 ]; then
  tmux send-keys -t "$SESSION:demo" "python3 cloud_bridge.py chay" C-m
  tmux split-window -h -t "$SESSION:demo"
fi
tmux send-keys -t "$SESSION:demo" \
  "$PY ap_trung.py --bo-dieu-khien $CTRL --phut $PHUT$EXTRA; echo; echo 'Lượt đã kết thúc. Gõ exit để đóng ô này.'" C-m
tmux set-option -t "$SESSION" status-right " Ctrl+B D: rời | Ctrl+B mũi tên: đổi ô " >/dev/null
exec tmux attach -t "$SESSION"
