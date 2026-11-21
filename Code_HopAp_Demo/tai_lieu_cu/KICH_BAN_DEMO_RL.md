> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Kịch bản demo Q-learning điều khiển hộp nhiệt

Nếu cần ưu tiên ít đổi mức điều khiển, xem [hướng kiểm chứng điểm làm việc ổn định](HUONG_DAN_GIU_MUC_ON_DINH.md). Đây là bước đo bổ sung; kết quả RL bên dưới thuộc policy 5 giây đã đo, chưa phải RL giữ mức dài hơn.

## Kết quả hiện có

Đã có một lượt thermostat và một lượt Q-learning đo thực, cùng hộp rỗng, cùng đầu dò, trạng thái nắp/lỗ thông gió và vị trí quạt theo xác nhận của người lắp. Mỗi lượt giữ nhiệt 600 giây, không có lỗi đọc hoặc ngắt bảo vệ.

| Chỉ số | Thermostat | Q-learning |
|---|---:|---:|
| MAE so với số đọc mục tiêu 37,5°C | 0,1214°C | 0,0568°C |
| Độ lệch chuẩn nhiệt | 0,1453°C | 0,0825°C |
| Thời gian trong ±0,15°C | 66,67% | 94,85% |
| Thời gian trong ±0,5°C | 100% | 100% |
| Lần đổi tổ hợp PWM | 53 | 88 |

Trong cặp thử này, MAE giảm **53,2%**, độ lệch chuẩn nhiệt giảm **43,3%**. RL bám nhiệt tốt hơn đối chứng đã chọn, đồng thời đổi mức PWM nhiều hơn. Không gọi đó là tiết kiệm điện khi chưa đo Wh, không suy rộng thành tốt hơn mọi máy ấp/PID hoặc tăng tỷ lệ nở trứng.

Báo cáo và đồ thị: [so sánh đo thực](../../outputs/so_sanh_RL_THUC_20261117/KET_QUA.md).

## Trình bày cách hệ thống hoạt động

1. Đầu dò DS18B20 đo nhiệt trong hộp; Pi đọc nhiệt và hiển thị OLED.
2. Policy dùng sai lệch so với 37,5°C, xu hướng tăng/giảm, bộ nhớ sưởi và trạng thái bảo vệ.
3. Q-table có 162 state, 9 action; mỗi action chọn đồng thời mức bóng và quạt. Hai MOSFET thực hiện các lệnh PWM.
4. Bảng Q được huấn luyện offline trước buổi demo. Khi chạy trên hộp, chương trình chỉ tra bảng, không thử ngẫu nhiên hoặc cập nhật Q online.
5. Lớp bảo vệ độc lập có quyền tắt sưởi bất kể Q-table chọn gì.

Không dùng đồ thị mô phỏng để gọi là số đo thực. Đồ thị so sánh hiện có lấy trực tiếp từ hai CSV đo trên Pi và căn cùng thời điểm bắt đầu giữ nhiệt.

## Chuẩn bị và chạy

Giữ hộp rỗng và nguyên bố trí đã đo. Để hộp nguội gần 26–27°C; pilot từ chối nếu nhiệt đầu dò ban đầu trên 30°C. Chuẩn bị thời gian làm ấm riêng: 10 phút được nói tới là giai đoạn giữ nhiệt, không gồm làm ấm và quạt cuối.

Từ Terminal laptop, dùng phiên bản code đã được chép lên Pi và chạy:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl"
```

Chương trình làm ấm bóng 75%/quạt 100% tối đa 10 phút; đạt 37°C thì tự bắt đầu giai đoạn Q-learning 600 giây. Theo dõi nhiệt và mức PWM trên Terminal/OLED. Có thể trình chiếu đồ thị hai lượt đã đo để giải thích lợi ích, trong lúc mạch đang hoạt động.

Khi trình bày, chỉ ra rằng thermostat có chu kỳ tăng/giảm nhiệt rõ hơn, còn policy RL đã dùng nhiều mức trung gian, ví dụ bóng 50%/quạt 75%. Không nói quạt quay chính xác bao nhiêu RPM hoặc bóng tiêu thụ bao nhiêu W chỉ từ duty.

## Các giới hạn vẫn giữ

- Ngắt mềm 38°C, trở lại 37°C; đạt 40°C hoặc mất số đo hợp lệ quá 3 giây thì dừng.
- State chưa học/ngoài miền, sai đầu dò hoặc gói policy bị thay đổi thì dừng pilot.
- Hộp rỗng, có người theo dõi. Ctrl+C để dừng; nếu tải không tắt theo chương trình, ngắt adapter 12 V.
- Không chạy đồng thời hai chương trình dùng GPIO18/23. Không thay lỗ thông gió, thêm nước/tải hoặc chuyển cảm biến giữa hai lượt so sánh.
- Chưa có kiểm chứng vận hành ấp trứng kéo dài; chưa đo độ ẩm hay độ đều nhiệt toàn hộp.

## Củng cố kết luận trước khi nộp

Hiện mới có một cặp thử; nhiệt ban đầu trong hộp là 26,437°C và 27,500°C, chưa có số đo nhiệt phòng riêng. Để giảm ảnh hưởng thứ tự thử/nhiệt dư, có thể chạy lại thermostat theo thứ tự **A–B–A**, đưa hộp về điều kiện đầu tương đương và ghi nhiệt phòng nếu có nhiệt kế.

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien doi-chung"
```

Giữ nguyên policy/reward trong giai đoạn kiểm tra. Lấy dữ liệu về bằng:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_giu_nhiet "D:\BTL_Nhom13\Du_lieu_giu_nhiet"
```

Nếu kiểm tra ở phòng lạnh hơn hoặc thay độ mở lỗ, ghi đó là điều kiện mới và đánh giá cả RL lẫn đối chứng. Không mặc định rằng kết quả ở phòng hiện tại sẽ giữ nguyên.
