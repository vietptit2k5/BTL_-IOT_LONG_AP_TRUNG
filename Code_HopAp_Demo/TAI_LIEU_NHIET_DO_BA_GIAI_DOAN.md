# Nhiệt độ ba giai đoạn ấp trứng gà — nguồn tham khảo trước huấn luyện

Tra cứu ngày 20/11/2026. Chưa áp dụng lịch này vào chương trình GPIO hoặc Q-table.

## Nguồn Việt Nam có đủ ba giai đoạn

Trung tâm Khuyến nông Quốc gia, **Bản tin Khuyến nông Việt Nam số 04/2026**, bài “Các biện pháp tăng tỷ lệ nở đối với trứng gia cầm”, mục 3 “Quản lý kỹ thuật ấp”, trang in **41** (trang **43** của PDF).

[Mở PDF chính thức tại trang tương ứng](https://khuyennongvn.gov.vn/data/documents/0/2026/11/09/hangweb/ban-tin-khuyen-nong-so-4-2026.pdf#page=43)

|Giai đoạn theo nguồn|Ngày ấp|Nhiệt độ nguồn nêu|Ẩm độ nguồn nêu|
|---|---|---|---|
|Đầu|1–10|37.8–38.0°C|60%|
|Giữa|11–17|37.5°C|55%|
|Cuối|18–21|37.2°C|65–70%|

Nguồn chỉ nêu một mức nhiệt ở hai giai đoạn sau, không quy định khoảng dung sai quanh các mức đó. Không được viết rằng “nguồn yêu cầu ±0.2°C”. Bài viết cũng không cung cấp thiết kế máy cụ thể, vị trí đo, quy trình hiệu chuẩn, giống gà hoặc lịch điều khiển quạt riêng cho hộp xốp của nhóm. Đây là quy trình tham khảo có nguồn, không phải xác nhận hộp hiện tại đã đáp ứng điều kiện ấp thật.

## Đề xuất mốc để xây dựng demo

Chọn bộ ba **37.8 / 37.5 / 37.2°C** với lịch ngày **1–10 / 11–17 / 18–21** làm cấu hình nghiên cứu ban đầu. 37.8°C là lựa chọn ở đầu dưới của khoảng giai đoạn đầu do nguồn nêu; không tự đổi thành 37.9°C chỉ vì đó là trung điểm.

Khoảng thưởng RL, dung sai điều khiển và ngưỡng báo lỗi cần thiết kế/đánh giá riêng sau khi hiệu chuẩn cảm biến và đo phản ứng hộp. Chưa chốt các khoảng dao động sinh học hợp lệ từ bài báo này.

## Đối chiếu và giới hạn

- [Mississippi State University — Hatching Quality Chicks](https://accessibility.extension.msstate.edu/publications/hatching-quality-chicks): ví dụ máy có quạt 100°F (~37.8°C), buồng nở ba ngày cuối có thể thấp hơn 1°F (~0.56°C). Cách chia ngày khác nguồn Việt Nam; không ghép mốc ngày của nguồn này với nhiệt của nguồn khác để tạo một “chuẩn chung”.
- [Cobb Hatchery Management Guide](https://www.cobbgenetics.com/assets/Cobb-Files/Hatchery-Guide.pdf#page=18), mục 4.2: lịch nhiệt của máy đơn kỳ có thể điều chỉnh theo phát triển/nhiệt sinh ra của phôi; nhiệt không khí tối ưu còn tùy máy. Phần đo nhiệt vỏ trứng phân biệt nhiệt vỏ/phôi với nhiệt không khí. Không lấy mục tiêu vỏ trứng thay trực tiếp cho setpoint không khí của DS18B20.

Gợi ý trước đây chia 1–7 / 8–18 / 19–21 là cách tổ chức phân tích, không phải ba giai đoạn quy định bởi nguồn chính thức vừa tìm được. Khi dùng nguồn Việt Nam nêu trên, dùng đúng lịch 1–10 / 11–17 / 18–21 và ghi rõ tài liệu tham chiếu.

## Việc cần làm trước khi sửa chương trình

1. Xác nhận nhóm chọn quy trình tham khảo nào, đơn kỳ (cả mẻ cùng thời điểm bắt đầu) và vị trí đo khí tại khay.
2. Đối chiếu cảm biến với thiết bị tham chiếu; khảo sát độ đồng đều. Chưa coi một đầu dò hộp rỗng là nhiệt vỏ trứng.
3. Đánh giá bảo vệ mềm hiện có 38→37°C: mốc đầu 37.8°C gần ngưỡng ngắt. Không tăng/bỏ bảo vệ tự động chỉ để chạy được profile mới; cần thiết kế lại biên an toàn có căn cứ trước lượt thử thật.
4. Huấn luyện ứng viên có giai đoạn/mục tiêu trong state hoặc ba chính sách riêng. Q-table hiện tại cố định 37.5°C chưa hỗ trợ đủ ba mốc.
5. Lưu ngày bắt đầu mẻ để khởi động lại không mất ngày ấp. Chế độ demo rút ngắn thời gian phải ghi rõ là giả lập lịch, không phải phát triển phôi thật.
6. DHT11 vẫn chỉ giám sát. RH trong bảng là yêu cầu tham khảo; hệ thống hiện chưa có cơ cấu tự động bảo đảm các mức RH đó.

Ngày/giai đoạn là cách chọn mục tiêu, chưa mô phỏng được nhiệt sinh học của phôi. Kết quả huấn luyện hoặc đổi setpoint trên hộp rỗng không chứng minh tỷ lệ nở.
