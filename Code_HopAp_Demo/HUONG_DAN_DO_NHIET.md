# Đo nhiệt độ hộp khi thay đổi bóng và quạt

[do_nhiet_hop.py](do_nhiet_hop.py) dùng **DS18B20 và hai MOSFET cho bóng/quạt 12 V**. Không dùng cấu hình quạt 5 V + S8050 trong hướng dẫn này. Kết quả hiện trên **OLED SSD1306 I²C**, Terminal và lưu CSV; không cần LED rời. Giữ file [oled_hop_ap.py](oled_hop_ap.py) cùng thư mục chương trình chính. Đây là công cụ khảo sát đáp ứng để thiết kế mô hình và RL, chưa phải bộ điều nhiệt hoặc chương trình huấn luyện Q-table.

Muốn chương trình **tự đổi mức, đo dốc nhiệt rồi thử các hệ số reward**, dùng [khao_sat_nhiet.py](khao_sat_nhiet.py) theo [hướng dẫn khảo sát RL](HUONG_DAN_KHAO_SAT_RL.md). Các chế độ thủ công bên dưới vẫn dùng được.

## 1. Nối DS18B20 và trả PWM về đúng GPIO

Rút adapter 12 V, tắt Pi bằng `sudo poweroff` trong phiên SSH rồi ngắt USB-C trước khi thay dây. Nếu trước đó thử MOSFET bằng cách nối PWM vào nguồn 3,3 V/chân 1, **tháo kết nối thử đó**. Phần mềm không tắt được tải nếu PWM vẫn nối cố định vào nguồn 3,3 V.

| Linh kiện/chân | Nối tới Pi 4 |
|---|---|
| DS18B20 VDD | 3,3 V, chân vật lý 1 hoặc 17 |
| DS18B20 GND | GND, ví dụ chân vật lý 9 |
| DS18B20 DQ/DATA | GPIO4/BCM4, **chân vật lý 7** |
| Điện trở 4,7 kΩ | Giữa DQ và 3,3 V; không nối tiếp dây DATA |
| PWM MOSFET quạt | GPIO18/BCM18, **chân vật lý 12** |
| GND tín hiệu MOSFET quạt | GND Pi, ví dụ chân vật lý 6 |
| PWM MOSFET bóng | GPIO23/BCM23, **chân vật lý 16** |
| GND tín hiệu MOSFET bóng | GND Pi, ví dụ chân vật lý 14 |

DS18B20 rời: đối chiếu sơ đồ chân và góc nhìn của đúng cảm biến. Đầu dò chống nước: đối chiếu mô tả nhà bán, **không xác định chân chỉ bằng màu dây**. Nếu module DS18B20 đã có trở kéo lên thì kiểm tra trước khi gắn thêm.

Phía tải: quạt dương vào WAGO +12 V, quạt âm vào LOAD module quạt; bóng một đầu vào +12 V (qua KSD301 NC nếu có), đầu kia vào LOAD module bóng. Cọc `+` mỗi module vào +12 V; cọc `−` vào WAGO 0 V. GND Pi vào **GND tín hiệu** của module cách ly quang như sơ đồ đã thống nhất; không tự nối thêm sang cọc nguồn `−`. Pi dùng USB-C riêng. Không đưa 12 V vào Pi/cảm biến.

Đầu dò đặt cố định ở vị trí khảo sát trong hộp, không chạm bóng/thành hộp và tránh nhận bức xạ trực tiếp từ bóng. Số đo chỉ đại diện tại đầu dò, chưa chứng minh mọi vị trí trong hộp đều nhiệt.

### Nối qua breadboard

Trên breadboard tiêu chuẩn, năm lỗ a–e cùng một số thông nhau, nhưng không thông với f–j ở bên kia rãnh giữa. Các số khác nhau là các nhóm riêng. Ví dụ a10 và e10 thông nhau; a10 và a11 không thông nhau. Các thanh nguồn dài có thể bị chia đoạn; cách dưới đây dùng nhóm a–e ở giữa nên không phụ thuộc thanh nguồn.

Tạo ba nhóm riêng: nhóm GND, nhóm DATA, nhóm 3,3 V. Đưa GND của cảm biến và GND Pi/chân 9 vào nhóm GND; DQ của cảm biến và GPIO4/chân 7 vào nhóm DATA; VDD của cảm biến và 3,3 V Pi/chân 1 vào nhóm 3,3 V. Hai chân trở 4,7 kΩ nối nhóm DATA với nhóm 3,3 V. Trở không phân cực; không cắm hai chân trở vào hai lỗ vốn cùng thông nhau.

