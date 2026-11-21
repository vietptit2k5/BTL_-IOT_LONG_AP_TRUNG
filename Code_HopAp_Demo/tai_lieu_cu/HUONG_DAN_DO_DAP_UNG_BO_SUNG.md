> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# Đo bổ sung đáp ứng nhiệt trước khi cải thiện Q-table

Chương trình: `do_dap_ung_bo_sung.py`. Chỉ dùng hộp rỗng có người theo dõi, giữ nguyên vị trí đầu dò/bóng/quạt/lỗ khí/nắp như lượt RL trước. Không thay Q-table, không học ngẫu nhiên trên phần cứng, không thêm độ ẩm vào state/reward/action. DHT11 là tùy chọn chỉ ghi/hiển thị.

## Một lần chạy đo đủ một mốc nhiệt

Đã thêm `--mot-moc`: mặc định đo **10 tổ hợp = bóng50/25/75/0/100 × quạt75/100** tại một mốc, tự chuẩn bị lại điều kiện đầu giữa các tổ hợp. Không cần chạy một lệnh cho mỗi mức bóng. Chế độ này tự dùng thời gian dài; không cần thêm `--do-dai`.

Sau khi cập nhật code và đăng nhập Pi, xem kế hoạch mốc37.5°C:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python do_dap_ung_bo_sung.py do --mot-moc --giai-doan 2 --dry-run
```

Nếu đã kiểm tra hộp rỗng, nhiệt ban đầu≤30°C, DS18B20 hợp lệ, có người theo dõi và chương trình GPIO khác đã dừng:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --mot-moc --giai-doan 2
```

Đổi `--giai-doan 3` để đo mốc37.2°C; `--giai-doan 1` để đo mốc37.8°C trong một lượt khác. Mỗi lượt tạo thư mục kết quả riêng trong `ket_qua_dap_ung/`. Không tự chuyển cả ba mốc liên tục. Có thể thêm `--dht11` để ghi RH hoặc `--dao-thu-tu` cho lượt lặp ngược thứ tự.

Thời gian mặc định tại một mốc: làm ấm≤15phút một lần, chuẩn bị≤10phút trước mỗi tổ hợp, kích thích≤20phút và quan sát sau tắt5phút mỗi tổ hợp. Giới hạn lượt **21.902s ≈6giờ5phút**, cộng khoảng10s quạt cuối. Tổng ba lượt tại ba mốc khoảng18giờ16phút theo giới hạn này; chưa tính nguội/thao tác giữa các lượt. Không cần nguội≤30°C giữa các tổ hợp trong cùng lượt, nhưng vẫn phải đạt điều kiện chuẩn bị quanh mốc; trước một lượt mới lại cần điều kiện đầu≤30°C.

Giới hạn2giờ cũ không bị tăng cho các chế độ khác. Ngoại lệ thời gian một mốc chỉ cho callback có đủ10 tổ hợp, bắt đầu bóng0/quạt100, ngắt cứng≤38.5°C, không kết hợp thử quạt0. Trần nội bộ7giờ để chặn lịch quá dài; lịch vượt trần bị từ chối trước khi bật tải, không cắt bớt các tổ hợp ngầm.

Mọi bảo vệ giữ nguyên: cắt kích thích37.9°C, guard38→37°C, dừng cứng38.5°C, mất số đo3s/CRC thì dừng. Kích thích bị ngắt sớm không được gọi là đủ20phút. Nếu không đạt nền trong thời gian chuẩn bị thì dừng cả lượt và giữ CSV, không tự nới điều kiện đầu. Đặc biệt mốc37.8°C có thể khó hoàn tất vì sát giới hạn trên.

Giữ SSH mở và không để máy tính mất mạng/ngủ trong khi đo. Nếu muốn kết thúc nhấnCtrl+C, đợi tắt tải; không dùng chương trình đo này để chạy không người giám sát. Đây là lịch đo phần cứng, không phải lịch ấp21ngày hoặc RL mới.

## Phủ đủ tập tổ hợp, không chỉ bóng50%

