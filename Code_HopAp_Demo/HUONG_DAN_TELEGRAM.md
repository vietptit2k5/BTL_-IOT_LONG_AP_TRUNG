# Cảnh báo hộp ấp qua Telegram

Từ bridge 1.5, khi có **Cảnh báo** hoặc **Nguy hiểm** (bảo vệ quá nhiệt, mất cảm biến, ngoài vùng, nghi mở nắp…), Pi nhắn ngay tới Telegram, **kể cả khi không ai mở app**. Pi cũng nhắn khi lượt chạy kết thúc và khi có kết quả thử nhiễu.

Tin nhắn có dạng:

```
🔴 NGUY HIỂM · Hộp ấp nhóm 13
Bảo vệ quá nhiệt kích hoạt ở 38.31 °C: tắt bóng, quạt 100%.
14:05:12 22/11 · 38,31 °C
https://hop-ap-nhom13.web.app
```

Bridge gửi tin qua HTTPS tới Bot API của Telegram, chạy trong luồng nền, nên mạng chậm không làm trễ vòng 5 s của bridge. Không cần gói Firebase trả phí.

## 1. Tạo bot (làm một lần, trên điện thoại)

1. Trong Telegram, tìm **@BotFather** → gửi `/newbot`.
2. Đặt tên hiển thị, ví dụ `Hộp ấp Nhóm 13`, và username kết thúc bằng `bot`, ví dụ `hopap_nhom13_bot`.
3. BotFather trả về **token** dạng `123456789:AAH...`. Token này là mật khẩu của bot: **không gửi vào nhóm chat, không đẩy lên git**.
4. Mở bot vừa tạo và bấm **Start** (hoặc gửi `/start`). Mỗi thành viên muốn nhận cảnh báo đều làm bước này.
   Muốn cả nhóm nhận chung: tạo nhóm Telegram, thêm bot vào nhóm, rồi gửi một tin bất kỳ trong nhóm.

## 2. Tạo file cấu hình trên Pi

Trên Pi, tạo file `~/Code_HopAp_Demo/telegram_bi_mat.json` (cùng thư mục với `cloud_bridge.py`):

```bash
nano ~/Code_HopAp_Demo/telegram_bi_mat.json
```

```json
{"token": "123456789:AAH...", "chat_id": []}
```

Sau đó lấy `chat_id`:

```bash
cd ~/Code_HopAp_Demo && python3 cloud_bridge.py telegram-chat-id
```

Lệnh in ra các dòng như `chat_id 987654321 (An Lê)` hoặc `chat_id -100123… (Nhóm 13)`. Chép các số đó vào file:

```json
{"token": "123456789:AAH...", "chat_id": [987654321, -1001234567890]}
```

Thử gửi:

```bash
python3 cloud_bridge.py telegram-thu
```

Điện thoại phải nhận tin "🟢 Thử kết nối". Cuối cùng khởi động lại bridge để nạp cấu hình:

```bash
sudo systemctl restart hop-ap-bridge
journalctl -u hop-ap-bridge -n 5 --no-pager     # phải có dòng "Telegram: bật, gửi tới N cuộc trò chuyện."
```

## 3. Gửi những gì

| Gửi | Ví dụ |
|---|---|
| Mọi cảnh báo mức **canh_bao** và **nguy_hiem** | NGOAI_VUNG, NGHI_MO_NAP, BAO_VE, LOI_CAM_BIEN, PI_KHONG_GHI, DUNG_BAT_THUONG, DUNG_TU_XA, BAT_DAU_LUOT, CHINH_TAY |
| Thêm 2 loại thông tin | KET_THUC (lượt chạy kết thúc), KET_QUA_THU_NHIEU |

Muốn đổi, thêm vào file cấu hình, ví dụ chỉ nhận nguy hiểm và kết thúc lượt:

```json
{"token": "...", "chat_id": [987654321], "muc": ["nguy_hiem"], "them": ["KET_THUC"]}
```

**Các quy tắc khác:**
- Mỗi cảnh báo chỉ gửi một lần.
- Cảnh báo được gửi bù sau khi mất mạng quá 15 phút thì không nhắn nữa, vì đã cũ.
- Lỗi mạng: thử lại 3 lần rồi bỏ qua. Bridge vẫn chạy bình thường.
- Không có file `telegram_bi_mat.json` thì bridge chạy như cũ, chỉ ghi một dòng log.
- Phát lại CSV trên laptop (`phat-lai`) không bao giờ nhắn Telegram.

## 4. An toàn

- Token chỉ nằm trong `telegram_bi_mat.json` trên Pi. File này có trong `.gitignore`.
- Khi gửi lỗi, log của bridge thay token bằng `<token>`.
- Nếu lỡ để lộ token: nhắn @BotFather → `/revoke` → chọn bot → thay token mới vào file.
