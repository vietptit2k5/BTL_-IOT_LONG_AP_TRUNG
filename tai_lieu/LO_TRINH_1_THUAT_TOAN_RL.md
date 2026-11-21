# Lộ trình 1 — Thuật toán RL và huấn luyện

Dành cho người học **cách nhóm thiết kế, huấn luyện và kiểm chứng Q-learning** cho hộp ấp. Toàn bộ lộ trình chạy trên laptop, **không cần Raspberry Pi**. Nên đọc theo thứ tự dưới đây: mỗi bước dựa trên bước trước.

**Ý tưởng chính:** không thể học trực tiếp trên hộp, vì 64.000 episode tương đương hàng nghìn giờ chạy máy. Nhóm làm theo 4 bước:
1. đo đáp ứng thật của hộp;
2. khớp một **mô hình nhiệt 5 giây** từ số đo đó;
3. **huấn luyện Q-learning trên mô hình**;
4. chạy Q-table đã đóng băng trên hộp thật và so sánh với thermostat.

## Bước 0 — Lý thuyết (sách Chương 6)

| File | Học gì |
|---|---|
| [../GIUA_KY_Quat_Taxi/taxi_v3_q_table_demo_with_test_results.ipynb](../GIUA_KY_Quat_Taxi/taxi_v3_q_table_demo_with_test_results.ipynb) | Q-learning dạng bảng trên Taxi-v3: phương trình cập nhật Bellman, ε-greedy |
| [../GIUA_KY_Quat_Taxi/taxi_v3_qnetwork_demo_numbers_compare_qtable.ipynb](../GIUA_KY_Quat_Taxi/taxi_v3_qnetwork_demo_numbers_compare_qtable.ipynb) | Q-Network tuyến tính so với Q-table |
| [../GIUA_KY_Quat_Taxi/Baocao_Nhom13_Chuong6/Code_Quat_QLearning/quat/fan_qlearning.py](../GIUA_KY_Quat_Taxi/Baocao_Nhom13_Chuong6/Code_Quat_QLearning/quat/fan_qlearning.py) | Bản đầu tiên trên phần cứng (giữa kỳ): 32 state, 3 action, mô phỏng rồi chạy trên Pi |

## Bước 1 — Mô hình nhiệt của hộp

Mô hình dự đoán mức thay đổi nhiệt độ trong 5 giây, ΔT, từ:
- nhiệt độ hiện tại,
- ΔT của bước trước,
- **bộ nhớ sưởi** (mức bóng đã làm mượt theo hằng số thời gian 25 s),
- mức quạt,
- tương tác giữa sưởi và quạt.

| File | Phần cần đọc |
|---|---|
| [../Code_HopAp_Demo/phan_tich_reward.py](../Code_HopAp_Demo/phan_tich_reward.py) | `read_log`, `transitions`, `features`, `ThermalModel`, `identify` (khớp mô hình bằng bình phương tối thiểu), `model_metrics` (sai số dự đoán 30/60 s) |
| [../Code_HopAp_PhanTich/hoc_du_lieu_moi.py](../Code_HopAp_PhanTich/hoc_du_lieu_moi.py) | `fit`, `identify`: khớp mô hình từ dữ liệu 20/11, chọn hằng số thời gian bằng kiểm định theo từng chu kỳ |
| Dữ liệu dùng | [../Du_lieu_khao_sat/](../Du_lieu_khao_sat/) (17/11), [../Du_lieu_dap_ung/](../Du_lieu_dap_ung/) (20/11, 9.862 mẫu) |
| Kết quả nên đọc | [../outputs/phan_tich_khao_sat_20261117/](../outputs/phan_tich_khao_sat_20261117/), phần "Nhận dạng mô hình" trong [../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md](../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md) |

## Bước 2 — Q1: Q-table đầu tiên (17/11)

- **State:** 162 = 9 mức sai lệch × 3 xu hướng × 3 mức bộ nhớ sưởi × 2 cờ bảo vệ.
- **Action:** 9 cặp (bóng %, quạt %).
- **Reward:** chỉ phạt sai lệch, không phạt đổi mức.

