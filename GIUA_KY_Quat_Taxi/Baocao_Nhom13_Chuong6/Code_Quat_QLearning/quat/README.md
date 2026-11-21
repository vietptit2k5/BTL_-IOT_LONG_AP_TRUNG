# Điều khiển quạt làm mát Raspberry Pi bằng Q-learning (Nhóm 13 – IoT và ứng dụng)

## Phần cứng
- Raspberry Pi 4, DS18B20 (GPIO4, trở kéo lên 4,7 kΩ lên 3,3 V), quạt 5 V qua S8050 (B ← 1 kΩ ← GPIO18), diode 1N4007 song song ngược với quạt.
- Bật 1-Wire: `sudo raspi-config` → Interface Options → 1-Wire, rồi reboot.

## Cài đặt
    sudo apt install -y python3-numpy python3-matplotlib python3-flask

## Chạy
    python3 test_phan_cung.py                                   # kiểm tra cảm biến + quạt
    python3 fan_qlearning.py train --tamb 34 --tmax0 66.7 --tmax3 48 --target 52 --eps_min 0.02 --alpha 0.3 --seed 1 --out q_quat.npy
    python3 xem_qtable.py                                       # in bảng Q
    # 3 cửa sổ:
    python3 tao_tai.py --cores 4 --on 180 --off 120 --lap 5
    python3 fan_qlearning.py real --q q_quat.npy --sensor cpu --target 52 --minutes 20 --log log_q.csv
    python3 dashboard.py --log log_q.csv --target 52            # mở http://pi:5000
    python3 fan_qlearning.py plot --log log_q.csv --target 52 --png bieu_do.png

## File
- fan_qlearning.py: Pi ảo (SimFanEnv), môi trường thật (RealFanEnv), Q-learning, lệnh train/real/plot
- tao_tai.py: tạo tải CPU; test_phan_cung.py: test phần cứng; xem_qtable.py: in bảng Q
- dashboard.py + chart.umd.js: web giám sát Flask (không cần Internet)
- q_quat.npy, q_quat_rewards.npy: bảng Q đã học, đường cong phần thưởng
- log_q.csv: log 20 phút chạy thật
