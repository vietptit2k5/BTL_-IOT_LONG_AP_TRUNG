# Lộ trình 2 — Đo đạc và lấy dữ liệu thực tế

Dành cho người học **phần cứng, đọc cảm biến, điều khiển tải, ghi dữ liệu và các phép đo** đã tạo ra bộ số liệu của nhóm. Phần đọc code làm được trên laptop. Phần chạy thật cần Raspberry Pi và hộp, và phải có người theo dõi.

**Luồng dữ liệu:** DS18B20 / DHT11 → `do_nhiet_hop.py` (mỗi giây: đọc, ra lệnh PWM, ghi một dòng CSV) → thư mục kết quả trên Pi → `scp` về laptop → `Du_lieu_*/` → script phân tích → `outputs/`.

## Bước 1 — Phần cứng và nối dây

| Tài liệu | Nội dung |
|---|---|
| [../Code_HopAp_Demo/README.md](../Code_HopAp_Demo/README.md) | **Sơ đồ hiện hành:** mạch 12 V hai MOSFET, bảng chân Pi, breadboard, các lớp an toàn |
| [../Code_HopAp_Demo/HUONG_DAN_DO_NHIET.md](../Code_HopAp_Demo/HUONG_DAN_DO_NHIET.md) | Nối DS18B20 (1-Wire, trở 4,7 kΩ), OLED I²C, kiểm tra cảm biến |
| [../Code_HopAp_Demo/HUONG_DAN_DHT11.md](../Code_HopAp_Demo/HUONG_DAN_DHT11.md) | DHT11 và driver kernel `dtoverlay=dht11` |
| [HUONG_DAN_LAP_DEMO_HOP_AP.md](HUONG_DAN_LAP_DEMO_HOP_AP.md), [DANH_SACH_MUA_HOP_AP.md](DANH_SACH_MUA_HOP_AP.md) | Lắp hộp ban đầu, danh sách linh kiện |

## Bước 2 — Thử mạch (chưa cần cảm biến)

| File | Học gì |
|---|---|
| [../Code_HopAp_Demo/thu_mach.py](../Code_HopAp_Demo/thu_mach.py), [thu_mach_12v.py](../Code_HopAp_Demo/thu_mach_12v.py), [chay_ca_mach_12v.py](../Code_HopAp_Demo/chay_ca_mach_12v.py) | Bật thử bóng và quạt vài giây bằng `gpiozero` với backend `lgpio`; luôn đưa tải về trạng thái tắt khi gặp Ctrl+C, SIGTERM hoặc lỗi |

## Bước 3 — Lõi đo và điều khiển: `do_nhiet_hop.py` (file quan trọng nhất)

[../Code_HopAp_Demo/do_nhiet_hop.py](../Code_HopAp_Demo/do_nhiet_hop.py), khoảng 770 dòng. Đọc theo thứ tự:

| Phần | Vai trò |
|---|---|
| `find_sensor`, `parse_temperature`, `SensorWorker` | Đọc DS18B20 qua `/sys/bus/w1/devices/28-*/w1_slave` trong một luồng riêng; số đo cũ quá 3 s bị coi là mất |
| `Outputs` | PWM 100 Hz trên GPIO23 (bóng) và GPIO18 (quạt); xung khởi động quạt; `heater_off()` |
| `Recorder` | Ghi CSV mỗi giây (các cột ở bảng dưới), hiện OLED, tính xu hướng nhiệt |
| `receive_reading` | Dừng cứng khi vượt ngưỡng `--ngat-nhiet` |
| `run_session` | Vòng lặp chính; gọi `control_policy` mỗi chu kỳ nếu có (RL, thermostat, khảo sát) |
| `make_parser`, `prepare`, `main` | 4 chế độ tay: `doc` (chỉ đọc), `giu` (giữ mức cố định), `tay` (gõ lệnh lúc chạy), `kich-ban` (theo file CSV) |

