# Cải thiện RL offline, phiên bản 2

Trạng thái: **SIMULATION_CANDIDATE_ONLY**.

Đây là phát triển trên lượt đo đã được xem trước, không phải kiểm chứng độc lập trên hộp.
Bảo vệ mềm mô phỏng 38→37°C dùng chung cho RL và đối chứng; khác quy trình mô phỏng cũ (38,5°C).
Không so trực tiếp chỉ số cũ và mới để quy toàn bộ cải thiện cho RL. Duty chưa phải điện năng.

162 state, 9 action phối hợp bóng/quạt; không phạt đổi action vì đã bỏ action trước khỏi state.
Chọn trên validation: **q-learning, 4000 episode**, weights={'hot': 10.0, 'duty': 0.05}.
Sau khi chốt, kiểm tra thêm các tình huống nhiễu và hai seed huấn luyện mới; không chọn lại theo kết quả đó.

| Bộ điều khiển | MAE mô phỏng °C | Trong vùng % | Seed thấp nhất % |
|---|---:|---:|---:|
| Đối chứng {'kind': 'thermostat', 'band': 0.1, 'fan_mode': 'trend'} | 0.149 | 96.6 | — |
| RL, trung bình 5 seed | 0.088 | 97.4 | 97.3 |

RL hơn đối chứng theo điều kiện đã đặt: **True**.
Ra ngoài miền mô hình: 0.00% tình huống; bảo vệ 0.56% bước; fallback 0.00% bước.
MAE có phạt phần còn lại nếu tình huống ra ngoài miền; không phải số đo sai số trên thiết bị.

## Kiểm tra từng seed

| Seed | MAE °C | Trong vùng % |
|---:|---:|---:|
| 11 | 0.090 | 97.3 |
| 29 | 0.089 | 97.5 |
| 47 | 0.087 | 97.4 |
| 73 | 0.087 | 97.4 |
| 101 | 0.088 | 97.4 |

## Tiếp theo

Chạy kiem_tra_giu_nhiet.py để thu lượt giữ nhiệt độc lập. Bộ này chưa cho chạy RL lên GPIO.
Cần so RL và đối chứng trên phần cứng cùng điều kiện trước khi kết luận nâng hiệu năng máy ấp.
Mô hình vẫn địa phương, một đầu dò, cùng một phiên; chưa đo độ ẩm, W/Wh hoặc độ đều nhiệt.

Thuật toán Expected SARSA: https://www.incompleteideas.net/book/RLbook2020.pdf (Chương 6).
