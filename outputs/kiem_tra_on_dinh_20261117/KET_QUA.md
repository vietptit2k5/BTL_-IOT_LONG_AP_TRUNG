# Kiểm tra hướng giữ mức ổn định — 17/11/2026

Kết quả mô phỏng thử bộ giữ mức sau Q-table cũ: **không đạt, không triển khai lên GPIO**. Mười hai cấu hình dùng giữ bóng 15/20/30 giây, giữ quạt 30/60 giây, vùng giữ ±0,1/±0,15°C đều cho kết quả nhiệt kém trong thử nghiệm này: MAE trung bình khoảng 0,30–0,37°C, thời gian trong vùng 37–38°C khoảng 73–82%.

Mô hình và Q-table giữ nguyên; 64 tình huống dùng block phần dư từ hai lượt nhiệt thực. Đây là phép kiểm tra độ nhạy phát triển, không phải một lượt đo phần cứng mới hoặc chứng minh mọi phương pháp giữ mức đều kém. Không so trực tiếp các số này với MAE đo thật 0,0568°C vì khác nguồn dữ liệu/điều kiện.

Đã loại bộ giữ mức thử khỏi thư mục chương trình Pi, giữ mã tại đây để có thể tái lập. File `thu_giu_muc_MO_PHONG.json` chứa cấu hình/chỉ số; `thu_bo_giu_muc.py` tái chạy phép thử offline.

Thay đổi đưa vào chương trình chính là **tùy chọn đo cặp mức cố định sau khi đạt 37,5°C**, không sửa policy RL cũ. Phép đo này sẽ kiểm tra điểm làm việc 50% bóng/75% quạt trước khi thiết kế RL mới ít đổi lệnh. Xem [hướng dẫn](../../Code_HopAp_Demo/HUONG_DAN_GIU_MUC_ON_DINH.md).

81 kiểm thử đã qua, gồm tiếp cận mục tiêu hai giai đoạn, giữ đúng mức khi đạt ngưỡng, dừng khi không đạt ngưỡng, ngắt nhiệt ưu tiên và giữ nguyên giao thức RL/thermostat cũ. Chưa chạy phép đo mức cố định mới lên phần cứng trong bước này.
