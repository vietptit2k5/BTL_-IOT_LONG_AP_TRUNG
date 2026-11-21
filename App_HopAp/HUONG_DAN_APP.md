# App web hộp ấp (PWA)

Đây là app trong sơ đồ IoT Level-2. App đọc Firebase Realtime Database mà [cloud_bridge.py](../Code_HopAp_Demo/cloud_bridge.py) đang ghi, theo dõi trực tiếp qua WebSocket (Firebase JS SDK lo phần này). Cùng một bộ code chạy được trên điện thoại và làm web dashboard trên màn hình rộng (từ 1024 px trở lên), dùng khi trình chiếu.

| Phần | Nội dung |
|---|---|
| Đăng nhập | Email và mật khẩu tạo trong Firebase Authentication. Chưa đăng nhập thì không đọc được dữ liệu, do quy tắc bảo mật chặn |
| Hiện tại | Nhiệt độ, trạng thái trong/ngoài vùng 37,3–37,7 °C, xu hướng, độ ẩm, % bóng, % quạt, giai đoạn, bộ điều khiển, thời gian lượt. Pi mất kết nối quá 15 s thì chuyển trạng thái đỏ và làm mờ số đo |
| Đồ thị | Nhiệt độ có dải mục tiêu, kèm % bóng và % quạt dạng bậc thang. Xem được 10 phút gần nhất hoặc cả lượt |
| Cảnh báo | 30 cảnh báo gần nhất, tô màu theo mức. Có nút "Bật thông báo" để hiện thông báo của trình duyệt **khi app đang mở** |
| Chỉnh tay | Trong thẻ Lượt chạy. Chọn bóng (0–100 %), quạt (75/100 %) và thời hạn (1/2/5 phút), bấm **Áp dụng chỉnh tay** 2 lần. Chỉ bấm được khi lượt ap_trung đã qua làm ấm. App đếm ngược thời gian còn lại; nút **Trả về RL ngay** trả quyền sớm. Bảo vệ quá nhiệt trên Pi vẫn luôn thắng lệnh tay |
| Dừng khẩn cấp | Chỉ bấm được khi có lượt đang chạy. Phải bấm 2 lần trong 5 giây. App ghi `commands/stop` kèm email người bấm |
| Lịch sử và so sánh | Bảng MAE, % trong vùng, độ lệch chuẩn, số lần đổi mức, thời gian làm ấm. Chọn 2 lượt để chồng đồ thị, căn từ lúc bắt đầu giữ nhiệt. Mặc định chọn sẵn Thermostat và lượt Q-learning mới nhất |

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
