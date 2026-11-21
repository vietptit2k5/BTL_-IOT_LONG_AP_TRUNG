# Hướng dẫn lắp và kiểm tra demo hộp ấp nhiệt Q-learning

> **Cập nhật 21/11/2026 — cấu hình hiện hành:** bóng 12 V–21 W và **quạt 12 V**, mỗi tải qua một module MOSFET (GPIO23 / GPIO18). Sơ đồ nối dây, phân chân và cách chạy xem [Code_HopAp_Demo/README.md](../Code_HopAp_Demo/README.md). Ghi chú ngày 15/11 về quạt 5 V qua S8050 đã lỗi thời (lưu ở [tai_lieu_cu](../Code_HopAp_Demo/tai_lieu_cu/SO_DO_NOI_DAY_quat_5V_cu.md)). Tài liệu dưới đây là hướng dẫn lắp ráp ban đầu (11/11).

**Cấu hình dùng trong hướng dẫn (11/11/2026):** Raspberry Pi 4 dùng nguồn USB-C riêng; một adapter **12 V DC, 5 A** cấp cho **một bóng sợi đốt ô tô 12 V–21 W** và **một quạt tản nhiệt 12 V, 2 dây, 50 × 50 × 10 mm**. Hai tải được điều khiển bằng **hai module MOSFET D4184/AOD4184 có cách ly quang**. Nhiệt độ hộp đo bằng một DS18B20; OLED I²C hiển thị thông tin; LED đỏ báo sưởi, LED xanh báo làm mát. Công tắc nhiệt **KSD301 thường đóng, ngắt khoảng 50 °C** mắc nối tiếp với bóng. Mục tiêu demo là **37,5 °C**.

Hướng dẫn này là sơ đồ lắp cho **module có hai chân tín hiệu `PWM`, `GND` và ba cọc tải ghi `+`, `−`, `LOAD`** như dòng module trong ảnh người bán. **Trước khi đấu, đọc chữ in trên đúng hai bo được giao.** Nếu tên chân hoặc sơ đồ của người bán khác, dừng ở bước kiểm tra và xác định lại mạch; không suy ra thứ tự cọc chỉ từ ảnh quảng cáo.

## 1. Kiểm đủ linh kiện và dụng cụ

Đối chiếu [danh sách mua hiện tại](DANH_SACH_MUA_HOP_AP.md). Phần nối dây cần **một bộ ít nhất 20 dây Dupont cái–cái** cho phía GPIO, **dây điện DC đỏ/đen** cho nguồn và tải 12 V, **hai đầu cos dẹt bọc cách điện** nếu KSD301 có chân dẹt, ống co nhiệt và gen bảo vệ dây xuyên thành hộp. Dụng cụ cần có: đồng hồ vạn năng, mỏ hàn và thiếc hàn, kìm cắt/tuốt dây, kìm bấm cos và tua vít. Nhờ người bán hàn sẵn các chân/cọc của OLED và module MOSFET nếu bạn không tự hàn. Nếu module quạt không có phần bảo vệ xung ngược ở tải, chuẩn bị **một diode 1N4007** (có thể tận dụng từ demo quạt giữa kỳ), lắp theo mục 4.4.

Khoảng **15 dây tín hiệu** được dùng cho OLED (4), hai module MOSFET (4), DS18B20 (khoảng 3) và hai LED (4); bộ 20 sợi còn vài dây dự phòng. Chọn dây dài **20–40 cm** theo vị trí Pi và nắp hộp, đủ để mở nắp mà không kéo căng dây. Pi có chân GPIO đực, nên đầu cắm vào Pi phải là **đầu cái**. Dây Dupont chỉ dùng phía tín hiệu 3,3 V; nhánh bóng và quạt 12 V dùng dây điện DC phù hợp dòng tải.

Trước khi dùng, xác nhận các điểm sau:

