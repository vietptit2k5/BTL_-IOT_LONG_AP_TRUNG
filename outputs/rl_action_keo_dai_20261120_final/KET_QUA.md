# Q-learning hành động kéo dài — chỉ mô phỏng

REJECTED_SIMULATION_TRADEOFF

Mốc 37.5°C, vùng ±0.20°C.

|Policy|Trong vùng %|Đổi bóng/10phút|Đổi quạt/10phút|Đoạn trong vùng dài nhất s|
|---|---|---|---|---|
|Q5s tham chiếu|97.21|6.4|7.0|439.8|
|Q hành động kéo dài|96.13|5.8|8.1|419.7|

Giữ dự kiến30s trong vùng,10s ngoài vùng; được ngắt sớm khi qua biên hoặc bảo vệ. Không đảm bảo mọi lần giữ đủ30s.
Reward được tích lũy từng bước5s và bootstrap theo gamma^n; không chỉ lấy Q cũ rồi chặn đầu ra.
Q5s tham chiếu ở đây là ứng viên ba giai đoạn mô phỏng, không phải Q-table đang chạy trên Pi. Xem pair_changes trong JSON để đánh giá đổi action chung.
Chưa chạy trên Pi, không sửa chương trình đo hoặc chính sách đang hoạt động.
