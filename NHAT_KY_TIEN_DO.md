# Nhật ký tiến độ hộp ấp (cuối kỳ)

## Giai đoạn 3 — Đám mây (IoT Level-2)

**Đã làm**
- Thêm `Code_HopAp_Demo/cloud_bridge.py`. Đây là tiến trình riêng, đọc CSV mà `do_nhiet_hop.py` đang ghi, rồi đẩy lên Firebase Realtime Database qua REST, đăng nhập bằng Firebase Auth. Có 4 lệnh: `kiem-tra`, `chay`, `phat-lai`, `tai-len`, và chế độ `--ghi-file` để chạy khi chưa có Firebase.
- Đọc được cả CSV định dạng mới 19 cột lẫn định dạng cũ 16 cột (các lượt ngày 17/11).
- Cảnh báo: ngoài vùng, đã ổn định lại, nghi mở nắp (khi bóng đang sưởi), bảo vệ, lỗi cảm biến, CSV ngừng cập nhật, kết thúc, dừng từ xa. Mỗi loại tối đa 1 lần mỗi 5 phút.
- Lệnh dừng từ xa: gửi SIGTERM tới đúng tiến trình python đang mở CSV (tìm qua `/proc`); bỏ qua lệnh cũ hơn 10 phút; mỗi lệnh chỉ xử lý một lần.
- Thêm `Code_HopAp_Demo/firebase/database.rules.json` (đã điền UID của Pi).
- Thêm `Code_HopAp_Demo/test_cloud_bridge.py`: 21 test, tất cả đều qua.
- Thêm `Code_HopAp_Demo/HUONG_DAN_CLOUD.md` và các file `.gitignore` để loại `firebase_bi_mat.json`.
- Sửa lỗi cú pháp JSON trong `firebase_bi_mat.json`: dòng `authDomain` thừa một dấu `"`.

**Kết quả kiểm tra**
- Phát lại lượt pilot 20/11 ở chế độ `--ghi-file`, tốc độ ×20: 188 mẫu, 17 sự kiện, tóm tắt `HOAN_TAT`, MAE 0,1084 °C, 94,0% thời gian trong 37,3–37,7 °C, 11 lần đổi mức, chỉ có một cảnh báo `KET_THUC`.
- Tóm tắt do bridge tính khớp các báo cáo gốc:

  | Lượt | MAE (bridge) | MAE (báo cáo gốc) |
  |---|---:|---:|
  | Thermostat 17/11 | 0,1207 | 0,1214 |
  | Q1 17/11 | 0,0561 | 0,0568 |
  | Q2 20/11 | 0,1084 | 0,1090 |

**Firebase thật (hoàn tất)**
- Đã sửa mật khẩu Pi. `pi_uid` trong file ban đầu là UID của một tài khoản khác; đã đổi thành UID thật của `pi.hopap@example.com` (`zxm5m1NT0jcpR9ndrtuVx8g5gWA3`), tạo lại `database.rules.json` và publish.
- `kiem-tra`: đăng nhập, ghi và đọc đều OK.
- Đã đưa lên lịch sử 3 lượt thật: Thermostat (17/11, MAE 0,1207), Q-learning v1 (17/11, MAE 0,0561), Q-learning v2 (20/11, MAE 0,1084). Thêm 1 phiên phát lại `phat_lai_20261120_pilot_01_231156`, có `meta.nguon = "phat_lai"`.
- Kiểm tra quy tắc bảo mật: đọc khi chưa đăng nhập bị từ chối (401); ghi `commands/stop` với `by` là email người khác bị từ chối (401); ghi với đúng email của mình thì được (200).

**Chưa kiểm**
- Chưa chạy trên Pi: gửi SIGTERM thật và mất mạng thật để giai đoạn 5.
- Ngưỡng `NGHI_MO_NAP` chưa thử với một lần mở nắp thật; làm ở giai đoạn 2.

