# Lộ trình 3 — IoT Level-2: dịch vụ trên Pi, Firebase, app web

Dành cho người học phần **"IoT"** của hệ thống:
- Pi tự đo và tự điều khiển cục bộ;
- một dịch vụ nền gửi dữ liệu lên Firebase và nhận lệnh;
- app web hiển thị trực tiếp và gửi lệnh.

Toàn bộ code có test chạy trên laptop.

| Thứ tự | File | Học gì |
|---|---|---|
| 1 | [../Code_HopAp_Demo/HUONG_DAN_CLOUD.md](../Code_HopAp_Demo/HUONG_DAN_CLOUD.md) | Kiến trúc mức 2, cấu trúc dữ liệu trên Firebase, các loại cảnh báo, lệnh dừng |
| 2 | [../Code_HopAp_Demo/cloud_bridge.py](../Code_HopAp_Demo/cloud_bridge.py) | `CsvTail` (đọc CSV đang ghi), `Engine` (mẫu 5 s, sự kiện, cảnh báo), `FirebaseStore` (REST + đăng nhập), `Bridge` (vòng chạy, gửi bù khi mất mạng, lệnh dừng / đổi ngày / mẻ / lượt, kiểm tra an toàn trước khi bật tải) |
| 3 | [../Code_HopAp_Demo/me_ap.py](../Code_HopAp_Demo/me_ap.py) | Lịch 21 ngày lưu bền; tạm dừng lịch demo |
| 4 | [../Code_HopAp_Demo/cai_dich_vu_bridge.sh](../Code_HopAp_Demo/cai_dich_vu_bridge.sh), [cai_dich_vu_do_am.sh](../Code_HopAp_Demo/cai_dich_vu_do_am.sh), [chay_demo.sh](../Code_HopAp_Demo/chay_demo.sh) | Dịch vụ systemd (`KillMode=process`), chạy lượt trong tmux |
| 5 | [../App_HopAp/HUONG_DAN_APP.md](../App_HopAp/HUONG_DAN_APP.md) | Chức năng của app, deploy lên Firebase Hosting |
| 6 | [../App_HopAp/public/logic.js](../App_HopAp/public/logic.js) → [app.js](../App_HopAp/public/app.js) | Logic thuần (có test) và phần nối giao diện với Firebase |
| 7 | [../App_HopAp/database.rules.json](../App_HopAp/database.rules.json) | Quy tắc bảo mật: ai đọc, ai ghi, kiểm tra tham số của lệnh |
| 8 | [../Code_HopAp_Demo/KIEM_THU_TICH_HOP.md](../Code_HopAp_Demo/KIEM_THU_TICH_HOP.md) | 12 tình huống kiểm thử trên phần cứng thật |

```bash
cd Code_HopAp_Demo && python -m unittest test_cloud_bridge test_ap_trung test_do_am -v
cd ../App_HopAp && node --test tests/logic.test.mjs
python ../Code_HopAp_Demo/cloud_bridge.py phat-lai ../Du_lieu_giu_nhiet/20261120_pilot_01/du_lieu.csv --toc-do 20 --ghi-file thu_db   # chạy thử không cần Firebase
```

Muốn chạy với Firebase thật thì cần file `firebase_bi_mat.json`. File này **không có trong repo**, xin riêng trưởng nhóm. Deploy app: `cd App_HopAp && firebase deploy --only database,hosting` (cần quyền vào project Firebase).
