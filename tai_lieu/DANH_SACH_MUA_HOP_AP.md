# Danh sách mua linh kiện demo hộp ấp nhiệt

Ngày ghi: 11/11/2026.

Phương án chốt để tính số lượng: tận dụng bóng sợi đốt vàng kiểu xi nhan **12V–21W** đã có, mua đui đúng kiểu chân bóng, dùng Raspberry Pi 4, **1 OLED và 2 LED**. Tận dụng Raspberry Pi 4, nguồn USB-C của Pi, DS18B20 và điện trở 4,7 kΩ; **mua 1 quạt tản nhiệt 12V mới**. Mua **2 module MOSFET riêng** để điều khiển bóng và quạt; không tính dùng lại mạch transistor S8050. Kiểm tra các món đang có trước khi mua.

| STT | Món cần mua | Số lượng | Ghi chú chọn mua |
|---:|---|---:|---|
| 1 | Bóng sợi đốt vàng kiểu xi nhan 12V–21W | 1 bóng (tận dụng) | Kiểm tra nhãn 12V–21W và công nghệ sợi đốt; không dùng bóng LED xi nhan |
| 2 | Đui chịu nhiệt đúng chân bóng xi nhan, có hai dây | 1 đui | Bóng vàng PY21W thường có chân BAU15s; P21W có chân BA15s. Kiểm tra chân bóng thực tế trước khi mua; đui E27 không lắp được |
| 3 | Adapter 12V DC ổn áp | 1 cái | Nên mua 5A để có dư địa khi bóng sợi đốt khởi động; cấp song song cho bóng 12V–21W và quạt 12V qua hai mạch MOSFET riêng. Raspberry Pi dùng nguồn USB-C riêng đã có |
| 4 | Module MOSFET AOD4184 có opto cho bóng | 1 module | Chọn bản module hoàn chỉnh nhận tín hiệu kích 3,3V; hỏi người bán xác nhận dùng được với bóng sợi đốt 12V–21W, xung khởi động và PWM khoảng 2Hz; có trạng thái mặc định tắt |
| 5 | Module MOSFET AOD4184 có opto cho quạt | 1 module | Cùng loại với dòng 4; hỏi người bán xác nhận nhận GPIO 3,3V và điều khiển được quạt 12V. Nếu dùng PWM khoảng 100Hz, cần thử quạt 2 dây thực tế vì không phải mẫu nào cũng chạy ổn ở mọi duty |
| 6 | Công tắc nhiệt ngắt quá nhiệt | 1 cái | Loại thường đóng, mở ở khoảng 50°C theo mô tả; kiểm tra định mức cho mạch DC |
| 7 | Màn OLED SSD1306 I²C 0,96 inch, loại 4 chân | 1 màn | Trên cùng module phải có đủ VCC, GND, SDA, SCL; chọn loại dùng được nguồn và tín hiệu 3,3V của Pi. Không cấp 12V từ adapter vào OLED |
| 8 | LED đỏ 5 mm, loại 2 chân | 1 cái | Báo đang sưởi; không mua loại đèn báo 12V có mạch tích hợp |
| 9 | LED xanh lá 5 mm, loại 2 chân | 1 cái | Báo đang làm mát; không mua LED RGB 4 chân |
| 10 | Điện trở 330 Ω | 2 con | Mỗi LED dùng 1 con |
| 11 | Hộp cách nhiệt có nắp | 1 hộp | Kích thước dự kiến khoảng 30 × 20 × 20 cm |
| 12 | Giá cố định đui chịu nhiệt | 1 cái/bộ | Không gắn đui trực tiếp vào xốp |
| 13 | Tấm chắn nhiệt bằng kim loại | 1 tấm/bộ | Chắn bức xạ tới thành hộp và cảm biến |
| 14 | Bộ cầu chì DC và đế | 1 bộ | Chọn trị số theo dây và tải thực tế, gồm 1 cầu chì lắp sẵn |
| 15 | Đầu nối dây gạt 5 lỗ thông nhau để chia nguồn DC (ví dụ WAGO 221-415) | 2 cái | Một cái chỉ nối các dây +12V sau cầu chì; một cái chỉ nối các dây 0V của adapter. Mỗi cái có 5 lỗ nối điện với nhau; không mua cầu đấu 2EDG 5.08 hàn PCB vì các chân của nó không tự nối thông. Chọn loại phù hợp tiết diện dây và dòng mạch; đặt ngoài hộp ấp |
| 16 | Dây điện DC đỏ/đen cho nguồn 12V, bóng và quạt | Mỗi màu khoảng 1–2 m | Chọn dây mềm có tiết diện phù hợp dòng và cầu chì (gợi ý 0,75 mm²); đoạn gần bóng phải có vỏ chịu nhiệt. Dây từ đui bóng chỉ nối vào dây chịu nhiệt; không dùng dây Dupont cho nhánh 12V–21W |
| 17 | Vít, đai ốc, ống co nhiệt và dây rút | 1 bộ | Lắp đui, màn, LED và cố định dây |
| 18 | Quạt tản nhiệt DC 12V, 2 dây, cỡ 50 × 50 × 10 mm | 1 cái | Chọn quạt có ghi rõ dòng định mức và chiều gió; cỡ 50 mm là điểm khởi đầu cho hộp khoảng 30 × 20 × 20 cm. Có thể dùng cỡ 40 × 40 × 10 mm nếu không gian lắp hẹp; chưa cần cỡ 80 × 80 × 25 mm. Không cần bộ giảm áp 12V xuống 5V |
| 19 | Jack DC cái ra 2 cọc vít, nhận đầu cắm tròn của adapter | 1 cái | Mua loại có lỗ nhận đầu cắm adapter và kim tiếp xúc ở giữa; không mua đầu cắm DC đực ra cọc vít. Kiểm tra kích thước 5,5 × 2,1 mm hay 5,5 × 2,5 mm, cực tính và dòng chịu tải trước khi mua |
| 20 | Dây Dupont cái–cái dài khoảng 20–40 cm | 1 bộ ít nhất 20 sợi | Dùng phía tín hiệu: 4 dây OLED, 4 dây PWM/GND của hai MOSFET, khoảng 3 dây DS18B20 và 4 dây cho hai LED. Chọn chiều dài đủ khi mở nắp hộp; có thể cắt một đầu rồi hàn vào điện trở/LED hoặc dây cảm biến, đầu cái còn lại cắm vào GPIO Pi. Không dùng cho dòng bóng/quạt 12V |
| 21 | Đầu cos dẹt bọc cách điện cho KSD301 | 2 cái nếu KSD có chân dẹt | Chọn đúng bề rộng chân công tắc thực nhận (thường gặp 6,3 mm); bấm cos vào dây, không hàn trực tiếp lên thân KSD301. Nếu KSD có dây sẵn thì không cần |
| 22 | Gen cao su/ống bảo vệ dây đi qua thành hộp | 1–2 cái/đoạn | Bảo vệ dây ở lỗ xuyên thành, tránh cọ xát cạnh sắc và kéo tuột dây; chọn theo đường kính bó dây thực tế |
| 23 | Diode 1N4007 bảo vệ nhánh quạt | 1 cái (tận dụng nếu còn) | Chỉ lắp theo sơ đồ ở hướng dẫn khi module/quạt thực mua cần diode bảo vệ xung ngược; đặt song song ngược với quạt, không lắp vào bóng |

