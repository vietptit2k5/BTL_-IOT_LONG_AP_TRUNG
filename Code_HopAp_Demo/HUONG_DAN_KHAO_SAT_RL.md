# Tự đo đáp ứng nhiệt và thử hệ số reward cho RL

Chương trình mới: [khao_sat_nhiet.py](khao_sat_nhiet.py). Nó tự đổi mức bóng/quạt, đo nhiệt bằng DS18B20, ghi dốc nhiệt °C/phút, rồi gọi [phan_tich_reward.py](phan_tich_reward.py) để thử hệ số reward **offline trong mô phỏng khớp từ CSV**. Phần điều khiển và bảo vệ tái sử dụng [do_nhiet_hop.py](do_nhiet_hop.py), OLED dùng [oled_hop_ap.py](oled_hop_ap.py). Chép cả thư mục, không chỉ một file.

**Đây chưa phải chương trình cho RL tự khám phá hoặc tự đổi hệ số trực tiếp trên hộp thật.** Phép đo thật có lịch kích thích giới hạn; việc thử 18 bộ reward và Q-learning diễn ra sau khi tải đã được yêu cầu tắt. Không coi kết quả mô phỏng là bằng chứng tăng tỷ lệ nở hoặc RL chắc chắn hơn PID.

## 1. Chuẩn bị và chạy

Dùng đúng cấu hình hai MOSFET, quạt 12 V, bóng 12 V và DS18B20. Theo yêu cầu cập nhật, chương trình khảo sát **bóng 0/25/50/75/100% và quạt 75/100%** ở cùng tần số PWM 100 Hz. Người dùng trước đó đã xác nhận quạt quay ổn định ở 50%; vẫn quan sát mức 75% khi bắt đầu và kiểm tra lại nếu đổi quạt/tần số. Phần mềm không có phản hồi RPM hoặc đo dòng để biết tải thật sự hoạt động.

DS18B20/OLED phải đọc được, cả hai MOSFET phải bật/tắt đúng. Giữ cách lắp đã kiểm tra trong [hướng dẫn đo nhiệt](HUONG_DAN_DO_NHIET.md). Chỉ khảo sát **hộp rỗng hoặc tải mô phỏng, có người theo dõi**, bóng gắn chắc và có chắn nhiệt tách khỏi xốp. Không dùng trứng có phôi để khám phá. Không chạy chương trình điều khiển GPIO18/23 khác đồng thời. Giữ bộ ngắt nhiệt đang có; ngưỡng phần mềm không thay bảo vệ điểm nóng/phần cứng.

