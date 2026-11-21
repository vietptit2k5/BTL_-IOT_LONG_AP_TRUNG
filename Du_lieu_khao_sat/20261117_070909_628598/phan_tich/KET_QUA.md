# Kết quả khảo sát nhiệt

Trạng thái: **NO_VALIDATED_REWARD_CANDIDATE**.

Dốc nhiệt bên dưới được tính từ CSV đầu vào. Dữ liệu mô phỏng được ghi riêng; không coi là phép đo trên hộp.

Mục tiêu 37.5°C, dung sai ±0.5°C. Có 1 lượt và 35 đoạn đáp ứng.

| Đoạn | Bóng % | Quạt % | Quan sát / yêu cầu (s) | Đủ liên tục | ΔT °C | Dốc °C/phút |
|---|---:|---:|---:|---|---:|---:|
| cho_cam_bien | 0 | 0 | 0.0 / — | — | +0.000 | chưa đủ mẫu |
| nen_ban_dau | 0 | 100 | 59.0 / — | — | -0.875 | -0.968 |
| lam_am_co_gioi_han | 75 | 100 | 178.0 / — | — | +4.063 | +1.503 |
| thu_1_bong_50_quat_75 | 50 | 75 | 119.0 / 120 | có | +1.250 | +0.617 |
| thu_1_bong_25_quat_75 | 25 | 75 | 119.0 / 120 | có | -0.937 | -0.534 |
| thu_1_bong_50_quat_100 | 50 | 100 | 119.0 / 120 | có | +0.000 | +0.062 |
| thu_1_bong_100_quat_100 | 100 | 100 | 77.0 / 120 | chưa | +1.875 | +1.580 |
| bao_ve_mem_1 | 0 | 100 | 59.0 / — | — | -1.000 | -1.282 |
| thu_1_bong_100_quat_100 | 100 | 100 | 42.0 / 120 | chưa | +0.500 | +0.948 |
| thu_1_bong_100_quat_75 | 100 | 75 | 24.0 / 120 | chưa | +0.563 | +1.343 |
| bao_ve_mem_2 | 0 | 100 | 50.0 / — | — | -1.000 | -1.470 |
| thu_1_bong_100_quat_75 | 100 | 75 | 61.0 / 120 | chưa | +1.000 | +1.201 |
| bao_ve_mem_3 | 0 | 100 | 51.0 / — | — | -1.000 | -1.472 |
| thu_1_bong_100_quat_75 | 100 | 75 | 32.0 / 120 | chưa | +0.375 | +0.957 |
| thu_1_bong_25_quat_100 | 25 | 100 | 119.0 / 120 | có | -1.562 | -0.901 |
| thu_1_bong_75_quat_75 | 75 | 75 | 119.0 / 120 | có | +1.938 | +1.042 |
| thu_1_bong_0_quat_100 | 0 | 100 | 119.0 / 120 | có | -2.750 | -1.571 |
| thu_1_bong_75_quat_100 | 75 | 100 | 119.0 / 120 | có | +1.375 | +0.824 |
| thu_1_bong_0_quat_75 | 0 | 75 | 119.0 / 120 | có | -2.125 | -1.186 |
| thu_2_bong_75_quat_75 | 75 | 75 | 119.0 / 120 | có | +1.875 | +1.091 |
| thu_2_bong_75_quat_100 | 75 | 100 | 115.0 / 120 | chưa | +2.063 | +1.056 |
| bao_ve_mem_4 | 0 | 100 | 51.0 / — | — | -1.000 | -1.377 |
| thu_2_bong_75_quat_100 | 75 | 100 | 3.0 / 120 | chưa | -0.125 | chưa đủ mẫu |
| thu_2_bong_100_quat_100 | 100 | 100 | 70.0 / 120 | chưa | +1.125 | +1.069 |
| bao_ve_mem_5 | 0 | 100 | 50.0 / — | — | -1.000 | -1.465 |
| thu_2_bong_100_quat_100 | 100 | 100 | 48.0 / 120 | chưa | +0.563 | +0.911 |
| thu_2_bong_50_quat_75 | 50 | 75 | 119.0 / 120 | có | +0.312 | +0.114 |
| thu_2_bong_0_quat_75 | 0 | 75 | 119.0 / 120 | có | -2.875 | -1.553 |
| thu_2_bong_50_quat_100 | 50 | 100 | 119.0 / 120 | có | -0.250 | -0.031 |
| thu_2_bong_0_quat_100 | 0 | 100 | 119.0 / 120 | có | -2.125 | -1.172 |
| thu_2_bong_25_quat_75 | 25 | 75 | 119.0 / 120 | có | -0.437 | -0.140 |
| thu_2_bong_25_quat_100 | 25 | 100 | 119.0 / 120 | có | +0.125 | +0.070 |
| thu_2_bong_100_quat_75 | 100 | 75 | 119.0 / 120 | có | +4.688 | +2.485 |
| ngung_suoi_cuoi | 0 | 100 | 119.0 / — | — | -2.062 | -1.244 |
| giu_quat_cuoi | 0 | 100 | 9.0 / — | — | -0.250 | chưa đủ mẫu |

Ghi chú lượt đo:

- Tổ hợp bóng 100%/quạt 100% chưa có cửa sổ 120s liên tục; không đưa tổ hợp đó vào Q-table ứng viên.

## So sánh CHỈ TRONG MÔ PHỎNG

| Bộ điều khiển | MAE °C | Trong vùng % | Ngoài miền mô hình % |
|---|---:|---:|---:|
| Đối chứng đã chỉnh trên validation | 0.157 | 95.7 | 0.0 |
| Q-learning, trung bình hai seed | 0.680 | 65.8 | 1.6 |

Hệ số ứng viên chọn bằng validation: `{'hot': 10.0, 'duty': 0.2, 'switch': 0.03}`.
Q-learning hơn đối chứng theo tiêu chí đã định trên test mô phỏng: **False**.
Không chọn lại hệ số theo test; không tự triển khai Q-table lên GPIO.

## Giới hạn

- Tốc độ tăng/giảm nhiệt không xác định duy nhất mức quan trọng của sai số, quá nhiệt và tiết kiệm. Mục tiêu và dung sai là yêu cầu thiết kế.
- Hệ số chọn bằng tiêu chí chung: tránh ngoài miền/ngắt bảo vệ, hạn chế vượt nhiệt, đạt vùng mục tiêu rồi cân nhắc MAE và duty. Không so tổng reward có thang điểm khác nhau.
- Duty là đại lượng thay thế mức điều khiển; chưa đo W/Wh/RPM. Một đầu dò không chứng minh độ đều nhiệt hoặc hiệu quả ấp nở.
- Mô hình địa phương giả định điều kiện phòng/bố trí giống lúc đo; nhiễu mô phỏng lấy từ sai số khớp, không phải khoảng tin cậy vật lý.
- Cần thêm lượt đo độc lập và so điều khiển thực trên cùng hộp trước khi nói RL nâng hiệu năng.
