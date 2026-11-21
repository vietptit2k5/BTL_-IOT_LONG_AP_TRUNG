# Phân tích gợi ý setup demo từ ghi âm

Ngày đối chiếu: 12/11/2026.

Nguồn: [10.08 09-11-2026.m4a](<10.08 09-11-2026.m4a>), thời lượng khoảng 1 phút 51 giây.

## Kết quả chính

Phần nội dung nhận dạng ổn định cho thấy giảng viên gợi ý một hộp điều khiển nhiệt thực: bóng làm tăng nhiệt, quạt làm giảm nhiệt, hộp hạn chế ảnh hưởng của môi trường, đèn báo cho phép quan sát từ bên ngoài. Sau khi có các thiết bị chấp hành và điều khiển được chúng, nhóm áp dụng reinforcement learning.

Đây là căn cứ cho mô hình demo điều khiển nhiệt hai chiều đang chuẩn bị. Chưa có căn cứ đủ tin cậy trong các đoạn nhận dạng được để xem số 27 trạng thái, 5 hành động, PWM 40%/50%, các giai đoạn ấp hay điều khiển độ ẩm là yêu cầu bắt buộc của thầy.

## Phạm vi kiểm tra và độ tin cậy

Đã xử lý trực tiếp bản M4A trên máy bằng Whisper small và large-v3-turbo, đối chiếu toàn đoạn và một số đoạn cắt có mốc thời gian. Đây là đối chiếu nhận dạng giọng nói tự động, chưa phải bản chép lời được người nghe xác nhận toàn bộ. Các bảng dưới diễn giải ý, không phải trích nguyên văn.

Các đoạn khoảng 00:30–01:08 và 01:27–01:49 có những ý nhất quán giữa các lượt nhận dạng. Đoạn đầu khoảng 00:00–00:30 và đoạn chuyển ý khoảng 01:13–01:27 có nhiều từ không rõ. Những câu lặp vô nghĩa hoặc không khớp ngữ cảnh do bộ nhận dạng sinh ra đã bị loại khỏi căn cứ phân tích. Mốc thời gian là gần đúng.

## Nội dung theo mốc thời gian

| Mốc | Nội dung có thể rút ra | Ý nghĩa với setup demo |
|---|---|---|
| 00:00–00:14 | Nhận dạng chưa ổn định; có nhắc bóng và điều khiển, nhưng cách diễn đạt chưa xác minh được. | Chưa thể kết luận thầy bắt buộc dùng rơ-le, một số mức công suất cụ thể hay một loại linh kiện đóng cắt nhất định. |
| 00:14–00:48 | Thảo luận khả năng tỏa nhiệt của bóng sợi đốt; đưa đèn dùng để xông tinh dầu làm ví dụ nguồn nhiệt nóng. Các từ nói về vị trí đặt/gắn thiết bị còn chưa rõ. | Thầy cần một nguồn nhiệt thật có tác động quan sát được. Không suy ra yêu cầu bắt buộc về điện áp, công suất, kiểu đui hoặc vị trí cảm biến từ đoạn này. |
| 00:48–00:55 | Chọn bóng sợi đốt; tránh dùng bóng LED làm nguồn sưởi. | Bóng sợi đốt 12V–21W là phương án nhóm lựa chọn để thực hiện ý tưởng; chưa phải thông số đã xác nhận là do thầy chỉ định. |
| 00:55–00:59 | Một thiết bị tăng nhiệt, một thiết bị thổi khí để giảm nhiệt. | Bóng và quạt là hai thiết bị chấp hành của bài toán. Vai trò làm mát của quạt phù hợp với phương án hộp demo hiện tại. |
| 00:59–01:08 | Khi có và điều khiển được thiết bị thì áp dụng reinforcement learning. | Cần có tác động điều khiển lên môi trường thật. Lời gợi ý chưa xác định cụ thể thuật toán Q-learning, kích thước bảng Q, state, action hoặc reward. |
| 01:08–01:20 | Có ý phê bình việc đọc cảm biến/nhiệt độ CPU; câu đầy đủ còn nhận dạng chưa chắc. | Cùng với nội dung bóng và quạt, có cơ sở diễn giải rằng nhóm nên chuyển sang đối tượng nhiệt bên ngoài Pi. Không dùng đoạn này làm trích dẫn nguyên văn. |
| 01:20–01:50 | Đưa thiết bị vào hộp, hạn chế ảnh hưởng từ ngoài; đưa LED báo ra ngoài để biết trạng thái bật/tắt mà vẫn quan sát được khi đóng hộp. | Cần hộp và hiển thị trạng thái bên ngoài. Trong phần nhận dạng được, LED được nhắc trực tiếp; chưa xác nhận thầy bắt buộc dùng OLED hay đồng thời cả OLED và hai LED. |

