> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Kiểm chứng mức bóng–quạt ổn định quanh 37,5°C

Mục tiêu mới là giữ nhiệt tốt **đồng thời giảm việc đổi mức điều khiển**. Hai điều này khác nhau: lượt RL trước bám nhiệt tốt hơn thermostat nhưng đổi tổ hợp PWM 88 lần trong 10 phút. Thay đổi duty là hoạt động phản hồi bình thường; để vận hành êm hơn, cần chọn điểm làm việc và chỉ điều chỉnh khi cần bù sai lệch/thất thoát nhiệt.

Không thể bảo đảm cùng một cặp mức sẽ giữ đúng 37,5°C trong mọi nhiệt độ phòng hoặc độ mở lỗ thông gió. Cặp mức cố định chỉ cân bằng tại một điều kiện nhiệt nhất định.

## 1. Những gì đã kiểm tra offline

Đã thử bộ giữ mức đặt sau Q-table cũ, với thời gian giữ bóng 15/20/30 giây, quạt 30/60 giây, vùng giữ quanh mục tiêu ±0,1/±0,15°C. Đây là mô phỏng trên mô hình đóng băng và phần dư lấy lại theo block từ hai lượt đo; không phải dữ liệu phần cứng mới.

Các cấu hình giữ mức này giảm số lần đổi lệnh nhưng tỷ lệ mô phỏng trong 37–38°C chỉ khoảng **73–82%**, MAE khoảng **0,30–0,37°C** và có nhiều thời gian bảo vệ mềm. Vì vậy **không đưa bộ giữ mức này vào chương trình Pi**. Mã và kết quả thử được giữ riêng tại `../outputs/kiem_tra_on_dinh_20261117/` để truy vết.

Kết quả cho thấy không nên chỉ đổi chu kỳ 5 giây của Q-table đã học thành 20–30 giây rồi coi đó là cùng policy đã được kiểm chứng. Policy/reward/gói RL cũ vẫn được giữ nguyên.

## 2. Bước đo thực hiện tại

Bổ sung tùy chọn `--bat-dau-giu 37.5` cho chế độ **co-dinh** trong `kiem_tra_giu_nhiet.py`. Đây là phép đo điểm làm việc, **không phải RL mới**.

Trình tự mặc định khi dùng bóng 50%/quạt 75%:

| Giai đoạn | Bóng | Quạt | Điều kiện chuyển |
|---|---:|---:|---|
| Làm ấm ban đầu | 75% | 100% | Đạt 37,0°C |
| Tiếp cận mục tiêu | 50% | 75% | Đạt 37,5°C |
| Kiểm tra giữ mức | **50%** | **75%** | Giữ nguyên trong **600 giây** |

**Cập nhật bố trí quạt:** quạt có lỗ khí phía sau và lỗ thoát ở mặt đối diện. Có thể thử thêm `--quat-lam-am 75` để giảm mức quạt trong giai đoạn làm ấm ban đầu; bảng trên mô tả mặc định 100% của giao thức cũ. Xem [vai trò quạt và các giai đoạn](ANH_HUONG_QUAT_VA_CAC_GIAI_DOAN.md) để chạy phép thử mới. Quan hệ này hiện chỉ được khảo sát ở 75/100%, chưa cho tắt quạt khi bóng sưởi.

Thời gian làm ấm và tiếp cận mục tiêu dùng chung giới hạn 600 giây. Nếu không đạt 37,5°C trong giới hạn đó thì dừng, không ghi là đã hoàn tất giai đoạn giữ mức. Điều này có thể do mức 50% chưa bù đủ thất thoát hoặc cần thời gian tiếp cận dài hơn; chưa đủ để kết luận mạch hỏng.