**Bước tiếp:** giai đoạn 4, làm app web PWA đọc đúng cấu trúc dữ liệu trong `Code_HopAp_Demo/HUONG_DAN_CLOUD.md`, mục 4. Cấu hình web lấy từ `firebase_bi_mat.json`, chỉ dùng các trường `apiKey`, `authDomain`, `databaseURL`, `projectId`, `appId`, tuyệt đối không đưa `pi_password` vào app.

## Giai đoạn 4 — App web PWA

**Đã làm**: thư mục `App_HopAp/`
- `public/index.html`, `styles.css`, `app.js`: app gồm đăng nhập, phần số đo hiện tại, đồ thị nhiệt độ có dải mục tiêu, đồ thị % bóng/quạt dạng bậc thang (xem 10 phút hoặc cả lượt), danh sách cảnh báo (có thông báo trình duyệt khi app đang mở), nút dừng khẩn cấp phải bấm 2 lần, bảng lịch sử và chồng đồ thị 2 lượt căn từ lúc bắt đầu giữ nhiệt. Màn hình rộng từ 1024 px dùng làm web dashboard. Có chế độ tối. Thư viện từ CDN, phiên bản cố định: Firebase 10.14.1, Chart.js 4.4.1.
- `public/logic.js`: phần logic thuần, tách riêng để kiểm thử; `tests/logic.test.mjs` có 7 test, tất cả qua.
- PWA: `manifest.webmanifest`, `sw.js` (chỉ lưu sẵn vỏ app, không lưu số đo), icon 192/512/maskable/SVG.
- `tao_cau_hinh.py` tạo `firebase-config.js` chỉ với 5 trường công khai; `firebase.json` và `.firebaserc` cho Hosting; hướng dẫn trong `HUONG_DAN_APP.md`.

**Đã kiểm**: cú pháp `app.js` và `sw.js` (node --check); 7/7 test logic; 4 đường dẫn CDN đều trả HTTP 200.

**Chưa kiểm**: chưa xem giao diện trong trình duyệt. Lệnh chụp màn hình bằng Edge không giao diện bị từ chối trong phiên làm việc. Chưa đăng nhập thật bằng tài khoản người dùng, chưa deploy, chưa thử nút dừng từ app.

**Bước tiếp**: chạy thử theo `App_HopAp/HUONG_DAN_APP.md` mục 2 (chạy trên localhost cùng với `phat-lai`). Sau đó `firebase login` và `firebase deploy --only hosting`, rồi sang giai đoạn 5 trên Pi.

**Cập nhật sau khi chạy thử (người dùng xác nhận giao diện ổn)**
- Sửa lỗi khung đăng nhập vẫn hiện sau khi đã đăng nhập: CSS `display: grid` ghi đè thuộc tính `hidden`, đã thêm `[hidden]{display:none!important}`.
- Giao diện tối là mặc định, có nút chuyển sáng/tối và app nhớ lựa chọn. Các ô số liệu tự co giãn.
- Bridge: cảnh báo tính khoảng thời gian theo `elapsed_s` của Pi; bản phát lại ghi mốc giờ đúng theo tốc độ phát. Thêm test, tổng cộng 22/22 test qua.
- Còn lại của giai đoạn 4: `firebase login` và `firebase deploy --only hosting`.
- Đã deploy lên Firebase Hosting: https://hop-ap-nhom13.web.app (firebase-tools 15.37.0). Cả 11 file trả HTTP 200 đúng kiểu nội dung; `firebase-config.js` trên mạng không chứa mật khẩu hay email Pi; `sw.js` có `Cache-Control: no-cache`. **Giai đoạn 4 hoàn tất.** Cập nhật app sau này: `cd App_HopAp`, rồi `firebase deploy --only hosting`.

## Ấp 3 giai đoạn: chỉnh ngày, RL tự đổi mốc (21/11)