Các file đi kèm:
- [oled_hop_ap.py](../Code_HopAp_Demo/oled_hop_ap.py): vẽ OLED trong luồng riêng.
- [dht_reader.py](../Code_HopAp_Demo/dht_reader.py): đọc DHT11 qua driver kernel hoặc thư viện Adafruit.
- [do_am.py](../Code_HopAp_Demo/do_am.py): dịch vụ đọc độ ẩm, ghi `do_am_moi_nhat.json`.
- [do_am_dht11.py](../Code_HopAp_Demo/do_am_dht11.py): nguồn độ ẩm cho chương trình điều khiển, đọc trực tiếp hoặc qua file.
- [kiem_tra_dht11.py](../Code_HopAp_Demo/kiem_tra_dht11.py): chẩn đoán DHT11.

**Các cột trong CSV** (mọi lượt đo đều dùng định dạng này; các lượt trước 20/11 chưa có 3 cột độ ẩm):

| Cột | Ý nghĩa |
|---|---|
| `timestamp_utc`, `elapsed_s` | Giờ UTC; số giây kể từ đầu lượt (đồng hồ đơn điệu) |
| `event` | `MEASUREMENT` (số đo mỗi giây), `COMMAND` (đổi lệnh), `OUTPUT_CHANGE`, `STOP`, `END`, `ERROR` |
| `phase` | Giai đoạn, ví dụ `lam_am_ap`, `ap_ngay12_gd2` (ngày 12, giai đoạn 2), `…_bao_ve`, `…_phuc_hoi`, `giu_quat_cuoi` |
| `sensor_id`, `temperature_c`, `temperature_age_s` | Mã DS18B20, nhiệt độ, tuổi của số đo |
| `gpio_control` | 1 nếu chương trình có điều khiển tải |
| `lamp_requested_pct`, `fan_requested_pct` | Mức được yêu cầu |
| `lamp_command_pct`, `fan_command_pct` | Mức thực sự gửi ra PWM (khác mức yêu cầu trong lúc xung khởi động quạt) |
| `fan_pwm_hz`, `cutoff_c` | Tần số PWM quạt; ngưỡng dừng cứng |
| `trend_c_per_min` | Xu hướng nhiệt trong 30 s (°C/phút) |
| `note` | Ghi chú của lệnh: lý do, state của Q, mô tả ngày ấp |
| `humidity_pct`, `humidity_age_s`, `humidity_error` | Độ ẩm, tuổi số đo, lỗi DHT11 |

Ngoài CSV, mỗi lượt còn có `cau_hinh.json` (tham số, mã hash của code, thống kê) và với một số chương trình có thêm `ket_qua.json` (MAE, % trong vùng).

## Bước 4 — Các phép đo đã tạo ra dữ liệu của nhóm

| Phép đo | Chương trình | Dữ liệu thu được | Dùng để |
|---|---|---|---|
| Khảo sát đáp ứng: bóng 0–100 %, quạt 75/100 %, 120 s mỗi tổ hợp, lặp 2 lần | [khao_sat_nhiet.py](../Code_HopAp_Demo/khao_sat_nhiet.py) (`do`) | [../Du_lieu_khao_sat/20261117_070909_628598/](../Du_lieu_khao_sat/20261117_070909_628598/) | Khớp mô hình, huấn luyện Q1 |
| Giữ nhiệt 600 s: thermostat, Q1, mức cố định | [kiem_tra_giu_nhiet.py](../Code_HopAp_Demo/kiem_tra_giu_nhiet.py) (`do --bo-dieu-khien doi-chung / thu-rl / co-dinh`) | [../Du_lieu_giu_nhiet/ket_qua_giu_nhiet/](../Du_lieu_giu_nhiet/ket_qua_giu_nhiet/) | So sánh thật thermostat với Q1 |
| Đáp ứng quanh mốc 37,5 °C, 20 phút mỗi tổ hợp | [do_dap_ung_bo_sung.py](../Code_HopAp_Demo/do_dap_ung_bo_sung.py), kế hoạch [ke_hoach_do_day_du.py](../Code_HopAp_Demo/ke_hoach_do_day_du.py) | [../Du_lieu_dap_ung/](../Du_lieu_dap_ung/) | Khớp lại mô hình, huấn luyện Q2 |
| Pilot Q2 trên hộp | [thu_rl_du_lieu_moi.py](../Code_HopAp_Demo/thu_rl_du_lieu_moi.py) | [../Du_lieu_giu_nhiet/20261120_pilot_01/](../Du_lieu_giu_nhiet/20261120_pilot_01/) | Kiểm chứng Q2 thật |
| Lượt 3 giai đoạn (RL hoặc thermostat) | [ap_trung.py](../Code_HopAp_Demo/ap_trung.py), chạy qua [chay_demo.sh](../Code_HopAp_Demo/chay_demo.sh) hoặc app | `ket_qua_ap_trung/` trên Pi (chưa chép về) | Kết quả cuối cho báo cáo |
| Thử quạt 0 % và 75 % khi làm ấm | [thu_quat_lam_am.py](../Code_HopAp_Demo/thu_quat_lam_am.py) | — | Phép thử ngắn |

