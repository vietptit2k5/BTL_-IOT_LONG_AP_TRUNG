# Thiết kế máy ấp trứng gà theo yêu cầu thực tế

Ngày lập: 12/11/2026.

## Mục tiêu và phạm vi

Thiết kế máy ấp trứng gà một lứa có quạt tuần hoàn, theo dõi và điều khiển nhiệt độ, độ ẩm, thông khí, đảo trứng và lịch ấp. Người dùng chọn hộp khoảng 30 × 20 × 20 cm và muốn số trứng phù hợp hộp. Phương án khởi đầu đề xuất là 4 trứng, khay 2 × 2, để dành chỗ cho nguồn sưởi, chắn nhiệt, đường gió và cơ cấu đảo. Đây là dự kiến bố trí, chưa phải sức chứa đã kiểm chứng; phải đo lòng hộp và kiểm tra khoảng trống khi khay chuyển động. Chỉ xem xét tăng lên 6 trứng sau khi bố trí và thử nghiệm chứng minh đủ chỗ, đủ đều nhiệt/ẩm. Chưa xác nhận công suất bóng 21W hoặc mô-men động cơ đảo đủ cho khay thật.

Bo điện, nguồn, bình cấp nước và động cơ nên bố trí ngoài hộp khi cơ cấu cho phép. Phần trong hộp gồm khay, đường truyền động, quạt tuần hoàn, cảm biến tại vùng trứng, phần bay hơi/cấp ẩm và nguồn sưởi có giá và chắn nhiệt phù hợp. Nếu các bộ phận này không bố trí vừa với khoảng cách cần thiết, phải đổi cấu trúc hoặc tăng kích thước hộp trước khi chốt sức chứa.

Buổi demo khoảng 10 phút có thể trình diễn các chức năng và chuyển giai đoạn bằng đồng hồ thử. Muốn chứng minh hiệu quả ấp nở cần vận hành qua chu kỳ ấp thật và đánh giá trứng có phôi, tỷ lệ nở, chất lượng con non; kết quả giữ nhiệt hộp rỗng không thay thế được việc đó.

## Các yêu cầu phải xuất phát từ quá trình ấp

| Chức năng | Yêu cầu thiết kế |
|---|---|
| Nhiệt độ | Dùng cấu hình cho máy có quạt tuần hoàn; mức đặt ban đầu tham khảo 37,5°C theo hướng dẫn Brinsea. Đo tại vùng khay trứng, kiểm tra nhiều vị trí và hiệu chỉnh cảm biến trước khi chốt sai số điều khiển. Không tự hạ nhiệt từng giai đoạn khi chưa có căn cứ phù hợp loại máy. |
| Độ ẩm | Có cảm biến và cơ cấu tăng ẩm. Theo cấu hình tham khảo Brinsea, bắt đầu khoảng 45–50% RH trong 18 ngày đầu, tăng lên khoảng 65% RH hoặc hơn trong ba ngày cuối; điều chỉnh theo diễn biến mất nước của trứng và điều kiện máy. Đây là một hướng dẫn tham khảo đã chọn, không phải giá trị duy nhất cho mọi máy. |
| Đảo trứng | Đảo theo lịch xác định và cơ cấu khay; dừng đảo khi chuyển sang giai đoạn nở sau khoảng 18 ngày. Động cơ, góc đảo và công tắc hành trình phải phù hợp khay và tải thật. |
| Tuần hoàn khí | Quạt bên trong giúp phân bố nhiệt và ẩm; phải kiểm tra độ đồng đều tại vị trí đặt trứng. Quạt này có thể chạy khi bóng sưởi đang bật. |
| Thông khí | Luôn bảo đảm trao đổi khí tối thiểu; không bịt kín hoàn toàn để giữ nhiệt hoặc giữ ẩm. Có thể bổ sung thông khí chủ động khi cần, đồng thời theo dõi mất nhiệt và mất ẩm. |
| Lịch và vận hành | Lưu thời điểm bắt đầu lứa, giai đoạn, thiết lập và nhật ký. Sau khi Pi khởi động lại không được tự đặt lại ngày ấp. Cần có cách giữ thời gian đúng khi mất mạng/mất điện. |
| Bảo vệ | Phát hiện lỗi cảm biến, quá nhiệt, lỗi cơ cấu đảo và cạn nước nếu bộ tạo ẩm cần nước. Ngắt sưởi độc lập với lựa chọn của RL; bộ ngắt phần cứng phải đúng định mức tải. |

