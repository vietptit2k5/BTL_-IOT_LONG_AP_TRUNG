> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Thử mạch hộp ấp khi chưa lắp cảm biến

**Nếu đang lắp sơ đồ cũ với cả quạt và bóng 12 V qua hai MOSFET:** dùng [README_12V.md](README_12V.md) và chạy `thu_mach_12v.py`. File này chọn sẵn cấu hình `12v-mosfet`; cần giữ cùng thư mục với `thu_mach.py`. Hướng dẫn quạt 5 V + S8050 dưới đây dành cho cấu hình đã chọn trước đó.

Chuỗi lệnh đầy đủ từ SSH đến chạy thử: [TU_SSH_DEN_CHAY_THU_12V.md](TU_SSH_DEN_CHAY_THU_12V.md).

Với sơ đồ hai MOSFET 12 V, muốn bật cả hai tải 100% cùng trong 3 giây mà không hỏi `y/n`, dùng [chay_ca_mach_12v.py](../chay_ca_mach_12v.py), theo [hướng dẫn chạy đồng thời](README_12V.md#chạy-quạt-và-bóng-cùng-lúc-không-hỏi-yn).

Để **đo DS18B20, hiển thị OLED, điều khiển mức PWM cả bóng và quạt, ghi CSV**, dùng [do_nhiet_hop.py](../do_nhiet_hop.py) và [hướng dẫn đo nhiệt](../HUONG_DAN_DO_NHIET.md). Công cụ này dành cho cấu hình hai MOSFET/quạt 12 V, có chế độ chỉ đọc và chế độ thay mức trong lúc đo. OLED SSD1306 I²C bật mặc định; giữ [oled_hop_ap.py](../oled_hop_ap.py) cùng thư mục và cài `python3-luma.oled` trên Pi. Dùng `--khong-oled` nếu chỉ cần Terminal/CSV.

**Tự khảo sát tăng/giảm nhiệt rồi thử reward:** chạy `python3 khao_sat_nhiet.py do`, xem [HUONG_DAN_KHAO_SAT_RL.md](../HUONG_DAN_KHAO_SAT_RL.md). Mặc định bóng 0/25/50/75/100%, quạt 75/100%, 120 giây/tổ hợp, lặp hai lần; lịch khoảng 43–46 phút và giới hạn cả lượt 90 phút. Có thể đổi bằng `--moi-to-hop`/`--lap`/`--gioi-han-phut`. Thử hệ số/Q-learning chỉ chạy offline sau khi tải được yêu cầu tắt; action chưa đủ cửa sổ đo liên tục không tự được đưa vào Q-table. Không tự triển khai RL lên GPIO.

**Cấu hình cập nhật 15/11/2026:** Raspberry Pi 4; bóng sợi đốt 12 V–21 W qua **một module MOSFET AOD4184/D4184 kích mức cao 3,3 V**; dùng lại **quạt 5 V + S8050 + điện trở base + diode** của bài giữa kỳ. Sơ đồ mới ở [SO_DO_NOI_DAY.md](SO_DO_NOI_DAY_quat_5V_cu.md).

Chương trình `thu_mach.py` không cần DS18B20, LED hay OLED. Đây là phép thử bật/tắt và PWM bóng, chưa phải chương trình điều nhiệt hoặc huấn luyện RL. Nhánh quạt hiện thử bật/tắt 100% qua S8050; chưa thử PWM tốc độ thấp.

## 1. Chân điều khiển

| Pi (số BCM) | Chân vật lý | Nối tới |
|---|---:|---|
| GPIO23 | 16 | `PWM` tín hiệu module bóng |
| GND | 14, ví dụ | `GND` tín hiệu module bóng |
| GPIO18 | 12 | Qua điện trở base của mạch giữa kỳ (tài liệu cũ dùng 1 kΩ) tới chân `B` S8050 |
| GND | 20, ví dụ | Chân `E` S8050 và cực âm nguồn 5 V của quạt |

Các chân GND trên Pi nối chung bên trong; dùng chân GND khác vẫn được. Quạt dương nhận **5 V**, quạt âm nối `C` S8050; chân `E` về GND. Giữ nguyên mạch quạt giữa kỳ đã hoạt động, gồm điện trở base và diode 1N4007. Cần xác nhận dòng ghi trên tem quạt và nguồn 5 V cũ trước khi quyết định lấy nguồn từ Pi hay nguồn 5 V rời.

Module MOSFET còn lại chỉ điều khiển bóng: `+` tới WAGO +12 V, `−` tới WAGO 0 V và `LOAD` tới dây còn lại của đui bóng. KSD301 NC nối tiếp dây dương bóng. WAGO +12 V dùng 3 cổng; WAGO 0 V dùng 2 cổng. Không nối nhánh quạt 5 V vào các WAGO nguồn 12 V. Pi dùng USB-C riêng. Dây tải bóng dùng dây nguồn 0,75 mm²; Dupont dùng phía tín hiệu. Với module bóng cách ly quang, GND Pi nối `GND` tín hiệu module; không chủ động nối sang WAGO 0 V của tải 12 V.

## 2. Cài trên Pi

Chép cả thư mục `Code_HopAp_Demo` sang Pi, ví dụ vào thư mục cá nhân. Mở Terminal **trên Pi**, rồi chạy:

```bash
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio
cd ~/Code_HopAp_Demo
```

Nếu chép vào vị trí khác, thay đường dẫn `cd` cho đúng. Dùng `python3` hệ thống đã cài bằng apt. Chương trình dùng `LGPIOFactory(chip=0)` cho Pi 4 và không tự chuyển sang backend giả hoặc điều khiển Pi từ xa.

## 3. Thử theo thứ tự

Mở nắp hộp, chưa đặt trứng hoặc vật dễ cháy gần bóng. Dừng các chương trình cũ đang dùng GPIO18/GPIO23. Trước khi sửa dây, ngắt cả adapter 12 V và nguồn 5 V/USB-C liên quan. Bóng, đui và giá chịu nhiệt phải được gắn chắc, tách khỏi xốp. Quạt 5 V phải được đấu đúng trước khi cấp USB-C cho Pi nếu lấy nguồn từ Pi.

1. Cấp USB-C cho Pi, gửi lệnh tắt khi chưa cắm adapter 12 V:

   ```bash
   python3 thu_mach.py tat
   ```

   Nếu quạt lấy 5 V từ Pi, nó đã có nguồn khi cắm USB-C nhưng phải còn tắt khi S8050 được điều khiển tắt. Sau đó cắm adapter 12 V; bóng phải còn tắt. Nếu tải tự bật, ngắt nguồn của tải đó rồi kiểm tra dây và trạng thái mặc định trước khi thử tiếp.

2. Thử riêng quạt ở 100% trong 5 giây:

   ```bash
   python3 thu_mach.py quat --giay 5
   ```

   Quạt phải quay rồi tắt. Chương trình chưa thử PWM tốc độ thấp của quạt hai dây.

3. Thử riêng bóng ở 100% trong 2 giây:

   ```bash
   python3 thu_mach.py den --giay 2
   ```

   Sau 2 giây chương trình tắt bóng, bật quạt thêm 5 giây rồi tắt quạt. Đây chỉ là thao tác thổi khí sau khi thử, không xác nhận bóng/hộp đã nguội.

4. So sánh PWM bóng ở hai mức, mỗi lần 2 giây:

   ```bash
   python3 thu_mach.py den --muc 25 --giay 2
   python3 thu_mach.py den --muc 100 --giay 2
   ```

   `--muc` là tỷ lệ thời gian bật PWM ở 100 Hz, không phải phần trăm độ sáng đo được. Quạt vẫn được bật thêm 5 giây sau mỗi lần thử bóng.

5. Khi từng nhánh đã đúng, thử đồng thời bóng 50% và quạt 100% trong 3 giây:

   ```bash
   python3 thu_mach.py ca-hai --muc 50 --giay 3
   ```

6. Có thể chạy một chuỗi tự động khoảng **22 giây**, chỉ một lượt:

   ```bash
   python3 thu_mach.py tu-dong
   ```

   Chuỗi gồm trạng thái tắt, thử quạt, thử bóng 25/50/100%, thử hai tải đồng thời, tắt bóng và giữ quạt thêm, rồi tắt hết. Tổng các bước có cấp PWM bóng là 6 giây. Không chạy lặp liên tục khi chưa có cảm biến.

Nhấn **Ctrl+C** để dừng sớm; chương trình gửi lệnh tắt bóng và quạt. Kiểm tra cả hai tải đã tắt, rồi rút adapter 12 V sau buổi thử. Lệnh mặc định `python3 thu_mach.py` cũng chỉ gửi lệnh tắt. Nếu cần tháo dây GPIO hoặc nguồn quạt lấy từ Pi, tắt Pi đúng cách và rút USB-C trước khi thao tác.

## 4. Giới hạn và lỗi thường gặp

- Mỗi bước có bật bóng giới hạn **5 giây**; thử riêng quạt giới hạn **10 giây**. Chương trình từ chối thời gian âm, bằng 0, quá giới hạn, `NaN` hoặc vô hạn. Một lượt chạy có giới hạn chờ 45 giây.
- Dòng in trên Terminal là **lệnh đã gửi**, không phải phép đo xác nhận tải đang hoạt động. Chương trình không đọc nhiệt độ, không xác nhận trạng thái KSD và không biết quạt có kẹt hay bóng có chập hay không.
- Chương trình cố tắt cả hai tải khi hết lượt, Ctrl+C, SIGTERM hoặc lỗi xử lý được; kể cả khi khởi tạo mới được một GPIO. Phần mềm không bảo đảm ngắt tải khi Pi treo, mất điện, bị `kill -9`, hoặc linh kiện đóng cắt hỏng. Nếu bóng không tắt, ngắt adapter 12 V; nếu quạt không tắt, ngắt nguồn 5 V của quạt (USB-C nếu lấy từ Pi).
- Nếu báo thiếu `gpiozero`/`lgpio`, chạy lại lệnh apt ở trên và dùng Python hệ thống, tránh môi trường ảo chưa có các gói này.
- Nếu báo GPIO đang được sử dụng, dừng chương trình khác chiếm GPIO18/GPIO23; không chạy hai bản thử cùng lúc. Nếu lỗi quyền truy cập `/dev/gpiochip0`, kiểm tra quyền GPIO của tài khoản trên Raspberry Pi OS.
- Nếu có lệnh bật mà bóng không sáng: rút nguồn, kiểm tra nhánh `+12 V → KSD NC → bóng → LOAD`, nguồn `+/−` của module, dây `PWM/GND` tín hiệu và KSD có đang mở hay không. Không nối tắt KSD để thử.
- Nếu quạt không quay hoặc S8050 nóng: ngắt nguồn, kiểm tra lại nguồn 5 V, dòng quạt, chân E/B/C theo đúng linh kiện, điện trở base và diode. Không giảm điện trở base tùy ý để tăng dòng GPIO. Sơ đồ tái sử dụng mạch giữa kỳ không phải bảo đảm cho mọi quạt 5 V.
- Các file `thu_mach.py`/`thu_mach_12v.py` chỉ thử tải, chưa điều khiển OLED. Muốn hiển thị nhiệt và mức bóng–quạt lên OLED, dùng `do_nhiet_hop.py` theo hướng dẫn đo nhiệt ở đầu file.

## 5. Xem kế hoạch trên laptop

```bash
python3 thu_mach.py tu-dong --dry-run
```

Chế độ này không cần thư viện GPIO, không chờ theo thời gian thực và không bật tải. Nó chỉ kiểm tra luồng lệnh; không thay thế thử thực tế trên Pi.

Tham khảo API chính thức: [PWMOutputDevice](https://gpiozero.readthedocs.io/en/stable/api_output.html#pwmoutputdevice), [LGPIOFactory và cách chọn backend](https://gpiozero.readthedocs.io/en/stable/api_pins.html#lgpio).

## 6. Bước tiếp theo cho mạch hai MOSFET 12 V đã khảo sát

Xem [HUONG_DAN_BUOC_TIEP_THEO.md](HUONG_DAN_BUOC_TIEP_THEO.md). Có bộ so Q-learning/Expected SARSA offline và chương trình đo giữ nhiệt độc lập, giữ ngắt mềm 38→37°C, dừng cứng 40°C và bảo vệ mất cảm biến. Chương trình này áp dụng quạt 12 V qua MOSFET, không áp dụng nguyên trạng nhánh quạt 5 V/S8050 ở các phần cũ phía trên.

Sau lượt thermostat đạt điều kiện kiểm tra, xem [HUONG_DAN_THU_RL.md](HUONG_DAN_THU_RL.md) để thử Q-table cố định có giám sát trên hộp rỗng trong 600 giây. Chế độ `thu-rl` kiểm tra đúng đầu dò, lịch sử PWM và trạng thái đã học; không cập nhật Q online.
