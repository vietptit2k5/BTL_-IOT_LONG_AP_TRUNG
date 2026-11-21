# Mô phỏng ấp 3 giai đoạn — Q2 dịch mốc so với thermostat

CHỈ MÔ PHỎNG (20 seed/kịch bản), mô hình 5 s nhận dạng từ lượt đo 20/11 ở 37,5 °C. Chưa kiểm chứng trên hộp thật ở 37,8/37,2 °C. Mỗi đoạn tính từ lúc đổi ngày (hoặc giao điều khiển).

| Kịch bản | Ngày | Mốc °C | Bộ điều khiển | Vào vùng sau (s) | Trong vùng sau khi vào (%) | MAE (°C) | Đổi mức/10 phút | Bước bảo vệ |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| giu_ngay_05_gd1 | 5 | 37.8 | Q2 dịch mốc | 14 | 99.3 | 0.063 | 9.2 | 0.0 |
| giu_ngay_05_gd1 | 5 | 37.8 | Thermostat | 14 | 89.9 | 0.114 | 54.5 | 0.0 |
| giu_ngay_14_gd2 | 14 | 37.5 | Q2 dịch mốc | 14 | 99.5 | 0.061 | 9.7 | 0.0 |
| giu_ngay_14_gd2 | 14 | 37.5 | Thermostat | 14 | 89.6 | 0.115 | 55.8 | 0.0 |
| giu_ngay_19_gd3 | 19 | 37.2 | Q2 dịch mốc | 13 | 99.7 | 0.057 | 11.4 | 0.0 |
| giu_ngay_19_gd3 | 19 | 37.2 | Thermostat | 13 | 90.4 | 0.114 | 55.4 | 0.0 |
| demo_5_12_19 | 5 | 37.8 | Q2 dịch mốc | 14 | 99.4 | 0.064 | 11.6 | 0.0 |
| demo_5_12_19 | 12 | 37.5 | Q2 dịch mốc | 9 | 99.4 | 0.061 | 11.8 | 0.0 |
| demo_5_12_19 | 19 | 37.2 | Q2 dịch mốc | 9 | 99.4 | 0.057 | 12.4 | 0.0 |
| demo_5_12_19 | 5 | 37.8 | Thermostat | 14 | 89.8 | 0.115 | 52.9 | 0.0 |
| demo_5_12_19 | 12 | 37.5 | Thermostat | 13 | 90.0 | 0.115 | 53.5 | 0.0 |
| demo_5_12_19 | 19 | 37.2 | Thermostat | 15 | 90.0 | 0.115 | 54.5 | 0.0 |
| nhay_nguoc_19_5 | 19 | 37.2 | Q2 dịch mốc | 13 | 99.8 | 0.058 | 12.7 | 0.0 |
| nhay_nguoc_19_5 | 5 | 37.8 | Q2 dịch mốc | 26 | 99.3 | 0.066 | 9.3 | 0.0 |
| nhay_nguoc_19_5 | 19 | 37.2 | Thermostat | 13 | 89.6 | 0.115 | 53.0 | 0.0 |
| nhay_nguoc_19_5 | 5 | 37.8 | Thermostat | 28 | 88.8 | 0.115 | 55.5 | 0.0 |

## Dừng sớm / dự phòng

- giu_ngay_05_gd1 / rl: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- giu_ngay_05_gd1 / thermostat: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- giu_ngay_14_gd2 / rl: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- giu_ngay_14_gd2 / thermostat: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- giu_ngay_19_gd3 / rl: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- giu_ngay_19_gd3 / thermostat: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- demo_5_12_19 / rl: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- demo_5_12_19 / thermostat: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- nhay_nguoc_19_5 / rl: dừng 0/20 lượt ; dự phòng làm mát 0 lần
- nhay_nguoc_19_5 / thermostat: dừng 0/20 lượt ; dự phòng làm mát 0 lần