Các nguồn thực tế nhấn mạnh nhiệt độ, độ ẩm, thông khí và đảo trứng cùng ảnh hưởng đến kết quả nở. Lịch tham khảo cho gà khoảng 21 ngày. Nhu cầu môi trường bên ngoài và cấu trúc máy phải được xét khi áp dụng các giá trị trên.

## Điều cần sửa so với phương án hộp nhiệt trước đây

- 27 trạng thái, 5 action và PWM 40%/50% là lựa chọn thử nghiệm cũ, chưa phải thông số đã chốt cho máy ấp thực tế.
- Không loại mọi tổ hợp sưởi và quạt cùng hoạt động. Đặc biệt, quạt tuần hoàn và sưởi đồng thời là tình huống bình thường của kiến trúc máy có quạt.
- Không dùng 42°C làm giới hạn được phép đối với phôi. Mốc này và KSD301 50°C trong thiết kế hộp trước đây chỉ liên quan đến lớp dự phòng quá nhiệt của thiết bị, không xác nhận an toàn ấp nở. Ngưỡng cảnh báo và ngắt cho máy ấp phải được xác định lại sau hiệu chỉnh và đo độ trễ.
- Quạt đưa khí ngoài vào chỉ giúp hạ nhiệt về gần điều kiện bên ngoài; nếu phòng nóng hơn mục tiêu thì cần thay đổi điều kiện đặt máy hoặc bổ sung giải pháp làm mát phù hợp.
- Tạo ẩm chỉ là tác động tăng ẩm. Giảm ẩm bằng thông khí chỉ hữu hiệu khi khí ngoài có hàm lượng hơi nước thấp hơn; RH ngoài thấp hơn chưa đủ để kết luận nếu nhiệt độ khác nhau. Cần đánh giá môi trường đặt máy nếu muốn cam kết giữ ẩm tự động trong mọi điều kiện.

## Phần cứng đang chuẩn bị và khoảng thiếu

Danh sách cũ có Pi 4, DS18B20, bóng 12V–21W và đui, adapter 12V dự kiến 5A, một quạt 12V, hai module MOSFET, OLED và hai LED cùng vật tư nối dây. Đây là cấu hình dự kiến/đã ghi trạng thái đặt mua, chưa phải xác nhận toàn bộ phần cứng đã nhận và đạt thử nghiệm.

Đối chiếu cột Trạng thái trong `DANH_SACH_MUA_HOP_AP_CO_DAY_NOI.docx` ngày 12/11/2026. “Đã đặt mua” không có nghĩa đã nhận hàng hoặc đã thử đạt. Các mục có dấu gạch được hiểu là chưa ghi nhận đã đặt; không tự suy ra những món trao đổi trong chat đã được mua.