Với đầu dò có ba dây rời đã xác định đúng chức năng, có thể bố trí cụ thể:

| Nhóm | Dây cảm biến | Dây từ Pi | Điện trở |
|---|---|---|---|
| Hàng 10, a–e | GND vào a10 | GND/chân 9 vào e10 | Không có |
| Hàng 15, a–e | DQ vào a15 | GPIO4/chân 7 vào e15 | Một chân vào c15 |
| Hàng 20, a–e | VDD vào a20 | 3,3 V/chân 1 vào e20 | Chân còn lại vào c20 |

Dây Pi–breadboard dùng Dupont cái–đực: đầu cái cắm chân Pi, đầu đực cắm breadboard. Đầu dây cảm biến phải tiếp xúc chắc, không để dây nhiều sợi xòe chạm hàng bên cạnh; dùng đầu nối/đầu chân phù hợp nếu dây trần không cắm chắc.

Nếu cảm biến là loại đen TO-92 ba chân, ba chân phải cắm vào **ba nhóm số khác nhau**. Không ép ba chân vào a10, b10, c10 vì ba lỗ đó thông nhau. Chọn các hàng gần nhau cho cảm biến rồi dùng dây nối ngắn tới ba nhóm GND/DATA/3,3 V ở bảng trên; không cố banh chân cảm biến tới hàng 10–15–20. Với mặt phẳng cảm biến hướng về người nhìn và chân hướng xuống, chân trái GND, giữa DQ, phải VDD; đối chiếu đúng DS18B20 trước khi cấp nguồn.

Giữ breadboard trong nhánh tín hiệu/nguồn 3,3 V; dây dòng tải bóng và quạt vẫn dùng WAGO/module theo sơ đồ. Chưa đưa 12 V lên breadboard đang nối Pi. Sau khi kiểm tra dây, cấp lại USB-C cho Pi và chạy chế độ `doc` khi adapter 12 V vẫn rút.

### Nối màn OLED SSD1306 I²C bốn chân

Ngắt nguồn trước khi đổi dây. Dùng bốn dây Dupont cái–cái nếu cả OLED và Pi đều có chân đực đã hàn. Đọc **chữ in trên module**, không suy thứ tự chân theo hình của sản phẩm khác:

| OLED | Raspberry Pi 4 |
|---|---|
| VCC | 3,3 V — **mạch đang lắp (21/11): qua hàng 3,3 V của breadboard (chân 1)**; bản gốc ghi chân 17 |
| GND | GND — **mạch đang lắp: qua hàng GND của breadboard (chân 9)**; bản gốc ghi chân 20 |
| SDA | GPIO2/SDA1, **chân vật lý 3** |
| SCL | GPIO3/SCL1, **chân vật lý 5** |

Sơ đồ chân hiện hành xem [README.md](README.md): chân 17 và 20 nay dành cho DHT11. Cách này để riêng chân 1/7/9 cho DS18B20, chân 12/16 cho hai PWM. Chân 20 là GND chung bên trong Pi, không phải chân GPIO20. OLED dùng nguồn 3,3 V phù hợp module đã chọn; không cấp 12 V, không kéo SDA/SCL lên 5 V. Đặt màn ngoài hộp.

Mặc định cấu hình **SSD1306 128×64, I²C-1**; tự thử địa chỉ 0x3C rồi 0x3D. Nếu màn thực tế là SH1106/SPI hoặc loại khác, phải đổi driver phù hợp; việc cùng địa chỉ không xác nhận cùng chip. Với SSD1306 128×32, thêm `--oled-cao 32` khi chạy.

## 2. Chép chương trình — Terminal laptop Windows