**Đã làm**
- `Code_HopAp_Demo/me_ap.py`: lịch 21 ngày lưu bền (`trang_thai_me_ap.json`). Lệnh `bat-dau` (có thể chọn ngày và demo rút gọn), `dat-ngay N`, `xem`. Mốc 37,8 / 37,5 / 37,2 °C, ngày 1–10 / 11–17 / 18–21.
- `Code_HopAp_Demo/ap_trung.py`: chương trình điều khiển mới, các chương trình đã đo cũ giữ nguyên. Dùng Q2 dịch theo mốc, đọc lại lịch mỗi 5 s. Bảo vệ cố định 38,3→37,8 °C, dừng cứng 38,8 °C. Pha dạng `ap_ngayNN_gdK`.
- Bridge v1.1: tính vùng mục tiêu theo từng dòng; cảnh báo `CHUYEN_GIAI_DOAN` có thời gian chờ chuyển mốc; tóm tắt `theo_giai_doan`; gửi `lich` lên cloud; nhận `commands/ngay_ap` (phiên phát lại không được đụng tới lịch).
- App: thẻ "Lịch ấp" (ngày, giai đoạn, thanh 21 ngày, ẩm độ khuyến nghị, đổi ngày bấm 2 lần); đồ thị vẽ vùng mục tiêu theo giai đoạn.
- Quy tắc bảo mật: thêm `lich` (chỉ Pi được ghi) và `commands/ngay_ap` (ngày 1–21, `by` = email người gửi). `firebase.json` khai báo luôn file quy tắc.
- Mô phỏng `Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py`, kết quả trong `outputs/mo_phong_ba_giai_doan/` (KET_QUA.md, ket_qua.json, DOI_NGAY_MO_PHONG.png).

**Đã kiểm**: 41 test Python và 9 test app đều qua; cú pháp app ổn; mô phỏng 5 kịch bản × 20 seed.

**Chưa làm hoặc chưa kiểm**
- Deploy quy tắc và app: lệnh bị chặn trong phiên, người dùng tự chạy `firebase deploy --only database,hosting`.
- Chưa chạy `ap_trung.py` trên Pi. Chưa đo thật ở 37,8 và 37,2 °C.

- Chuyển file quy tắc vào `App_HopAp/database.rules.json` (Firebase không cho dùng file nằm ngoài thư mục project). Đây là bản quy tắc duy nhất; deploy bằng `firebase deploy --only database,hosting`.

## Chuẩn bị trước buổi làm với Pi: A2–A7 (21/11)

- **A2** `ap_trung.py --bo-dieu-khien thermostat`: đối chứng dùng cùng lịch, cùng làm ấm, bảo vệ và CSV; thermostat lấy từ `doi_chung_kiem_tra.json`. Mô phỏng chuyển sang dùng đúng class này; số liệu không đổi (~89–90 % trong vùng).
- **A3** `Code_HopAp_PhanTich/phan_tich_ap_trung.py`: tách lượt theo đoạn ngày; với mỗi đoạn tính thời gian vào vùng, % trong vùng, MAE, độ lệch chuẩn, số lần đổi mức, thời gian bảo vệ; có bảng so sánh theo giai đoạn và đồ thị; đánh dấu ⚠ cho dữ liệu MÔ PHỎNG. Mô phỏng xuất thêm CSV mẫu (`outputs/mo_phong_ba_giai_doan/csv_MO_PHONG/`).
- **A4** `chay_demo.sh`: một lệnh mở tmux 2 ô (bridge và điều khiển); kiểm tra tmux, phiên cũ, chương trình đang giữ GPIO, lịch; chạy dry-run; hỏi xác nhận an toàn.
- **A5** `cai_dich_vu_bridge.sh` (dịch vụ systemd `hop-ap-bridge`, chạy bằng tài khoản hiện tại, `Restart=always`) và `KIEM_THU_TICH_HOP.md` (10 tình huống T1–T10).
- **A6** `kiem_tra_dht11.py`: chẩn đoán DHT11, phân loại lỗi, so sánh với DS18B20. **Phát hiện trùng chân:** hướng dẫn DHT11 cũ nối VCC vào chân 17 (đã dùng cho OLED) và GND vào chân 14 (đã dùng cho MOSFET bóng). Đã đổi sang nhóm 3,3 V trên breadboard và GND chân 25.
- **A7** `Code_HopAp_Demo/README.md` mới: kiến trúc, nối dây, bảng phân chân không trùng, bảng an toàn, bản đồ file, cách chạy, bằng chứng. Chuyển 13 hướng dẫn cũ vào `tai_lieu_cu/` (link đã sửa); sửa ghi chú quạt 5 V ở `HUONG_DAN_LAP_DEMO_HOP_AP.md`.
- **Test:** 196 (Code_HopAp_Demo) + 19 (Code_HopAp_PhanTich) + 9 (app), tất cả qua. Script bash đã kiểm cú pháp bằng `bash -n`; chưa chạy thật trên Pi.