| Chức năng máy ấp | Linh kiện và trạng thái trong tài liệu | Mapping vào thiết kế thực tế | Phần còn thiếu hoặc cần xác minh |
|---|---|---|---|
| Điều khiển và lịch ấp | Pi 4, nguồn Pi, thẻ microSD được ghi dự kiến tận dụng từ giữa kỳ; không thuộc 23 dòng mua mới | Chạy chương trình, ghi log, lưu ngày bắt đầu lứa và điều khiển các tải | Kiểm kê thực tế; viết phần mềm máy ấp. Giữ thời gian đúng và phục hồi lịch sau khởi động lại; cân nhắc RTC có pin nếu cần vận hành không mạng. |
| Đo nhiệt độ vùng trứng | DS18B20 và trở 4,7 kΩ được ghi là tận dụng | Đo tại vùng khay; dùng để phản hồi điều khiển | Hiệu chỉnh và đo nhiều vị trí bằng nhiệt kế tham chiếu. Cảm biến ngoài hộp là lựa chọn bổ sung, chưa xác nhận đã mua. |
| Tạo nhiệt | Bóng 12V–21W, đui đúng chân và MOSFET thứ nhất: đã đặt mua | Giữ nguyên nhánh sưởi, điều khiển bằng Pi | Giá đui và chắn nhiệt chưa ghi đã đặt. Chưa xác nhận 21W đủ với thông khí và tải khay thật, hoặc các mức PWM trung gian có ích. |
| Tuần hoàn khí | Quạt 12V cỡ 50 mm và MOSFET thứ hai: đã đặt mua | Bố trí làm quạt tuần hoàn trong hộp ở mức đã thử; được phép chạy đồng thời với bóng | Thử phân bố gió và nhiệt tại cả 4 vị trí trứng. Một quạt không tạo thành hai kênh tuần hoàn và hút khí độc lập. |
| Trao đổi khí | Hộp: đã đặt mua; chưa có cơ cấu thông khí độc lập trong BOM | Tạo đường vào/ra bảo đảm trao đổi khí tối thiểu | Chọn vị trí và độ mở bằng thử nghiệm. Chỉ bổ sung quạt hút/cửa gió có điều khiển khi thiết kế yêu cầu thông khí chủ động; chưa chốt phải mua quạt thứ hai. |
| Đo độ ẩm | Chưa có cảm biến RH trong BOM | Bổ sung SHT31 hoặc tương đương; có thể dùng chung bus I²C với OLED nếu địa chỉ và điện áp phù hợp | Cảm biến và dây nối. DS18B20 hiện tại không đo RH. |
| Tự tăng độ ẩm | Chưa có bộ tạo ẩm, bơm hoặc cơ cấu cấp nước điều khiển được | Bổ sung một phương án tạo ẩm có công suất phù hợp hộp nhỏ | Bình nước/bề mặt bay hơi hoặc bộ phun có driver; kênh điều khiển và nguồn đúng điện áp. Nếu chỉ dùng khay nước và thêm nước thủ công thì chưa phải tự điều chỉnh RH. |
| Giảm ẩm | Chưa có cơ cấu riêng | Tắt tạo ẩm và điều chỉnh trao đổi khí nếu điều kiện khí ngoài cho phép | Đánh giá nhiệt/ẩm phòng trước khi cam kết điều khiển RH theo cả hai chiều. |
| Đảo trứng | Chưa có khay, động cơ hay driver trong BOM | Khay 2 × 2; đảo theo lịch, dừng khi chuyển nở | Cơ cấu cơ khí, động cơ phù hợp tải và driver. Nếu dùng động cơ DC đảo chiều cần driver đảo chiều; một MOSFET đóng/cắt đơn không tự thay thế chức năng đó. Đảo bằng tay theo lịch là phương án thủ công, chưa phải đảo tự động. |
| Hiển thị | OLED đã đặt; LED đỏ, LED xanh và hai trở 330 Ω chưa ghi đã đặt | Hiển thị T/RH, ngày/giai đoạn, trạng thái tải và lỗi; LED báo trạng thái | Hoàn thiện các món chưa đặt và chương trình hiển thị. Buzzer là phần bổ sung nếu cần cảnh báo bằng âm thanh. |
| Nguồn và chia nhánh | Adapter 12V, jack DC cái và 2 đầu nối gạt 5 lỗ: đã đặt; dây nguồn, Dupont và vật tư cố định/cách điện chưa ghi đã đặt | Tận dụng nguồn 12V cho các tải 12V; Pi dùng nguồn riêng | Xác nhận nhãn adapter, cực tính và dòng. Tính tổng tải và khởi động khi thêm bơm/động cơ; mở rộng đầu chia nếu hết lỗ. Hạ áp riêng khi chọn tải 5V. |
| Bảo vệ | Công tắc nhiệt, cầu chì/đế, đầu cos và gen bảo vệ chưa ghi đã đặt | Bảo vệ đường điện và ngắt sưởi độc lập; bố trí nước cách bo điện | Chọn đúng định mức và kiểm thử. KSD301 50°C nếu lắp đúng không được coi là ngưỡng bảo vệ phôi; các ngưỡng vận hành cần xác định riêng. |

Hai MOSFET đã đặt hiện được phân cho bóng và quạt tuần hoàn. Bộ tạo ẩm, thông khí chủ động và đảo khay cần được đánh giá riêng theo cách điều khiển, điện áp và dòng thực; không mặc định mua thêm cùng một loại MOSFET cho mọi cơ cấu.