Bóng50% trước đây chỉ là bài thăm dò quanh mức trung bình đã dùng, không chứng minh mức đó tối ưu. Muốn so sánh đầy đủ tập đang xét cần **5 mức bóng0/25/50/75/100 ×2 mức quạt75/100 ×3 mốc37.2/37.5/37.8 =30 tổ hợp** mỗi lượt lặp.

Đã tạo kế hoạch ở `outputs/ke_hoach_do_day_du_20261120_final/KE_HOACH.md` và ma trận theo dõi `ma_tran.csv`. Kế hoạch có15đợt, mỗi đợt một mức bóng và hai mức quạt; vẫn giới hạn từng đợt khoảng85phút. Tổng giới hạn khoảng21.3giờ, chưa tính chờ nguội/thao tác. Phải chia nhiều buổi có giám sát, không tự chạy qua đêm. Chạy hai lượt lặp thì60tổhợp và30đợt; lượt lặp thứ hai đảo thứ tự.

Mọi lệnh trong kế hoạch dùng `--muc-bong` rõ ràng; không phụ thuộc mặc định bóng50 của `--do-dai`. Chẳng hạn đo bóng25 ở mốc37.5°C:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --muc-bong 25
```

Đo đợt khác chỉ sau khi dừng chương trình trước, lưu CSV và để hộp về điều kiện đầu≤30°C. Một tổ hợp bị rút ngắn do giới hạn nhiệt vẫn ghi nhận đã thử, nhưng không đánh dấu là đủ20phút. Giữ `actual_probe_s`, `full_duration`, `end_reason` và đường dẫn log thực.

Có thể tạo kế hoạch mới mà không bật tải:

```bash
python3 ke_hoach_do_day_du.py --lap 2 --out ke_hoach_lap_2_moi
```

Lệnh chỉ ghi kế hoạch, không chạySSH/GPIO hay tự đánh dấu đã đo. Bản đầy đủ này chỉ phủ tập quạt75/100 đang xét; không tuyên bố đã thử mọi PWM liên tục hoặc quạt0/50.

## Đo thực tại ba mốc giai đoạn

Mô phỏng trước đây không thay thế phép đo trên Pi. Đã thêm `--giai-doan 1/2/3`, tương ứng mốc chuẩn bị 37.8/37.5/37.2°C. Tùy chọn này chỉ chọn **đợt đo đáp ứng thật**, không chạy Q-table và không giả định có trứng đúng ngày tuổi trong hộp. Không dùng cùng `--nhiet-nen`.

Sau khi cập nhật thư mục code và đăng nhập Pi, **bắt đầu ở giai đoạn 2 (37.5°C)** vì có nhiều dữ liệu cũ để đối chiếu:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai --dry-run
```

