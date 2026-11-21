# Hộp ấp 3 giai đoạn điều khiển bằng Q-learning — IoT Level-2 (Nhóm 13)

Bài tập lớn môn **IoT và ứng dụng** (PTIT, GV TS. Nguyễn Đức Minh), Chương 6 *Reinforcement Learning* của sách *Hands-On Artificial Intelligence for IoT*.

Một hộp xốp giữ nhiệt theo lịch ấp trứng gà 21 ngày (37,8 / 37,5 / 37,2 °C, vùng ±0,2 °C). Raspberry Pi 4 đọc DS18B20, Q-learning chọn mức bóng sợi đốt 12 V và quạt 12 V mỗi 5 giây qua hai MOSFET. Dữ liệu được đẩy lên Firebase; app web https://hop-ap-nhom13.web.app dùng để theo dõi, tạo mẻ, bắt đầu lượt, đổi ngày và dừng khẩn cấp.

## Bạn cần đọc phần nào?

| Bạn muốn học | Bắt đầu ở | Thư mục chính |
|---|---|---|
| **Thuật toán RL và huấn luyện**: mô hình nhiệt, state/action/reward, Q-learning, mô phỏng, đánh giá | [tai_lieu/LO_TRINH_1_THUAT_TOAN_RL.md](tai_lieu/LO_TRINH_1_THUAT_TOAN_RL.md) | `Code_HopAp_PhanTich/` + phần RL trong `Code_HopAp_Demo/` |
| **Đo đạc và lấy dữ liệu thực tế**: phần cứng, đọc cảm biến, PWM, ghi CSV, khảo sát, giữ nhiệt, phân tích lượt | [tai_lieu/LO_TRINH_2_DO_DAC_DU_LIEU.md](tai_lieu/LO_TRINH_2_DO_DAC_DU_LIEU.md) | `Code_HopAp_Demo/` + `Du_lieu_*/` |
| **IoT, đám mây và app**: bridge, Firebase, dịch vụ trên Pi, app web | [tai_lieu/LO_TRINH_3_IOT_APP.md](tai_lieu/LO_TRINH_3_IOT_APP.md) | `Code_HopAp_Demo/cloud_bridge.py`, `App_HopAp/` |
| Tổng quan hệ thống, phần cứng, chạy demo | [Code_HopAp_Demo/README.md](Code_HopAp_Demo/README.md) | — |

## Cấu trúc thư mục

```text
BTL_Nhom13/
├── Code_HopAp_Demo/        Code chạy trên Raspberry Pi: đo, điều khiển, RL lúc chạy, bridge, dịch vụ, test
│   └── tai_lieu_cu/        Hướng dẫn của các giai đoạn trước (lưu trữ)
├── Code_HopAp_PhanTich/    Code chạy trên laptop: huấn luyện Q-learning, mô phỏng, phân tích lượt đo
├── App_HopAp/              App web PWA, quy tắc bảo mật Firebase, cấu hình Hosting
├── Du_lieu_khao_sat/       Số đo thật: khảo sát đáp ứng nhiệt 17/11/2026
├── Du_lieu_dap_ung/        Số đo thật: đáp ứng quanh 37,5 °C 20/11/2026 (dữ liệu huấn luyện Q2)
├── Du_lieu_giu_nhiet/      Số đo thật: các lượt giữ nhiệt (thermostat, Q1, Q2)
├── outputs/                Kết quả huấn luyện, mô phỏng, so sánh (báo cáo .md, đồ thị, Q-table)
├── GIUA_KY_Quat_Taxi/      Phần giữa kỳ: notebook Taxi Q-learning, demo quạt làm mát CPU
├── tai_lieu/               Lộ trình đọc code, hướng dẫn lắp, danh sách linh kiện, mô tả demo
└── NHAT_KY_TIEN_DO.md      Nhật ký tiến độ theo ngày
```

Tên các thư mục code và dữ liệu được giữ nguyên vì code và Pi tham chiếu tới chúng: script huấn luyện đọc `Du_lieu_*`, Pi chạy ở `/home/pi/Code_HopAp_Demo`, dịch vụ systemd trỏ vào thư mục đó.

## Cài nhanh để đọc và chạy thử (không cần Pi)

```bash
# Phân tích, mô phỏng, huấn luyện: Python 3.11+ có numpy, numba, matplotlib (ví dụ Anaconda)
cd Code_HopAp_Demo && python -m unittest discover -p "test_*.py"        # khoảng 217 test, không cần GPIO
cd ../Code_HopAp_PhanTich && python -m unittest discover -p "test_*.py"  # cần numpy, numba
python mo_phong_ba_giai_doan.py --seeds 5                                  # mô phỏng RL 3 giai đoạn
cd ../App_HopAp && node --test tests/logic.test.mjs                        # test logic của app
```

## Không có trong repo

- `firebase_bi_mat.json` (mật khẩu tài khoản Pi trên Firebase) và `.pi-access/` (khóa SSH): **không bao giờ đẩy lên git**. Ai cần chạy bridge thì xin riêng trưởng nhóm.
- `tai_lieu/rieng_tu/` (ghi âm buổi học, sách có bản quyền), `_LUU_TRU_FILE_THUA/`, file Office của phần giữa kỳ.
- File tạo ra lúc chạy trên Pi: `ket_qua_ap_trung/`, `logs/`, `trang_thai_me_ap.json`, `do_am_moi_nhat.json`, `.cloud_bridge/`.