## Kiến trúc điều khiển đề xuất

Tách trách nhiệm thành các lớp có mục tiêu rõ ràng:

1. Lịch ấp quyết định giai đoạn, mục tiêu môi trường và việc cho phép đảo trứng. Đảo theo lịch, không để tác tử tùy ý bỏ đảo hoặc đảo lúc sắp nở.
2. Quạt tuần hoàn chạy ở mức được kiểm chứng; thông khí có mức tối thiểu. Lớp bảo vệ luôn có quyền ngắt sưởi hoặc dừng tải lỗi.
3. Bộ điều khiển môi trường điều chỉnh sưởi, tạo ẩm và phần thông khí bổ sung. Trước hết kiểm tra bằng điều khiển theo ngưỡng/PID để có số liệu nền, sau đó huấn luyện và so sánh RL trên cùng bài toán.

Nếu dùng một tác tử chung, action là tổ hợp công suất sưởi, bật/tắt tạo ẩm và mức thông khí bổ sung. Ví dụ ba mức sưởi, hai mức tạo ẩm, hai mức thông khí tạo tối đa 12 tổ hợp trước khi áp dụng các ràng buộc. Đây chỉ là ví dụ về cấu trúc; duty và tập tổ hợp cuối cùng phải được chọn từ đặc tính tải và thử nghiệm. Quạt tuần hoàn không mặc định bị tắt trong action sưởi.

Trạng thái ứng viên gồm giai đoạn, sai lệch nhiệt độ, xu hướng nhiệt và sai lệch độ ẩm; cân nhắc điều kiện phòng và xu hướng ẩm nếu số liệu cho thấy thiếu chúng làm quyết định không nhất quán. Chưa chốt số khoảng chia hoặc kích thước Q-table khi chưa chốt phần cứng và thu dữ liệu.

Reward phải phản ánh việc giữ nhiệt và ẩm theo giai đoạn, thời gian lệch khỏi vùng mục tiêu và năng lượng. Không để tiết kiệm điện bù điểm cho việc vi phạm giới hạn môi trường. Điều kiện bảo vệ vẫn nằm ngoài reward và Q-table.

## Thực nghiệm cần có

1. Hiệu chỉnh cảm biến và kiểm tra nhiệt/ẩm tại nhiều vị trí khay.
2. Thử riêng sưởi, thông khí và tạo ẩm; ghi cả ảnh hưởng chéo giữa nhiệt và ẩm trong các điều kiện phòng dự kiến.
3. Chạy thử với tải nhiệt mô phỏng trứng, kiểm tra ổn định trước khi dùng trứng có phôi. Kiểm tra riêng lịch đảo, hành trình, phục hồi sau mất điện và các nhánh bảo vệ.
4. Khớp mô hình nhiệt và ẩm; huấn luyện trong mô phỏng, đánh giá trên các tình huống khác với lúc huấn luyện. Không cho tác tử khám phá ngẫu nhiên trên trứng có phôi.
5. Với thử nghiệm ấp thật, lưu log xuyên suốt lứa và đánh giá cả kết quả nở. Cần phân biệt sai số cảm biến, sai số điều khiển và chênh lệch giữa các vị trí trứng.

## Nguồn đối chiếu

- [Brinsea Maxi 48 manual](https://www.brinsea.com/manuals/Maxi48ZoologicaManualUS.pdf): cấu hình máy, nhiệt độ đặt mặc định, lịch đảo và cảnh báo.
- [Brinsea Humidity in Incubation](https://www.brinsea.com/t-Humidity.aspx): hướng dẫn RH khởi đầu cho trứng gà và điều chỉnh theo mất nước của trứng.
- [Utah State University Hatching and Caring for Chicks](https://extension.usu.edu/utah4h/research/hatching-and-caring-for-chicks): chu kỳ ấp, đảo trứng, giai đoạn nở.
- [University of Maine Hatching Your Own Chicks](https://extension.umaine.edu/publications/2072e/): vai trò tuần hoàn khí và chuẩn bị máy trước khi đặt trứng.
- [Mississippi State University Incubation temperature requirements](https://extension.msstate.edu/agriculture/livestock/poultry/incubation-temperature-requirements): tác hại của nhiệt độ cao và khác biệt giữa máy có quạt và không có quạt.
