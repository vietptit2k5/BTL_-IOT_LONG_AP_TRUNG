# Kế hoạch đo đầy đủ — chưa phải dữ liệu thực

15 đợt, 30 phép kích thích; quạt75/100, bóng0/25/50/75/100 tại ba mốc.
Tổng giới hạn các đợt khoảng 21.30 giờ; chưa tính để hộp nguội và thao tác.

Mỗi đợt bắt đầu hộp rỗng ≤30°C, giữ nguyên bố trí, có người theo dõi. Chạy từng lệnh, lấy dữ liệu và để hộp nguội trước đợt sau; không dán toàn bộ lệnh chạy liên tục.
Dừng sớm do giới hạn nhiệt phải ghi là rút ngắn. Không bỏ bảo vệ để lấy đủ20phút; mức100/100 được khảo sát như kích thích, chưa mặc định là action RL đã có bằng chứng.
Tên giai đoạn chỉ chọn mốc nhiệt khảo sát, chưa tái tạo sinh nhiệt của phôi. 20phút chưa chắc đủ cân bằng.

|Đợt|Lặp|Mốc °C|Bóng %|Thứ tự quạt %|Lệnh chạy trên Pi|
|---|---|---|---|---|---|
|1|1|37.5|0|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 0`|
|2|1|37.5|25|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 25`|
|3|1|37.5|50|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 50`|
|4|1|37.5|75|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 75`|
|5|1|37.5|100|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 100`|
|6|1|37.2|0|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 3 --do-dai --muc-bong 0`|
|7|1|37.2|25|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 3 --do-dai --muc-bong 25`|
|8|1|37.2|50|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 3 --do-dai --muc-bong 50`|
|9|1|37.2|75|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 3 --do-dai --muc-bong 75`|
|10|1|37.2|100|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 3 --do-dai --muc-bong 100`|
|11|1|37.8|0|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 1 --do-dai --muc-bong 0`|
|12|1|37.8|25|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 1 --do-dai --muc-bong 25`|
|13|1|37.8|50|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 1 --do-dai --muc-bong 50`|
|14|1|37.8|75|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 1 --do-dai --muc-bong 75`|
|15|1|37.8|100|[75, 100]|`.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 1 --do-dai --muc-bong 100`|

Thêm --dry-run vào một lệnh để kiểm tra kế hoạch, không bật tải. Thêm --dht11 nếu cần ghi RH.
Một lượt chỉ xác nhận độ phủ; muốn kiểm tra độ lặp lại thì tạo kế hoạch --lap2. Lượt chẵn đảo thứ tự các đợt và cặp quạt.
Sau đo, điền đường dẫn CSV thật và trạng thái vào ma_tran.csv; không đổi measured thành YES chỉ vì kế hoạch đã tạo hoặc mô phỏng đạt.
Chọn thêm mức25/50% quạt hoặc quạt0% là một bài khác; không thuộc ma trận này và không tự nới giới hạn của thử quạt0.