Khi dấu nhắc là `D:\BTL_Nhom13>` hoặc `PS ...>`, chạy:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
ssh pi@pi
```

Nhập mật khẩu khi được hỏi. Khi dấu nhắc là `pi@pi:~ $`, bạn đã vào **Pi**; không chạy lệnh chứa ổ `D:\...` ở đây.

## 3. Bật 1-Wire, I²C và cài thư viện — Terminal Pi

Chỉ cấp USB-C cho Pi; giữ adapter 12 V đang rút.

```bash
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio python3-luma.oled i2c-tools
sudo raspi-config
```

Trong **Interface Options**, bật cả **1-Wire → Yes** và **I2C → Yes**, sau đó **Finish**, rồi:

```bash
sudo reboot
```

SSH đóng là bình thường. Đợi Pi khởi động xong, kết nối lại bằng `ssh pi@pi` trên laptop. Trên Pi kiểm tra:

```bash
ls /sys/bus/w1/devices/
```

Phải có thư mục `28-xxxxxxxxxxxx`. Nếu chưa có: kiểm tra dây, nguồn, trở 4,7 kΩ, 1-Wire và GPIO4/chân 7; chưa bật tải. Nếu bus 1-Wire đã được cấu hình trên GPIO khác, phải nối theo cấu hình hoặc sửa cấu hình bus; chương trình không tự đổi chân bus.

Kiểm tra địa chỉ OLED khi adapter 12 V vẫn rút:

```bash
i2cdetect -y 1
```

Màn thường xuất hiện ở `3c` hoặc `3d`. Nếu không thấy thì kiểm tra nguồn, bốn dây, mối hàn chân và I²C đã bật. Nếu báo quyền truy cập, kiểm tra tài khoản có quyền dùng `/dev/i2c-1`/nhóm `i2c`. Không cần đổi GPIO PWM để dùng OLED.

### Thử riêng OLED trước, không cần DS18B20

Trên Pi, trong thư mục chương trình:

```bash
cd /home/pi/Code_HopAp_Demo
python3 oled_hop_ap.py --giay 10
```

Màn phải hiện `OLED TEST` và `T --.-- C`: đây là kiểm tra hiển thị, không phải số đo nhiệt. Chương trình này không đọc DS18B20, không khởi tạo GPIO tải và không tạo CSV. Giữ adapter 12 V đang rút khi thử màn. Nếu muốn chỉ định địa chỉ:

```bash
python3 oled_hop_ap.py --dia-chi 0x3d --giay 10
```

## 4. Chỉ đọc nhiệt độ trước

Giữ adapter 12 V đang rút:

```bash
cd /home/pi/Code_HopAp_Demo
python3 do_nhiet_hop.py doc --giay 30
```

`doc` không khởi tạo GPIO điều khiển tải và không tự gửi lệnh bật/tắt tải; **OLED vẫn được cập nhật qua I²C**. Trong CSV, duty để trống và `gpio_control=0`. Không dùng nhiệt độ CPU Pi thay nhiệt độ hộp. Thiếu/lỗi cảm biến sẽ báo lỗi, không tạo số đo giả.

OLED bật mặc định trong mọi chế độ đo. Ví dụ bố cục minh họa trên màn 128×64, không phải dữ liệu đã đo của hộp:

```text
T 37.50 C
H:35% F:75%
MANUAL 120s
RUN
```

`H` là duty bóng được gửi; `F` là duty quạt được gửi, không phải W/RPM thực. Chế độ chỉ đọc hiện `H:-- F:--`. Trạng thái gồm `WAIT SENSOR`, `FAN START`, `RUN`, `SENSOR ERROR`, `SENSOR STALE`, `OVER TEMP`, `FAN POSTRUN`. Nếu số đo cũ quá 3 giây, màn bỏ giá trị nhiệt và hiện `--.--` thay vì giữ số cũ như số đo mới. Số chữ trên màn dùng ASCII để tránh thiếu font tiếng Việt.

OLED chạy ở luồng riêng; lỗi thư viện/không có màn/lỗi I²C sẽ báo trên Terminal rồi tiếp tục phần đo và CSV. I²C chậm/treo không được chờ trên vòng điều khiển nhiệt. Nếu OLED ngừng cập nhật, xem Terminal; không coi một ảnh cũ còn trên màn là số đo hiện tại. Khi kết thúc, driver thường xóa/tắt màn. Dùng các tùy chọn sau khi cần:

```bash
python3 do_nhiet_hop.py doc --giay 30 --oled-dia-chi 0x3c
python3 do_nhiet_hop.py doc --giay 30 --oled-cao 32
python3 do_nhiet_hop.py doc --giay 30 --khong-oled
```

Nếu có nhiều đầu dò, chọn đúng mã đầu dò hộp; thay mã mẫu bằng mã thật:

```bash
python3 do_nhiet_hop.py doc --sensor 28-0123456789ab --giay 30
```

## 5. Đặt mức cố định, ghi nhiệt độ

Chỉ thử sau khi cả hai MOSFET bật/tắt đúng và cảm biến đọc hợp lệ. Không chạy đồng thời chương trình khác điều khiển GPIO18/23. Dùng hộp rỗng có bóng gắn chắc, chắn nhiệt và cách xốp; theo dõi trực tiếp. Giữ bộ ngắt nhiệt đang có. Nguồn quạt đi qua module tải 12 V, không lấy từ chân nguồn 3,3 V.

Cắm adapter 12 V sau khi kiểm tra dây, thử quạt trước:

```bash
python3 do_nhiet_hop.py giu --bong 0 --quat 100 --giay 10
```

Xác nhận quạt quay, thử sưởi thấp:

```bash
python3 do_nhiet_hop.py giu --bong 25 --quat 100 --giay 60
```

Ví dụ lượt đo 120 giây, chỉ dùng quạt 75% sau khi đã kiểm tra mức đó quay ổn định:

```bash
python3 do_nhiet_hop.py giu --bong 35 --quat 75 --giay 120
```

**35% là duty PWM, không xác nhận công suất bóng bằng 35% × 21 W. Quạt 75% PWM cũng không xác nhận 75% RPM.** Quạt hai dây có mạch điện tử riêng; cần kiểm tra khả năng điều tốc và tần số phù hợp. Mặc định 100 Hz là cấu hình thử, có thể đổi bằng `--tan-so-quat` dựa vào đặc tính quạt. Nếu quạt đứng/giật, tắt bóng và dừng thử; log không phát hiện được quạt kẹt hoặc mất gió.

Khi bắt đầu từ quạt tắt, chương trình gửi quạt 100% trong 1 giây và giữ bóng tắt, rồi áp dụng mức yêu cầu. CSV ghi riêng duty yêu cầu và duty gửi để nhận biết đoạn này. Xung khởi động không chứng minh quạt thực sự đã quay.

## 6. Thay mức khi đang đo

```bash
python3 do_nhiet_hop.py tay --giay 600
```

Ban đầu cả hai đầu ra được yêu cầu tắt. Gõ từng lệnh và bấm Enter; dòng nhiệt vẫn hiện trong lúc bạn nhập:

```text
dat 0 100
dat 25 100
bong 35
quat 75
bong 0
tat
thoat
```

| Lệnh | Ý nghĩa |
|---|---|
| `dat B Q` | Đặt duty bóng B% và quạt Q% |
| `bong B` | Đổi bóng, giữ mức quạt yêu cầu |
| `quat Q` | Đổi quạt, giữ mức bóng yêu cầu |
| `tat` | Gửi lệnh tắt cả hai nhưng tiếp tục đo |
| `thoat` | Kết thúc lượt đo |
| `help` | Nhắc cú pháp |

Giá trị từ 0 đến 100, dùng dấu chấm cho số thập phân. Công cụ thử hộp này không nhận bật bóng khi yêu cầu quạt 0%; muốn tắt quạt thì tắt bóng trước hoặc dùng `tat`.

Nếu chạy trực tiếp từ Terminal laptop, dùng `-t` để nhập lệnh:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/do_nhiet_hop.py tay --giay 600"
```

