# Đưa hộp ấp lên đám mây (IoT Level-2)

`cloud_bridge.py` là một **tiến trình riêng** chạy song song với chương trình điều khiển trên Pi. Nó đọc file CSV mà chương trình điều khiển đang ghi, rồi đẩy lên Firebase Realtime Database. Bridge không import, không sửa và không làm chậm vòng điều khiển.

```text
 LOCAL (Raspberry Pi)                                    CLOUD (Firebase)
 DS18B20/DHT11 → do_nhiet_hop (Q-table + bảo vệ) → du_lieu.csv
                         ▲ SIGTERM                       │
                         └──── cloud_bridge.py ── REST ──┼──► /hop_ap_01/live       số đo mới nhất
                                                          │    /hop_ap_01/sessions/  lịch sử từng lượt
                                                          │    /hop_ap_01/alerts     cảnh báo
                                     đọc lệnh  ◄──────────┼─── /hop_ap_01/commands/stop
                                                          │          ▲ WebSocket
                                                          │      App web (GĐ 4)
```

- **Phân tích ở cục bộ:** Pi tự đo, tự ra quyết định bằng Q-table và tự bảo vệ (ngắt mềm 38 °C, dừng cứng, KSD301).
- **Mất Internet thì hộp vẫn giữ nhiệt bình thường.** Bridge ghi nhớ đã gửi tới dòng nào và gửi bù khi có mạng lại.
- **Đám mây chỉ được ra lệnh DỪNG.** Không có lệnh bật bóng hay đổi nhiệt độ đặt từ xa.

## 1. Chuẩn bị Firebase (làm một lần)

1. Kiểm tra lại file `D:\BTL_Nhom13\firebase_bi_mat.json` có đủ các trường: `apiKey`, `authDomain`, `databaseURL`, `projectId`, `appId`, `pi_email`, `pi_password`, `pi_uid`. Mật khẩu phải đúng mật khẩu đã đặt cho tài khoản Pi trong **Authentication → Users**.
2. Dán quy tắc bảo mật:
   - Trên Firebase console, vào **Databases & Storage → Realtime Database → tab Rules**.
   - Cách nhanh nhất: `cd D:\BTL_Nhom13\App_HopAp` rồi `firebase deploy --only database`. Cách thủ công: xóa nội dung cũ, dán toàn bộ file [App_HopAp/database.rules.json](../App_HopAp/database.rules.json), rồi bấm **Publish**.
   - Quy tắc này cho phép mọi tài khoản đã đăng nhập được đọc. Chỉ tài khoản Pi (theo UID) được ghi `live`, `sessions`, `alerts`, `trang_thai`. Mọi tài khoản đã đăng nhập được ghi `commands/stop`, nhưng trường `by` bắt buộc phải trùng email của chính tài khoản đó.
3. Thử trên laptop, đứng ở thư mục `D:\BTL_Nhom13\Code_HopAp_Demo`:

```powershell
python cloud_bridge.py kiem-tra
```

Kết quả đúng là in ra 3 dòng: `Đăng nhập OK`, `Ghi trang_thai/bridge OK`, `Đọc commands/stop OK`.

## 2. Thử trên laptop, không cần Pi

```powershell
# Đưa các lượt đo thật đã có lên mục lịch sử (thermostat 17/11, Q1 17/11, Q2 20/11)
python cloud_bridge.py tai-len ..\Du_lieu_giu_nhiet\ket_qua_giu_nhiet\20261117_084602_831190\du_lieu.csv ..\Du_lieu_giu_nhiet\ket_qua_giu_nhiet\20261117_092305_477345\du_lieu.csv ..\Du_lieu_giu_nhiet\20261120_pilot_01\du_lieu.csv

# Phát lại lượt 20/11 nhanh gấp 10 lần, như đang chạy thật (khoảng 1,5 phút)
python cloud_bridge.py phat-lai ..\Du_lieu_giu_nhiet\20261120_pilot_01\du_lieu.csv --toc-do 10
```