So sánh Q-learning với Expected SARSA.

| File | Phần cần đọc |
|---|---|
| [../Code_HopAp_Demo/toi_uu_rl_offline.py](../Code_HopAp_Demo/toi_uu_rl_offline.py) | `state`, `epsilon_at`, `expected_value`, `step_reward`, `train_checkpoints` (vòng học), `rollout`, `evaluate`, `rank` |
| [../Code_HopAp_Demo/chinh_sach_rl.py](../Code_HopAp_Demo/chinh_sach_rl.py) | Chạy Q-table đã đóng băng trên Pi (không học online) |
| [../Code_HopAp_Demo/goi_thu_rl_20261117.json](../Code_HopAp_Demo/goi_thu_rl_20261117.json) | Gói Q1: mô hình, Q, số lần ghé từng state |
| Kết quả | [../outputs/toi_uu_rl_v2_20261117/](../outputs/toi_uu_rl_v2_20261117/), đo thật: [../outputs/so_sanh_RL_THUC_20261117/KET_QUA.md](../outputs/so_sanh_RL_THUC_20261117/KET_QUA.md) |

Q1 bám nhiệt tốt nhất (MAE 0,057 °C) nhưng **đổi mức 88 lần mỗi 10 phút**. Đây là lý do có Q2.

## Bước 3 — Q2: thêm phạt đổi mức (20/11), bộ điều khiển đang dùng

- **State:** 2.430 = 9 mức sai lệch × 3 xu hướng × 5 mức bộ nhớ sưởi × 9 hành động trước × 2 cờ bảo vệ.
- **Reward:**
  - trong vùng ±0,2 °C: thưởng nhiều hơn khi càng gần mốc;
  - ngoài vùng: bị phạt;
  - đổi mức: bị phạt, trong vùng phạt nặng hơn ngoài vùng;
  - chạm bảo vệ: −25.

| File | Phần cần đọc |
|---|---|
| [../Code_HopAp_Demo/rl_vung_on_dinh.py](../Code_HopAp_Demo/rl_vung_on_dinh.py) | **Đọc kỹ file này trước:** `state_id` và `reward`, chỉ 35 dòng |
| [../Code_HopAp_PhanTich/hoc_vung_on_dinh.py](../Code_HopAp_PhanTich/hoc_vung_on_dinh.py) | `step` (mô hình 5 s), `train` (Q-learning tăng tốc bằng numba), `rollout`, `cases`, `evaluate` |
| [../Code_HopAp_PhanTich/hoc_du_lieu_moi.py](../Code_HopAp_PhanTich/hoc_du_lieu_moi.py) | `training`: 24 cấu hình × 64.000 episode, chọn trên 128 tình huống kiểm định, đánh giá trên 192 tình huống khác |
| [../Code_HopAp_PhanTich/bao_cao_du_lieu_moi.py](../Code_HopAp_PhanTich/bao_cao_du_lieu_moi.py) | Dựng lại báo cáo và đồ thị từ dữ liệu |
| [../Code_HopAp_Demo/goi_rl_moi_20261120.json](../Code_HopAp_Demo/goi_rl_moi_20261120.json) | Gói Q2 đang chạy trên Pi. **Không sửa file này:** Pi kiểm tra mã SHA-256 trước khi dùng |
| Kết quả | [../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md](../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md) |

## Bước 4 — Từ Q-table tới điều khiển thật, 3 giai đoạn