Trên **Terminal laptop Windows**:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
ssh pi@pi
```

Trên **Pi**, xem kế hoạch trước, lúc adapter 12 V đang rút:

```bash
cd /home/pi/Code_HopAp_Demo
python3 khao_sat_nhiet.py do --dry-run
```

Sau khi kiểm tra dây và cảm biến, cấp adapter 12 V cho tải rồi chạy:

```bash
python3 khao_sat_nhiet.py do
```

**Không cần nhập `dat`, không cần nhập `y`.** Chương trình tự đổi mức và in nhiệt độ, dốc nhiệt, duty bóng/quạt và tên bước. OLED hiện `AUTO`, `WARMUP`, `SOFT GUARD` hoặc trạng thái lỗi. Ctrl+C để dừng. Nếu tải không tắt theo lệnh, rút adapter 12 V. Riêng các tổ hợp có **40 phút đo**; tổng danh định khoảng **43–46 phút** tùy đoạn làm ấm, chưa tính chờ hạ nhiệt. Giới hạn toàn lượt mặc định **90 phút**. Đây là khảo sát dài hơn buổi demo 10 phút đã trao đổi trước đó; không tự chạy nếu không bố trí theo dõi được hết lượt.

Không thêm thư viện AI nặng: phần khảo sát/phân tích/RL mới dùng thư viện chuẩn Python. Các thư viện GPIO/OLED vẫn như hướng dẫn cũ. Nếu chưa lắp OLED:

```bash
python3 khao_sat_nhiet.py do --khong-oled
```

## 2. Lịch thử mặc định

| Giai đoạn | Cách chạy |
|---|---|
| Nền ban đầu | Bóng 0%, quạt 100%, khoảng 60 giây; chưa tự coi đây là nhiệt độ phòng |
| Làm ấm | Bóng 75%, quạt 100%, đến khoảng 37°C hoặc tối đa 180 giây |
| Khảo sát tổ hợp | Bóng **0/25/50/75/100%** × quạt **75/100%** = **10 tổ hợp**; mỗi tổ hợp xuất hiện hai lần, **120 giây/lần** |
| Ngừng sưởi | Bóng 0%, quạt 100%, khoảng 120 giây |
| Kết thúc | Gửi lệnh tắt bóng, giữ quạt 100% thêm 10 giây nếu đã có sưởi, rồi tắt hết |

Thứ tự **20 kích thích** được trộn bằng seed 31 và được lưu lại; không phải tùy ý thử PWM ngoài các mức đã chọn. Thời gian mỗi tổ hợp không bị nén xuống nếu đặt giới hạn cả lượt ngắn; khi hết giới hạn thì dừng và ghi thiếu dữ liệu. Hai lần lặp giúp xem mức độ lặp lại của đáp ứng; không bảo đảm nhiệt đã cân bằng sau đúng 120 giây.

Mục tiêu mặc định **37,5°C**, dung sai **±0,5°C**. Khi đo được **38°C**, lớp khảo sát tạm đặt bóng 0%/quạt 100%, chờ xuống khoảng **37°C** rồi tiếp tục. Thời gian chờ vẫn nằm trong ngân sách cả lượt và không tính vào thời gian yêu cầu cấp tổ hợp. Khi quay lại, CSV tách thành đoạn liên tục mới: **không cộng hai đoạn 60 giây bị ngắt để gọi là 120 giây liên tục**. Nếu chờ lâu, lịch có thể chưa hoàn tất. Không giả định quạt trong hộp kín hạ nhiệt như một hệ làm lạnh chủ động.

Đạt **40°C**, lỗi cảm biến, CRC lỗi hoặc không có mẫu mới trong 3 giây: cơ chế gốc dừng lượt, không tự khởi động lại. Ngân sách cả lượt mặc định **5.400 giây/90 phút**, cho phép cấu hình tối đa **7.200 giây/120 phút**, cộng thời gian khởi tạo ngắn và tối đa 10 giây giữ quạt cuối. Đây là lớp dừng phần mềm độc lập với lịch/RL, không thay công tắc phần cứng và không bảo đảm an toàn cho trứng/xốp. Các chế độ thủ công `doc/giu/tay/kich-ban` trong `do_nhiet_hop.py` vẫn giữ giới hạn 10 phút; chỉ bộ khảo sát tự động dùng giới hạn mở rộng.

Đổi thời gian mỗi tổ hợp, ví dụ **180 giây**, hai lần lặp (khoảng 63–66 phút danh định), giữ giới hạn 90 phút:

```bash
python3 khao_sat_nhiet.py do --moi-to-hop 180 --lap 2 --gioi-han-phut 90
```

Muốn quan sát 300 giây/tổ hợp, cần tăng cả ngân sách lượt để chứa lịch (khoảng 103–106 phút danh định):

```bash
python3 khao_sat_nhiet.py do --moi-to-hop 300 --lap 2 --gioi-han-phut 120
```

Rút xuống một lần mỗi tổ hợp bằng `--lap 1` thì mặc định khoảng 23–26 phút danh định, nhưng chưa có mẫu lặp. Có thể chỉ định mức rõ ràng:

```bash
python3 khao_sat_nhiet.py do --muc-bong 0 25 50 75 100 --muc-quat 75 100 --moi-to-hop 120 --lap 2
```

Các phần trăm là duty được gửi, không xác nhận W/Wh, RPM hoặc luồng gió thật. Đặc biệt bóng 100% có thể đạt ngưỡng trước 120 giây; không bỏ ngắt nhiệt để ép đủ thời gian. Báo cáo sẽ ghi đoạn đó chưa đủ thời gian và không tự đưa action chưa đủ cửa sổ đo vào Q-table.

## 3. Đo sự tăng/giảm nhiệt thế nào?

- CSV thô lưu nhiệt khoảng mỗi giây, thời điểm đổi lệnh, duty yêu cầu và duty gửi, gồm cả xung khởi động quạt.
- Cột `trend_c_per_min` và dòng Terminal dùng hồi quy tuyến tính trên tối đa 30 giây gần nhất; cần ít nhất 10 giây và 5 mẫu. Chưa đủ thì để trống/hiện `--`, không gán tốc độ bằng 0.
- Báo cáo mỗi bước ghi nhiệt đầu/cuối, ΔT và dốc °C/phút. Đoạn khởi động và 5 giây đầu được bỏ khi tính dốc đại diện. Dốc dương là tăng, âm là giảm; ngưỡng gần ổn định chỉ là cách tóm tắt, chưa phải kết luận thống kê về ảnh hưởng quạt.
- Bước bị ngắt mềm được tách thành đoạn riêng. Không lấy nhiệt độ cuối các bước có nhiệt ban đầu khác nhau để khẳng định quạt nào tốt hơn.
- `planned_duration_s`, `duration_s`, `stable_span_s`, `continuous_window_complete`: thời gian yêu cầu, đoạn quan sát thực, khoảng còn lại sau loại đoạn đầu/khởi động và đã có cửa sổ liên tục đủ thời gian hay chưa. Có dung sai vài giây cho chu kỳ đọc mẫu, không cộng gộp các đoạn bị ngắt.
- `last_30s_slope_c_per_min`, `near_flat_hint`: dốc 30 giây cuối và chỉ báo gần phẳng. Chỉ báo cần ít nhất 60 giây quan sát sau đoạn đầu, dốc cuối không quá 0,1°C/phút và độ lệch chuẩn cuối không quá 0,1°C. Đây là quy tắc theo dõi ban đầu, **không chứng minh trạng thái cân bằng hoặc thời gian xác lập thật**. Tăng thời gian nếu nhiệt còn trôi, nhưng vẫn giữ ngắt nhiệt.

Để đánh giá ảnh hưởng quạt, cần xét nhiệt ban đầu và nhiệt đã tích trước đó. Một đầu dò chỉ đo tại vị trí đặt; muốn đánh giá đều nhiệt phải đo ở nhiều vị trí. Giữ nguyên vị trí đầu dò, cách chắn bức xạ, nắp hộp, khay/nước/tải và điều kiện phòng giữa các lượt được gộp.

## 4. Khớp mô hình và điều kiện để thử reward

Chương trình dựng mô hình tự hồi quy địa phương với bước 5 giây: ΔT phụ thuộc nhiệt độ hiện tại, xu hướng trước đó, lịch sử lệnh sưởi, mức quạt và tương tác sưởi–quạt. Nó thử bộ nhớ nhiệt có hằng số 0/10/25 giây, giải least-squares bằng QR, báo thiếu hạng thay vì tự thêm thông số giả. Không mặc định quạt cao luôn làm nhiệt giảm.

Mỗi CSV được chia **60% train, 20% validation, 20% test theo thời gian**, có khoảng cách 10 giây giữa các phần. Chọn bộ nhớ nhiệt bằng validation; test chỉ đánh giá sau khi đã chọn. Kiểm tra dự báo một bước và chạy dự báo 30 giây dùng các lệnh đã đo. Không chia ngẫu nhiên các hàng gần nhau để tạo kiểm định dễ giả tạo.

Các điều kiện chất lượng khởi đầu của công cụ gồm: có đoạn tăng/giảm nhiệt đủ dài; ít nhất ba mức bóng/hai mức quạt có mẫu đủ; dữ liệu cùng mã đầu dò và tần số PWM; có đủ các phần train/validation/test; hệ số ổn định, tác dụng sưởi hợp lý; dự báo trên phần giữ lại đủ tốt và hơn dự báo giữ nguyên nhiệt. Với lịch tự động, chỉ đưa action có ít nhất một cửa sổ liên tục đạt thời gian yêu cầu vào tập action của Q-table. Action bị loại được liệt kê; không tự giả định đã khảo sát đủ cả mười. Vùng quanh mục tiêu phải nằm trong vùng nhiệt đã khảo sát với biên nhỏ 0,25°C. Các ngưỡng này là quy tắc kiểm tra ban đầu của chương trình, không phải chứng nhận mô hình đúng.

Nếu không đạt, vẫn xuất bảng đáp ứng nhưng ghi **NEEDS_MORE_MEASUREMENTS**, lý do thiếu dữ liệu và **không xuất Q-table/reward như một kết quả đã tối ưu**. Ví dụ nếu hộp mới lên 32°C, không dùng mô hình đó để tuyên bố điều khiển tốt ở 37,5°C. Đo thêm hoặc điều chỉnh phần cứng/lịch đo theo điều kiện thực.

## 5. Thử và sai với reward, thực hiện offline

Sau khi tải đã được yêu cầu tắt và mô hình vượt kiểm tra, chương trình thử:

```text
r = - |T - T_mục_tiêu| / dung_sai
    - w_hot × [max(0, T - T_mục_tiêu - dung_sai) / dung_sai]²
    - w_duty × (duty_bóng + duty_quạt) / 2
    - w_switch × (|Δduty_bóng| + |Δduty_quạt|)