| Món | Phải kiểm tra trên món thực nhận |
|---|---|
| Bóng và đui | Bóng ghi **12 V–21 W**, đúng là sợi đốt; đui khớp chân bóng thực tế (PY21W thường BAU15s, P21W thường BA15s), có hai dây chịu nhiệt. Không dùng đui E27 cho bóng này. |
| Adapter và jack DC cái | Adapter ra **12 V DC**, cực tính đo bằng đồng hồ. Jack cái phải vừa đầu cắm (thường 5,5 × 2,1 hoặc 5,5 × 2,5 mm) và có định mức dòng phù hợp. Không đoán cực + theo màu dây. |
| Hai module MOSFET | Cả hai cùng mã **D4184/AOD4184**, đã hàn đầy đủ cọc/chân; ngõ tín hiệu nhận **3,3 V**, bật khi `PWM` mức cao và tắt khi mức thấp; tải là **DC 12 V**. Hỏi người bán khả năng chịu dòng khởi động của bóng sợi đốt 21 W. |
| KSD301 | Đúng loại **NC (thường đóng)**, thông mạch ở nhiệt độ phòng và ngắt khi thân công tắc nóng khoảng **50 °C**; có thông số phù hợp khi **ngắt tải 12 V DC**. Dòng 10/16 A ở 250 V AC không tự xác nhận định mức DC. |
| OLED | Module SSD1306 I²C **4 chân `VCC`, `GND`, `SDA`, `SCL`**, dùng được nguồn và tín hiệu **3,3 V**. |
| Hai LED | **Một đỏ, một xanh lá**, loại rời **5 mm, 2 chân**; mỗi LED đi với **một điện trở 330 Ω**. Không dùng LED RGB 4 chân hoặc đèn báo 12 V có mạch tích hợp. |
| DS18B20 | Loại **3 dây** hoặc có ba chân `VDD`, `DQ`, `GND`; kiểm tra sơ đồ của đúng cảm biến. Không tin màu dây nếu chưa có thông số. |
| Quạt | **12 V DC, 2 dây**, ghi dòng định mức và có mũi tên chỉ chiều gió trên khung hoặc nhãn. |
| Cầu chì, cầu đấu, dây | Đế cầu chì và jack chịu được dòng nhánh nguồn. Chọn cầu chì DC theo dây và dòng khởi động thực đo; dùng dây cấp bóng phù hợp dòng và nhiệt, không dùng dây Dupont cho nhánh bóng. |

**Chưa cấp điện** nếu thiếu thông số của KSD301 cho tải DC, module MOSFET không có nhãn chân rõ ràng, hoặc jack/đui không xác định được cực và kiểu lắp.

## 2. Sơ đồ tổng thể

Các đường **12 V công suất** đi từ adapter qua jack DC cái, cầu chì và hai cầu đấu phân phối. Pi vẫn dùng **nguồn USB-C riêng**. Hai đường điều khiển `PWM/GND` đi từ Pi tới *phía tín hiệu* của từng module. Dây `GND` phía tín hiệu là GND của Pi; cọc `−` phía tải là 0 V của adapter. Nếu module cách ly quang thật, **không tự nối tắt hai phía GND**; chỉ làm theo sơ đồ của đúng module thực nhận.

```text
ADAPTER 12 V DC
  đầu tròn → JACK DC CÁI
                 cọc + → CẦU CHÌ DC → CẦU ĐẤU +12 V ─┬─→ cọc + module ĐÈN
                                                       ├─→ KSD301 NC → dây 1 đui BÓNG
                                                       ├─→ cọc + module QUẠT
                                                       └─→ dây đỏ (+) QUẠT
                 cọc − → CẦU ĐẤU 0 V ──────────────────┬─→ cọc − module ĐÈN
                                                       └─→ cọc − module QUẠT

  dây 2 đui BÓNG ───────────────────────────────→ cọc LOAD module ĐÈN
  dây đen (−) QUẠT ─────────────────────────────→ cọc LOAD module QUẠT

PI 4 (nguồn USB-C riêng)
  GPIO23 → PWM module ĐÈN       GND Pi → GND tín hiệu module ĐÈN
  GPIO18 → PWM module QUẠT      GND Pi → GND tín hiệu module QUẠT
  GPIO4  ↔ DQ DS18B20          3V3 Pi → VDD DS18B20
  GPIO2  ↔ SDA OLED            3V3 Pi → VCC OLED
  GPIO3  ↔ SCL OLED            GND Pi → GND OLED, GND DS18B20, âm hai LED
  GPIO24 → 330 Ω → LED ĐỎ (+)
  GPIO25 → 330 Ω → LED XANH (+)
```

