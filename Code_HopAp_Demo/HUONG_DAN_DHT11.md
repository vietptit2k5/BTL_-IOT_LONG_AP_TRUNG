# Đọc thêm độ ẩm DHT11

## Nếu đèn module sáng mà không đọc được: bật driver DHT11 của kernel (khuyên dùng)

Đèn đỏ chỉ báo **có nguồn**. Thư viện Adafruit canh thời gian ngay trong Python nên hay báo "DHT sensor not found" trên Raspberry Pi OS mới, kể cả khi dây đúng. Driver có sẵn trong kernel ổn định hơn nhiều:

```bash
grep -n dht11 /boot/firmware/config.txt || echo "dtoverlay=dht11,gpiopin=17" | sudo tee -a /boot/firmware/config.txt
sudo reboot
# sau khi Pi khởi động lại:
cat /sys/bus/iio/devices/iio:device*/name                        # phải thấy dht11@...
cat /sys/bus/iio/devices/iio:device*/in_humidityrelative_input   # ví dụ 58000 = 58 %
```

(Bản Raspberry Pi OS cũ hơn dùng `/boot/config.txt` thay cho `/boot/firmware/config.txt`.) Thỉnh thoảng một lần `cat` báo `Connection timed out` hoặc `Input/output error` là bình thường, chương trình tự đọc lại. Lần nào cũng `timed out` thì kiểm tra dây DATA hoặc thay cảm biến.

`do_am.py`, `kiem_tra_dht11.py` và `--dht11` **tự dùng driver kernel khi đã bật**, không cần thư viện Adafruit nữa. Muốn ép một cách đọc: `--cach-doc kernel` hoặc `--cach-doc thu_vien`. Tắt driver: xóa dòng `dtoverlay=dht11,gpiopin=17` rồi khởi động lại.

## Cách dùng hiện hành (21/11/2026): chương trình `do_am.py`

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python kiem_tra_dht11.py        # 1) chẩn đoán dây/thư viện (30 s)
.venv/bin/python do_am.py                 # 2) đọc và hiển thị liên tục trên Terminal (Ctrl+C để dừng)
.venv/bin/python do_am.py --oled          #    thêm OLED (chỉ khi không có lượt điều khiển đang dùng OLED)
bash cai_dich_vu_do_am.sh                 # 3) chạy nền, tự khởi động cùng Pi; app luôn có độ ẩm
```

- GPIO17 chỉ cho **một** chương trình đọc tại một lúc. Khi dịch vụ `hop-ap-do-am` chạy, chương trình điều khiển lấy độ ẩm qua file (`ap_trung.py --do-am`; `chay_demo.sh` tự thêm), **không** dùng `--dht11`.
- Không có dịch vụ thì vẫn dùng được kiểu cũ: `ap_trung.py --dht11` (tự đọc GPIO17).
- Độ ẩm **chỉ để giám sát**, không vào Q-table. App so số đo với độ ẩm khuyến nghị của giai đoạn (60 / 55 / 65–70 %).

**Cách nối hiện hành (21/11):** VCC → lỗ **d10** (hàng 3,3 V trên breadboard), GND → lỗ **d18** (hàng GND), DATA → **chân 11** (GPIO17) nối thẳng. Dùng chung nguồn breadboard với DS18B20 và OLED (chân 1 và 9), nên không chiếm thêm chân nguồn nào của Pi. Không cắm DATA của DHT11 vào hàng 14: hàng đó là DATA của DS18B20 (GPIO4). Xem [README.md](README.md).

> **Sửa 21/11/2026:** bản cũ ghi VCC → chân 17 và GND → chân 14, trùng chân với OLED và MOSFET bóng. Dùng bảng dưới (khớp [README.md](README.md)). Chẩn đoán: `.venv/bin/python kiem_tra_dht11.py`.

DHT11 chỉ theo dõi độ ẩm, không điều chỉnh độ ẩm và không thay DS18B20 trong bảo vệ nhiệt. Chương trình đọc mỗi 3 giây trong tiến trình riêng. Khi lỗi đọc, RH hiện `--`, CSV để trống giá trị và ghi lỗi; không dùng giá trị giả. Quá 10 giây không có cập nhật thì ẩn giá trị cũ. Lỗi DHT không tắt các bảo vệ nhiệt hiện có.

## Nối dây khi đã ngắt nguồn Pi và adapter

| DHT11 | Raspberry Pi 4 | Dây |
|---|---|---|
| VCC / + | 3,3 V từ **nhóm 3,3 V trên breadboard** (chung với DS18B20, lấy từ chân 1). **Không** dùng chân 17: đã cấp cho OLED | Dupont |
| DATA / OUT / S | GPIO17 (BCM17), chân vật lý 11 | Dupont |
| GND / - | GND, **chân vật lý 25** (chân 14 đã dùng cho MOSFET bóng) | Dupont |

Đọc đúng chữ trên module, không suy thứ tự theo màu dây. Chọn module hỗ trợ nguồn 3.3V. Không cấp 12V; không đưa tín hiệu DATA kéo lên 5V vào Pi. Nếu cảm biến rời 4 chân: nhìn mặt lưới hướng về mình, chân chĩa xuống, từ trái là VCC, DATA, NC (bỏ trống), GND; đối chiếu tài liệu đúng sản phẩm trước khi cấp nguồn. Cảm biến rời cần điện trở 10 kΩ giữa DATA và 3.3V. Module 3 chân thường đã có điện trở kéo lên, kiểm tra module trước khi thêm.

Đặt DHT11 trong hộp ở vùng khí lưu thông gần đầu dò nhiệt, tránh sát bóng, thành nóng, tia nhiệt trực tiếp và nước đọng. Dùng DS18B20 cho nhiệt độ chính.

## Chép từ Terminal Windows (không chạy scp này trong SSH)

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
ssh pi@pi
```