| File | Phần cần đọc |
|---|---|
| [../Code_HopAp_Demo/thu_rl_du_lieu_moi.py](../Code_HopAp_Demo/thu_rl_du_lieu_moi.py) | `read_package` (kiểm tra gói), `NewPilot`: làm ấm, giao cho Q, phục hồi, bảo vệ |
| [../Code_HopAp_Demo/ap_trung.py](../Code_HopAp_Demo/ap_trung.py) | `ApTrungPolicy`: **dịch mốc** `T' = T − (M − 37,5)` để dùng Q2 cho 37,8 / 37,5 / 37,2 °C; xử lý state chưa học; thermostat đối chứng |
| [../Code_HopAp_Demo/me_ap.py](../Code_HopAp_Demo/me_ap.py) | Lịch 21 ngày, tạm dừng lịch demo |
| [../Code_HopAp_Demo/chinh_sach_nhiet.py](../Code_HopAp_Demo/chinh_sach_nhiet.py) | `SoftGuard` (bảo vệ mềm), `ReferenceController` (thermostat/PID dùng làm đối chứng) |

## Bước 5 — Kiểm chứng bằng mô phỏng

| File | Học gì |
|---|---|
| [../Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py](../Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py) | Chạy **đúng class `ApTrungPolicy` dùng trên Pi** trên mô hình nhiệt: giữ từng mốc, đổi ngày giữa chừng, so với thermostat |
| [../Code_HopAp_Demo/danh_gia_giu_nhiet.py](../Code_HopAp_Demo/danh_gia_giu_nhiet.py) | Đối chiếu dự báo của mô hình với một lượt đo mới |
| Kết quả | [../outputs/mo_phong_ba_giai_doan/KET_QUA.md](../outputs/mo_phong_ba_giai_doan/KET_QUA.md) và `DOI_NGAY_MO_PHONG.png` |

## Thí nghiệm phụ (đọc khi đã nắm phần chính)

| File | Nội dung | Kết luận |
|---|---|---|
| [../Code_HopAp_PhanTich/qtable_study.py](../Code_HopAp_PhanTich/qtable_study.py) + `results/*.npz` | Nghiên cứu thiết kế ban đầu trên mô hình giả định: so sánh các kiểu state (chỉ T; T + xu hướng; T + xu hướng + bộ nhớ), trọng số phạt nóng và phạt năng lượng, 3 seed | Chỉ là mô phỏng (`SIM_ONLY`) |
| [../Code_HopAp_PhanTich/hoc_ba_giai_doan.py](../Code_HopAp_PhanTich/hoc_ba_giai_doan.py) | 3 Q-table riêng cho 3 giai đoạn | Giai đoạn 1 vướng ngưỡng bảo vệ cũ (38 °C), không triển khai |
| [../Code_HopAp_PhanTich/hoc_action_keo_dai.py](../Code_HopAp_PhanTich/hoc_action_keo_dai.py) + [../Code_HopAp_Demo/giu_hanh_dong_rl.py](../Code_HopAp_Demo/giu_hanh_dong_rl.py) | Semi-Markov: giữ hành động 30 s trong vùng | Bị loại: đánh đổi không có lợi |

## Chạy thử

Cần Python 3.11+ có `numpy`, `numba`, `matplotlib`. Chạy từ thư mục gốc repo:

```bash
python Code_HopAp_PhanTich/qtable_study.py --test                                   # chạy nhanh để kiểm tra
python Code_HopAp_PhanTich/hoc_du_lieu_moi.py --out outputs/thu_lai --episodes 4000  # huấn luyện lại Q2 (giảm episode cho nhanh)
python Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py --seeds 5 --out outputs/thu_mo_phong
python -m unittest discover -s Code_HopAp_PhanTich -p "test_*.py"
```

Luôn ghi kết quả vào **thư mục mới** (`--out`), không ghi đè các thư mục `outputs/*_final` và `*_v2` mà báo cáo đang dẫn tới.

**Bài tập gợi ý:**
1. Đổi hệ số phạt đổi mức trong `rl_vung_on_dinh.reward` (0 / 1 / 3), huấn luyện lại, so số lần đổi mức với độ bám nhiệt.
2. Vẽ policy: với mỗi mức sai lệch, Q2 chọn hành động nào?
3. Thử bỏ bộ nhớ sưởi khỏi state và xem kết quả xấu đi thế nào.
