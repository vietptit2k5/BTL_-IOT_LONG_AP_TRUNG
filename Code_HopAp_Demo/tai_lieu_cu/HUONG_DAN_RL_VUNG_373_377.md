> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Q-learning ưu tiên vùng 37.3–37.7°C

## Thử bàn giao gần biên trên (tùy chọn, chưa đo trên hộp)

Bản điều phối v3 thêm `--ban-giao 37`, `37.5` hoặc `37.65` và `--giu-giay 600` hoặc `1200`. Mặc định vẫn là bàn giao 37°C, giữ 600s. Q-table, vùng chấp nhận 37,3–37,7°C và reward đã huấn luyện giữ nguyên.

Để thử ý tưởng cho nhiệt tiến gần 37,7°C trước khi vào giữ nhiệt:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python thu_rl_du_lieu_moi.py --ban-giao 37.65 --giu-giay 1200
```

Dùng 37,65°C làm ngưỡng tiếp cận gần biên trên, có khoảng dự phòng trước 37,7°C; nhiệt bàn giao thực tế được ghi riêng, có thể cao hơn ngưỡng do chu kỳ đọc và quán tính. Dưới 37°C vẫn bóng 75%/quạt 100%; từ 37°C dùng bóng 50%/quạt 75% để tiếp cận chậm. Đạt ngưỡng mới bắt đầu RL và đồng hồ giữ nhiệt 20 phút. Nếu không đạt trong tổng 900s làm ấm thì dừng và ghi là chưa đạt điều kiện, không coi là phép thử giữ nhiệt thành công. Ngắt mềm 38→37°C, dừng cứng 38,5°C và mất số đo 3s vẫn áp dụng. Phục hồi khi nhiệt giảm sâu vẫn giao lại Q ở 37°C, không đổi theo tham số bàn giao ban đầu.

Để so sánh, mỗi lượt bắt đầu hộp rỗng, nhiệt <=30°C và gần bằng nhau (cố gắng lệch không quá 0,5°C), cùng bố trí và lỗ khí, không thay Q-table. Thử lần lượt:

```bash
.venv/bin/python thu_rl_du_lieu_moi.py --ban-giao 37 --giu-giay 1200
.venv/bin/python thu_rl_du_lieu_moi.py --ban-giao 37.5 --giu-giay 1200
.venv/bin/python thu_rl_du_lieu_moi.py --ban-giao 37.65 --giu-giay 1200
```

Các lệnh là **các lượt riêng**, phải để nguội về điều kiện đầu giữa các lượt, không chạy nối tiếp ngay. Nên lặp lại ít nhất 2 lần mỗi phương án và đảo thứ tự để giảm ảnh hưởng thay đổi môi trường. Nhiệt ban đầu chỉ là chỉ dấu điều kiện nền, chưa thay thế đo nhiệt độ phòng. Đây là so sánh **cả chiến lược tiếp cận và bàn giao**, không phải thí nghiệm chỉ thay nhiệt độ trong khi giữ nguyên bộ nhớ sưởi/xu hướng: chính các điều kiện đó cũng thay đổi và được ghi lại.

`ket_qua.json` tách **120 giây đầu** và **phần còn lại**: tỷ lệ trong vùng, MAE, nhiệt trung bình/min/max; thêm thời gian đến lần đầu ra khỏi vùng sau khi đã vào vùng. `cau_hinh.json` ghi nhiệt, xu hướng và bộ nhớ sưởi đúng lúc bàn giao. Nếu chỉ 2 phút đầu tốt hơn còn 18 phút sau vẫn giảm, bàn giao cao chỉ trì hoãn việc hạ nhiệt; cần sửa chính sách duy trì hoặc mô hình, không mặc định tăng ngưỡng là đã tối ưu. Chưa có dữ liệu thật chứng minh phương án 37,65°C tốt hơn. Lượt đang chạy không tự đổi theo file cập nhật; tùy chọn có hiệu lực ở lần khởi chạy mới.

## Phục hồi khi nhiệt giảm sâu (bản điều phối v2)

`thu_rl_du_lieu_moi.py` đã có chế độ làm ấm phục hồi bên cạnh Q-table. Khi đang giữ nhiệt mà số đo hợp lệ xuống dưới **36,6°C**, chương trình chuyển ngay sang **bóng 75% / quạt 100%**; lên **37°C** thì giao lại Q-table. Hai ngưỡng khác nhau tránh đổi qua lại liên tục. 36,6°C là ngưỡng thiết kế dựa trên miền nhiệt khởi tạo huấn luyện của ứng viên; không phải chương trình tự học được ngưỡng này. Mức phục hồi giống mức làm ấm ban đầu đã chạy trên hộp.

Nếu gặp state chưa có lượt thăm khi nhiệt dưới 37°C, chương trình cũng làm ấm phục hồi. State chưa học trong/gần vùng mục tiêu vẫn dừng; không tự tăng sưởi trong trường hợp đó. Mỗi lần phục hồi tối đa **450 giây**; không đạt 37°C trong giới hạn thì dừng thử. Lượt thử vẫn kết thúc sau 600 giây giữ nhiệt kể cả đang phục hồi, không tự kéo dài thời gian chạy.

Mất số đo hợp lệ quá 3 giây, sai đầu dò và ngắt quá nhiệt vẫn được ưu tiên. Bộ nhớ nhiệt không bị xóa khi chuyển chế độ. CSV ghi phase `kiem_tra_rl_moi_phuc_hoi`; cấu hình ghi phiên bản điều phối, số lượt và thời gian phục hồi. Q-table giữ nguyên, không học online.

Nhánh này đã kiểm thử bằng dữ liệu giả lập trong unit test và dry-run; **chưa thử giảm nhiệt đột ngột trên hộp thật**. Các số đo 93,83% bên dưới thuộc bản trước khi thêm nhánh phục hồi. Mã nguồn đúng của lượt đó được giữ ở `../Du_lieu_giu_nhiet/20261120_pilot_01/thu_rl_du_lieu_moi_v1.py`. Không dùng số đo cũ như kiểm chứng của chế độ phục hồi mới.

## Cập nhật từ dữ liệu thật ngày 20/11/2026

Đã phân tích lượt đo đủ 10 tổ hợp ở mốc 37,5°C, khớp lại mô hình, huấn luyện 24 ứng viên và chạy thử gói mới trực tiếp trên Pi. Chỉ một tổ hợp khảo sát (bóng 50% / quạt 100%) đủ 20 phút; các tổ hợp còn lại bị cắt kích thích theo giới hạn nhiệt, vẫn được dùng thận trọng để nhận dạng đáp ứng ngắn.

Lượt thử Q mới đã hoàn thành 600 giây giữ nhiệt: **93,83% trong 37,3–37,7°C**, MAE **0,109°C**, đổi bóng **8 lần**, đổi quạt **7 lần**, đổi tổ hợp **11 lần**, không ngắt quá nhiệt. Giữ nguyên một tổ hợp lâu nhất **261,7 giây**. Xét quyết định mỗi 5 giây; không bắt đổi mỗi 5 giây và không khóa cứng action trong vùng. Độ ẩm chỉ theo dõi; DHT11 không đọc được trong lượt này.

Kết quả giảm số lần đổi mức đã thấy trên phần cứng, nhưng tỷ lệ giữ vùng thấp hơn mô phỏng 98,05%. Mô hình còn tích lũy sai số dài hạn; đây là **bản thử có giám sát**, chưa chốt tối ưu và chưa xác nhận hai mốc nhiệt khác của lịch ba giai đoạn.

Báo cáo, đồ thị và đối chiếu với lượt Q cũ: [Phân tích lượt mới](../../outputs/rl_du_lieu_moi_20261120_v2/BAO_CAO.md). Dữ liệu vật lý đã chép về `../Du_lieu_giu_nhiet/20261120_pilot_01/`.

Chạy đúng bản mới trong Terminal Pi, khi hộp rỗng và nhiệt không quá 30°C:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python thu_rl_du_lieu_moi.py --dry-run
.venv/bin/python thu_rl_du_lieu_moi.py --dht11
```

