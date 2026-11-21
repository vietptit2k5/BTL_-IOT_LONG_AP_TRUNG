> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Sơ đồ hiện tại: bóng 12 V qua MOSFET, quạt 5 V qua S8050

**Cập nhật 15/11/2026 theo lựa chọn của người dùng.** Dùng lại nguyên mạch quạt của bài giữa kỳ đã chạy được: quạt 5 V, S8050, điện trở base (tài liệu giữa kỳ ghi 1 kΩ) và diode 1N4007. Bóng sợi đốt 12 V–21 W tiếp tục dùng module MOSFET D4184/AOD4184 và KSD301 NC. Người dùng không dùng cầu chì trong cấu hình hiện tại. Chưa lắp LED và cảm biến; chương trình thử cũng chưa điều khiển OLED.

## 1. Nhánh quạt 5 V

```text
Nguồn +5 V ───────┬──────────── Quạt (+)
                 │                │
                 │              [QUẠT]
                 │                │
                 │          ┌── Quạt (−)
                 │          │     │
                 └─ cathode │     C
                    DIODE   │   S8050
                    anode ──┘     E
                                  │
Nguồn 5 V (−) ────────────────────┴──── GND Pi

Pi GPIO18 / chân vật lý 12 ── điện trở base ── B của S8050
```

Diode mắc song song với quạt: **đầu có vạch bạc (cathode) tới quạt dương/+5 V**, đầu không có vạch (anode) tới quạt âm/chân C. Không nối trực tiếp B với GPIO mà bỏ điện trở base. Với S8050 rời, xác định E/B/C theo đúng nhà sản xuất và kiểu vỏ; không đoán thứ tự trái/phải. Có thể tham khảo [datasheet SS8050 của onsemi](https://www.onsemi.com/download/data-sheet/pdf/ss8050-d.pdf) nếu đúng linh kiện đó; các biến thể khác cần tài liệu tương ứng.

Ưu tiên giữ nguyên nguồn 5 V và mạch đã hoạt động ở bài giữa kỳ. Dòng trên tem quạt và nguồn cũ đang được hỏi lại để xác nhận cách cấp nguồn. Nếu mạch cũ lấy từ Pi, chân vật lý **2 hoặc 4 là nguồn 5 V**, chân vật lý **6/9/14/20/25/30/34/39 là GND**. Việc lấy quạt từ đường 5 V của Pi còn phụ thuộc nguồn USB-C và dòng quạt; không coi GPIO18 là chân cấp nguồn. Nếu dùng nguồn 5 V rời, nối âm nguồn đó với GND Pi để S8050 nhận đúng tín hiệu, và không nối song song hai nguồn +5 V độc lập với nhau.

Không đưa quạt 5 V vào WAGO +12 V. Bỏ các dây của module MOSFET quạt 12 V cũ khi đã ngắt nguồn. GPIO18 chỉ nối tới một mạch điều khiển quạt hiện tại.

## 2. Nhánh bóng 12 V

```text
Adapter 12 V ── đầu cắm tròn ── Jack DC

Jack DC (+) ── WAGO A +12 V ──┬── MOSFET bóng (+)
                             └── KSD301 NC ── Đui/bóng dây 1
                                                    [BÓNG]
MOSFET bóng LOAD ──────────────────────────── Đui/bóng dây 2
      │
 [MOSFET khi bật]
      │
MOSFET bóng (−) ── WAGO B 0 V ── Jack DC (−)

Pi GPIO23 / chân vật lý 16 ── PWM tín hiệu module bóng
Pi GND / ví dụ chân 14 ────── GND tín hiệu module bóng
```

Với module cách ly quang đúng loại đã thống nhất, giữ riêng phía nguồn 12 V: GND Pi chỉ đi tới `GND` tín hiệu module; WAGO B đi tới cọc `−` phía tải. Không dùng S8050 của quạt để thay MOSFET bóng 21 W.

| WAGO 5 cổng | Các cổng sử dụng |
|---|---|
| A, +12 V | 1: jack DC +; 2: module bóng +; 3: đầu vào KSD301; còn 2 cổng trống |
| B, 0 V | 1: jack DC −; 2: module bóng −; còn 3 cổng trống |

Mỗi WAGO này thông điện giữa toàn bộ 5 cổng. Những cổng trống chỉ dành cho đúng cực của WAGO đó, không phải đầu nối riêng để nối dài đường quạt hoặc LOAD.

KSD mắc nối tiếp với bóng và phải là NC. Nhiệt độ ngắt là nhiệt tại thân/mặt cảm nhiệt KSD, không mặc định là nhiệt không khí hoặc số đọc DS18B20. Thông số AC in trên KSD không tự xác nhận định mức đóng ngắt tải DC.

## 3. Dây và vị trí

- Nhánh 12 V: dùng dây đồng 0,75 mm² hiện có; giữ đoạn dây gốc chịu nhiệt của đui ở gần bóng. Đui/giá và tấm chắn phải tách khỏi xốp, không gắn bóng trực tiếp lên xốp.
- Nhánh quạt: giữ dây gốc quạt và các mối nối chắc của bộ giữa kỳ. Dây GPIO18 và GND tín hiệu có thể dùng Dupont; nguồn quạt không đi qua chân GPIO18.
- Pi, S8050 và MOSFET bóng ở ngoài hộp, cố định trên đế cách điện. Quạt, bóng và KSD ở trong; dây đi sát thành và qua lỗ có gen bảo vệ.
- Đo đường đi thực tế, chừa 5–10 cm mỗi nhánh rồi mới cắt; không để dây hoặc đầu nối chạm bóng nóng.

## 4. Thứ tự thử

Pi hiện chưa kết nối SSH thành công. Trước khi gắn lại mạch, kiểm tra Pi khởi động và cổng LAN có liên kết khi chỉ giữ nguồn USB-C, thẻ nhớ và dây LAN. Ngắt cả 12 V và 5 V/USB-C trước khi đổi dây phần cứng.

Sau khi Pi khởi động và đăng nhập được, dùng [thu_mach.py](../thu_mach.py) theo [README](README_cu_thu_mach.md): thử quạt 100% trong 5 giây trước, sau đó thử bóng 2 giây. Chương trình hiện thử quạt bằng bật/tắt; việc PWM tốc độ thấp cần được xác nhận riêng trên quạt thực. Mở nắp và dùng hộp rỗng vì chưa có cảm biến.

Nguồn tham khảo: [sơ đồ GPIO và giới hạn điện áp Pi](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [SS8050 onsemi](https://www.onsemi.com/download/data-sheet/pdf/ss8050-d.pdf), cùng cấu hình bài giữa kỳ trong [README cũ](../../GIUA_KY_Quat_Taxi/Baocao_Nhom13_Chuong6/Code_Quat_QLearning/quat/README.md).