Hướng dẫn chi tiết từng phép đo nằm ở [../Code_HopAp_Demo/HUONG_DAN_KHAO_SAT_RL.md](../Code_HopAp_Demo/HUONG_DAN_KHAO_SAT_RL.md) và trong [../Code_HopAp_Demo/tai_lieu_cu/](../Code_HopAp_Demo/tai_lieu_cu/).

## Bước 5 — Lấy dữ liệu về và phân tích

```powershell
# Trên laptop (PowerShell), thay IP nếu khác
scp -r pi@192.168.0.172:/home/pi/Code_HopAp_Demo/ket_qua_ap_trung "D:\BTL_Nhom13\Du_lieu_giu_nhiet"
```

| Script (chạy trên laptop) | Làm gì |
|---|---|
| [../Code_HopAp_PhanTich/phan_tich_ap_trung.py](../Code_HopAp_PhanTich/phan_tich_ap_trung.py) | Lượt 3 giai đoạn: tách đoạn theo ngày; tính thời gian vào vùng, % trong vùng, MAE, số lần đổi mức; vẽ đồ thị |
| [../Code_HopAp_Demo/kiem_tra_giu_nhiet.py](../Code_HopAp_Demo/kiem_tra_giu_nhiet.py) `phan-tich --log …` | Tóm tắt một lượt giữ nhiệt 600 s |
| [../Code_HopAp_Demo/so_sanh_giu_nhiet.py](../Code_HopAp_Demo/so_sanh_giu_nhiet.py) | So sánh nhiều lượt giữ nhiệt hoàn chỉnh |
| [../Code_HopAp_Demo/danh_gia_giu_nhiet.py](../Code_HopAp_Demo/danh_gia_giu_nhiet.py) | Đối chiếu một lượt mới với dự báo của mô hình |

Dữ liệu rút gọn (mỗi 5 s một mẫu) cũng có trên Firebase: vào console, mở **Realtime Database → Export JSON**. App có bảng lịch sử các lượt.

## Quy tắc khi đo

- Hộp rỗng, có người theo dõi; nhiệt ban đầu ≤ 30 °C với các phép đo có làm ấm.
- Mỗi lúc chỉ **một** chương trình dùng GPIO18/23; DHT11 (GPIO17) thuộc về dịch vụ `hop-ap-do-am` khi dịch vụ này chạy.
- Giữ nguyên vị trí đầu dò, bóng, quạt, nắp giữa các lượt định so sánh; ghi nhiệt độ phòng nếu có nhiệt kế.
- **Không sửa CSV gốc** trong `Du_lieu_*`. Một số script kiểm tra mã SHA-256 của dữ liệu, và repo khai báo các thư mục này để giữ nguyên từng byte.
- Tải không tắt theo lệnh thì **rút adapter 12 V**.

## Test (không cần Pi)

```bash
cd Code_HopAp_Demo
python -m unittest test_do_nhiet_hop test_khao_sat_rl test_do_dap_ung_bo_sung test_ke_hoach_do_day_du test_do_am test_dht_reader test_kiem_tra_dht11 -v
```