Ba cọc `+`, `−`, `LOAD` của module là **cọc phía tải**. Một module là **một kênh**: phải có **2 module riêng**, mỗi module nhận cả `+12 V` và `0 V` ở hai cọc nguồn của chính nó. Dòng tải đi qua cọc `LOAD` theo cấu trúc đóng cắt phía âm. Không nối bóng/quạt trực tiếp vào GPIO Pi.

## 3. Bố trí cơ khí trước khi đấu dây

1. Đặt bóng ở một góc dưới của hộp, gắn đui lên **giá và tấm kim loại**. Giữ bóng cách thành xốp **ít nhất 5 cm** theo tài liệu demo; tấm chắn không được chạm bóng, dây hoặc đầu nối. Nếu hộp không đủ chỗ giữ khoảng cách, thay đổi vị trí/loại hộp trước khi thử nhiệt.
2. Gắn quạt ở thành đối diện để **hút không khí phòng vào hộp**. Tạo một lỗ thoát khí ở phía trên và bảo vệ cánh quạt. Quạt chạy trong hộp kín chỉ đảo khí, không hạ nhiệt về nhiệt độ phòng. Đừng để luồng quạt thổi thẳng vào cảm biến.
3. Treo đầu dò DS18B20 gần **vị trí cần giữ 37,5 °C**, không áp sát bóng hoặc thành hộp; che bức xạ trực tiếp từ bóng bằng tấm chắn có khe thoáng khí.
4. Gắn KSD301 chắc vào vị trí kim loại có nhiệt độ đại diện cho điểm cần bảo vệ gần nguồn nhiệt. Nó ngắt theo **nhiệt độ của thân công tắc**, không theo số đọc DS18B20. Không đặt hai đầu cốt trần chạm tấm kim loại; bọc cách điện và cố định dây.
5. Đặt **Pi, adapter, cầu chì, cầu đấu và hai MOSFET ngoài hộp**. OLED và LED có thể ở mặt ngoài nắp. Luồn dây qua lỗ có gen/ống bảo vệ cạnh sắc, cố định chống kéo và bịt kín sau khi thử xong.

## 4. Đấu dây khi cả hai nguồn đã rút

### 4.1. Chia nguồn 12 V

1. Cắm đầu tròn adapter vào jack DC cái **chỉ để đo cực tính**, chưa nối bo. Đo hai cọc jack bằng đồng hồ ở chế độ V DC, đánh dấu `+12 V` và `0 V`, rồi **rút adapter**.
2. Dùng **dây điện DC đỏ/đen** nối cọc `+` jack → **đế cầu chì** → cầu đấu `+12 V` và cọc `−` jack → cầu đấu `0 V`. Không kẹp nhiều dây vào một cọc jack nếu jack không cho phép; dùng cầu đấu làm điểm chia nhánh. Không dùng dây Dupont cho đường nguồn 12 V.
3. Lắp cầu chì DC có đế; trị số cuối cùng phải phù hợp dây, jack, adapter và dòng khởi động thực tế. Bóng tiêu thụ khoảng **21/12 = 1,75 A khi sáng**, nhưng dòng lúc bật có thể cao hơn nhiều trong thời gian ngắn. Không thay cầu chì bằng dây nối tắt.

### 4.2. Nhánh bóng và module MOSFET thứ nhất

