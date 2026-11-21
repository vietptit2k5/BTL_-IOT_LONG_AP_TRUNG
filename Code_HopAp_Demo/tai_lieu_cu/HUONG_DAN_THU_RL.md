> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Thử Q-learning trên hộp sau lượt thermostat

**Cập nhật sau pilot RL:** lượt RL đã hoàn tất 600 giây, MAE 0,0568°C so với 0,1214°C của thermostat; cả hai đạt 100% trong 37–38°C. Xem [kịch bản demo và giới hạn kết luận](KICH_BAN_DEMO_RL.md) và [báo cáo so sánh đo thực](../../outputs/so_sanh_RL_THUC_20261117/KET_QUA.md).

Lượt thermostat ngày 17/11/2026 đã hoàn tất: MAE **0,121°C**, **100%** thời gian trong 37–38°C, nhiệt **37,000–37,750°C**, không kích hoạt bảo vệ mềm. Đã xác nhận hộp rỗng, vị trí bóng/quạt/đầu dò và trạng thái nắp giữ nguyên.

Mô hình đóng băng dự báo 30 giây có RMSE **0,111°C**, tốt hơn dự báo giữ nguyên nhiệt hiện tại **0,223°C**. Khi phát lại gần 10 phút, sai số tăng đến RMSE **0,372°C**. Vì vậy bước tiếp theo là một **pilot đo thực có giám sát**, không coi kết quả mô phỏng là hiệu năng đã chứng minh.

## 1. Chế độ mới chạy gì?

- Dùng Q-table đã huấn luyện, không cập nhật Q và không khám phá ngẫu nhiên trên hộp thật.
- Seed pilot là **11**, seed đầu tiên của ứng viên cũ; không chọn seed theo kết quả đẹp nhất của lượt mới.
- **162 state, 9 action phối hợp bóng và quạt**, cập nhật quyết định mỗi 5 giây. DS18B20 vẫn được kiểm tra và ghi khoảng mỗi giây.
- Bộ nhớ sưởi dùng tham số 25 giây của mô hình, cập nhật từ PWM thực sự đã áp dụng trong phần mềm, gồm cả thời gian bóng bị giữ tắt khi khởi động quạt. Đây chưa phải phép đo công suất bóng.
- Bảo vệ mềm **38→37°C** có quyền ưu tiên hơn Q-table. Nhiệt đạt **40°C**, mất số đo hợp lệ quá **3 giây**, sai đầu dò, state ngoài miền hoặc state chưa học đều làm dừng pilot.
- Thời gian bảo vệ vẫn nằm trong 600 giây kiểm tra; không loại khỏi chỉ số.
- Sau khi kết thúc/ngắt có kiểm soát, tắt bóng và giữ quạt 100% thêm 10 giây rồi tắt hết theo bộ điều khiển hiện có.

Gói `goi_thu_rl_20261117.json` chỉ dành cho pilot này. File ứng viên mô phỏng cũ vẫn giữ `deploy_allowed=false`; chế độ mặc định vẫn là thermostat. Chỉ lệnh có `--bo-dieu-khien thu-rl` mới dùng gói pilot. Không cần sửa dây hoặc thêm linh kiện.

## 2. Chuẩn bị điều kiện đầu

Để hộp nguội gần **26–27°C**, tương tự lúc bắt đầu lượt thermostat. Có thể mở nắp cho nguội trước, rồi đưa nắp về đúng trạng thái lúc đo. Không thêm nước/trứng hoặc chuyển đầu dò, bóng, quạt.

Chương trình từ chối bắt đầu pilot nếu nhiệt đầu dò lúc đầu **trên 30°C**. Khi đó để nguội rồi chạy lại; không tăng ngưỡng này để chạy tiếp. Nhiệt đầu dò giống nhau chưa bảo đảm mọi phần của hộp có cùng lịch sử nhiệt, nên nếu muốn kết luận chắc vẫn cần lặp và đổi thứ tự hai bộ điều khiển.

## 3. Chép và chạy từ Terminal laptop Windows

Chạy ở dòng dạng `D:\...>`. Nếu đang ở `pi@pi:~ $`, gõ `exit` để về laptop trước khi dùng đường dẫn `D:\...`.

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
```

Chép cả thư mục để cập nhật bộ ghi/quan sát PWM và gói Q-table. Dừng chương trình cũ đang dùng GPIO18/23.

Xem kế hoạch; lệnh này không bật tải:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl --dry-run"
```

Khi hộp đã đủ nguội, vẫn rỗng và có người theo dõi, cấp USB-C riêng cho Pi và adapter 12 V cho tải, rồi chạy:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl"
```

Trình tự giống lượt đối chứng: làm ấm bóng 75%/quạt 100% tối đa 10 phút, bắt đầu đo khi đạt 37°C, rồi điều khiển bằng Q-table **10 phút**. OLED hiển thị nhiệt và mức bóng/quạt qua bộ hiển thị hiện có. Lượt đo cũ không có RH. Khi đã lắp DHT11, xem [hướng dẫn độ ẩm](../HUONG_DAN_DHT11.md), cài thư viện vào `.venv` rồi dùng `.venv/bin/python kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl --dht11` trên Pi. RH chỉ để theo dõi trên Terminal/OLED/CSV, không đổi Q-table, state, action hoặc reward.

Ctrl+C để dừng. Nếu tải không tắt theo chương trình, ngắt adapter 12 V. Không chạy hai chương trình điều khiển cùng lúc.

Nếu báo state chưa học/ngoài miền, giữ log và chuyển sang phân tích nguyên nhân; không sửa visits, bỏ kiểm tra hoặc chạy action ngẫu nhiên để ép đủ thời gian.

## 4. Lấy dữ liệu và so với thermostat

Khi Terminal đã in `BÁO CÁO: ...`, chép kết quả về laptop:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_giu_nhiet "D:\BTL_Nhom13\Du_lieu_giu_nhiet"
```

Mỗi lần chạy tạo thư mục timestamp mới. `cau_hinh.json` ghi `bo_dieu_khien=thu-rl`, seed/hash của policy, state đã dùng và `q_updates=0`; CSV vẫn chứa nhiệt và PWM đã áp dụng. Lượt bị ngắt/lỗi phải được báo chưa hoàn tất, không chọn riêng đoạn đẹp để so.

So sánh MAE, sai số lớn nhất, tỷ lệ thời gian trong các vùng ±0,15/±0,25/±0,5°C đã định trước, độ dao động và số lần đổi lệnh. Vùng ±0,5°C đã đạt 100% ở lượt thermostat nên mục tiêu cải tiến chính là giảm sai lệch/dao động, không tăng tỷ lệ vượt quá 100%. Các vùng hẹp hơn chỉ là chỉ số bám setpoint của đầu dò, chưa xác nhận độ chính xác nhiệt thật của toàn hộp.

Ghi mức PWM như đại lượng hoạt động; không quy ra Wh khi chưa đo điện năng. Đây là pilot hộp rỗng, chưa phải bằng chứng cải thiện tỷ lệ nở trứng.