**Dụng cụ cần có khi lắp:** đồng hồ vạn năng; mỏ hàn và thiếc hàn; kìm cắt/tuốt dây; kìm bấm cos nếu dùng đầu cos dẹt; tua vít nhỏ. Kiểm tra đồ đã có trước khi mua. Các mối hàn LED–điện trở–dây phải bọc ống co nhiệt ở dòng 17. Nếu OLED hoặc module MOSFET giao chưa hàn chân/cọc vít, nhờ người bán hàn sẵn hoặc tự hàn trước khi đấu mạch.

**Nối hai LED:** mỗi LED dùng 2 dây Dupont có đầu cái cắm Pi. Với LED đỏ: chân vật lý 18 (GPIO24) → dây → điện trở 330 Ω → chân dài LED; chân ngắn LED → dây → GND chân 25. Với LED xanh: chân vật lý 22 (GPIO25) → dây → điện trở 330 Ω → chân dài LED; chân ngắn LED → dây → GND chân 30. Điện trở không phân cực; hàn các mối nối rồi bọc ống co nhiệt.

**Cách chia nguồn từ một đầu tròn adapter:** cắm đầu tròn vào jack DC cái ở dòng 19, từ hai cọc +12V và GND của jack đi tới cầu đấu ở dòng 15. Sau cầu chì trên dây +12V, chia thành hai nhánh song song: (1) +12V → công tắc nhiệt thường đóng → bóng 12V–21W → MOSFET đèn → GND; (2) +12V → quạt 12V → MOSFET quạt → GND. Hai LED báo được cấp qua điện trở 330 Ω từ Raspberry Pi, không đấu trực tiếp vào adapter 12V. Chỉ nối chân tải và chân tín hiệu của module MOSFET theo đúng sơ đồ của module thực mua.