1. Từ cầu đấu `+12 V` cấp cho **cọc `+` của module đèn** và **một chân KSD301 NC**.
2. Chân KSD301 còn lại → **dây thứ nhất của đui bóng**. Nếu KSD có hai chân dẹt, bấm **hai cos dẹt bọc cách điện đúng cỡ** vào dây rồi cắm lên chân KSD; không hàn trực tiếp vào thân công tắc.
3. Dây thứ hai của đui bóng → **cọc `LOAD` của module đèn**.
4. Cầu đấu `0 V` → **cọc `−` của module đèn**.
5. Chân vật lý **16 / GPIO23** của Pi → `PWM` tín hiệu module đèn. Chân vật lý **14 / GND** của Pi → `GND` tín hiệu module đèn.

KSD301 ở **nối tiếp riêng với bóng**, nên khi ngắt thì bóng mất điện dù Pi hoặc MOSFET có đang ra lệnh bật. **Không dùng loại thường mở (NO).** Bọc cách điện hai đầu nối KSD và đui; bóng 12 V sợi đốt vẫn rất nóng khi hoạt động.

### 4.3. Nhánh quạt và module MOSFET thứ hai

1. Cầu đấu `+12 V` → **cọc `+` module quạt** và **dây đỏ (+) của quạt**.
2. **Dây đen (−) của quạt** → cọc `LOAD` module quạt.
3. Cầu đấu `0 V` → **cọc `−` module quạt**.
4. Chân vật lý **12 / GPIO18** của Pi → `PWM` tín hiệu module quạt. Chân vật lý **20 / GND** của Pi → `GND` tín hiệu module quạt.

Quạt 2 dây phải được thử ở **100%** trước. Nếu không khởi động ổn định ở 50% PWM hoặc kêu bất thường ở 100 Hz, phần mềm cần đổi mức điều khiển/tần số hoặc dùng bật–tắt; không giả định mọi quạt 2 dây đều chạy được ở 50%.

### 4.4. Diode bảo vệ nhánh quạt

Nếu tài liệu của **đúng module** không cho thấy diode bảo vệ tải cảm ứng, có thể dùng một diode **1N4007** đặt **song song ngược với quạt**: đầu có **vạch bạc (cathode)** về dây đỏ `+12 V` của quạt, đầu còn lại về dây đen của quạt/cọc `LOAD`. Kiểm tra cực diode bằng đồng hồ trước khi cấp điện. **Không lắp diode song song bóng đèn.** Nếu module hoặc quạt có chỉ dẫn khác của nhà sản xuất, làm theo chỉ dẫn đó.

### 4.5. DS18B20, OLED và LED

| Kết nối Pi 4 | Chân vật lý | Đi tới |
|---|---:|---|
| 3V3 | 1 | `VDD` của DS18B20; nối một đầu điện trở kéo lên 4,7 kΩ tại cùng đường dây 3V3 này |
| 3V3 | 17 | `VCC` của OLED |
| GND | 6 | `GND` DS18B20 |
| GND | 9 | `GND` OLED |
| GND | 14 | `GND` tín hiệu module đèn |
| GND | 20 | `GND` tín hiệu module quạt |
| GPIO4 | 7 | `DQ/DATA` của DS18B20 |
| GPIO2 / SDA1 | 3 | `SDA` OLED |
| GPIO3 / SCL1 | 5 | `SCL` OLED |
| GPIO23 | 16 | `PWM` module đèn |
| GPIO18 | 12 | `PWM` module quạt |
| GPIO24 | 18 | Điện trở 330 Ω → chân dài/anode LED đỏ; chân ngắn/cathode → GND Pi chân vật lý 25 |
| GPIO25 | 22 | Điện trở 330 Ω → chân dài/anode LED xanh; chân ngắn/cathode → GND Pi chân vật lý 30 |

Mắc **một điện trở 4,7 kΩ giữa `DQ` DS18B20 và dây 3V3 từ chân vật lý 1**, gần Pi. OLED lấy 3V3 ở **chân vật lý 17**, nên mỗi dây nguồn có một chân Pi riêng. Không kéo `DQ` lên 5 V; GPIO Pi chỉ dùng logic 3,3 V. Nếu sau này dùng cảm biến DS18B20 thứ hai, có thể nối cùng ba đường 1-Wire và nhận diện theo **mã serial**, nhưng bản lắp này chỉ cần một cảm biến.

