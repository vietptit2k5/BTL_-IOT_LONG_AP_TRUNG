> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Chạy sơ đồ cũ: bóng 12 V và quạt 12 V qua hai MOSFET

**Đo nhiệt độ, hiển thị OLED và thay đổi mức bóng/quạt:** xem [HUONG_DAN_DO_NHIET.md](../HUONG_DAN_DO_NHIET.md), chạy [do_nhiet_hop.py](../do_nhiet_hop.py). Công cụ này dùng DS18B20, PWM cả hai kênh, OLED SSD1306 I²C bật mặc định và lưu CSV. Giữ [oled_hop_ap.py](../oled_hop_ap.py) cùng thư mục; bắt đầu kiểm tra cảm biến/màn khi adapter 12 V đang rút.

**Khảo sát tự động và hiệu chỉnh reward từ dữ liệu:** [khao_sat_nhiet.py](../khao_sat_nhiet.py), theo [hướng dẫn khảo sát RL](../HUONG_DAN_KHAO_SAT_RL.md). Mặc định bóng **0/25/50/75/100%**, quạt **75/100%**, **120 giây/tổ hợp, lặp hai lần**. Khoảng 43–46 phút danh định, giới hạn cả lượt 90 phút gồm chờ hạ nhiệt. Đoạn bị ngắt được ghi là chưa đủ quan sát liên tục; các chế độ thử thủ công vẫn giới hạn 10 phút.

**16/11/2026 — theo sơ đồ người dùng vừa gửi.** Hướng dẫn này chỉ dành cho quạt ghi 12 V và bóng sợi đốt 12 V–21 W. Mỗi tải dùng một module AOD4184/D4184 có đầu vào `PWM/GND` nhận 3,3 V, kích mức cao. Pi lấy nguồn USB-C riêng. Không cần cảm biến, OLED hoặc LED để chạy phép thử ngắn này.

**Toàn bộ lệnh từ laptop tới Pi:** xem [TU_SSH_DEN_CHAY_THU_12V.md](TU_SSH_DEN_CHAY_THU_12V.md). Có thể dùng `chay_tu_laptop_12v.ps1` trên laptop hoặc `chay_thu_12v.sh` trong phiên SSH.

## Chạy quạt và bóng cùng lúc, không hỏi y/n

File [chay_ca_mach_12v.py](../chay_ca_mach_12v.py) mặc định gửi lệnh **bóng 100% và quạt 100% cùng trong 3 giây**, sau đó tắt bóng, giữ quạt thêm 5 giây rồi tắt hết. Có 1 giây đầu gửi lệnh tắt để khởi tạo. Cần giữ `thu_mach.py` trong cùng thư mục. Không cần cảm biến, OLED hoặc LED.

Trên Terminal laptop đang ở `D:\BTL_Nhom13`, cập nhật thư mục rồi chạy:

```powershell
scp -r .\Code_HopAp_Demo pi@pi:/home/pi/
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/chay_ca_mach_12v.py"
```

Nhập mật khẩu SSH/SCP khi được hỏi. Chương trình thử không hỏi `y/n`. Trước khi chạy, cấp USB-C cho Pi và cấp adapter 12 V cho tải đúng định mức, mở nắp và để hộp rỗng. GPIO23/chân 16 tới PWM module bóng; GPIO18/chân 12 tới PWM module quạt; GND tín hiệu từng module nối về GND Pi. Đầu ra được khởi tạo ở mức tắt.

Đổi sang 5 giây (giới hạn tối đa) hoặc chỉ xem mô phỏng:

```bash
python3 /home/pi/Code_HopAp_Demo/chay_ca_mach_12v.py --giay 5
python3 /home/pi/Code_HopAp_Demo/chay_ca_mach_12v.py --dry-run
```

Ctrl+C gửi lệnh tắt và giải phóng GPIO. Nếu Terminal đã hiện lệnh cả hai 100% mà tải vẫn đứng yên, cần kiểm tra nguồn/đấu dây/module; phần mềm không tự cấp nguồn 12 V và không đo được tải đã chạy. Rút adapter 12 V nếu tải không tắt theo lệnh.

## 1. Sửa cách đếm cổng trong hình

WAGO A cần **5 cổng tổng cộng**, gồm **1 đầu vào và 4 nhánh ra**. Chữ “4 cổng” trong hình chưa tính dây từ jack DC. Dùng WAGO 5 cổng đã mua:

| Cổng WAGO A (+12 V) | Dây |
|---|---|
| 1 | Jack DC + |
| 2 | MOSFET quạt + |
| 3 | Quạt + |
| 4 | Bóng +, qua KSD301 NC nếu đã lắp |
| 5 | MOSFET bóng + |

WAGO B dùng 3 cổng: jack DC −, MOSFET quạt − và MOSFET bóng −. Mỗi WAGO thông điện giữa các cổng của chính nó; không gộp hai cực nguồn hoặc đường LOAD vào một WAGO.

## 2. Các dây cần nối

```text
Adapter 12 V -> Jack DC
Jack DC + -> WAGO A +12 V
Jack DC - -> WAGO B 0 V

WAGO A -> Quạt +
Quạt - -> LOAD của MOSFET quạt
WAGO A -> MOSFET quạt +
WAGO B -> MOSFET quạt -

WAGO A -> KSD301 NC (nếu có) -> Bóng dây 1
Bóng dây 2 -> LOAD của MOSFET bóng
WAGO A -> MOSFET bóng +
WAGO B -> MOSFET bóng -

Pi GPIO18 / chân vật lý 12 -> PWM tín hiệu MOSFET quạt
Pi GND / ví dụ chân 20 -> GND tín hiệu MOSFET quạt
Pi GPIO23 / chân vật lý 16 -> PWM tín hiệu MOSFET bóng
Pi GND / ví dụ chân 14 -> GND tín hiệu MOSFET bóng
```

