# Hộp ấp 3 giai đoạn điều khiển bằng Q-learning — IoT Level-2 (Nhóm 13)

Hộp xốp rỗng giữ nhiệt theo **lịch ấp trứng gà 21 ngày**: 37,8 / 37,5 / 37,2 °C, vùng ±0,2 °C. Bóng sợi đốt sưởi, quạt trao đổi khí với phòng. Q-learning trên Raspberry Pi 4 chọn mức bóng và quạt mỗi 5 s. Dữ liệu được đẩy lên Firebase, người dùng theo dõi, **đổi ngày ấp** và **dừng khẩn cấp** trên app web: https://hop-ap-nhom13.web.app

```text
 LOCAL — Raspberry Pi 4 (phân tích + điều khiển)                     CLOUD — Firebase (lưu trữ + app)
 DS18B20, DHT11 ─► ap_trung.py (Q-table + bảo vệ) ─► PWM ─► MOSFET ─► bóng 12 V / quạt 12 V
                      │ ghi CSV mỗi 1 s        ▲ đọc lịch mỗi 5 s
                      ▼                        │
                 du_lieu.csv            trang_thai_me_ap.json ◄─┐
                      │                                          │ đổi ngày
                      └──► cloud_bridge.py ──REST/HTTPS──► Realtime Database ◄──WebSocket── App PWA
                               (dịch vụ systemd)    ◄── lệnh dừng / đổi ngày ──┘
```

Mất Internet thì hộp **vẫn giữ nhiệt** (điều khiển cục bộ), bridge gửi bù khi có mạng lại. Đám mây chỉ được ra hai lệnh: **dừng** và **chọn ngày 1–21**, tức chỉ chọn trong 3 mốc định sẵn. Mọi bảo vệ nằm trên Pi.

## 1. Phần cứng và nối dây (cấu hình hiện hành)

**Phía 12 V** (dây 0,75 mm²; Pi dùng nguồn USB-C riêng, 12 V không bao giờ đi vào Pi):

```text
Adapter 12 V → jack DC (+) → cầu chì 3 A → WAGO A (+12 V)       jack DC (−) → WAGO B (0 V)
WAGO A → KSD301 (NC, ~50 °C) → bóng sợi đốt 12 V–21 W → LOAD module MOSFET bóng
WAGO A → quạt 12 V (+) ;  quạt (−) → LOAD module MOSFET quạt
Mỗi module AOD4184 (cách ly quang): cọc + → WAGO A, cọc − → WAGO B
```

**Phía tín hiệu** (Dupont; mọi cảm biến dùng **3,3 V**; đúng mạch đang lắp ngày 21/11, không chân nào bị dùng hai lần).

DS18B20 và OLED đi qua **breadboard**, chia thành 3 hàng ngang: hàng 10 là **3,3 V** (từ chân 1), hàng 14 là **DATA 1-Wire** (GPIO4, chân 7), hàng 18 là **GND** (chân 9). Trên breadboard, cột a là cảm biến, cột b là OLED, cột c là điện trở, cột e là dây về Pi.

```text
hàng 10 (3,3 V):  a = DS18B20 VDD · b = OLED VCC · c = trở 4,7 kΩ (đầu trên) · d = DHT11 VCC · e → Pi chân 1
hàng 14 (DATA):   a = DS18B20 DATA · c = trở 4,7 kΩ (đầu dưới) · e → Pi chân 7 (GPIO4)
hàng 18 (GND):    a = DS18B20 GND · b = OLED GND · d = DHT11 GND · e → Pi chân 9
OLED SDA → Pi chân 3 (GPIO2) · OLED SCL → Pi chân 5 (GPIO3) · DHT11 DATA → Pi chân 11 (GPIO17) — nối thẳng, không qua breadboard
```


