# Ấp 3 giai đoạn — chỉnh ngày, RL tự đổi mốc nhiệt

| Giai đoạn | Ngày | Mốc | Vùng điều khiển | Ẩm độ khuyến nghị (chỉ theo dõi) |
|---|---|---|---|---|
| 1 | 1–10 | 37,8 °C | 37,6–38,0 °C | 60 % |
| 2 | 11–17 | 37,5 °C | 37,3–37,7 °C | 55 % |
| 3 | 18–21 | 37,2 °C | 37,0–37,4 °C | 65–70 % |

Mốc nhiệt lấy theo Bản tin Khuyến nông Việt Nam số 04/2026 (xem [TAI_LIEU_NHIET_DO_BA_GIAI_DOAN.md](TAI_LIEU_NHIET_DO_BA_GIAI_DOAN.md)). Vùng ±0,2 °C là thiết kế kỹ thuật của nhóm, nguồn không quy định dung sai này.

## Cơ chế

- **Ngày ấp** lưu trong `trang_thai_me_ap.json` trên Pi, do [me_ap.py](me_ap.py) quản lý. File ghi thời điểm bắt đầu mẻ, và ngày tự tăng theo thời gian. **Chỉnh ngày** nghĩa là dời thời điểm bắt đầu, nên sau khi chỉnh, ngày vẫn tự tăng tiếp.
- **[ap_trung.py](ap_trung.py)** đọc lại lịch **mỗi chu kỳ 5 s**, đổi mốc và vùng theo giai đoạn, rồi dùng **nguyên Q-table Q2** (đã thử trên hộp thật ngày 20/11) với nhiệt độ đã dịch theo mốc. Trạng thái của Q2 là sai lệch so với 37,5 °C, nên cùng một chính sách dùng được cho cả 3 mốc.
- **Bảo vệ cố định, không đổi theo ngày**: ngắt mềm 38,3 °C (bật lại ở 37,8 °C), dừng cứng 38,8 °C, mất số đo quá 3 s thì dừng, cộng KSD301. Đổi ngày không bao giờ nới các ngưỡng này.
- Nếu Q-table gặp trạng thái chưa học: khi nhiệt **trên mốc** thì làm mát (bóng 0 %, quạt 100 %); khi **dưới mốc** thì làm ấm phục hồi. Chương trình không bao giờ tự tăng sưởi khi hộp đã nóng.
- File lịch bị hỏng giữa chừng thì chương trình **giữ mốc đang dùng** và ghi nhận lỗi, không dừng lượt.
- Pha (phase) trong CSV có dạng `ap_ngay12_gd2`, nên từng dòng dữ liệu tự ghi lại ngày và giai đoạn. Bridge và app dựa vào đó để vẽ đúng vùng mục tiêu theo thời gian.

## Chạy trên Pi

```bash
cd /home/pi/Code_HopAp_Demo
python3 me_ap.py bat-dau --ngay 5            # tạo mẻ, bắt đầu ở ngày 5 (thời gian thật)
python3 me_ap.py xem                          # Ngày 5/21 · Giai đoạn 1 · mốc 37.8 °C ...
.venv/bin/python ap_trung.py --dry-run        # kiểm tra, chưa bật tải
.venv/bin/python ap_trung.py --phut 30        # chạy: làm ấm rồi điều khiển 30 phút
```

Đang chạy thì đổi ngày bằng **một trong hai cách**:
- Trên Pi, ở một cửa sổ khác: `python3 me_ap.py dat-ngay 12`
- **Trong app**, thẻ **Lịch ấp**: nhập ngày hoặc bấm GĐ1/GĐ2/GĐ3, rồi **bấm 2 lần** nút Đổi ngày. Cần bridge đang chạy, `python3 cloud_bridge.py chay`.

**Lịch demo chỉ chạy khi RL giữ nhiệt (22/11):** mẻ rút gọn (1 ngày = 1, 2 hoặc 5 phút) tạo ra ở trạng thái **tạm dừng**. Lịch đứng yên trong lúc làm ấm (khoảng 5 phút), chạy khi RL nhận điều khiển, và dừng lại khi lượt kết thúc (hết giờ, dừng khẩn cấp hoặc lỗi). Nhờ vậy thời gian làm ấm không làm mất ngày demo, và lượt sau chạy tiếp từ đúng ngày đã dừng. Mẻ thời gian thật không bao giờ tạm dừng. Hàm tương ứng: `me_ap.pause()` và `me_ap.resume()`.