Trong lúc phát lại, mở Realtime Database trên console để thấy mục `hop_ap_01/live` thay đổi liên tục. Lượt phát lại có `meta.nguon = "phat_lai"`.

Chưa có Firebase thì thêm `--ghi-file thu_muc_thu` vào lệnh: bridge sẽ ghi cùng cấu trúc dữ liệu vào file `thu_muc_thu/firebase_gia_lap.json`.

## 3. Cài và chạy trên Pi

Chép từ Terminal Windows, **không chạy trong phiên SSH**:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
scp "D:\BTL_Nhom13\firebase_bi_mat.json" pi@pi:/home/pi/Code_HopAp_Demo/
```

Trên Pi:

```bash
cd /home/pi/Code_HopAp_Demo
chmod 600 firebase_bi_mat.json
sudo apt install -y python3-requests      # thường đã có sẵn
python3 cloud_bridge.py kiem-tra
```

Mỗi lượt đo dùng **2 cửa sổ SSH**:

```bash
# Cửa sổ 1: chương trình điều khiển, như trước
.venv/bin/python thu_rl_du_lieu_moi.py --dht11

# Cửa sổ 2: bridge (tự tìm CSV mới nhất trong ket_qua_*/ và logs/)
python3 cloud_bridge.py chay
```

Bridge có thể bật trước hoặc sau chương trình điều khiển. Tắt bridge (Ctrl+C) **không ảnh hưởng** tới việc điều khiển. Khởi động lại bridge thì nó đọc tiếp từ vị trí đã lưu trong `.cloud_bridge/trang_thai.json`. Giai đoạn 5 sẽ cho bridge tự chạy bằng systemd.

## 4. Cấu trúc dữ liệu trên Firebase

| Đường dẫn | Nội dung |
|---|---|
| `hop_ap_01/live` | Số đo mới nhất. `nhiet_c`, `do_am_pct`, `bong_pct`, `quat_pct` (phần trăm PWM theo lệnh, không phải W hay vòng/phút đo được), `giai_doan`/`giai_doan_ten`, `trong_vung`, `xu_huong_c_phut`, `trang_thai` (`DANG_CHAY`/`KET_THUC`), `ts` (thời điểm đo), `bridge_ts` (thời điểm gửi) |
| `hop_ap_01/sessions/<id>/meta` | Bộ điều khiển (Thermostat / Q-learning v1 / Q-learning v2), vùng mục tiêu, thời điểm bắt đầu, nguồn (`truc_tiep` / `phat_lai` / `tai_len`) |
| `hop_ap_01/sessions/<id>/samples/<giây>` | Một mẫu mỗi 5 s: `T`, `RH`, `L` (% bóng), `F` (% quạt), `g` (giai đoạn) |
| `hop_ap_01/sessions/<id>/events/<ms>` | Các dòng không phải `MEASUREMENT`: lệnh, đổi mức, STOP, END, ERROR |
| `hop_ap_01/sessions/<id>/summary` | Tóm tắt thống nhất (MAE, % trong 37,3–37,7 °C, độ lệch chuẩn, số lần đổi mức, thời gian làm ấm) cùng `ket_qua_goc` từ `ket_qua.json` |
| `hop_ap_01/alerts/<ms>_<loại>` | Cảnh báo: `loai`, `muc` (`thong_tin`/`canh_bao`/`nguy_hiem`), `noi_dung`, `phien`, `nhiet_c` |
| `hop_ap_01/commands/stop` | `{value, ts, by}`: app ghi `value: true`; Pi xử lý xong thì đặt lại `false` và ghi `ket_qua` |
| `hop_ap_01/trang_thai/bridge` | Nhịp sống của bridge, gửi mỗi 5 s. App dựa vào đây để biết Pi có online hay không |

Khóa của mẫu, sự kiện và cảnh báo đều tính từ thời gian đo. Vì vậy gửi lại sau khi mất mạng sẽ **ghi đè đúng chỗ cũ, không tạo bản trùng**.

## 5. Cảnh báo

| Loại | Điều kiện | Mức |
|---|---|---|
| `NGOAI_VUNG` | Đang giữ nhiệt mà ra ngoài 37,3–37,7 °C liên tục 60 s. Bỏ qua trong lúc làm ấm | cảnh báo |
| `ON_DINH` | Sau `NGOAI_VUNG`, đã ở lại trong vùng 60 s | thông tin |
| `NGHI_MO_NAP` | **Bóng đang sưởi** mà nhiệt tụt ≥ 0,5 °C trong 30 s. Nguội do tắt bóng là bình thường nên không tính | cảnh báo |
| `BAO_VE` | Bước vào chế độ bảo vệ quá nhiệt | cảnh báo |
| `LOI_CAM_BIEN` / `LOI` | Mất số đo DS18B20, hoặc chương trình ghi dòng ERROR | nguy hiểm |
| `PI_KHONG_GHI` | CSV ngừng cập nhật quá 20 s mà chưa kết thúc | nguy hiểm |
| `KET_THUC` | Lượt chạy kết thúc (dòng END) | thông tin |
| `DUNG_TU_XA` | Đã xử lý lệnh dừng từ app, kèm kết quả | cảnh báo |

Mỗi loại cảnh báo được gửi tối đa 1 lần mỗi 5 phút (trừ `ON_DINH`, `KET_THUC`, `DUNG_TU_XA`). Đã kiểm tra trên 4 lượt đo thật (thermostat và Q1 ngày 17/11, Q2 ngày 20/11, đáp ứng 20/11): không có `NGHI_MO_NAP` hay báo lỗi giả. Ngưỡng mở nắp **chưa được thử với lần mở nắp thật**. Cần chỉnh lại sau phép thử mở nắp ở giai đoạn 2.

## 6. Lệnh DỪNG từ xa

1. App ghi `commands/stop = {value: true, ts: <thời điểm>, by: <email người bấm>}`.
2. Mỗi 5 s, bridge đọc mục này. Nếu là lệnh mới, chưa xử lý và không cũ quá 10 phút, bridge tìm **tiến trình python đang mở đúng file CSV** (qua `/proc/<pid>/fd`) và gửi `SIGTERM`.
3. `do_nhiet_hop.py` bắt SIGTERM, tắt bóng, tắt quạt, giải phóng GPIO và ghi END. Đây đúng là đường xử lý đã có sẵn khi nhấn Ctrl+C.
4. Bridge đặt lại `value: false`, ghi `ket_qua`, rồi tạo một cảnh báo `DUNG_TU_XA`.

Lệnh quá 10 phút bị bỏ qua, để tránh trường hợp bridge vừa khởi động lại thì thực hiện một lệnh dừng cũ. Lệnh dừng từ xa **không thay thế** việc rút adapter 12 V khi tải không tắt.

## 7. Kiểm thử

```powershell
python -m unittest test_cloud_bridge -v
```

Có 21 test, không cần mạng, Firebase hay GPIO. Các test bao phủ:
- đọc CSV đang ghi dở, có BOM, có dấu phẩy trong ngoặc kép, cả định dạng cũ 16 cột;
- mẫu 5 s; các loại cảnh báo và giới hạn 5 phút;
- không có cảnh báo giả trên dữ liệu thật;
- gửi bù sau khi mất mạng mà không trùng dữ liệu, đọc tiếp sau khi khởi động lại;
- tóm tắt khớp báo cáo gốc;
- lệnh dừng chỉ xử lý một lần, bỏ qua lệnh cũ;
- tìm đúng tiến trình (giả lập `/proc`);
- tải lịch sử lên.

Phần **chưa** kiểm thử trên laptop: gửi SIGTERM thật trên Pi, và hành vi khi mất mạng thật trên Pi. Hai phần này để giai đoạn 5.
