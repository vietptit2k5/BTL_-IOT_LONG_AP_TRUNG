# App web hộp ấp (PWA)

Đây là app trong sơ đồ IoT Level-2. App đọc Firebase Realtime Database mà [cloud_bridge.py](../Code_HopAp_Demo/cloud_bridge.py) đang ghi, theo dõi trực tiếp qua WebSocket (Firebase JS SDK lo phần này). Cùng một bộ code chạy được trên điện thoại và làm web dashboard trên màn hình rộng, dùng khi trình chiếu.

## Bố cục (app v12)

App có 4 mục. Trên điện thoại, thanh mục nằm ở đáy màn hình; từ 960 px trở lên, thanh mục nằm trên thanh tiêu đề. Mỗi mục có địa chỉ riêng (`#/tong-quan`, `#/dieu-khien`, `#/bieu-do`, `#/lich-su`), nên nút Quay lại của trình duyệt và đường dẫn chia sẻ đều dùng được.

| Vị trí | Nội dung |
|---|---|
| Thanh trên | Chip kết nối (Đang chạy / Online / Mất kết nối). **Chuông thông báo** có số tin chưa đọc, màu theo mức nặng nhất. Nút tài khoản mở menu đổi giao diện sáng/tối, xem phiên bản và đăng xuất |
| Chuông | 30 thông báo gần nhất, lọc "Tất cả" hoặc "Cảnh báo & nguy hiểm". Tin chưa đọc được tô sáng; mở chuông thì coi như đã đọc (ghi nhớ trên máy này). Có nút bật thông báo trình duyệt (chỉ hiện khi app không ở trên màn hình) |
| Thông báo nổi | Cảnh báo / nguy hiểm mới, và tin kết thúc lượt, hiện ở góc phải 7 s (nguy hiểm thì 15 s). Chạm vào để mở chuông |
| **Tổng quan** | Hộp đang làm gì (Giữ nhiệt / Làm ấm / Chỉnh tay / Bảo vệ / Hộp đang nghỉ…) kèm nút gợi ý bước tiếp theo. Nhiệt độ lớn, mốc, xu hướng, **thang nhiệt** 36,5–39 °C (vùng mục tiêu, vạch bảo vệ 38,3 và dừng 38,8). Ô độ ẩm, bóng, quạt (có thanh mức), giai đoạn. Lịch 21 ngày thu gọn, đồ thị nhiệt 10 phút gần nhất. Đang chỉnh tay thì có dải báo kèm đếm ngược |
| **Điều khiển** | 3 bước theo thứ tự. **1 Mẻ ấp:** tạo / kết thúc mẻ, đổi ngày bằng nút −/+ hoặc chọn nhanh GĐ1/2/3, có xem trước mốc của ngày chọn. **2 Lượt chạy:** chọn bộ điều khiển và thời lượng bằng nút lớn, danh sách điều kiện ✓/○ cho biết còn thiếu gì, ô xác nhận có người ở cạnh hộp. **3 Chỉnh tay:** bóng, quạt, thời hạn, Áp dụng / Trả về RL. Phần giải thích an toàn nằm trong mục "ⓘ" thu gọn |
| **Biểu đồ** | Nhiệt độ có dải mục tiêu đổi theo giai đoạn, % bóng/quạt dạng bậc thang. Xem 10 phút, 30 phút hoặc cả lượt |
| **Lịch sử** | Danh sách lượt dạng thẻ (bộ điều khiển, thời điểm, % trong vùng, MAE). Chạm tối đa 2 thẻ để so sánh: bảng chỉ số cạnh nhau, lượt tốt hơn ở từng chỉ số được đánh dấu ★, và đồ thị chồng 10 phút đầu giữ nhiệt. Mặc định chọn sẵn Thermostat và lượt Q-learning mới nhất đã có tóm tắt |
| **Dừng khẩn cấp** | Thanh nổi ở đáy màn hình, **hiện ở mọi mục** khi có lượt đang chạy. Phải bấm 2 lần trong 5 giây. App ghi `commands/stop` kèm email người bấm |