| Thiết bị | Chân thiết bị | Pi 4 (BCM / chân vật lý) |
|---|---|---|
| MOSFET bóng | PWM / GND tín hiệu | GPIO23 / **16** · GND **14** |
| MOSFET quạt | PWM / GND tín hiệu | GPIO18 / **12** · GND **6** |
| DS18B20 (+ trở 4,7 kΩ giữa DQ và 3,3 V) | VDD / DQ / GND | qua breadboard: 3,3 V **1** · GPIO4 / **7** · GND **9** |
| OLED SSD1306 I²C (0x3C) | VCC / GND / SDA / SCL | VCC, GND qua breadboard (chân **1** / **9**) · SDA GPIO2 / **3** · SCL GPIO3 / **5** |
| DHT11 (module 3 chân) | VCC / DATA / GND | VCC, GND qua breadboard (lỗ d10 / d18, tức chân **1** / **9**) · DATA GPIO17 / **11** nối thẳng |
| LED đỏ / xanh (tùy chọn, chưa lắp) | qua trở 330 Ω | GPIO24 / **18** → GND **30** · GPIO25 / **22** → GND **34** |

Chân 3,3 V và GND của cả ba cảm biến/màn đều đi qua breadboard (chân 1 và 9), nên trên Pi chỉ dùng thêm các chân tín hiệu: **3, 5** (OLED) · **7** (DS18B20) · **11** (DHT11) · **12, 16** (PWM quạt, bóng) cùng GND tín hiệu của hai module MOSFET. Chân 17 (3,3 V) và các GND 20, 25, 30, 34 còn trống.

**Cơ cấu chấp hành:** 2 cái, là bóng và quạt; MOSFET chỉ là mạch công suất. **Cảm biến:** DS18B20 (nhiệt, dùng cho điều khiển), DHT11 (độ ẩm, **chỉ giám sát**).

## 2. An toàn (độc lập với Q-table)

| Lớp | Ngưỡng | Hành động |
|---|---|---|
| Ngắt mềm (phần mềm) | ≥ 38,3 °C, bật lại khi ≤ 37,8 °C | Bóng 0 %, quạt 100 % |
| Dừng cứng (phần mềm) | ≥ 38,8 °C, hoặc mất số đo DS18B20 > 3 s | Dừng lượt, tắt bóng, quạt chạy thêm 10 s |
| State chưa học | Trên mốc thì làm mát; dưới mốc thì làm ấm phục hồi | Không bao giờ tự tăng sưởi khi đã nóng |
| KSD301 (phần cứng) | Thân KSD khoảng 50 °C | Ngắt mạch bóng |
| Cầu chì 3 A | Chập mạch / quá dòng | Ngắt +12 V |

Các ngưỡng này **cố định, không đổi theo ngày ấp**. Các chương trình đo cũ (kiem_tra_giu_nhiet, thu_rl_du_lieu_moi) dùng ngưỡng riêng của giai đoạn đó (38 → 37 °C; dừng 40 / 38,5 °C) và chỉ để tái lập số liệu cũ.

## 3. Phần mềm

**Dùng hằng ngày**

| File | Vai trò |
|---|---|
| [chay_demo.sh](chay_demo.sh) | **Một lệnh chạy lượt**: tmux 2 ô (bridge + điều khiển), kiểm tra trước, hỏi xác nhận |
| [ap_trung.py](ap_trung.py) | Điều khiển 3 giai đoạn: `--bo-dieu-khien rl` (Q2 dịch mốc) hoặc `thermostat` (đối chứng), `--phut N` |
| [me_ap.py](me_ap.py) | Lịch 21 ngày lưu bền: `bat-dau`, `dat-ngay N`, `xem` |
| [cloud_bridge.py](cloud_bridge.py) | CSV → Firebase; cảnh báo; nhận lệnh dừng và đổi ngày. [Hướng dẫn](HUONG_DAN_CLOUD.md) |
| [cai_dich_vu_bridge.sh](cai_dich_vu_bridge.sh) | Cài bridge thành dịch vụ systemd, tự chạy khi Pi khởi động. Bridge còn nhận lệnh **tạo/kết thúc mẻ** và **bắt đầu lượt** từ app, kiểm tra an toàn rồi chạy `ap_trung.py` trong tmux `hopap_app` |
| [do_am.py](do_am.py) | **Đọc và hiển thị độ ẩm** DHT11 (Terminal, `--oled`), lọc trung vị 3 lần đọc, ghi `do_am_moi_nhat.json`. Là chương trình duy nhất mở GPIO17 |
| [cai_dich_vu_do_am.sh](cai_dich_vu_do_am.sh) | Cài `do_am.py` thành dịch vụ `hop-ap-do-am`. Khi đó `chay_demo.sh` tự dùng `--do-am`, và app luôn có độ ẩm, kể cả khi không có lượt chạy |
| [kiem_tra_dht11.py](kiem_tra_dht11.py) | Chẩn đoán DHT11 (chỉ đọc) |
| `goi_rl_moi_20261120.json` | Q-table Q2 (2.430 state × 9 action), đã thử trên hộp thật; chương trình kiểm tra mã SHA-256 trước khi dùng |

