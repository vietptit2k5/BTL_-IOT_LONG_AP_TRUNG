> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Ba vùng điều khiển theo ngày ấp — bản nghiên cứu cho demo

Đã tạo lịch ba giai đoạn và chương trình huấn luyện ba Q-table riêng. Lịch tự chọn giai đoạn theo thời gian từ khi bắt đầu mẻ; mỗi policy học một vùng, có cùng bộ nhớ sưởi và hành động trước. Chưa ghép các policy này vào chương trình GPIO trên Pi.

## Cấu hình đề xuất

|Ngày|Mốc mục tiêu|Vùng kỹ thuật thử nghiệm|
|---|---|---|
|1–10|37.8°C|37.6–38.0°C|
|11–17|37.5°C|37.3–37.7°C|
|18–21|37.2°C|37.0–37.4°C|

**Các vùng ±0.2°C là thiết kế kỹ thuật để khảo sát, không phải dung sai sinh học được tài liệu xác nhận.** Nguồn chính thức chỉ nêu nhiệt 37.8–38.0°C / 37.5°C / 37.2°C tương ứng các ngày trên. Đặc biệt, vùng kỹ thuật giai đoạn đầu có phần thấp hơn khoảng nguồn nêu và chạm ngưỡng ngắt mềm 38°C. Không được gọi vùng này là “khoảng ấp chuẩn đã xác nhận”.

Nguồn và phân biệt nhiệt không khí/vỏ trứng: [tài liệu tham khảo](../TAI_LIEU_NHIET_DO_BA_GIAI_DOAN.md). File cấu hình thuần Python: `lich_ap_ba_giai_doan.py`, cờ `deploy_allowed=False`, `biological_tolerance_validated=False`.

## RL học điều gì?

- Thưởng mỗi bước còn trong vùng, ưu tiên mềm trung tâm.
- Phạt đổi duty bóng/quạt; ngoài vùng giảm chi phí đổi mức để cho phép hồi phục nhanh.
- Vẫn cho phép chỉnh sớm khi trong vùng nhưng xu hướng sắp vượt biên.
- State của mỗi bảng gồm sai lệch chuẩn hóa theo vùng, xu hướng nhiệt, bộ nhớ sưởi, action trước, guard: 2.430 state, 9 action. Có ba bảng tương ứng ba mục tiêu.
- Không có cơ cấu thêm để tăng/giảm ẩm. DHT11 không vào state/action/reward.
- Khi chuyển giai đoạn trong mô phỏng, giữ bộ nhớ sưởi và action trước; chỉ đổi policy/mục tiêu. Không đặt lại hộp về nhiệt trung tâm hoặc xóa quán tính nhiệt.

Giữ nguyên guard 38→37°C. Nó có thể kéo nhiệt xuống ngoài vùng giai đoạn đầu; đó là ưu tiên bảo vệ hiện có, không che khỏi chỉ số hoặc tự bỏ để làm đẹp kết quả. Vì xung đột này, chưa thể đưa ba policy lên hộp thật từ kết quả mô phỏng.

## Kiểm tra lịch ngày — không bật tải

Trên Pi hoặc laptop có Python, trong thư mục `Code_HopAp_Demo`:

```bash
python3 lich_ap_ba_giai_doan.py --ngay 1
python3 lich_ap_ba_giai_doan.py --ngay 11
python3 lich_ap_ba_giai_doan.py --ngay 18
```

Có thể tính từ thời điểm bắt đầu cụ thể, có múi giờ:

```bash
python3 lich_ap_ba_giai_doan.py --bat-dau 2026-11-20T08:00:00+07:00 --tai 2026-11-30T08:00:00+07:00
```

Ví dụ trả ngày 11, giai đoạn giữa. Ngày được định nghĩa bằng số khoảng 24 giờ đã trôi qua +1; sau đủ 21 ngày thì báo hết miền lịch, không quay về ngày1. Mốc bắt đầu phải do người dùng ghi/lưu và đưa lại khi khởi động; CLI hiện chỉ tính/xem, chưa tạo mẻ thật hoặc tự ghi ngày bắt đầu. Pi phải có đồng hồ đúng.

## Huấn luyện trong mô phỏng

`Code_HopAp_PhanTich/hoc_ba_giai_doan.py` chạy trên laptop bằng Python Anaconda có numpy/numba. Mỗi giai đoạn thử 6 bộ hệ số ×3 seed, 64.000 episode/seed. Chọn hệ số/seed trên 128 kịch bản validation mỗi giai đoạn, rồi đánh giá 192 kịch bản khác riêng từng giai đoạn.

Mô hình được lấy từ gói cũ `goi_thu_rl_20261117.json`, nhận dạng trên khảo sát hộp rỗng ngày17/11. Khởi đầu mô phỏng quanh từng mục tiêu, kèm trạng thái bộ nhớ/độ dốc từ dữ liệu thực và nhiễu động cộng nhỏ. Không giả lập chính xác thay đổi sinh nhiệt của phôi, số lượng trứng, nhiệt vỏ trứng hoặc độ đồng đều.

Kết quả ở `outputs/rl_ba_giai_doan_20261120_final/`:

- `KET_QUA.md`, `ket_qua.json`: kết quả tách từng giai đoạn và gate mô phỏng.
- `giao_thuc.json`: nguồn/hash, cấu hình, seed, giới hạn và cờ chưa được triển khai.
- `lua_chon_da_chot.json`, `thu_he_so.json`: lựa chọn theo validation và toàn bộ thử hệ số.
- `Q_BA_GIAI_DOAN_MO_PHONG.npz`, `UNG_VIEN_KHONG_CHAY_PI.json`: bảng học được; chưa phải gói loader Pi.
- `CHUYEN_GIAI_DOAN_MO_PHONG.csv`: ví dụ rút ngắn thành 10 phút/giai đoạn, giữ liên tục trạng thái nhiệt; không phải dữ liệu ấp21ngày hoặc log GPIO thật.

Các kịch bản có nhiệt ban đầu ngoài vùng/bảo vệ nên tỷ lệ trong vùng không chỉ đo đoạn đã ổn định. Số lần đổi mức là số lần đổi duty/600s, không phải đếm các xung PWM. Một bảng đạt gate mô phỏng cũng chưa được dùng cho trứng thật.

Chạy lại từ PowerShell laptop, chọn thư mục mới:

```powershell
cd D:\BTL_Nhom13
& "C:\Users\ADMIN\anaconda3\python.exe" Code_HopAp_PhanTich\hoc_ba_giai_doan.py --episodes 64000 --out outputs\rl_ba_giai_doan_lap_lai
```

## Bước còn lại trước khi chạy mạch

Lấy dữ liệu bài đo dài đã chuẩn bị, kiểm tra mô hình ở cả ba vùng. Xác nhận dung sai/hiệu chuẩn và thiết kế lại tương quan giữa vùng điều khiển với bảo vệ (đặc biệt vùng đầu) bằng đánh giá cụ thể. Sau đó mới tạo loader và lịch mẻ lưu bền cho Pi, thử hộp rỗng có giám sát và đối chứng. Lệnh `kiem_tra_giu_nhiet.py ... --bo-dieu-khien thu-rl` hiện vẫn dùng Q-table37.5°C cũ; không tự nhận bộ ba này.
