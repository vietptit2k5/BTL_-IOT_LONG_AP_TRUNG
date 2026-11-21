> **Tài liệu cũ (lưu trữ).** Mô tả một giai đoạn phát triển trước; cấu hình hiện hành xem [README.md](../README.md).

# So sánh quạt 0% và 75% trong giai đoạn tăng nhiệt ban đầu

## Cùng mức nhiệt ngay trước khi bật bóng

**Cập nhật giao thức:** cả hai lượt phải bắt đầu sưởi ở cùng mức nhiệt tại cùng đầu dò, chênh tối đa **0,10°C**. Giới hạn chênh 0,5°C trước đây không còn dùng để chấp nhận phép so sánh này.

Lượt quạt 75% đầu tiên hợp lệ tự lưu file `moc_thu_quat_0_75.json` trong thư mục code trên Pi. Mốc lấy từ **số đo ngay trước khi bật bóng**, không phải nhiệt lúc vừa mở chương trình. Lượt quạt 0% phải có file mốc và log nguồn hợp lệ; nếu nhiệt chưa khớp, chương trình dừng khi bóng vẫn tắt, không tự sưởi để đuổi theo mốc.

Ví dụ lượt 75% bắt đầu sưởi ở 27,000°C thì lượt 0% phải bắt đầu trong 26,900–27,100°C. Đây là dung sai số đọc để làm thí nghiệm, không phải chứng nhận độ chính xác tuyệt đối của đầu dò.

Hai lượt dùng chung bước trộn khí 75% trong 20 giây, sau đó đặt quạt về mức thử trong 3 giây khi bóng vẫn tắt. Cuối bước này, kiểm tra nhiệt mốc và độ ổn định của 15 giây số đo gần nhất: độ dốc không quá 0,15°C/phút, khoảng dao động không quá 0,2°C. Nếu không đạt thì chưa bật bóng. Cùng số đọc nhiệt ban đầu vẫn chưa chứng minh thành hộp/bóng có cùng nhiệt dư; cần để cả hộp nguội và giữ điều kiện phòng tương đương.

**Không giữ nhiệt hai lượt giống nhau trong suốt khi bật bóng:** khác biệt tốc độ tăng nhiệt sau cùng một mốc mới là kết quả cần đo.

## Có nên bật quạt khi làm ấm?

Quạt có hai tác dụng: đảo nhiệt trong hộp và, với bố trí có lỗ phía sau/quạt cùng lỗ thoát đối diện, hỗ trợ trao đổi khí với phòng. Nếu phòng mát hơn hộp, giảm quạt có thể giảm thất thoát, nhưng tắt quạt cũng có thể làm nhiệt phân bố không đều. Một đầu dò có thể đọc thấp trong khi vùng gần bóng nóng hơn, hoặc đọc cao cục bộ nếu nằm trong luồng nóng.