Thứ tự vị trí cọc thay đổi theo hướng xoay bo: theo chữ `+`, `LOAD`, `−`, `PWM`, `GND` in trên đúng bo thực nhận. Với module cách ly quang đã thống nhất, GND Pi đi tới GND tín hiệu; không chủ động nối chung với WAGO B phía tải. Nguồn 12 V không đi vào Pi hoặc GPIO.

Hình chưa thể hiện KSD301. Nếu KSD301 NC đã có trong mạch, giữ nó nối tiếp với bóng. Không nối tắt KSD khi thử. Đây là phép thử vài giây với hộp mở và rỗng; bóng/đui được cố định trên giá chịu nhiệt, tách khỏi xốp. Quạt cần được đấu bảo vệ tải cảm theo tài liệu đúng module/quạt.

## 3. Pi phải khởi động và đăng nhập được trước

Đèn đỏ nguồn sáng chưa xác nhận hệ điều hành đã chạy. Cần Pi khởi động từ thẻ nhớ và truy cập được Terminal/SSH. Nếu nối dây trực tiếp Pi–laptop mà Windows vẫn báo `Ethernet: Media disconnected`, phải xử lý liên kết LAN hoặc việc khởi động Pi trước khi chạy GPIO.

Khi sửa dây, ngắt cả adapter 12 V và USB-C. Có thể thử khởi động Pi riêng với thẻ nhớ và LAN trước, sau đó tắt Pi đúng cách, rút nguồn rồi nối lại GPIO.

## 4. Chép chương trình và chạy trên Pi

Chép thư mục `Code_HopAp_Demo` sang thư mục cá nhân trên Pi. **Giữ thu_mach_12v.py và thu_mach.py cùng thư mục**, vì file 12 V dùng lại bộ điều khiển trong file chính. Sau khi SSH vào Pi:

```bash
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio
cd ~/Code_HopAp_Demo
```

Ban đầu rút adapter 12 V, cấp USB-C cho Pi rồi gửi lệnh tắt:

```bash
python3 thu_mach_12v.py tat
```

Cắm adapter 12 V; bóng và quạt phải còn tắt. Sau đó thử lần lượt:

```bash
# Quạt bật 100% trong 5 giây rồi tắt.
python3 thu_mach_12v.py quat --giay 5

# Bóng bật 2 giây, sau đó tắt bóng và chạy quạt thêm 5 giây.
python3 thu_mach_12v.py den --giay 2

# Chỉ chạy sau khi từng nhánh đã đúng: bóng 50% và quạt 100% trong 3 giây.
python3 thu_mach_12v.py ca-hai --muc 50 --giay 3
```

Nhấn Ctrl+C để chương trình gửi lệnh tắt. Nếu tải không tắt, rút adapter 12 V cấp hai tải. Lần thử bóng giới hạn tối đa 5 giây; chưa chạy điều nhiệt trong hộp kín khi chưa có số đo nhiệt độ.

Chạy chuỗi khoảng 22 giây sau khi các lần thử riêng đã đúng:

```bash
python3 thu_mach_12v.py tu-dong
```

## 5. Kiểm tra trên laptop

```bash
python3 thu_mach_12v.py tu-dong --dry-run
```

`--dry-run` chỉ in kế hoạch, không làm quạt quay hoặc bóng sáng. Trong hai cấu hình, GPIO vẫn chỉ phát tín hiệu logic 3,3 V; việc chọn cấu hình phần mềm không thay đổi điện áp cấp cho tải.

## 6. Sau khi đã hoàn tất khảo sát nhiệt

Xem [hướng dẫn bước tiếp theo](HUONG_DAN_BUOC_TIEP_THEO.md): tối ưu RL offline qua nhiều seed và chạy lượt đối chứng giữ nhiệt 10 phút bằng `kiem_tra_giu_nhiet.py`. Bộ kiểm tra dùng DS18B20/OLED hiện có, bảo vệ mềm 38→37°C và dừng cứng 40°C; mặc định chạy thermostat đối chứng.

Sau khi đã kiểm tra lượt đối chứng, xem [hướng dẫn pilot RL](HUONG_DAN_THU_RL.md). Chế độ `thu-rl` dùng bảng Q cố định trong 600 giây, có bảo vệ độc lập và dừng khi gặp state chưa học; không tự học trên hộp.

Đã có hai lượt đo thực để so sánh; xem [kịch bản demo RL](KICH_BAN_DEMO_RL.md). Trong một cặp thử, RL giảm MAE 53,2% so với thermostat đã chọn, nhưng đổi mức PWM nhiều hơn; cần lặp ở các điều kiện khác trước khi suy rộng.

Nếu ưu tiên giữ mức bóng/quạt ổn định, xem [phép đo điểm làm việc cố định](HUONG_DAN_GIU_MUC_ON_DINH.md). Tùy chọn `--bat-dau-giu 37.5` chỉ dành cho `co-dinh`; không tự thay đổi chính sách RL đã đo.

Để so ảnh hưởng quạt tắt và quạt 75% lúc tăng nhiệt ban đầu, dùng [phép thử ngắn riêng](HUONG_DAN_THU_QUAT_0_VA_75.md). Công cụ giới hạn bóng 50%, sưởi 30 giây và ngắt ở 35°C; không mở quạt 0% cho RL hoặc chế độ giữ nhiệt cũ.
