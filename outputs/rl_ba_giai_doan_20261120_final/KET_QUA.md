# Ba giai đoạn — kết quả mô phỏng

Chỉ là dung sai kỹ thuật đề xuất. Chưa xác nhận điều kiện ấp thật, chưa thay Q-table Pi.

|Ngày|Mốc °C|Vùng kỹ thuật °C|Trong vùng %|Đổi bóng/10 phút|Bảo vệ % bước|Đạt gate mô phỏng|
|---|---|---|---|---|---|---|
|1–10|37.8|37.6–38.0|95.12|32.3|2.02|False|
|11–17|37.5|37.3–37.7|97.42|6.0|0.00|True|
|18–21|37.2|37.0–37.4|97.91|6.1|0.00|True|

Các chỉ số là trung bình 192 kịch bản 600s riêng từng giai đoạn, cùng mô hình cũ. Không chứng minh ổn định 21 ngày hay tỷ lệ nở.
Guard38→37°C giữ nguyên. Vùng đầu chạm ngưỡng guard; không coi đạt gate mô phỏng là cho phép dùng sinh học.
CSV chuyển giai đoạn dùng 10 phút/giai đoạn để minh họa phần mềm, giữ nguyên bộ nhớ nhiệt; không mô phỏng phát triển phôi theo ngày.
Lịch thật tham chiếu nguồn: ngày1–10:37.8..38.0; ngày11–17:37.5; ngày18–21:37.2. Dung sai của demo là đề xuất riêng.