Nếu chưa nối DHT11 thì bỏ `--dht11`; OLED mặc định bật. `Ctrl+C` dừng. Lệnh `kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl` vẫn chạy gói Q cũ. Các kết quả mô phỏng từ dữ liệu cũ ở phần dưới được giữ làm lịch sử nghiên cứu.

## Ưu tiên của người dùng: action không đổi liên tục

Đánh giá phải đếm **cặp action bóng/quạt thay đổi**, không chỉ đếm các lần đưa ra quyết định hay riêng mức bóng. Quyết định lại mỗi5giây vẫn có thể chọn giữ cùng action nhiều lần liên tiếp. Mục tiêu là thời gian giữ mức dài hơn trong vùng mà không tăng lệch nhiệt đáng kể.

Đã thử thêm Q-learning hành động kéo dài (semi-Markov), code `../Code_HopAp_PhanTich/hoc_action_keo_dai.py`: giữ dự kiến30s khi trong vùng,10s ngoài vùng; ngắt sớm khi qua biên hoặc guard. Reward cộng theo các bước5s thực tế và bootstrap theo gamma^n. Không lấy bảngQ5s rồi chặn đầu ra sau huấn luyện.

Kết quả ở `outputs/rl_action_keo_dai_20261120_final/`: tại mốc37.5°C, trung bình192kịch bản600s, tỷ lệ trong vùng giảm97.21→96.13%, số lần đổi cặp action giảm12.03→11.23; đổi bóng giảm6.40→5.75 nhưng đổi quạt tăng6.95→8.08. Tham chiếu là **ứng viên ba giai đoạn mô phỏng**, không phải bảng đang dùng trên Pi. Bản kéo dài bị đánh dấu `REJECTED_SIMULATION_TRADEOFF`, không áp dụng lên mạch.