## Cài trên Pi

```bash
cd /home/pi/Code_HopAp_Demo
sudo apt update
sudo apt install -y python3-venv
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install adafruit-circuitpython-dht
```

Giữ `--system-site-packages` để dùng thư viện GPIO/OLED đã cài bằng apt. Nếu thư viện báo thiếu libgpiod, kiểm tra gói hệ điều hành bằng `apt-cache search '^libgpiod[0-9]'` và cài đúng gói có trong kết quả (ví dụ `sudo apt install libgpiod2`). Không cài các thư viện Pi trên laptop để đọc cảm biến.

## Chạy thử chỉ đọc, rồi chạy cùng mạch

Giữ DS18B20 và OLED nối như cũ. Lệnh đầu chỉ đọc, không điều khiển bóng/quạt:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python do_nhiet_hop.py doc --dht11 --giay 60
```

Terminal hiện nhiệt DS18B20 và RH; OLED hiện RH ở dòng thứ ba; CSV trong `logs/` có thêm `humidity_pct`, `humidity_age_s`, `humidity_error`. Trong lúc chờ số đo đầu tiên sẽ hiện RH `--`.

Sau khi đã kiểm tra dây và số đo, thử hộp rỗng có giám sát, điều chỉnh bóng/quạt bằng chế độ tay đang dùng:

```bash
.venv/bin/python do_nhiet_hop.py tay --dht11 --giay 600
```

Chế độ tay khởi đầu bóng/quạt 0%; xem cú pháp lệnh điều khiển trong hướng dẫn đo nhiệt hiện có. Ctrl+C để kết thúc. Bỏ `--dht11` thì chương trình không truy cập DHT11.

## Chạy Q-table và đo thêm độ ẩm

Sau khi cài thư viện và nối DHT11 như trên, xem kế hoạch trước:

```bash
.venv/bin/python kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl --dht11 --dry-run
```

Hộp rỗng, nhiệt ban đầu không quá 30°C, có người theo dõi, chỉ chạy một chương trình điều khiển:

```bash
.venv/bin/python kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl --dht11
```

Làm ấm theo quy tắc hiện có, khi đạt 37°C bắt đầu 600 giây dùng Q-table đã huấn luyện để bám mục tiêu 37.5°C. Độ ẩm chỉ được hiển thị và ghi trong `ket_qua_giu_nhiet/<timestamp>/du_lieu.csv`; `cau_hinh.json` ghi `dht11: true`. RH không đi vào state, action, reward hay cập nhật Q. Các ngưỡng bảo vệ nhiệt và chính sách Q-table giữ nguyên. DHT11 lỗi thì RH hiện `--`, không dùng RH thay DS18B20. Các launcher khảo sát khác chưa chuyển tiếp tùy chọn DHT11.

Thư viện và cách xử lý lỗi đọc theo [Adafruit CircuitPython DHT](https://github.com/adafruit/Adafruit_CircuitPython_DHT) và [ví dụ chính thức](https://github.com/adafruit/Adafruit_CircuitPython_DHT/blob/main/examples/dht_simpletest.py). Chưa xác nhận đọc cảm biến thực trên Pi trong lần cập nhật này.