**Cách làm dây LED:** lấy **2 dây Dupont cái–cái cho mỗi LED**, cắt bỏ một đầu của mỗi dây và tuốt phần vỏ ngắn. Hàn dây thứ nhất vào **điện trở 330 Ω**, đầu còn lại của điện trở hàn với **chân dài (+) LED**; đầu cái của dây này cắm vào GPIO24/chân vật lý 18 (LED đỏ) hoặc GPIO25/chân vật lý 22 (LED xanh). Hàn dây thứ hai vào **chân ngắn (−) LED**; đầu cái cắm vào GND Pi chân 25 (đỏ) hoặc chân 30 (xanh). Bọc ống co nhiệt riêng cho từng mối hàn. Điện trở không phân cực và có thể nằm ở phía chân âm nếu vẫn mắc nối tiếp.

**Cách làm dây OLED, DS18B20 và MOSFET:** nếu hai đầu đều là hàng chân đực, cắm thẳng dây Dupont cái–cái theo bảng trên. Với cảm biến DS18B20 bọc inox có dây trần ở đầu ra, cắt một đầu dây Dupont, hàn/nối đúng `VDD`, `DQ`, `GND` theo nhãn của cảm biến rồi bọc cách điện từng mối. Không xoắn dây trần để dùng lâu dài. Điện trở 4,7 kΩ có thể hàn nối giữa hai nhánh `DQ` và `3V3` gần Pi, bọc từng điểm nối để không chạm chân khác.

Với **mỗi module MOSFET**, `GND` ở cặp chân tín hiệu nối về GND Pi; cọc `−` ở cụm ba cọc tải nối về 0 V adapter. Không nối nhầm `PWM` với 12 V. Nếu bo của bạn có thêm chân `VCC` hoặc tên chân khác, sơ đồ mục 2–4 **không áp dụng nguyên xi**.

## 5. Kiểm tra trước và sau khi cấp điện

Làm theo thứ tự. Sau mỗi bước, **rút nguồn** trước khi đổi dây.

| Bước | Cách làm | Kết quả cần thấy |
|---|---|---|
| 1. Kiểm tra nguội | Chưa cắm nguồn; kiểm tra bằng mắt từng dây theo mục 2; dùng thang thông mạch để xác nhận không chập `+12 V`–`0 V`. Kiểm tra KSD301 NC thông ở nhiệt độ phòng. | Không có dây trần chạm nhau, hai nhánh đi qua đúng module. |
| 2. Đo adapter và jack | Chỉ cắm adapter vào jack, đo tại cọc jack và sau cầu chì; chưa cắm Pi và chưa nối tải. | Điện áp khoảng 12 V DC, đúng cực tại các cọc đã đánh dấu. |
| 3. Thử Pi riêng | Rút adapter 12 V; cấp USB-C cho Pi. Bật I²C và 1-Wire, đọc DS18B20, quét OLED, thử từng LED qua điện trở. | Có nhiệt độ hợp lý, OLED được nhận, LED đúng màu/chân. |
| 4. Kiểm tra trạng thái khởi động | Đã đấu module nhưng chưa gắn bóng/quạt; cấp 12 V khi Pi đang tắt, rồi cấp nguồn Pi. | Module đèn **không tự bật** trong lúc Pi tắt và khởi động. Nếu tự bật, dừng và xử lý trạng thái mặc định trước khi lắp bóng. |
| 5. Thử quạt | Chỉ gắn quạt; ra lệnh bật 100% trong thời gian ngắn, rồi 50%, sau đó tắt. | Quạt quay đúng chiều gió, không kẹt hoặc kêu lạ, tắt khi lệnh tắt. |
| 6. Thử bóng | Chỉ gắn bóng; để nắp mở, bật ngắn ở 100%, sau đó tắt và đo điện áp hai đầu bóng. | Bóng sáng, tắt theo lệnh; không có jack, cầu đấu, dây hoặc module nóng bất thường. |
| 7. Thử KSD độc lập | Dùng nguồn nhiệt **có kiểm soát** làm ấm thân KSD từ ngoài hộp trong lúc lệnh đèn đang bật ngắn hạn; theo dõi bằng đồng hồ/nhiệt kế. Không dùng ngọn lửa, không nhúng KSD vào nước. | KSD mở thì bóng tắt dù GPIO vẫn ra lệnh bật. Khi nguội, loại tự hồi sẽ đóng lại: phải bảo đảm phần mềm đã ra lệnh tắt. |
| 8. Chạy hộp không có vật ấp | Đóng hộp, đặt cảm biến và tấm chắn, theo dõi nhiệt độ ít nhất một chu trình tăng/giảm; quan sát điểm nóng ở xốp và đầu nối. | Chỉ cho chạy tiếp khi phần mềm tắt đèn ở ngưỡng cứng, quạt hạ được nhiệt và không có điểm nóng nguy hiểm. |