Nếu DS18B20 hợp lệ, nhiệt ban đầu ≤30°C, hộp rỗng và có người theo dõi:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan 2 --do-dai
```

Hai tổ hợp bóng50/quạt75 và bóng50/quạt100, mỗi tổ hợp tối đa20phút, sau tắt5phút, chuẩn bị tối đa10phút; giới hạn đợt khoảng85phút. Thêm `--dht11` nếu cần ghi RH. Kiểm tra dữ liệu đợt này trước khi chạy giai đoạn3 và giai đoạn1, hoặc thử mức bóng25/75.

`cau_hinh.json` ghi `stage_reference` và `purpose=REAL_HARDWARE_RESPONSE_COLLECTION_NOT_RL_VALIDATION`. CSV ghi số đo từ DS18B20 thật; không có số đo thì chương trình dừng, không tạo nhiệt giả. Phân tích sau lượt đo đọc CSV thật, không thay bằng mô phỏng.

Giữ nguyên ngưỡng cắt kích thích cao37.9°C, guard38→37°C và dừng cứng38.5°C. Đợt nền37.8°C gần ngưỡng trên nên có thể bị rút ngắn hoặc không đạt điều kiện đầu; đó là kết quả cần giữ lại, không nới bảo vệ để ép đủ20phút. Chặn bắt đầu kích thích khi mẫu hiện tại đã ngoài cửa sổ kích thích, kể cả vẫn trong dung sai chuẩn bị.

Đợt này đo **đặc tính hộp với PWM cố định**, không phải chứng minh Q-table mới đạt chỉ số. Đánh giá RL thực tế là bước riêng, cần loader đúng policy/giao thức và lượt đối chứng có giám sát sau khi kiểm tra lại mô hình.

Giữ nguyên nắp, lỗ khí, vị trí quạt/đầu dò, không thêm nước/trứng giữa các lượt so sánh. Kiểm tra nhiệt bằng thiết bị tham chiếu nếu có. Ghi nhận điều kiện phòng và mọi lần mở nắp/mất điện; đầu dò tại một điểm không đo được độ đồng đều hoặc nhiệt vỏ trứng.

## Bản đo dài — ưu tiên dùng khi cần quan sát nhiệt trôi chậm

Đã bổ sung `--do-dai`. Thời gian mặc định của bản dài:

|Giai đoạn|Thời gian|
|---|---|
|Làm ấm đầu lượt|Tối đa 15 phút|
|Chuẩn bị cùng điều kiện đầu trước từng tổ hợp|Tối đa 10 phút|
|Bóng 50% + quạt 75%|Tối đa 20 phút|
|Tắt bóng, quan sát sau tổ hợp đầu|5 phút|
|Bóng 50% + quạt 100%|Tối đa 20 phút|
|Tắt bóng, quan sát sau tổ hợp thứ hai|5 phút|

Tổng giới hạn **5.102 giây ≈85 phút**, cộng khoảng 10 giây quạt cuối. Không đạt nền hoặc mất số đo thì dừng; chạm giới hạn nhiệt sẽ rút ngắn kích thích. Bản dài không nới ngưỡng nhiệt, không tự thay PWM của tổ hợp để cố giữ đủ thời gian.

Sau khi chép bản cập nhật sang Pi, xem kế hoạch:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python do_dap_ung_bo_sung.py do --do-dai --nhiet-nen 37 --dry-run
```

Chỉ khi đã kiểm tra hộp rỗng, bố trí, cảm biến, nhiệt đầu ≤30°C và có người theo dõi, chạy:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --do-dai --nhiet-nen 37
```

Thêm `--dht11` nếu muốn ghi RH; vẫn không đưa RH vào RL. Dừng mọi chương trình GPIO khác trước khi đo.

Nếu sau khi phân tích lượt 20 phút còn cần cửa sổ dài hơn, bản dài cho phép `--moi-to-hop 1800` (30 phút mỗi tổ hợp; giới hạn cả đợt hai tổ hợp khoảng 105 phút). **Không chạy nhiều lượt dài liên tiếp mà chưa xem dữ liệu.** Sau khi dữ liệu đủ tốt, lặp với `--dao-thu-tu` để kiểm tra độ lặp lại ở điều kiện đầu tương tự.

Có thể chọn mức bóng bằng `--muc-bong`, nhưng lịch tối đa 120 phút. Ví dụ nhiều mức bóng trong cùng bản dài có thể bị từ chối; khi đó chia thành các đợt, mỗi đợt một mức bóng. Không tự động cắt bớt các phép đo mà vẫn báo hoàn tất.

Báo cáo bổ sung độ dốc ở 300–600, 600–900, 900–1200, 1200–1800 giây và độ dốc/biên độ/độ phủ mẫu trong **180 giây cuối của thời gian yêu cầu**. Nếu kích thích dừng sớm thì các cửa sổ chưa đo sẽ là null, không lấy 3 phút đầu thay cho 3 phút cuối. Cửa sổ cuối có dữ liệu một phần vẫn phải kiểm tra độ phủ, không tự gọi là cân bằng nhiệt. Độ dốc gần 0 tại một đầu dò chưa chứng minh nhiệt toàn hộp đồng đều.

Các tùy chọn thời gian theo giây: `--chuan-bi` (30–900), `--sau-tat` (30–600), `--lam-am` (60–1200), `--moi-to-hop` (120–1800). Giá trị được kiểm tra và ghi trong cấu hình kết quả. Giữ cùng thời gian khi lặp/đổi thứ tự. `--do-dai` mặc định chỉ chọn bóng 50%; không có tùy chọn này thì lịch cũ vẫn giữ nguyên.

## Bài thăm dò ngắn đã có, dùng khi chỉ cần kiểm tra vận hành

Sau khi chép code cập nhật và đăng nhập Pi, ưu tiên chạy **một đợt bóng 50%, hai mức quạt**, nền 37°C:

```bash
cd /home/pi/Code_HopAp_Demo
.venv/bin/python do_dap_ung_bo_sung.py do --nhiet-nen 37 --muc-bong 50 --dry-run
```

Khi đã kiểm tra điều kiện, thực hiện đo:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --nhiet-nen 37 --muc-bong 50
```

