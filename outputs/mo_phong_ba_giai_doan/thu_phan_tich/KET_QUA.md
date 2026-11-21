# Phân tích lượt ấp 3 giai đoạn

> **Có lượt MÔ PHỎNG** (đánh dấu ⚠). Không dùng các số đó như số đo thật.

Chỉ số trong vùng/MAE/độ lệch chuẩn tính **từ lúc nhiệt đã vào vùng** của đoạn (sau khi đổi ngày cần thời gian chuyển mốc, được báo riêng ở cột "Vào vùng sau"). Trọng số theo thời gian.

## Theo từng đoạn ngày

| Lượt | Bộ điều khiển | Ngày | GĐ | Mốc °C | Dài (s) | Vào vùng sau (s) | Trong vùng (%) | MAE (°C) | Độ lệch chuẩn (°C) | Đổi mức/10 phút | Bảo vệ (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MO_PHONG_demo_rl ⚠ | Q-learning 3 giai đoạn | 5 | 1 | 37,8 | 600 | 10 | 99,2 | 0,062 | 0,076 | 17,0 | 0 |
| MO_PHONG_demo_rl ⚠ | Q-learning 3 giai đoạn | 12 | 2 | 37,5 | 600 | 10 | 99,2 | 0,080 | 0,082 | 16,0 | 0 |
| MO_PHONG_demo_rl ⚠ | Q-learning 3 giai đoạn | 19 | 3 | 37,2 | 596 | 0 | 100,0 | 0,047 | 0,057 | 10,1 | 0 |
| MO_PHONG_demo_thermostat ⚠ | Thermostat 3 giai đoạn | 5 | 1 | 37,8 | 600 | 10 | 89,0 | 0,114 | 0,130 | 50,0 | 0 |
| MO_PHONG_demo_thermostat ⚠ | Thermostat 3 giai đoạn | 12 | 2 | 37,5 | 600 | 20 | 86,2 | 0,117 | 0,135 | 55,0 | 0 |
| MO_PHONG_demo_thermostat ⚠ | Thermostat 3 giai đoạn | 19 | 3 | 37,2 | 596 | 0 | 89,9 | 0,110 | 0,127 | 57,4 | 0 |

## So sánh theo giai đoạn

| Giai đoạn | Mốc °C | Q-learning 3 giai đoạn ⚠: trong vùng % / MAE °C / đổi mức | Thermostat 3 giai đoạn ⚠: trong vùng % / MAE °C / đổi mức |
|---|---:|---|---|
| 1 | 37,8 | 99,2 / 0,062 / 17,0 | 89,0 / 0,114 / 50,0 |
| 2 | 37,5 | 99,2 / 0,080 / 16,0 | 86,2 / 0,117 / 55,0 |
| 3 | 37,2 | 100,0 / 0,047 / 10,1 | 89,9 / 0,110 / 57,4 |

## Tình trạng lượt

- MO_PHONG_demo_rl (Q-learning 3 giai đoạn): kết thúc bình thường; 0 lỗi; 360 mẫu điều khiển.
- MO_PHONG_demo_thermostat (Thermostat 3 giai đoạn): kết thúc bình thường; 0 lỗi; 360 mẫu điều khiển.