## 7. Chạy kịch bản CSV

[kich_ban_do_nhiet.csv](kich_ban_do_nhiet.csv) có 5 bước, tổng 450 giây, sưởi tối đa 35%. Chỉ chạy sau khi quạt 75% đã được kiểm tra ổn định:

```bash
python3 do_nhiet_hop.py kich-ban --tep kich_ban_do_nhiet.csv --dry-run
python3 do_nhiet_hop.py kich-ban --tep kich_ban_do_nhiet.csv
```

Tiêu đề kịch bản là `ten,giay,bong_pct,quat_pct`. Toàn bộ file được kiểm tra trước khi khởi tạo GPIO. Tổng thời gian tối đa 600 giây, chưa tính 10 giây giữ quạt cuối nếu có sưởi.

**Kịch bản chỉ tạo một chuỗi kích thích để đo đáp ứng.** Không so trực tiếp nhiệt cuối hai bước để kết luận mức quạt nào tốt hơn: nhiệt ban đầu và nhiệt tích trong thành khác nhau. Khi so sánh, lặp lại điều kiện từ nhiệt ban đầu gần nhau, giữ nguyên vị trí cảm biến, nắp hộp và điều kiện phòng. Ghi chú lần mở nắp/di chuyển đầu dò; không trình bày tác động tay như đáp ứng tự nhiên của hộp.