Mọi lệnh làm thay đổi hộp (tạo/kết thúc mẻ, đổi ngày, bắt đầu lượt, chỉnh tay, dừng) đều phải bấm 2 lần. Pi vẫn tự kiểm tra lại điều kiện an toàn và trả lời bằng dòng trạng thái ngay dưới nút. Pi mất kết nối quá 15 s thì chuyển trạng thái đỏ và làm mờ số đo.

## 1. Tạo tài khoản đăng nhập app

Vào Firebase console, **Security → Authentication → Users → Add user**. Mỗi thành viên dùng email của mình. Tạo thêm `demo@example.com` để đưa thầy đăng nhập khi demo. Không dùng tài khoản của Pi để đăng nhập app.

## 2. Chạy thử trên laptop

Trong PowerShell:

```powershell
cd D:\BTL_Nhom13\App_HopAp\public
python -m http.server 8000
```

Mở `http://localhost:8000` rồi đăng nhập. Firebase cho phép `localhost` sẵn, không cần cấu hình thêm.

Muốn xem số đo chạy trực tiếp, mở thêm một cửa sổ PowerShell khác và phát lại lượt 20/11:

```powershell
cd D:\BTL_Nhom13\Code_HopAp_Demo
python cloud_bridge.py phat-lai ..\Du_lieu_giu_nhiet\20261120_pilot_01\du_lieu.csv --toc-do 10
```

Để xem bố cục điện thoại trên laptop: nhấn F12, rồi bấm biểu tượng điện thoại (Ctrl+Shift+M).

## 3. Đưa lên mạng (Firebase Hosting)

Làm một lần:

```powershell
npm install -g firebase-tools
firebase login
```

Mỗi lần cập nhật app:

```powershell
cd D:\BTL_Nhom13\App_HopAp
firebase deploy --only hosting
```

Xong sẽ có địa chỉ `https://hop-ap-nhom13.web.app`. Lệnh trên **chỉ** đưa app lên. Quy tắc bảo mật vẫn dán tay trên console như trước, không bị lệnh này ghi đè.

## 4. Cài lên điện thoại

- **Android (Chrome):** mở địa chỉ app, chọn menu ⋮ → **Thêm vào màn hình chính** (hoặc **Cài đặt ứng dụng**).
- **iPhone (Safari):** bấm nút Chia sẻ → **Thêm vào MH chính**.

## 5. Cấu hình và bảo mật

- `public/firebase-config.js` được tạo bởi `python tao_cau_hinh.py`. Script chỉ lấy 5 trường công khai: `apiKey`, `authDomain`, `databaseURL`, `projectId`, `appId`. **Không bao giờ** chép mật khẩu hay email của Pi vào app.
- `apiKey` của app web được thiết kế để công khai. Ai đọc và ghi được dữ liệu là do [quy tắc bảo mật](database.rules.json) quyết định: phải đăng nhập mới đọc được, chỉ Pi ghi được số đo, và người dùng chỉ ghi được lệnh dừng mang đúng email của mình.
- Thư viện tải từ CDN, phiên bản cố định: Firebase JS SDK 10.14.1, Chart.js 4.4.1. Service worker chỉ lưu sẵn phần vỏ app, **không lưu số đo**, nên app không bao giờ hiện số đo cũ như thể là số mới.

## 6. Giới hạn

- Thông báo chỉ hiện khi app đang mở, kể cả mở ở nền trên Android. Muốn có thông báo khi app đã đóng hẳn thì phải dùng Firebase Cloud Messaging, cần thêm máy chủ hoặc Cloud Functions; phần này chưa làm.
- iPhone chỉ hiện thông báo web khi app đã được thêm vào màn hình chính (iOS 16.4 trở lên).
- Trang tải toàn bộ `sessions`, kể cả các mẫu đo. Với vài chục lượt (khoảng 30 KB mỗi lượt) thì không đáng kể. Nếu số lượt tăng lên hàng trăm, nên cho bridge ghi thêm một mục chỉ mục riêng.

## 7. Kiểm thử

```powershell
cd D:\BTL_Nhom13\App_HopAp
node --test tests/logic.test.mjs
```

Có 7 test cho phần logic: định dạng số, trạng thái kết nối, vùng mục tiêu, chuỗi mẫu và cách căn đồ thị so sánh, danh sách phiên, cảnh báo mới, trạng thái lệnh dừng.