Kết quả này không bác bỏ ưu tiên ít đổi action; nó cho thấy ép thời gian giữ30s chưa tự tạo chính sách tốt hơn. Dữ liệu đo phần cứng đang chuẩn bị vẫn cần để xác định mức sưởi cân bằng, độ trễ và thời gian giữ phù hợp. Chưa thay chu kỳ quyết định của chương trình chạyPi hoặc lịch đo đáp ứng.

Đã huấn luyện một Q-table ứng viên mới trong mô hình nhiệt từ dữ liệu đo cũ. Trung tâm 37.5°C, vùng chấp nhận 37.3–37.7°C. **Ứng viên chỉ dành cho mô phỏng, chưa thay chính sách trên Pi.** Độ ẩm không tham gia state/action/reward.

## Hành vi mong muốn

- Khi nhiệt ở trong vùng và xu hướng ổn định: ưu tiên tiếp tục mức bóng/quạt đang dùng, tránh đổi duty không cần thiết.
- Khi trong vùng nhưng đang tăng/giảm nhanh: vẫn cho phép đổi mức để tránh sắp ra ngoài. Không có quy tắc cứng “còn trong vùng thì cấm đổi”.
- Khi ra ngoài vùng: phạt sai lệch và thời gian ở ngoài, giảm chi phí đổi mức để không giữ nguyên một action không còn phù hợp.
- Trung tâm 37.5°C được ưu tiên mềm. Không bắt phải đạt đúng từng mẫu; không đảm bảo đứng yên tuyệt đối.

“Đổi mức” ở đây là thay duty PWM 0/25/50/75/100%, không phải đếm từng xung MOSFET 100Hz. Giữ nguyên duty vẫn có PWM.

## State mới và action

State: **9 mức sai lệch × 3 xu hướng × 5 mức bộ nhớ sưởi × 9 action trước × 2 trạng thái bảo vệ = 2.430 trạng thái**. Bộ nhớ sưởi EMA 25s theo lệnh PWM đã áp dụng là ước lượng, không phải nhiệt đo của bóng/thành hộp. Đây vẫn là xấp xỉ trạng thái của một hệ có phần động học chưa quan sát.

Action giữ chín tổ hợp cũ: bóng 0/25/50/75% kết hợp quạt 75/100%, và bóng 100%/quạt 75%. Không thêm 100/100 vào RL vì bộ dữ liệu nhận dạng cũ chưa xác nhận đủ tổ hợp đó. Chu kỳ quyết định mô phỏng 5 giây.

**Previous action được học trong state**, không chặn hoặc làm trơn đầu ra của Q-table cũ sau khi đã học. Chưa thêm thời gian giữ tối thiểu bắt buộc; số lần đổi mức do chính sách mới chọn dưới chi phí đã học.

## Reward

Đặt `e=abs(T_next-37.5)`, `o=max(0,e-0.2)/0.2`:

- Trong vùng: `1 - 0.5*(e/0.2)^2` mỗi bước.
- Ngoài vùng: `-1 - w_recovery*o - 2*o^2`.
- Thêm `0.5*(o_before-o_after)` để khuyến khích tiến về vùng.
- Chi phí đổi mức: `w_switch * (action_changed + abs(ΔH) + 0.5*abs(ΔF))`. H/F chuẩn hóa 0–1. Trong vùng tính đủ; ngoài vùng nhân 0.15.
- Phạt thêm 25 khi kích hoạt bảo vệ mềm 38→37°C. Guard có quyền ưu tiên hơn action RL.

Phần thưởng tích lũy khuyến khích dành nhiều bước trong vùng; nó không chứng minh thời gian hồi phục tối thiểu toàn cục hoặc chắc chắn vượt mọi thuật toán khác. Không sửa ngưỡng bảo vệ theo band 0.2°C.

Thử 8 bộ hệ số (`switch=0.25/0.5/1/2`, `recovery=2/4`), mỗi bộ 3 seed, **64.000 episode/seed**. Chọn cả hệ số và seed trên 128 kịch bản validation, sau đó kiểm tra ứng viên đã chốt trên 192 kịch bản khác. Có mô phỏng khởi đầu trong và ngoài vùng, nhiệt tích trữ khác nhau, nhiễu và nhiễu động cộng nhỏ. Đây không phải phép đo thời tiết thực.

Các lượt phát triển v1/v2 không đạt đủ tiêu chí được giữ trong thư mục outputs tương ứng, không triển khai. V3 chọn ứng viên theo validation với điều kiện bám vùng/hồi phục so với Q cũ trước khi xét giảm đổi mức. Lượt `final` tái chạy cùng thiết kế V3, bổ sung lưu toàn bộ kết quả hệ số, đối chiếu ghép cặp và dấu vết mã nguồn.

## Kết quả và chạy lại trên laptop

Xem `outputs/rl_vung_373_377_20261120_final/KET_QUA.md`, `ket_qua.json`, `thu_cac_he_so.json`, `so_sanh.csv`, `tung_kich_ban_MO_PHONG.csv`. File `Q_UNG_VIEN_CHUA_DUOC_CHAY_PI.json` có `deploy_allowed=false` và `supervised_pilot_allowed=false`.

Code tính state/reward: `rl_vung_on_dinh.py`. Code huấn luyện: `../Code_HopAp_PhanTich/hoc_vung_on_dinh.py`. Dùng Python Anaconda trên **laptop Windows**, không chạy chương trình huấn luyện này trên GPIO/Pi:

```powershell
cd D:\BTL_Nhom13
& "C:\Users\ADMIN\anaconda3\python.exe" Code_HopAp_PhanTich\hoc_vung_on_dinh.py --episodes 64000 --out outputs\rl_vung_lap_lai_moi
```

Trong Command Prompt thay `& "...python.exe"` bằng `"...python.exe"`. Thư mục output phải chưa tồn tại. Thư viện numpy/numba đã có trong môi trường Anaconda dùng khi huấn luyện. Không chạy lệnh này trong SSH trên Pi.

Chương trình `kiem_tra_giu_nhiet.py ... --bo-dieu-khien thu-rl` **vẫn dùng Q-table cũ**, không tự nhận ứng viên mới. Không chép đè file `goi_thu_rl_20261117.json` bằng ứng viên này: bộ mã hóa/state count/giao thức khác nhau.

## Giới hạn và bước kế tiếp

Kết quả là trên cùng mô hình được nhận dạng từ dữ liệu khảo sát ngày 17/11; chưa có CSV bài đo dài bổ sung. Mô hình cũ đã có sai lệch ở phát lại dài hạn, nên tỷ lệ bám vùng trong mô phỏng không phải hiệu năng đã đo của hộp. Khoảng bootstrap trong báo cáo chỉ thể hiện biến động các kịch bản mô phỏng, không bao gồm sai số mô hình.

Giữ nguyên file Q cũ và báo cáo gốc. Lấy kết quả bài đo dài, kiểm tra lại mô hình trước; sau đó mới đánh giá lại ứng viên, tạo loader riêng cho bộ mã hóa mới và thực hiện lượt thử có giám sát trên hộp rỗng. So với Q cũ ở cùng điều kiện, ghi cả số lần đổi duty, thời gian trong vùng, các lần vượt vùng, hồi phục và kích hoạt bảo vệ. Không tự động triển khai khi chỉ đạt gate mô phỏng.