Giới hạn khoảng **31 phút + 10 giây quạt cuối**, gồm làm ấm, chuẩn bị, hai kích thích 5 phút và quan sát sau tắt. Có thể hoàn thành sớm hơn hoặc dừng nếu không đạt nền. Đây là bước kiểm tra tính khả thi/độ sạch dữ liệu, **chưa đủ kết luận mức quạt tối ưu hoặc nhiệt cân bằng**. Có thể thêm `--dht11` chỉ để theo dõi.

Chép dữ liệu về và kiểm tra trước khi mở rộng. Nếu không đạt điều kiện nền, giữ nguyên ngưỡng và gửi log để xem lại bộ chuẩn bị/đặc tính hộp; không bỏ điều kiện ổn định để ép chạy.

Sau khi bài nhỏ đạt, trình tự dự kiến là: lặp thứ tự ngược (`--dao-thu-tu`) ở điều kiện đầu tương tự; mở rộng các mức bóng quanh vùng 37°C; sau đó đo các đợt riêng ở nền 35°C và 33°C nếu cần mở rộng miền mô hình. Các lựa chọn được hỗ trợ:

- `--nhiet-nen 33`, `35`, `37`: chọn nhiệt chuẩn bị, không sửa mục tiêu RL 37.5°C.
- `--muc-bong 25 50 75`: chỉ thử các mức đã chọn; mỗi mức vẫn có hai phép quạt 75/100. Không lặp mức trùng trong cùng đợt.
- Ở nền 33°C, giới hạn kích thích là 32–34°C; nền 35°C là 34–36°C; nền 37°C là 36–37.9°C. Các giới hạn mềm 38→37°C và dừng cứng 38.5°C không bị nâng lên.

Không cần chạy toàn bộ mọi mức ở cả ba nền trước khi xem dữ liệu đầu tiên. Cũng chưa có mode tự kéo dài giữ mức đến cân bằng; nếu cửa sổ 5 phút chưa đủ, cần thiết kế lượt giữ mức riêng sau khi biết tổ hợp nào có thể duy trì trong vùng cho phép.

Phần dưới mô tả **lịch mặc định đầy đủ ở nền 37°C**, dùng khi đã kiểm tra bài nhỏ thành công.

## Vì sao đo thêm

Khảo sát cũ đổi mức liên tiếp nên nhiệt bắt đầu và nhiệt tích trữ của mỗi tổ hợp khác nhau; một số tổ hợp bị ngắt trước khi đủ thời gian. Lượt mới tập trung quanh vùng mục tiêu, ghi độ dốc theo từng cửa sổ và nhiệt còn tăng sau khi tắt bóng. Không hứa dữ liệu mới chắc chắn làm RL tốt hơn: còn phải kiểm tra mô hình và đối chứng thực.

## Lịch tự động

1. Bắt đầu khi DS18B20 ≤30°C. Làm ấm bóng 75%/quạt 100%, đến 36.7°C, tối đa 600 giây. Không đạt thì dừng.
2. Trước mỗi phép kích thích, bộ chuẩn bị riêng (PI có thành phần xu hướng, làm tròn mức bóng theo bước 5%, quạt 75%) đưa hộp về **37°C**. Đây là bộ chuẩn bị, không phải RL và không phải chính sách đang được đánh giá.
3. Chỉ bắt đầu phép thử khi trong cửa sổ khoảng 30 giây có ít nhất 20 mẫu, mọi mẫu nằm trong **37±0.125°C**, độ dốc tuyệt đối ≤**0.12°C/phút**. Bộ nhớ sưởi EMA 25s tính từ lệnh PWM đã áp dụng phải cách mốc lượt đầu không quá 0.1 (thang 0–1). Chờ tối đa 240 giây mỗi lần; không đạt thì dừng và giữ log. Không tự nới ngưỡng để ép chạy.
4. Giữ tổ hợp tối đa **300 giây (5 phút)**. Chạm **37.9°C** hoặc **36°C** thì kết thúc kích thích sớm, ghi lý do. Không cố giữ bóng 100% đủ 5 phút nếu nhiệt tăng quá cao.
5. Tắt bóng, quạt 75%, quan sát thêm **90 giây**. Nếu nhiệt đạt 38°C, bảo vệ mềm tắt bóng/quạt 100% đến khi ≤37°C; thời gian này vẫn tính trong lượt.
6. Quay lại bước chuẩn bị cho tổ hợp kế tiếp.