**Công cụ đo và lõi** (`do_nhiet_hop.py` đọc cảm biến, xuất PWM, ghi CSV, hiển thị OLED; `khao_sat_nhiet.py` khảo sát đáp ứng; `oled_hop_ap.py`; `do_am_dht11.py`; `chinh_sach_*.py`, `rl_vung_on_dinh.py`). **Chương trình đo cũ, giữ để tái lập số liệu:** `kiem_tra_giu_nhiet.py`, `thu_rl_du_lieu_moi.py`, `thu_mach*.py`, `chay_ca_mach_12v.py`… Tài liệu cũ nằm trong [tai_lieu_cu/](tai_lieu_cu/).

**Laptop:** [../App_HopAp/](../App_HopAp/) (app PWA, quy tắc bảo mật Firebase), [../Code_HopAp_PhanTich/](../Code_HopAp_PhanTich/) (huấn luyện, mô phỏng `mo_phong_ba_giai_doan.py`, phân tích `phan_tich_ap_trung.py`).

## 4. Chạy

Lần đầu trên Pi (chi tiết trong [KIEM_THU_TICH_HOP.md](KIEM_THU_TICH_HOP.md), mục 0):

```bash
sudo apt install -y tmux python3-requests
bash cai_dich_vu_bridge.sh                 # cần firebase_bi_mat.json cạnh script
python3 me_ap.py bat-dau --ngay 5          # tạo mẻ
```

Mỗi lượt:

```bash
bash chay_demo.sh                          # RL, 30 phút;   thêm: thermostat | --phut 40 | --ngay 12 | --dht11
```

Đổi ngày trên app (thẻ **Lịch ấp**) hoặc `python3 me_ap.py dat-ngay 12`. Xem chi tiết trong [HUONG_DAN_AP_3_GIAI_DOAN.md](HUONG_DAN_AP_3_GIAI_DOAN.md). Lấy dữ liệu về và phân tích: [KIEM_THU_TICH_HOP.md](KIEM_THU_TICH_HOP.md), mục 2.

## 5. Bằng chứng hiện có

| Nội dung | Loại | Kết quả | Nguồn |
|---|---|---|---|
| Thermostat vs Q1 ở 37,5 °C | **Đo thật** 17/11 | MAE 0,121 so với 0,057 °C; Q1 đổi mức 88 lần/10 phút | [so_sanh_RL_THUC](../outputs/so_sanh_RL_THUC_20261117/KET_QUA.md) |
| Q2 (phạt đổi mức) ở 37,5 °C | **Đo thật** 20/11 | 93,8 % trong 37,3–37,7 °C, MAE 0,109 °C, **11** lần đổi mức | [rl_du_lieu_moi_v2](../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md) |
| Q2 dịch mốc, 3 giai đoạn, đổi ngày | **Mô phỏng** | ~99 % trong vùng so với thermostat ~89 %; vào vùng mới sau 9–26 s | [mo_phong_ba_giai_doan](../outputs/mo_phong_ba_giai_doan/KET_QUA.md) |
| Mốc 37,8 và 37,2 °C trên hộp thật | **Chưa đo** | — | Xem KIEM_THU_TICH_HOP.md |

## 6. Kiểm thử

```bash
python -m unittest test_ap_trung test_cloud_bridge test_kiem_tra_dht11     # Code_HopAp_Demo
python -m unittest test_phan_tich_ap_trung                                  # Code_HopAp_PhanTich (Anaconda)
node --test tests/logic.test.mjs                                            # App_HopAp
```