Trong 600 giây giữ mức, chương trình không tự đổi PWM theo nhiệt. Các ngưỡng bảo vệ vẫn độc lập: đạt 38°C thì bóng 0%/quạt 100%, về 37°C mới trở lại mức thử; đạt 40°C hoặc mất số đo quá 3 giây thì dừng. Nếu bảo vệ phải can thiệp, cặp mức này chưa duy trì được toàn bộ lượt trong vùng đã định; không bỏ bảo vệ để ép giữ duty.

Tùy chọn mới chỉ áp dụng cho phép thử `co-dinh`. Giao thức thermostat và RL cũ vẫn bắt đầu giai đoạn giữ nhiệt tại 37°C, không thay đổi Q-table. Không so trực tiếp hai phép đo có điều kiện đầu khác nhau như một đối chứng công bằng cho hiệu năng thuật toán.

## 3. Chạy từ Terminal laptop Windows

Giữ hộp rỗng, vị trí bóng/quạt/đầu dò, trạng thái nắp và lỗ thông gió như các lượt trước. Để hộp nguội về điều kiện đầu tương tự, khoảng 26–27°C. Không chạy cùng lúc chương trình khác dùng GPIO18/23.

Chép bản mới:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
```

Xem kế hoạch, không bật tải:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien co-dinh --bong 50 --quat 75 --bat-dau-giu 37.5 --dry-run"
```

Chạy phép đo có giám sát:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien co-dinh --bong 50 --quat 75 --bat-dau-giu 37.5"
```

Phần kiểm tra giữ mức kéo dài 10 phút, chưa gồm làm ấm tối đa 10 phút và 10 giây giữ quạt cuối. Ctrl+C để dừng; nếu tải không tắt theo chương trình, ngắt adapter 12 V.

Chép dữ liệu về sau khi Terminal in báo cáo, hoặc sau khi phiên đã dừng có lỗi để phân tích nguyên nhân:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_giu_nhiet "D:\BTL_Nhom13\Du_lieu_giu_nhiet"
```

CSV ghi cả giai đoạn tiếp cận bằng 50%/75%; cấu hình ghi `hold_start_threshold_c=37.5`. Không chỉ nhìn nhiệt cuối cùng: cần xem nhiệt còn tăng/giảm ở cuối phiên, mức lệch khỏi 37,5°C và có lần nào bảo vệ can thiệp không.

## 4. Dùng kết quả để thiết kế RL ít đổi mức

- Nếu 50%/75% gần cân bằng nhưng lệch mục tiêu, khảo sát tinh hơn quanh điểm đó. Các bước 25 điểm phần trăm có thể quá thô; các mức nhỏ hơn chỉ được chốt sau khi đo, không mặc định 50% là tối ưu.
- State của RL mới cần chứa mức bóng/quạt hiện tại; nếu có thời gian giữ tối thiểu, phải thể hiện thông tin thời gian giữ còn lại hoặc xây bước chuyển thời gian phù hợp.
- Action cần có **giữ nguyên**, tăng/giảm bóng nhẹ, và chỉ đổi quạt khi có lý do. Vẫn có thể chọn đồng thời cả bóng và quạt.
- Reward đánh giá cả sai số nhiệt, vượt nhiệt, số lần đổi mức và biên độ thay đổi. Không thêm phạt đổi action vào state cũ mà bỏ thông tin mức trước đó.
- Huấn luyện và kiểm tra phải mô phỏng đúng cơ chế giữ mức, thay vì gắn bộ lọc sau policy cũ rồi dùng lại số liệu 53,2% để công bố hiệu năng mới.

Tham khảo nguyên lý [giữ tín hiệu trong chu kỳ lấy mẫu](https://www.mathworks.com/help/simulink/slref/zeroorderhold.html) và [lựa chọn chu kỳ điều khiển](https://www.mathworks.com/help/control/getstart/converting-between-continuous-and-discrete-time-systems.html). Các mức PWM và thời gian trong phép thử này là cấu hình thí nghiệm của dự án, chưa phải thông số tối ưu được các nguồn trên xác nhận.