Thứ tự mặc định:

|Lượt|Bóng %|Quạt %|
|---|---|---|
|1|50|75|
|2|50|100|
|3|25|75|
|4|25|100|
|5|75|75|
|6|75|100|
|7|0|75|
|8|0|100|
|9|100|75|
|10|100|100|

Giới hạn toàn lượt mặc định không có `--do-dai` là **6.902 giây = khoảng 115 phút**, cộng tối đa khoảng 10 giây quạt cuối. Thường kết thúc sớm hơn khi đạt nền nhanh hoặc kích thích bị rút ngắn. `--moi-to-hop 180` chỉ giảm thời gian mỗi kích thích; nếu so sánh hai lượt phải dùng cùng giá trị. Bản mới cho phép 120–1800 giây mỗi kích thích, nhưng phải chọn ít mức bóng hơn nếu tổng lịch vượt 120 phút.

Ngưỡng dừng cứng phần mềm **38.5°C**, DS18B20 lỗi/CRC hoặc số đo quá hạn 3 giây làm dừng theo bộ điều khiển cũ. Không có ngoại lệ quạt 0%; quạt luôn 75% hoặc 100%. Nếu tải không tắt theo lệnh, rút adapter 12V. Phần mềm không thay bộ ngắt nhiệt phần cứng.

**Điều kiện nền chỉ gần tương đương:** cùng nhiệt đầu dò, xu hướng và bộ nhớ sưởi không chứng minh nhiệt thành hộp giống nhau. Bộ nhớ EMA là mô hình từ PWM, không phải nhiệt độ dây tóc hay công suất điện đã đo. Chưa có đầu dò môi trường độc lập. Ghi nhận thời tiết/phòng, không mở nắp giữa lượt; nếu có can thiệp phải báo lại khi phân tích.

## Chép code — Terminal Windows

Nếu đang ở `pi@pi:... $`, gõ `exit` trước. Chạy ở dòng `D:\...>`:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
ssh pi@pi
```

## Chuẩn bị và chạy — Terminal Pi

Giữ nguyên phần cứng đang chạy được. DS18B20 phải có địa chỉ `28-...`, không chỉ các thư mục `00-...`. Dừng mọi chương trình khác đang dùng GPIO trước khi chạy. Không có người theo dõi đủ thời gian thì chưa bắt đầu lượt đo này.

```bash
cd /home/pi/Code_HopAp_Demo
ls /sys/bus/w1/devices/
.venv/bin/python do_dap_ung_bo_sung.py do --dry-run
```

Sau khi kiểm tra điều kiện, chạy:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do
```