```text
Jack DC cái, cọc + ── cầu chì ── [cầu đấu chỉ cho +12V] ──┬── cực + mạch bóng
                                                            └── cực + mạch quạt
Jack DC cái, cọc - ───────────── [cầu đấu chỉ cho GND] ────┬── đường về mạch bóng
                                                            └── đường về mạch quạt
```

Mỗi mạch lấy **một dây từ cầu đấu +** và có **một đường về cầu đấu GND**. Quạt 12V nối vào nhánh 12V riêng qua MOSFET quạt, không cần bộ giảm áp. Cầu đấu chỉ chia dây, không đổi điện áp. Không kẹp nhiều dây vào một cọc vít của jack nếu cọc đó không được thiết kế cho việc đó.

**Nguồn cho phương án quạt 12V:** một adapter 12V cấp cho bóng và quạt qua hai MOSFET riêng. Bóng 21W có dòng danh định khoảng 1,75A ở 12V; kiểm tra dòng định mức và dòng khởi động thực tế của quạt, đồng thời bảo đảm tổng tải không vượt khả năng adapter. Raspberry Pi tiếp tục dùng nguồn USB-C 5V riêng; nối chung GND điều khiển theo sơ đồ của module MOSFET. Không đưa 12V vào GPIO.

**Lắp quạt làm mát:** nếu quạt hút khí nóng ra ngoài, hộp cần có lỗ lấy khí bù ở phía khác; chỉ quay quạt trong hộp kín thì quạt chủ yếu đảo khí, không thải nhiệt ra ngoài. Tránh thổi trực tiếp vào bóng hoặc cảm biến; kiểm tra nhiệt độ thực tế sau khi lắp.

**Nếu một trong các món dự định tận dụng bị thiếu:** bổ sung 1 Raspberry Pi 4, 1 nguồn USB-C phù hợp Pi 4, 1 thẻ microSD, 1 DS18B20, 1 điện trở 4,7 kΩ hoặc dây tín hiệu tương ứng. Đây là phần đã được ghi là có sẵn trong tài liệu giữa kỳ, chưa được kiểm kê thực tế.

Thông số cần đối chiếu trước khi đặt mua: [Pi 4 và GPIO 3,3V](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [ví dụ module AOD4184 có opto được bán tại Việt Nam](https://dientutuyetnga.com/products/module-cong-suat-mosfet-aod4184), [module DFRobot DFR0457 có tài liệu hãng rõ ràng](https://www.dfrobot.com/product-1567.html), [điện trở kéo lên DS18B20](https://support.analog.com/en-US/knowledgebase/article/000094969), [bóng vàng PY21W 12V–21W chân BAU15s](https://www.documents.philips.com/assets/20230914/91760674c0f4466da86cb07d0179b09b.pdf).