## Phân biệt lời gợi ý với lựa chọn thiết kế

| Nội dung | Căn cứ hiện có |
|---|---|
| Bóng tạo nhiệt, quạt giảm nhiệt, hộp, đèn báo ngoài hộp, áp dụng RL | Có căn cứ trực tiếp từ các đoạn nhận dạng nhất quán của bản ghi âm. |
| Raspberry Pi 4, DS18B20, bóng 12V–21W, quạt 12V, MOSFET, adapter | Cấu hình nhóm chọn để thực hiện demo và tận dụng phần cứng đã có. Chưa xác nhận là toàn bộ mã/thông số thầy yêu cầu trong đoạn ghi âm. |
| Mục tiêu 37,5°C, bước 5 giây, 27 trạng thái và 5 hành động | Đề xuất trong thiết kế hộp ấp; chưa xác nhận là con số được thầy nêu trong các đoạn nhận dạng được. |
| Sưởi nhẹ 40%, quạt nhẹ 50% | Các mức thử kỹ thuật, phải đo hộp và kiểm tra khả năng khởi động của quạt trước khi chốt. |
| Độ ẩm, đảo trứng, lịch các giai đoạn ấp | Phần mở rộng theo ứng dụng ấp trứng. Chưa có căn cứ đủ tin cậy từ đoạn âm thanh này để xem là phần bắt buộc. |
| Công tắc nhiệt, cầu chì, giá đui, chắn nhiệt | Thành phần bảo vệ và lắp đặt theo cấu hình thực tế; không lấy việc chưa xác nhận trong âm thanh làm lý do bỏ qua yêu cầu lắp phù hợp. |

## Tác động đến thiết kế trạng thái và hành động

Không nên giải thích 5 hành động sưởi mạnh, sưởi nhẹ, nghỉ, làm mát nhẹ, làm mát mạnh là 5 giai đoạn sinh học của quá trình ấp. Đây là cách chia mức điều khiển cho hai thiết bị chấp hành.

Với thiết bị chỉ bật/tắt, một thiết kế cơ bản có thể thử 3 hành động: bật bóng và tắt quạt; tắt cả hai; tắt bóng và bật quạt. Khi có PWM phù hợp và các phép đo cho thấy mức trung gian có ích, có thể mở rộng lên 5 hành động. Cả hai cách đều là lựa chọn thiết kế cần giải thích và đánh giá; bản ghi âm chưa buộc nhóm chọn chính xác một trong hai.

27 trạng thái được đề xuất từ 9 khoảng sai lệch nhiệt và 3 xu hướng nhiệt. Đây cũng là lựa chọn mô hình hóa của nhóm, cần kiểm tra bằng mô phỏng và dữ liệu hộp thật.

Phần ghi âm xác định được nói đến quạt giảm nhiệt. Do đó, phương án hiện tại dùng quạt để trao đổi khí/làm mát vẫn phù hợp ý tưởng demo. Nếu chuyển sang máy ấp thực tế có quạt tuần hoàn chạy liên tục, nhóm sẽ phải thiết kế lại cách bố trí gió và hành động; đó là một bước mở rộng riêng.

## Setup nên hoàn thiện cho đúng phạm vi demo

1. Hoàn thiện hộp có nguồn nhiệt thật, cảm biến đo vùng không khí cần điều khiển và quạt có đường gió làm mát hữu hiệu. Vị trí cảm biến phải được kiểm tra bằng số đo, không suy ra từ những từ chưa rõ ở đầu bản ghi âm.
2. Điều khiển độc lập bóng và quạt; thử riêng từng tải trước khi ghép toàn hệ thống.
3. Đưa trạng thái ra mặt ngoài hộp. OLED và hai LED mà nhóm đã chọn có thể phục vụ mục đích này.
4. Đo đáp ứng nóng lên, nguội tự nhiên và nguội khi chạy quạt; từ đó chọn mô hình nhiệt, mức điều khiển và huấn luyện Q-table.
5. Trình diễn hệ thống tự tiến về mục tiêu và phản ứng khi có nhiễu. Đây là kịch bản triển khai đề xuất từ ý tưởng thầy; không phải lời nguyên văn hay một rubric đã được xác minh bằng bản ghi âm.

Trong báo cáo có thể diễn đạt: “Từ gợi ý của giảng viên về hộp điều khiển nhiệt dùng bóng sưởi và quạt, nhóm xây dựng mô hình điều khiển nhiệt bằng Q-learning. Không gian trạng thái, mức công suất và hàm thưởng được nhóm thiết kế và đánh giá thực nghiệm.”