Muốn ghi thêm RH bằng DHT11 đã nối, thư viện đã cài trong `.venv`:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --dht11
```

Chọn **một** trong hai lệnh trên. Chương trình tự đổi mức, không nhập lệnh bóng/quạt thủ công. Ctrl+C để dừng; đợi chương trình tắt tải và kết thúc trước khi chạy chương trình khác.

## Lượt lặp để kiểm tra hiệu ứng thứ tự

Nếu lượt đầu có dữ liệu tốt, để hộp nguội tự nhiên về điều kiện ban đầu tương tự, đưa nắp/lỗ khí về đúng trạng thái rồi chạy thứ tự ngược:

```bash
.venv/bin/python do_dap_ung_bo_sung.py do --dao-thu-tu
```

Có thể thêm `--dht11` như lượt trước. Đây là một lượt khác, thư mục timestamp khác; không ghi đè lượt đầu. Hai lượt vẫn chưa đại diện cho mọi nhiệt độ phòng hoặc hộp có trứng/nước.

## Kết quả và cách dùng cho RL

Mỗi lượt lưu ở `ket_qua_dap_ung/<timestamp>/`:

- `du_lieu.csv`: chuỗi thời gian gốc, pha chuẩn bị/kích thích/sau tắt/bảo vệ, lệnh PWM, nhiệt, RH nếu bật.
- `cau_hinh.json`: thứ tự, điều kiện đầu từng phép, bộ nhớ sưởi, thời gian thật, lý do rút ngắn, mã thoát.
- `phan_tich.json`: độ dốc 0–30, 30–90, 90–180, 180–300 giây; độ phủ mẫu/khoảng trống; đỉnh nhiệt quan sát được trong đoạn sau tắt; chênh lệch quạt khi cặp đạt điều kiện.
- `KET_QUA.md`: bảng đọc nhanh. `COMPLETE` chỉ là chạy hết lịch, không có nghĩa mọi tổ hợp đủ 300s hoặc RL đã tốt hơn. Kiểm tra `full_trial_count` và từng `continuous_full_probe`.

Độ tăng sau tắt hiện lấy mốc mẫu cuối trong pha kích thích, không nội suy chính xác nhiệt tại thời điểm tắt; độ phân giải đầu dò và chu kỳ lấy mẫu giới hạn độ chính xác. Đỉnh trong 90s chưa chắc là đỉnh cuối cùng nếu nhiệt tiếp tục tăng về sau. Dữ liệu bị ngắt phải giữ lại nhưng không gọi là đáp ứng đủ 5 phút/cân bằng nhiệt.

Cặp quạt chỉ được báo chênh lệch độ dốc khi cả hai phép đủ cửa sổ, lệnh PWM đúng, nhiệt đầu chênh ≤0.125°C, xu hướng đầu chênh ≤0.12°C/phút và bộ nhớ sưởi đầu chênh ≤0.1. Chưa có ước lượng khoảng tin cậy hoặc kiểm định ý nghĩa thống kê từ một cặp.

Phân tích lại mà không truy cập phần cứng:

```bash
.venv/bin/python do_dap_ung_bo_sung.py phan-tich --thu-muc ket_qua_dap_ung/TEN_THU_MUC_THUC_TE
```

Chép dữ liệu về từ Terminal Windows:

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_dap_ung "D:\BTL_Nhom13\Du_lieu_dap_ung"
```

Sau khi có log thật, bước tiếp theo là:

1. Kiểm tra chất lượng, đoạn bị ngắt, dấu tác động của quạt và ảnh hưởng lịch sử nhiệt. Tách pha chuẩn bị (mức bóng có thể khác tập action RL) khỏi phép so sánh mức cố định.
2. Khớp lại mô hình có quán tính bằng **lệnh PWM thực đã áp dụng**, gồm cả pha tắt/bảo vệ. Đánh giá trên lượt/đoạn độc lập, không chia ngẫu nhiên các hàng thời gian sát nhau. Không đưa nguyên log mới vào bộ fit cũ nếu bộ đó giả định mọi pha là action RL rời rạc.
3. Chỉ thay mô hình khi dự báo nhiệt 5/30/60s trên dữ liệu kiểm tra tốt hơn; giữ mô hình cũ làm đối chứng. Không coi sai số fit trên dữ liệu huấn luyện là bằng chứng.
4. Huấn luyện Q-table ứng viên, kiểm tra các hệ số reward trên nhiều kịch bản/seed, dùng bài kiểm tra riêng. Nếu tác động quạt chưa phân biệt được thì không tự suy ra fan75/100 khác nhau rõ rệt.
5. Thử ứng viên trên hộp rỗng và so với thermostat/Q-table cũ ở điều kiện tương đương. Chưa tuyên bố cải thiện trước khi có lượt đo xác nhận.

Chương trình không tự động thực hiện các bước 2–5, không sửa reward, không thay gói Q-table đã dùng. Các kiểm thử phần mềm dùng dữ liệu giả, chưa phải kết quả đo của hộp.