```

Duty trong công thức tính từ 0 đến 1. Hệ số sai số nhiệt cố định bằng 1 để tránh chỉ thay thang điểm. Grid hiện tại là `w_hot = 1/3/10`, `w_duty = 0/0.05/0.2`, `w_switch = 0/0.03`: **18 bộ**. Tốc độ nhiệt dùng xây mô hình, không xác định duy nhất ba hệ số này. `(duty_bóng+duty_quạt)/2` là đại lượng thay thế mức hoạt động, **không phải điện năng đo được**.

Mỗi bộ được huấn luyện Q-learning hai seed độc lập (11/29), mặc định 250 episode/seed, 120 bước/episode. State chứa sai lệch nhiệt, xu hướng, bộ nhớ sưởi và action trước đó; **nếu đủ cả mười action**, có 810 state, Q-table 810×10. Nếu chỉ một phần action đủ cửa sổ, bảng chỉ dùng phần được kiểm tra và báo rõ. Đây là một thiết kế thử nghiệm; không phải số trạng thái thầy bắt buộc hoặc bảo đảm tính Markov của hộp thật.

Việc chọn hệ số **không dựa vào tổng reward giữa các công thức khác thang điểm**. Mọi bộ điều khiển được đánh giá bằng cùng tiêu chí đã định: tránh ra ngoài miền đã đo/ngắt bảo vệ, hạn chế vượt vùng nhiệt, hướng đến ít nhất 80% thời gian trong vùng, rồi cân nhắc sai số và mức điều khiển. Tất cả dùng cùng các tình huống/nhiễu validation. Lấy kết quả trung bình hai seed, không chọn seed đẹp nhất.

Đối chứng gồm thermostat/PID với cùng các mức action được phép; mức quạt có thể cố định thấp/cao hoặc theo quy tắc xu hướng. Thông số đối chứng được chọn trên validation. Sau khi chốt reward, dùng seed test mô phỏng 905, không chọn lại reward theo test. Đoạn không có state đã học phải dùng fallback được đếm; nhiều fallback thì không công nhận là ứng viên đạt.

Nếu vượt kiểm tra mô phỏng, file Q-table vẫn mang nhãn **UNG_VIEN_MO_PHONG**, `deploy_allowed=false`. Công cụ không tự chạy chính sách đó lên GPIO. Nếu RL thua đối chứng hoặc không đạt thì báo nguyên kết quả; không đổi tiêu chí để làm RL trông tốt hơn. Nhiễu mô phỏng dựa trên sai số khớp, không phải khoảng tin cậy vật lý hay bằng chứng chịu được mọi nhiễu môi trường.

## 6. File kết quả

Mỗi lần chạy tạo thư mục mới dưới `Code_HopAp_Demo/ket_qua_khao_sat/`, đường dẫn được in ở đầu phiên:

| File | Nội dung |
|---|---|
| `du_lieu.csv` | Nhiệt và lệnh từ lượt khảo sát |
| `cau_hinh.json` | Mức kích thích, seed, mục tiêu và lịch đã hoàn tất hay chưa |
| `phan_tich/dap_ung_tung_buoc.csv` | ΔT và °C/phút từng đoạn |
| `phan_tich/phan_tich.json` | Nguồn CSV/hash, kiểm tra mô hình, lý do thiếu dữ liệu và kết quả reward nếu đã thử |
| `phan_tich/KET_QUA.md` | Báo cáo dễ đọc |
| `phan_tich/thu_he_so_reward.csv` | 18 bộ reward và chỉ số validation, nếu đủ dữ liệu |
| `phan_tich/so_sanh_MO_PHONG.csv` | Một trace test mô phỏng, ghi rõ không phải nhiệt đo thực |
| `phan_tich/qtable_UNG_VIEN_MO_PHONG.json` | Chỉ xuất khi ứng viên đạt kiểm tra mô phỏng; chưa cho phép triển khai |
| `phan_tich/reward_de_xuat_MO_PHONG.json` | Hệ số ứng viên và mô hình tương ứng, không có bảng Q lớn |

Tùy nhiệt ban đầu/nhiễu và số lần ngắt bảo vệ, một lượt dài vẫn có thể chưa đủ dữ liệu. Không tự lặp khảo sát không giới hạn. Có thể đo lượt mới với thứ tự khác sau khi kiểm tra điều kiện hộp:

```bash
python3 khao_sat_nhiet.py do --thu-tu 47
```

Chỉ đo và lập báo cáo đáp ứng, chưa huấn luyện:

```bash
python3 khao_sat_nhiet.py do --chi-do
```

Phân tích lại CSV có sẵn, **không bật GPIO**; thay các đường dẫn mẫu bằng tên thật đã được in:

```bash
python3 khao_sat_nhiet.py phan-tich --log ket_qua_khao_sat/TEN_LUOT_1/du_lieu.csv --log ket_qua_khao_sat/TEN_LUOT_2/du_lieu.csv --episodes 500
```

Chỉ gộp lượt cùng bố trí, vị trí cảm biến, quạt và tần số PWM. Sau khi khảo sát, phần thử reward có thể cần thêm thời gian CPU; Terminal in tiến độ mỗi bộ. Ctrl+C ở giai đoạn phân tích dừng tính toán nhưng CSV đo đã lưu vẫn còn, có thể phân tích lại.

Từ **Terminal laptop Windows** lấy dữ liệu về:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_khao_sat "D:\BTL_Nhom13\Du_lieu_khao_sat"
```