**Tiếp theo (buổi làm với Pi):** làm theo `Code_HopAp_Demo/KIEM_THU_TICH_HOP.md`: phần cứng, cài đặt, tình huống T1–T10, đo RL và thermostat theo lịch 5 → 12 → 19, rồi chạy `phan_tich_ap_trung.py`.

## Độ ẩm: chương trình đọc và hiển thị (21/11)

- `do_am.py`: đọc DHT11 (GPIO17) mỗi 3 s, lọc trung vị 3 lần đọc tốt, hiển thị trên Terminal (thêm `--oled` để hiện trên màn), ghi nguyên khối `do_am_moi_nhat.json`; giải thích lỗi bằng bảng của `kiem_tra_dht11`. Chỉ đọc DS18B20 khi có `--ds18b20`.
- `cai_dich_vu_do_am.sh`: dịch vụ `hop-ap-do-am`. `do_nhiet_hop.py --do-am-file` / `ap_trung.py --do-am` lấy độ ẩm qua file, không mở GPIO17, nên không tranh chân; `chay_demo.sh` tự chọn `--do-am` khi dịch vụ đang chạy.
- Bridge đưa `/hop_ap_01/do_am` lên cả khi không có lượt chạy (phiên phát lại thì không). Quy tắc bảo mật thêm `do_am` (chỉ Pi được ghi). App: ô độ ẩm ưu tiên số trong lượt, không có thì lấy từ dịch vụ, kèm ghi chú nguồn và tỷ lệ đọc tốt.
- Test: 204 (Code_HopAp_Demo) và 10 (app), tất cả qua. **Cần deploy lại** app và quy tắc: `firebase deploy --only database,hosting`.
- Cách người dùng đang nối DHT11: VCC chân 17, DATA chân 11, GND chân 20. Trùng chân nguồn với OLED theo HUONG_DAN_DO_NHIET; chờ người dùng xác nhận OLED đang cắm ở đâu.