Khi thử phần cứng, **không để hộp chạy không người giám sát**. Nếu thấy mùi khét, nhựa mềm, dây/jack nóng, bóng quá gần xốp, hoặc nhiệt độ tiếp tục tăng khi lệnh đèn tắt: rút **adapter 12 V**, để nguội rồi kiểm tra lại.

## 6. Cấu hình Pi và yêu cầu phần mềm

Trên Raspberry Pi OS, chạy `sudo raspi-config`, bật **I²C** và **1-Wire** trong *Interface Options*, rồi khởi động lại. Có thể kiểm tra cảm biến bằng `ls /sys/bus/w1/devices/28-*` và `cat /sys/bus/w1/devices/28-*/w1_slave`; dòng đo phải có CRC hợp lệ (`YES`). Nếu đã cài `i2c-tools`, dùng `i2cdetect -y 1` để kiểm tra địa chỉ OLED (thường 0x3C, nhưng đọc kết quả thực tế). [Hướng dẫn cấu hình Raspberry Pi](https://www.raspberrypi.com/documentation/computers/configuration.html).

**Mã hiện có trong `GIUA_KY_Quat_Taxi/Baocao_Nhom13_Chuong6/Code_Quat_QLearning/quat/` là demo giữa kỳ**: nó điều khiển quạt **5 V qua S8050**, chưa có driver bóng 12 V, OLED, LED, KSD/giám sát hộp hay Q-table cho hộp. Không chạy nguyên `test_phan_cung.py` hoặc `fan_qlearning.py real` để điều khiển mạch lắp mới. Cần viết/thử chương trình hộp ấp riêng trước buổi demo.

Chương trình hộp ấp phải có các quy tắc tối thiểu sau:

1. Khi khởi động, đặt **đèn tắt, quạt tắt**. Chỉ cho phép bật đèn sau khi đọc DS18B20 **thành công, CRC hợp lệ** và nhiệt độ hợp lý.
2. Đọc cảm biến liên tục; **trên 42 °C thì tắt đèn và bật quạt 100%**, không phụ thuộc hành động Q-learning. Không đặt mục tiêu bằng hoặc cao hơn ngưỡng ngắt cứng này.
3. Nếu mất cảm biến, dữ liệu sai, lỗi chương trình hoặc khi `Ctrl+C`: **tắt đèn trước**, quạt có thể tiếp tục làm mát theo trạng thái an toàn; cuối cùng giải phóng GPIO với đầu ra đèn ở mức tắt.
4. Không có hành động sưởi và làm mát đồng thời. Theo đề xuất, chu kỳ quyết định là **5 giây**; đèn có các mức 0/40/100% (băm xung thấp khoảng 2 Hz), quạt 0/50/100% (ban đầu thử 100 Hz, điều chỉnh theo quạt thực). OLED hiển thị nhiệt độ, mục tiêu, hành động và lỗi; LED đỏ/xanh phản ánh **lệnh điều khiển thực tế**.
5. Q-learning dùng **27 trạng thái × 5 hành động** theo tài liệu đề xuất. Huấn luyện trong mô phỏng trước, sau đó chạy hộp thật có log; so sánh với bộ bật–tắt có trễ. Không coi `q_quat.npy` của bài giữa kỳ là Q-table dùng trực tiếp cho hộp.

| Hành động đề xuất | Đèn | Quạt | LED |
|---|---:|---:|---|
| Sưởi mạnh | 100% | 0% | Đỏ |
| Sưởi nhẹ | 40% | 0% | Đỏ |
| Nghỉ | 0% | 0% | Tắt |
| Làm mát nhẹ | 0% | 50% | Xanh |
| Làm mát mạnh | 0% | 100% | Xanh |

## 7. Đo đáp ứng, chạy thử và trình diễn

1. **Đo tăng nhiệt:** ở nhiệt độ phòng, cho đèn chạy trong thời gian ngắn có giám sát và ghi nhiệt độ mỗi **5 giây**. Tự động dừng sưởi trước ngưỡng cứng; lưu log để thấy độ trễ sau khi tắt bóng.
2. **Đo nguội tự nhiên:** tắt đèn, tắt quạt, theo dõi nhiệt độ giảm. Sau đó thử quạt 100% để đo mức làm mát thêm. Chỉ thử trong giới hạn an toàn của hộp và phần mềm.
3. **Kiểm tra điều khiển:** đặt mục tiêu 37,5 °C, chạy liên tục và ghi các cột ít nhất gồm thời gian, nhiệt độ đo, mục tiêu, hành động, duty đèn/quạt, trạng thái bảo vệ. Kiểm tra vọt lố, thời gian vào dải ±0,5 °C và phản ứng sau khi mở nắp.
4. **Kịch bản trình bày:** giới thiệu bóng, quạt, DS18B20, OLED và hai LED; khởi động hộp trước vài phút; cho thấy nhiệt độ tăng và giảm sưởi gần mục tiêu; mở nắp khoảng 10 giây rồi đóng; nếu nhiệt độ phòng **thấp hơn 35 °C**, có thể hạ mục tiêu xuống 35 °C để minh họa quạt làm mát; trình chiếu biểu đồ log và một hàng Q-table đã học.

**Điểm dừng trước demo:** chỉ coi phần cứng hoàn thành sau khi đã kiểm được cực jack, KSD301 NC và định mức DC, trạng thái mặc định tắt của module đèn, test riêng từng tải, ngưỡng ngắt phần mềm, và ít nhất một lần chạy hộp thật có giám sát. Việc lắp dây không tự tạo ra Q-learning; mã điều khiển hộp và Q-table phải được triển khai, huấn luyện và thử riêng.

## Tài liệu đối chiếu

- [Mô tả demo cuối kỳ của dự án](M%C3%B4%20t%E1%BA%A3%20demo%20cu%E1%BB%91i%20k%E1%BB%B3%20-%20H%E1%BB%99p%20%E1%BA%A5p%20nhi%E1%BB%87t%20%C4%91%E1%BB%99%20Q-learning.pdf): sơ đồ GPIO, bố trí hộp, ngưỡng 42/50 °C, hành động Q-learning và kịch bản demo.
- [Tài liệu module MOSFET D4184/FR120N/LR7843 của nhà sản xuất](https://agelectronica.lat/pdfs/textos/O/OKY3496-17.PDF): tín hiệu điều khiển 3/5 V, cách ly quang, PWM.
- [Sơ đồ module D4184-M của nhà sản xuất](https://www.hestore.eu/sk/prod_getfile.php?id=17125): các chân `PWM`, `GND`, `+`, `−`, `LOAD`.
- [Sơ đồ chân GPIO Raspberry Pi](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) và [cấu hình I²C/1-Wire](https://www.raspberrypi.com/documentation/computers/configuration.html).
- [Datasheet DS18B20](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf) và [xác nhận điện trở kéo lên 4,7 kΩ](https://support.analog.com/en-US/knowledgebase/article/000094969).
- [Thông số KSD301 của nhà sản xuất](https://www.ksd301thermostatswitch.com/photo/ksd301thermostatswitch/document/22564/KSD301%20Thermostat%20Specification%28common%29.pdf) và [lý do phải kiểm riêng định mức DC](https://www.ia.omron.com/product/cautions/28/precautions_for_correct_use.html).
