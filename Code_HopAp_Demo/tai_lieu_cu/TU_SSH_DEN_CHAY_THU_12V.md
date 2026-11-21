> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Từ ssh pi@pi tới chạy thử mạch hai MOSFET 12 V

**16/11/2026.** Quạt 12 V qua MOSFET/GPIO18, bóng 12 V–21 W qua MOSFET/GPIO23. Chưa cần LED, DS18B20 hoặc OLED. Đây là phép thử ngắn với hộp mở, không phải chương trình điều nhiệt.

`pi@pi` nghĩa là tài khoản `pi` trên máy có hostname `pi`. Hostname phải được laptop tìm thấy. Nếu `ssh pi@pi` báo `Could not resolve hostname pi`, thay **mọi đích** `pi@pi` dưới đây bằng `pi@IP_THUC_TE` hoặc `pi@pi.local` khi đúng hostname đó. Không gõ chữ `IP_THUC_TE` nguyên dạng. Chỉ chuyển sang chép file sau khi SSH đăng nhập được. Lỗi `Connection timed out` cần được xử lý ở nguồn/khởi động Pi, dây mạng, địa chỉ hoặc dịch vụ SSH trước.

## 1. Thử đăng nhập — trên PowerShell laptop

Ban đầu rút adapter 12 V của bóng/quạt; Pi giữ nguồn USB-C riêng.

```powershell
ssh pi@pi
```

Lần đầu kết nối đúng Pi, SSH có thể hỏi xác nhận host key; xác nhận khi đã xác định đúng máy Pi. Nhập mật khẩu tài khoản Pi khi hỏi. Mật khẩu không hiện ký tự lúc gõ.

Khi đã thấy dấu nhắc kiểu `pi@pi:~ $`, chạy **trên Pi**:

```bash
hostname
hostname -I
python3 --version
exit
```

`exit` đưa bạn về PowerShell laptop. Dấu nhắc lúc này thường bắt đầu bằng `PS` và có đường dẫn Windows.

## 2. Chép cả thư mục — trên PowerShell laptop

```powershell
cd D:\BTL_Nhom13
scp -r .\Code_HopAp_Demo pi@pi:/home/pi/
```

Nhập mật khẩu Pi khi SCP hỏi. Chỉ làm bước tiếp theo khi lệnh hoàn tất không báo lỗi.

## 3. Chạy quy trình có hướng dẫn — trên PowerShell laptop

```powershell
ssh -t pi@pi "bash /home/pi/Code_HopAp_Demo/chay_thu_12v.sh"
```

Script trên Pi sẽ:

1. Kiểm tra Python và các file chương trình.
2. Kiểm tra `gpiozero` và `lgpio`; cài bằng apt nếu thiếu. Bước cài cần Pi có Internet; nếu gói đã có thì không cần tải lại. `sudo` có thể hỏi mật khẩu Pi.
3. Gửi lệnh tắt cả hai tải.
4. Dừng chờ bạn cắm adapter 12 V, quan sát cả hai tải vẫn tắt và nhập `y` để bắt đầu.
5. Thử quạt 100% trong 5 giây rồi tắt.
6. Chờ bạn xác nhận quạt chạy/tắt đúng; nhập `y` để thử bóng 2 giây. Sau đó bóng tắt và quạt chạy thêm 5 giây.
7. Gửi lệnh tắt khi kết thúc hoặc thoát. Nếu lệnh tắt lỗi, ngắt adapter 12 V bằng tay.

Ở mỗi câu hỏi, chỉ nhập **một chữ `y`** rồi Enter để chạy, hoặc **`n`** rồi Enter để dừng. Không nhập `100`, `100000` hoặc mức PWM tại lời nhắc này. Nếu nhập nhầm, script bản mới sẽ giải thích và hỏi lại. Thời gian và công suất đã được đặt trong từng lệnh thử.

Nhấn Ctrl+C để dừng. Chương trình Python xử lý Ctrl+C/SIGTERM và SIGHUP trên Pi khi phiên SSH đóng, nhưng không bảo đảm cắt tải khi mất điện, Pi treo, bị kill cưỡng bức hoặc phần công suất hỏng. Theo dõi thực tế và rút adapter 12 V nếu tải không tắt.

## 4. Nếu muốn gõ từng lệnh trên Pi

Sau bước chép file, đăng nhập lại:

```powershell
ssh pi@pi
```

Trong phiên SSH, chạy:

```bash
cd /home/pi/Code_HopAp_Demo
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio
python3 thu_mach_12v.py tat
```

Lúc này cắm adapter 12 V, kiểm tra bóng và quạt vẫn tắt, rồi chạy lần lượt:

```bash
python3 thu_mach_12v.py quat --giay 5
python3 thu_mach_12v.py den --giay 2
python3 thu_mach_12v.py tat
```

Chỉ sau khi mỗi lần thử riêng đã đúng, có thể thử hai tải đồng thời:

```bash
python3 thu_mach_12v.py ca-hai --muc 50 --giay 3
```

## 5. Script PowerShell tùy chọn

Trong PowerShell laptop, khi môi trường cho phép chạy file `.ps1`:

```powershell
cd D:\BTL_Nhom13\Code_HopAp_Demo
.\chay_tu_laptop_12v.ps1 -PiHost pi
```

Nếu dùng IP thực tế, truyền IP đó thay cho `pi`. Script chép thư mục rồi mở phiên chạy thử trên Pi; mật khẩu chỉ được nhập tại lời nhắc SSH/SCP. Nếu Windows chặn script PowerShell, sử dụng các lệnh thủ công ở mục 1–3 theo chính sách của máy.

## 6. Kiểm tra khi tải không hoạt động

- Đọc chữ `+`, `−`, `LOAD`, `PWM`, `GND` trên từng bo và đối chiếu [README_12V.md](README_12V.md).
- Quạt: GPIO18 là **chân vật lý 12**, đi tới `PWM`; GND Pi đi tới GND tín hiệu module quạt.
- Bóng: GPIO23 là **chân vật lý 16**, đi tới `PWM`; GND Pi đi tới GND tín hiệu module bóng.
- Phía tải: mỗi module nhận đủ +12 V và 0 V; dây âm quạt/bóng đi tới `LOAD` tương ứng.
- WAGO A cần **5 cổng tổng**, WAGO B dùng 3 cổng.
- Nếu KSD301 NC đã mắc nối tiếp bóng, kiểm tra trạng thái của nó; giữ nguyên đường bảo vệ khi thử.

Nguồn: [SSH và chép file trên Raspberry Pi](https://www.raspberrypi.com/documentation/computers/remote-access.html), [GPIO Zero](https://gpiozero.readthedocs.io/en/stable/api_output.html).
