# Checklist kiểm thử tích hợp (IoT Level-2) trên Pi

Dùng trong buổi làm với Pi và hộp. Ghi kết quả **thật** vào cột "Thực tế", chụp ảnh app hoặc lưu log theo cột "Bằng chứng". Ô nào không đạt thì ghi rõ hiện tượng, không bỏ trống. Hộp rỗng, có người theo dõi; nếu tải không tắt theo lệnh thì rút adapter 12 V.

## 0. Chuẩn bị (một lần)

| Bước | Lệnh hoặc việc | Đạt? |
|---|---|---|
| Phần cứng | Cầu chì 3 A trên dây +12 V; KSD301 nối tiếp bóng; dây DHT11 đúng (`python3 kiem_tra_dht11.py`) | ☐ |
| Chép code | Laptop: `scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/`, rồi `scp "D:\BTL_Nhom13\firebase_bi_mat.json" pi@pi:/home/pi/Code_HopAp_Demo/` | ☐ |
| Gói cần có | `sudo apt install -y tmux python3-requests` | ☐ |
| Đồng hồ | `timedatectl` hiện `System clock synchronized: yes` | ☐ |
| Dịch vụ bridge | `bash cai_dich_vu_bridge.sh`; app hiện **Pi online** | ☐ |
| Mẻ ấp | `python3 me_ap.py bat-dau --ngay 5`; app (thẻ Lịch ấp) hiện **Ngày 5/21 · Giai đoạn 1** | ☐ |
| Độ ẩm | `.venv/bin/python kiem_tra_dht11.py` đạt, rồi `bash cai_dich_vu_do_am.sh`; app hiện độ ẩm khi chưa chạy lượt | ☐ |

## 1. Các tình huống

| # | Tình huống | Cách làm | Mong đợi | Thực tế | Bằng chứng |
|---|---|---|---|---|---|
| T1 | Bridge tự chạy khi khởi động | `sudo reboot`, chờ khoảng 1 phút | App tự về **Pi online**, không cần SSH | | Ảnh app |
| T2 | Bắt đầu lượt | `bash chay_demo.sh` | App chuyển **Đang chạy**, đồ thị vẽ làm ấm rồi giữ nhiệt; OLED khớp với số trên app | | Ảnh app + OLED |
| T3 | Đổi ngày từ app | Thẻ Lịch ấp: ngày 12 → Đổi ngày (bấm 2 lần) | ≤ 5 s sau, pha trong CSV thành `ap_ngay12_gd2`; app có cảnh báo **Đổi ngày** và **Chuyển giai đoạn**; nhiệt hạ về 37,3–37,7 °C | | Ảnh app, thời gian vào vùng |
| T4 | Đổi ngày trên Pi | Ô tmux mới: `python3 me_ap.py dat-ngay 19` | App cập nhật ngày 19 / GĐ 3 trong ≤ 30 s; nhiệt hạ về 37,0–37,4 °C | | Ảnh app |
| T5 | Rớt SSH | Đóng cửa sổ SSH trên laptop, chờ 2 phút, SSH lại, `tmux attach -t hopap` | Lượt vẫn chạy (OLED và app vẫn cập nhật), không có END | | Ảnh app |
| T6 | Mất Internet | Ngắt Wi-Fi hoặc router (giữ nguồn Pi) khoảng 2 phút rồi bật lại | Trong lúc mất mạng: hộp vẫn giữ nhiệt (OLED), app hiện **Pi mất kết nối**. Có mạng lại: app online, **đồ thị không bị khuyết** đoạn mất mạng (bridge gửi bù) | | Ảnh app trước, trong và sau |
| T7 | Nghi mở nắp | Đang giữ nhiệt, mở nắp 30 s rồi đóng | Có cảnh báo **NGHI_MO_NAP** (khi bóng đang sưởi mà nhiệt tụt ≥ 0,5 °C/30 s). Nếu không có, ghi mức tụt thực tế để chỉnh ngưỡng | | Ảnh cảnh báo, mức tụt °C |
| T8 | Dừng khẩn cấp từ app | Bấm **Dừng lượt đang chạy** 2 lần | ≤ 10 s: bóng tắt, quạt chạy thêm 10 s rồi tắt, CSV có END; app ghi "Pi đã tắt bóng…" và cảnh báo **DUNG_TU_XA** | | Ảnh app, quan sát tải |
| T9 | Mất cảm biến | (Nên làm cuối buổi) Đang giữ nhiệt, rút dây DATA của DS18B20 | ≤ 3 s chương trình dừng và tắt bóng; app có **LOI_CAM_BIEN** / **KET_THUC** | | Ảnh app, log tmux |
| T11 | Bắt đầu lượt từ app bị từ chối | Hộp còn > 30 °C, hoặc không tích xác nhận, hoặc đang có lượt chạy | App ghi rõ "Pi từ chối: …", bóng không bật | | Ảnh app |
| T12 | Tạo mẻ và bắt đầu lượt hoàn toàn từ app | Thẻ Mẻ ấp: ngày 5, thời gian thật; thẻ Lượt chạy: RL 30 phút, tích xác nhận | App ghi "Đang chạy" và cảnh báo **BAT_DAU_LUOT**; `tmux attach -t hopap_app` thấy ap_trung đang chạy | | Ảnh app |
| T10 | Ngày còn đúng sau khởi động lại | `sudo reboot` rồi `python3 me_ap.py xem` | Vẫn đúng ngày (lịch lưu bền), app hiện đúng ngày | | Kết quả lệnh |

## 2. Lấy dữ liệu về

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_ap_trung "D:\BTL_Nhom13\Du_lieu_giu_nhiet"
```

Phân tích (laptop):

```powershell
cd D:\BTL_Nhom13
& "C:\Users\ADMIN\anaconda3\python.exe" Code_HopAp_PhanTich\phan_tich_ap_trung.py Du_lieu_giu_nhiet\ket_qua_ap_trung\<lượt_rl> Du_lieu_giu_nhiet\ket_qua_ap_trung\<lượt_thermostat> --out outputs\phan_tich_ap_trung
```

## 3. Ghi chú để đưa vào báo cáo

- Nhiệt độ phòng lúc đo (nhiệt kế): ……… °C
- Vị trí đầu dò, lỗ thông gió, nắp: giữ nguyên giữa các lượt? ☐
- Những tình huống không đạt và nguyên nhân: ………
