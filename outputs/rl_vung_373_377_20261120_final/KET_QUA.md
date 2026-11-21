# Q-learning vùng 37.3–37.7°C

PASS_SIMULATION_ONLY

Mục tiêu trung tâm 37.5°C; đây là mô phỏng phát triển, chưa được phép chạy Pi.

|Controller|Trong vùng %|MAE °C|Đổi bóng/10 phút|Đổi quạt/10 phút|Đoạn trong vùng dài nhất s|Hồi phục có phạt s|
|---|---|---|---|---|---|---|
|candidate|98.203|0.060|19.562|9.755|564.401|12.669|
|old_q|97.934|0.071|49.865|31.766|532.552|14.718|
|deadband_relay|46.918|0.204|13.818|13.500|38.125|40.602|
|fixed_50_75|49.379|0.254|1.490|1.224|200.208|141.443|

Không áp bộ lọc giữ action lên Q-table cũ. Chính sách mới được huấn luyện với previous action trong state và chi phí đổi mức trong reward.
Các chỉ số là trung bình 192 kịch bản mô phỏng, mỗi kịch bản 600s. Đoạn trong vùng dài nhất là trung bình độ dài tối đa của từng kịch bản. Recovery có phạt các đoạn chưa trở về, không phải chứng minh thời gian tối thiểu.
Xem chênh lệch ghép cặp và khoảng bootstrap trong ket_qua.json; khoảng này chỉ phản ánh các kịch bản trong cùng mô hình, không bao gồm sai số mô hình hoặc độ chính xác cảm biến.
Dữ liệu thật đo dài chưa có; mô hình cũ chỉ được kiểm chứng tốt ở chân trời ngắn. Không khẳng định giữ ổn định cả hộp/trứng hoặc tối ưu toàn cục.
Q-table Pi cũ không bị sửa. Cần kiểm tra mô hình và lượt thử thật độc lập trước khi triển khai.