- Xác nhận sơ đồ chân thật (21/11): DS18B20 và OLED qua breadboard (hàng 10 = 3,3 V từ chân 1, hàng 14 = DATA ở chân 7, hàng 18 = GND ở chân 9), OLED SDA/SCL ở chân 3/5; DHT11 nối thẳng vào chân 17/11/20. Không trùng chân. Đã cập nhật README, HUONG_DAN_DO_NHIET, HUONG_DAN_DHT11, kiem_tra_dht11.
- DHT11 sáng đèn mà không đọc được: thêm `dht_reader.py`, tự dùng **driver kernel** (`dtoverlay=dht11,gpiopin=17`, đọc `/sys/bus/iio/.../in_humidityrelative_input`) nếu đã bật, không thì dùng thư viện Adafruit. `do_am.py`, `kiem_tra_dht11.py` và `do_am_dht11.py` đều dùng bộ đọc chung này; lỗi ETIMEDOUT được xếp vào "không có tín hiệu", EIO vào "checksum". Hướng dẫn bật nằm trong HUONG_DAN_DHT11.md. Test: 207 qua. Chưa thử trên Pi.
- Chốt cách nối DHT11 (21/11): VCC → breadboard d10 (hàng 3,3 V), GND → d18 (hàng GND), DATA → chân 11. Đã cập nhật README, HUONG_DAN_DHT11, kiem_tra_dht11.
- **DHT11 đọc được trên Pi (21/11)** bằng driver kernel: 5/10 lần đọc tốt, RH 58 %, T(DHT11) 26,0 °C so với DS18B20 24,75 °C (lệch +1,3 °C, trong sai số ±2 °C của DHT11). Các lần lỗi đều là checksum/EIO, xen kẽ với lần đọc tốt; do_am.py có lọc trung vị nên vẫn có số mới khoảng mỗi 6 s. Lỗi cũ "sensor not found" là do thư viện Adafruit, không phải do dây.
- Đã deploy (21/11) quy tắc bảo mật và app v4 bằng `firebase deploy --only database,hosting`. Kiểm tra: web phục vụ đúng bản `hop-ap-v4` (có ô độ ẩm từ `/do_am`); Pi ghi được `/do_am` và `/lich` (200); đọc khi chưa đăng nhập bị chặn (401); gửi ngày 30 vào `ngay_ap` bị chặn (401).
- Bridge dịch vụ đã chạy trên Pi (21/11 13:37); dịch vụ hop-ap-do-am chưa cài. App v5: mặc định ẩn các phiên không có giai đoạn giữ nhiệt (log đọc thử), ô tích "Hiện phiên phát lại / đọc thử" để xem lại. Đã deploy hosting.
- Lỗi `set: pipefail` trên Pi (21/11): do các script Python sửa file trên Windows ghi CRLF. Đã đổi tất cả .sh/.py/.js/.md về LF (giữ nguyên CRLF của 2 gói Q-table JSON, SHA-256 vẫn khớp); thêm .editorconfig và cài đặt VS Code để .sh luôn lưu LF. 207 + 10 test qua.
- **Hoàn tất (21/11):** dịch vụ hop-ap-do-am đã cài trên Pi; app hiện độ ẩm từ DHT11 qua Firebase khi không có lượt chạy. Hai dịch vụ nền đang chạy: hop-ap-bridge và hop-ap-do-am.

## Tạo mẻ và bắt đầu lượt từ app (22/11)