Vì vậy có thể so sánh hai phương án trên **hộp rỗng có giám sát**, nhưng không mặc định quạt 0% làm cả hộp đạt nhiệt nhanh hơn hoặc tốt hơn cho ấp trứng. Nguồn về khác biệt tuần hoàn/không tuần hoàn: [Mississippi State University — Incubation temperature requirements](https://extension.msstate.edu/agriculture/livestock/poultry/incubation-temperature-requirements).

## Phạm vi thử đầu tiên

Đã tạo `thu_quat_lam_am.py` riêng, không nới quy tắc của các chế độ cũ.

| Giai đoạn | Thời gian | Bóng | Quạt |
|---|---:|---:|---:|
| Ghi nền, trộn khí chung | 20 giây | 0% | 75% ở cả hai lượt |
| Về mức thử, kiểm tra mốc nhiệt | 3 giây | 0% | Theo lượt: 0% hoặc 75% |
| So tốc độ tăng nhiệt ban đầu | Tối đa **30 giây** | **50%** | Theo lượt: **0% hoặc 75%** |
| Quan sát nhiệt sau trộn | 60 giây | **0%** | Cả hai lượt: 100% trong 1 giây, rồi 75% |
| Kết thúc | 10 giây | 0% | 100%, rồi tắt hết |

Nhiệt ban đầu và nhiệt trước lúc bật bóng phải không quá 30°C. Khi đầu dò đạt 33°C, kết thúc sưởi sớm và chuyển sang trộn khí. Đạt 35°C hoặc mất số đo hợp lệ quá 3 giây thì dừng thử. Bộ điều khiển đầu ra giới hạn tổng thời gian bóng bật/quạt 0% không quá khoảng 30 giây theo vòng điều khiển; đổi tên phase hoặc bật lại không đặt lại ngân sách này. Đây là giới hạn phần mềm, không thay thế bảo vệ vật lý.

Bóng phải được cố định chắc, không chạm xốp hoặc vật dễ cháy. Giữ các bảo vệ phần cứng đang lắp; không nối tắt KSD. Theo dõi trực tiếp. Không dùng trứng hoặc nước trong phép thử đầu tiên này. Nếu có điểm nóng bất thường, mùi khét hoặc tải không tắt thì ngắt adapter 12 V, không chờ đầu dò báo ngưỡng.

Đây là **phép đo quá độ ngắn**, chưa phải thử toàn bộ quá trình làm ấm tới 37,5°C. Chưa cho phép dùng quạt 0% trong toàn bộ quá trình làm ấm nhiều phút, vận hành ấp trứng hoặc Q-table. Muốn đánh giá độ đều/điểm nóng khi không quạt, cần đo thêm các vị trí trong hộp, đặc biệt gần bóng và vùng đặt trứng.

## Chạy hai lượt từ Terminal laptop

Chép code mới từ laptop Windows, không dùng đường dẫn `D:\...` ở prompt `pi@pi:~ $`:

```powershell
scp -r "D:\BTL_Nhom13\Code_HopAp_Demo" pi@pi:/home/pi/
```

Xem kế hoạch quạt 0%, không bật tải:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/thu_quat_lam_am.py do --quat 0 --dry-run"
```

Giữ hộp ở cùng vị trí và trạng thái nắp/lỗ thông gió như trước, đầu dò không di chuyển. Dừng mọi chương trình khác dùng GPIO18/23.

**Lượt 1 — quạt 75%:** để hộp nguội gần 26–27°C rồi chạy, theo dõi đến khi Terminal in báo cáo và dòng `MỐC CẶP THỬ: ...°C`:

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/thu_quat_lam_am.py do --quat 75"
```

**Lượt 2 — quạt 0%:** chờ hộp và các bộ phận nguội lại về điều kiện lượt 1, gần mốc đã được in. Có thể mở nắp để nguội, sau đó đóng lại đúng như lúc đo. Không chạy ngay khi hộp còn nhiệt dư sau lượt 1. Chương trình kiểm tra lại nhiệt ngay trước sưởi; lệch quá 0,10°C hoặc nhiệt còn trôi thì báo lỗi và giữ bóng tắt.

```powershell
ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/thu_quat_lam_am.py do --quat 0"
```

Mỗi lượt kéo dài khoảng 2 phút, chưa tính thời gian chờ nguội giữa hai lượt. Không tăng thời gian hoặc mức bóng để ép thử tới 37,5°C trong công cụ này. Ctrl+C để dừng; nếu mạch không tắt theo lệnh, ngắt adapter 12 V.

File mốc không bị ghi đè. Nếu chạy lại lượt 75% khi mốc đã có, nó cũng phải khớp mốc cũ. Để tạo một cặp thử mới, dùng cùng một tên mới cho cả hai lệnh, ví dụ thêm `--moc-so-sanh moc_quat_cap2.json`. Tên tương đối được lưu trong thư mục code, không phụ thuộc thư mục hiện tại của Terminal.

## Lấy dữ liệu và đọc kết quả

Mỗi lượt tạo thư mục riêng dưới `Code_HopAp_Demo/ket_qua_thu_quat/`, đuôi `_quat75` hoặc `_quat0`. Có CSV đầy đủ, cấu hình, báo cáo Markdown và JSON.

```powershell
scp -r pi@pi:/home/pi/Code_HopAp_Demo/ket_qua_thu_quat "D:\BTL_Nhom13\Du_lieu_thu_quat"
```

Các chỉ số cần so:

- Nhiệt thực tại thời điểm bật bóng, cùng mức bóng 50% và thời gian sưởi thực khoảng 30 giây.
- Độ tăng nhiệt ΔT và độ dốc °C/phút toàn đoạn, cùng độ dốc sau khi bỏ 5 giây đầu.
- Đỉnh nhiệt trong 60 giây sau khi tắt bóng và trộn khí. Nhiệt tăng thêm sau trộn là dữ liệu về phân bố/lưu nhiệt cần xem xét, không tự xác định được nhiệt độ cực đại gần bóng.
- Trạng thái hoàn tất, có ngắt sớm tại 33°C hoặc mất mẫu không. Không so lượt đủ 30 giây với lượt bị rút ngắn như hai lượng sưởi bằng nhau.

Ví dụ phân tích hai CSV đã có trên Pi; thay tên thư mục mẫu bằng tên thật:

```bash
python3 thu_quat_lam_am.py so-sanh --lan1 ket_qua_thu_quat/TEN_LUOT_QUAT75/du_lieu.csv --lan2 ket_qua_thu_quat/TEN_LUOT_QUAT0/du_lieu.csv --out ket_qua_so_sanh_quat_moi
```

Công cụ kiểm tra chênh nhiệt trước sưởi không quá 0,10°C, liên kết đúng lượt 75% làm mốc, mức bóng/thời lượng, nhiệt nền ổn định, ngắt sớm, đầu dò và tần số PWM. Báo cáo ghi `comparison_conditions_accepted=false` nếu có điều kiện không đạt; không coi đó là phép so sánh công bằng. Bố trí và nhiệt phòng vẫn cần giữ tương đương; nếu có nhiệt kế phòng riêng thì ghi lại.

Tỷ lệ tăng nhiệt trong 30 giây không được ngoại suy tuyến tính thành thời gian đến 37,5°C. Đặc tính mất nhiệt thay đổi theo chênh lệch nhiệt, và nhiệt một vị trí không đại diện toàn hộp. Chưa huấn luyện lại hoặc thêm action quạt tắt vào RL từ phép thử này.