## 8. CSV và cách dừng

Mỗi lượt tạo file mới trong `/home/pi/Code_HopAp_Demo/logs/`, đường dẫn được in đầu phiên. CSV dùng UTF-8 BOM để Excel đọc tiếng Việt. `--csv TEN_FILE.csv` chọn tên khác và từ chối ghi đè file có sẵn.

- `timestamp_utc`, `elapsed_s`: thời điểm UTC và giây từ lúc bắt đầu log, bao gồm đoạn chờ cảm biến.
- `event`, `phase`: số đo `MEASUREMENT`, lệnh đổi mức `COMMAND`, kết thúc xung khởi động `OUTPUT_CHANGE`, lỗi và kết thúc.
- `temperature_c`, `temperature_age_s`, `sensor_id`: số đo đã qua CRC, tuổi số đo tại lúc ghi và mã đầu dò. **Chỉ dòng MEASUREMENT là mẫu nhiệt mới**; dòng sự kiện có thể nhắc lại số đo gần nhất.
- `gpio_control`, các cột `*_requested_pct`, `*_command_pct`: có điều khiển GPIO hay không, duty yêu cầu và duty được gửi tại lúc ghi. Không phải đo điện áp/công suất/RPM.
- `fan_pwm_hz`, `cutoff_c`, `note`: tần số, ngưỡng dừng và ghi chú; để trống khi không áp dụng.
- `trend_c_per_min`: dốc nhiệt OLS trên tối đa 30 giây gần nhất, cần ít nhất 10 giây/5 mẫu; để trống nếu chưa đủ. Dốc không phải số đo độc lập bổ sung hoặc bằng chứng quạt làm lạnh.

Nhấn **Ctrl+C** để dừng. Lỗi CRC/đọc hoặc quá 3 giây không có số đo mới sẽ dừng điều khiển; không dùng nhiệt cũ để tiếp tục sưởi. Khi đạt `--ngat-nhiet` (mặc định **40°C**, cho phép hạ thấp), dừng lượt thử, không tự bật lại khi nguội. Khi đã có sưởi, cố gửi lệnh tắt bóng, giữ quạt 100% thêm 10 giây rồi tắt cả hai và đóng GPIO.

EOF và SIGHUP từ phiên SSH được xử lý, nhưng không coi rút mạng là cách dừng chắc chắn. Nếu mất kết nối mà chưa biết tải đã tắt chưa, rút adapter 12 V.

40°C chỉ là ngưỡng dừng khảo sát **hộp rỗng**, không bảo vệ trứng/xốp/mặt bóng. Một đầu dò không phát hiện hết điểm nóng. Pi treo, mất điện, `kill -9`, MOSFET chập hoặc PWM nối cố định vào 3,3 V có thể làm tắt bằng phần mềm mất tác dụng. Không thay bộ ngắt phần cứng; nếu tải không tắt, **rút adapter 12 V**.

Từ **Terminal laptop**, chép log về:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/logs "D:\BTL_Nhom13\Du_lieu_do_hop"
```

## Nguồn đối chiếu

- [DS18B20 — Analog Devices](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf): nguồn, chân, trở kéo lên, độ chính xác và giá trị khởi động 85°C.
- [Linux w1_therm](https://docs.kernel.org/w1/slaves/w1_therm.html): `w1_slave`, CRC và `t=`.
- [Raspberry Pi: bật 1-Wire](https://www.raspberrypi.com/documentation/computers/configuration.html#enable-or-disable-the-one-wire-interface).
- [GPIO Zero: PWMOutputDevice](https://gpiozero.readthedocs.io/en/stable/api_output.html#pwmoutputdevice).
- [Adafruit: cấu tạo breadboard](https://learn.adafruit.com/breadboards-for-beginners/breadboards).
- [Adafruit: chân DS18B20 và trở kéo lên](https://learn.adafruit.com/using-ds18b20-temperature-sensor-with-circuitpython/hardware).
- [Luma.OLED: SSD1306 qua I²C và hiển thị ảnh/chữ](https://luma-oled.readthedocs.io/en/latest/python-usage.html).
- [Debian: gói python3-luma.oled](https://packages.debian.org/bookworm/python3-luma.oled).
- [Raspberry Pi: sơ đồ chân GPIO](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio).