- Bridge: thêm lệnh `commands/me_ap` (tạo mẻ với ngày và tốc độ 86400/300/120/60 s mỗi ngày; kết thúc mẻ thì lưu lại file lịch, từ chối khi đang có lượt) và `commands/luot` (RL hoặc thermostat, 10/20/30/45/60 phút, bắt buộc `co_nguoi=true`). Trước khi bật tải, Pi kiểm tra: có mẻ, không có chương trình điều khiển nào khác (dò /proc), đọc được DS18B20, hộp ≤ 30 °C; thiếu thì trả "TU_CHOI: lý do". Lượt chạy trong tmux `hopap_app` (không có tmux thì dùng setsid), ghi log vào `.cloud_bridge/luot_app_*.log`. Dịch vụ bridge thêm `KillMode=process`.
- Quy tắc bảo mật thêm `me_ap` và `luot`. Đã thử trên Firebase thật: 6/6 lệnh sai bị chặn (401).
- App v6: phần "Mẻ ấp" trong thẻ Lịch ấp; thẻ "Lượt chạy" gồm bắt đầu lượt và dừng khẩn cấp; các nút đều bấm 2 lần; có hiện lý do khi nút bị khóa. Đã deploy.
- Test: 213 Python, 12 app, tất cả qua. Chưa thử trên Pi: cần chép code, chạy lại `cai_dich_vu_bridge.sh` và cài `tmux`.
- Sửa lỗi app không hiện giao diện mới (22/11): trang gốc `/` bị Firebase Hosting trả `max-age=3600` vì quy tắc header chỉ khớp tên file có đuôi; đổi sang `no-cache` cho mọi đường dẫn (riêng icons cache 1 ngày). SW v7 tải với `cache: no-cache`; app.js bỏ qua phần tử thiếu khi HTML cũ. Đã deploy; `/`, index.html, app.js đều trả no-cache.
- App v8 có số phiên bản ở chân trang; người dùng đã xác nhận thấy v8 và thẻ "Lượt chạy" (22/11). Đã kiểm tra bằng DOM giả lập (jsdom, Firebase giả): app.js không lỗi khi chạy, các nút bật/khóa đúng điều kiện.
- Bridge 1.2 chạy trên Pi (21/11 14:07) sau `systemctl restart`; lệnh tạo mẻ từ app được xử lý (DA_TAO). Nguyên nhân trước đó: code đã chép lên Pi nhưng dịch vụ chưa khởi động lại, nên vẫn chạy bản cũ trong bộ nhớ.
- Lịch demo tạm dừng (22/11): mẻ rút gọn tạo ra ở trạng thái dừng (`tam_dung_utc`); ap_trung gọi `resume` khi RL nhận điều khiển và `pause` khi lượt kết thúc (hết giờ, dừng khẩn cấp, lỗi); `set_day` giữ nguyên trạng thái dừng. Mẻ thời gian thật không đổi. 216 test qua; app v9 hiện "lịch đang dừng/đang chạy" (đã deploy). Cần chép code lên Pi và khởi động lại bridge, rồi tạo lại mẻ demo.
- Sự cố 21/11: `systemctl restart hop-ap-bridge` khi chưa có KillMode=process đã dừng luôn lượt đang chạy (không có END), app kẹt "Đang chạy" nên khóa nút bắt đầu. Sửa: bridge 1.3 đóng lượt kèm cảnh báo DUNG_BAT_THUONG khi CSV đứng quá 20 s và không còn tiến trình điều khiển; app v10 chỉ coi là đang chạy khi số đo mới hơn 30 s. 217 + 13 test qua; app đã deploy. Cần chạy lại cai_dich_vu_bridge.sh trên Pi (không chỉ restart).
- Sửa script cài: `enable --now` không khởi động lại dịch vụ đang chạy, nên bridge vẫn chạy code cũ 1.2; đổi thành `enable` rồi `restart`.
- Bridge 1.3 chạy trên Pi (14:45); lượt cũ 20261121_071922_rl đã được đóng kèm cảnh báo DUNG_BAT_THUONG. App hết kẹt.

## Sắp xếp repo để đẩy lên git (22/11)

- Giữ nguyên các thư mục code và dữ liệu (Pi, systemd và script phân tích tham chiếu tới tên này). Gom tài liệu rời vào `tai_lieu/`; ghi âm và sách đưa vào `tai_lieu/rieng_tu/` (không đẩy lên git).
- Thêm README gốc và 3 lộ trình: `tai_lieu/LO_TRINH_1_THUAT_TOAN_RL.md`, `LO_TRINH_2_DO_DAC_DU_LIEU.md`, `LO_TRINH_3_IOT_APP.md`.
- `.gitignore` loại bí mật (firebase_bi_mat.json, .pi-access), lưu trữ, file Office giữa kỳ, file sinh ra khi chạy. `.gitattributes` đặt LF cho code và giữ nguyên từng byte gói Q-table JSON, Du_lieu_*, outputs (mã SHA-256 của gói Q2 sau khi qua git vẫn là 882c7746…).
- Đã `git init` (nhánh main), chưa commit: 319 file, khoảng 6,9 MB nén, không có file bí mật.