**Demo rút gọn thời gian:** `python3 me_ap.py bat-dau --ngay 1 --giay-moi-ngay 120` (1 ngày = 2 phút). App ghi rõ "Demo rút gọn". Muốn chủ động thì dùng thời gian thật và tự đổi ngày lúc trình bày: ngày 5, sau 10 phút đổi sang ngày 12, rồi ngày 19.

## Làm hoàn toàn trên app (22/11)

Cần hai dịch vụ `hop-ap-bridge` và `hop-ap-do-am` đang chạy trên Pi, và đã cài `tmux`.

1. **Tạo mẻ** (thẻ Lịch ấp → Mẻ ấp): chọn ngày bắt đầu và tốc độ lịch (thời gian thật, hoặc demo 1 ngày = 5 / 2 / 1 phút), bấm **Tạo mẻ mới** 2 lần. Nếu đang có mẻ thì mẻ cũ bị thay.
2. **Bắt đầu lượt** (thẻ Lượt chạy): chọn RL hoặc Thermostat và thời lượng 10–60 phút, **tích xác nhận đang có người ở cạnh hộp**, rồi bấm **Bắt đầu lượt** 2 lần. Pi kiểm tra lại: có mẻ, không có chương trình điều khiển nào khác đang chạy, đọc được DS18B20, hộp ≤ 30 °C. Thiếu điều kiện nào thì **từ chối** và ghi lý do trên app.
3. Trong lúc chạy: **Đổi ngày** và **Dừng khẩn cấp** như trước. Trên Pi xem được bằng `tmux attach -t hopap_app`; log nằm trong `.cloud_bridge/luot_app_*.log`.
4. **Kết thúc mẻ**: chỉ làm được khi không có lượt đang chạy. File lịch được đổi tên lưu lại, không bị xóa.

Quy tắc bảo mật của Firebase chặn lệnh sai ngay từ máy chủ (thiếu xác nhận có người, thời lượng ngoài 10/20/30/45/60, ngày ngoài 1–21, tốc độ lạ). Lượt bắt đầu từ app chạy tách khỏi bridge (`KillMode=process`), nên bridge khởi động lại thì lượt vẫn chạy tiếp và vẫn được bảo vệ đầy đủ.

## Kiểm chứng

- **Test:** `python -m unittest test_ap_trung test_cloud_bridge`. Có 12 test cho lịch và policy (biên ngày, đổi ngày giữa chừng, bảo vệ cố định, file lịch hỏng, trạng thái chưa học, kết thúc lượt) và 7 test cho bridge ở chế độ 3 giai đoạn.
- **Mô phỏng** (`Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py`): chạy **đúng class `ApTrungPolicy`** trên mô hình nhiệt nhận dạng từ dữ liệu 20/11, 20 seed cho mỗi kịch bản. Kết quả ở `outputs/mo_phong_ba_giai_doan/`.
  - Q2 dịch mốc giữ **99,3–99,7 %** thời gian trong vùng; thermostat khoảng 89 %.
  - MAE khoảng 0,06 °C; thermostat khoảng 0,115 °C.
  - Số lần đổi mức khoảng 9–12 mỗi 10 phút; thermostat khoảng 55.
  - Sau khi đổi ngày, nhiệt vào vùng mới sau trung bình 9–26 s.
  - Không có lượt nào dừng sớm, không phải dùng dự phòng làm mát, không bước nào kích hoạt bảo vệ.
- **Giới hạn:** đây là kết quả **mô phỏng**. Trên hộp thật, Q2 ở 37,5 °C đạt 93,8 % thời gian trong vùng (lượt ngày 20/11), thấp hơn mô phỏng. Chưa đo thật ở mốc 37,8 và 37,2 °C. Một lượt chạy tối đa 100 phút, vì do_nhiet_hop giới hạn 2 giờ cho mỗi phiên hộp rỗng có giám sát, nên chưa chạy liên tục 21 ngày.
