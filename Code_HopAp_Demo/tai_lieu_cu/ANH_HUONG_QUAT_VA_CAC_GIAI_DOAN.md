> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Vai trò của quạt và các giai đoạn điều khiển hộp

**Cập nhật phép thử 0/75%:** có [công cụ thử ngắn riêng](HUONG_DAN_THU_QUAT_0_VA_75.md) cho hộp rỗng, bóng tối đa 50%, sưởi tối đa 30 giây. Ngoại lệ này không áp dụng cho chế độ làm ấm/giữ nhiệt/RL cũ. Các phần dưới mô tả miền khảo sát và giao thức 75/100% đang có.

## Bố trí đã xác nhận

Người lắp xác nhận quạt nằm trong hộp, phía sau quạt có lỗ khí, mặt đối diện có lỗ thoát. Bố trí này có đường trao đổi khí với phòng, không chỉ đảo khí trong một khoang kín. Cần phân biệt chiều hút/thổi thực tế của quạt; vị trí lỗ tự nó chưa xác nhận được lưu lượng khí đi qua hộp.

Khi không khí phòng lạnh hơn trong hộp và tăng tốc quạt thực sự tăng trao đổi khí, quạt mạnh hơn có thể làm nhiệt tăng chậm hơn hoặc giúp nguội nhanh hơn. Quạt vẫn còn vai trò phân bố nhiệt. Nếu chỉ đảo khí trong khoang kín, hoặc thay vị trí đầu dò/luồng gió, quan hệ tại một đầu dò có thể khác.

Nguồn: [quạt tuần hoàn trong máy ấp](https://extension.msstate.edu/publications/hatching-quality-chicks), [làm mát bằng trao đổi không khí](https://bsesc.energy.gov/energy-basics/natural-ventilation-and-cooling).

## Dữ liệu hiện tại nói gì?

Mô hình đóng băng có bước 5 giây, với biến quạt F dùng thang 0–1 và bộ nhớ sưởi M:

```text
Độ nhạy của ΔT5 với F = -0,132498 + 0,076333 × M
```

Trong M từ 0 đến 1, biểu thức này âm. Tức là **giữ cùng nhiệt, xu hướng và lịch sử sưởi**, mô hình dự báo tăng quạt từ 75% lên 100% làm tốc độ nhiệt thấp hơn. Đây là tác động riêng một bước trong mô hình khớp, không phải phép đo hiệu ứng độc lập hoặc tốc độ nguội dài hạn được bảo đảm.

Chỉ có hai mức quạt 75/100% trong khảo sát tự động hiện tại. Không dùng công thức đó để suy ra hiệu quả quạt 0%, không coi việc quạt đã quay ở 50% là đã xác nhận nhiệt phân bố đều ở mức đó. Một đầu dò chưa kiểm chứng được điểm nóng hoặc độ đều nhiệt.

## Khung điều khiển cần hướng tới

| Giai đoạn | Vai trò của bóng | Vai trò của quạt |
|---|---|---|
| Làm ấm nhanh | Tạo nhiệt đủ để tăng nhiệt | Chọn mức thấp đã kiểm tra nhưng vẫn tuần hoàn; thử 75% thay vì mặc định 100% |
| Tiếp cận mục tiêu | Giảm sưởi trước khi chạm 37,5°C nếu nhiệt còn tăng | Giữ mức ổn định, tránh đổi quạt không cần thiết |
| Duy trì | Bù mất nhiệt bằng mức gần điểm cân bằng | Giữ mức ổn định, đổi khi điều kiện thực sự cần |
| Hạ nhiệt | Giảm hoặc tắt bóng | Tăng lên 100% để hỗ trợ thoát nhiệt khi phòng mát hơn |
| Bảo vệ ở 38°C | Tắt bóng | 100%, chờ về 37°C; dừng cứng ở 40°C/mất số đo |

Đây là khung chức năng. RL cần học quan hệ phối hợp bóng–quạt, tốc độ tăng/giảm nhiệt và chi phí đổi mức; không mặc định mọi trường hợp quạt cao đều tốt hơn.

**Giới hạn hiện tại:** phần làm ấm của chương trình là quy tắc đặt trước, chưa do Q-table điều khiển. RL được đo trước đây chỉ bắt đầu khi đạt 37°C. Muốn RL tối ưu cả làm ấm từ nhiệt phòng, cần dữ liệu và miền state phù hợp ở đoạn nhiệt thấp; không dùng bảng cũ ngoại suy xuống 26°C.

## Thay đổi phần mềm vừa thực hiện

Thêm `--quat-lam-am 75` cho chế độ thử điểm làm việc **co-dinh**. Mặc định vẫn 100% để bảo toàn giao thức thermostat/RL đã đo. Hai chế độ đó từ chối tham số làm ấm 75% trong bản hiện tại; Q-table và kết quả cũ không bị thay đổi.

Phép thử mới có trình tự:

1. Dưới 37°C: bóng 75%, quạt 75%.
2. Từ 37°C đến 37,5°C: bóng 50%, quạt 75%.
3. Đạt 37,5°C: giữ bóng 50%, quạt 75% trong 600 giây.
4. Bảo vệ luôn có quyền đổi ngay sang bóng 0%, quạt 100%.

Đầu ra vẫn có xung khởi động quạt 100% khoảng một giây trước khi về mức yêu cầu, với bóng được giữ tắt trong xung đó. Không cho tắt quạt khi bóng đang sưởi trong giao thức thử hiện tại.

Chạy ở Terminal laptop sau khi chép lại thư mục code và đưa hộp rỗng về điều kiện đầu tương tự:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
```

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien co-dinh --bong 50 --quat 75 --bat-dau-giu 37.5 --quat-lam-am 75"
```

Muốn chỉ xem kế hoạch, thêm `--dry-run`. Làm ấm/tiếp cận giới hạn 600 giây; nếu không đạt ngưỡng thì dừng và lưu log. Phần giữ mức kéo dài 600 giây riêng, không tính làm ấm/quạt cuối. Theo dõi trực tiếp, giữ nguyên nắp/lỗ thông gió/đầu dò, không chạy hai chương trình cùng lúc.

Cấu hình làm ấm 75% quạt là **phép thử mới**, chưa có thời gian làm ấm thực để kết luận nhanh hơn bao nhiêu. So thời gian phải xét cả nhiệt ban đầu, nhiệt phòng và việc chuyển sớm sang bóng 50%; không quy toàn bộ khác biệt cho quạt nếu các yếu tố còn lại khác nhau.