## 7. Cần làm gì sau khi có ứng viên?

Hiệu chỉnh/kiểm tra đầu dò và thêm lượt đo độc lập để xem mô hình còn đúng. Nếu muốn chạy RL thật, cần một chương trình triển khai có giới hạn và log riêng, rồi so với đối chứng trên cùng hộp, cùng điều kiện đầu/nhiễu; không chạy bảng Q này chỉ vì file đã được xuất. Chưa có log thực thì chưa được kết luận đã cải tiến máy ấp. Dung sai đặt ±0,5°C cũng không tự chứng minh sai số nhiệt thật nằm trong ±0,5°C.

Các kiểm tra tự động trong `test_khao_sat_rl.py` dùng plant tổng hợp được ghi nhãn SYNTHETIC. Không sử dụng số liệu test tổng hợp làm số đo demo của nhóm.

Nguồn thuật toán: [Watkins & Dayan — Q-learning](https://www.gatsby.ucl.ac.uk/~dayan/papers/cjch.pdf). Các ràng buộc vận hành và tiêu chí chọn trong công cụ là thiết kế thực nghiệm của dự án, chưa phải một bảo đảm hội tụ/tối ưu toàn cục trên hộp thật.

Tham khảo [đặc tính đáp ứng bước và thời gian xác lập](https://python-control.readthedocs.io/en/latest/generated/control.step_info.html): cần phân biệt thời gian quan sát với việc tín hiệu đã vào vùng quanh giá trị xác lập. Công cụ này không gọi `step_info` và không biết trước nhiệt độ xác lập để chứng nhận thời gian đó.
