"""Offline review of the measured 2026-11-17 survey; never opens GPIO."""
from pathlib import Path
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timedelta

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, String, Rect, Line
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUN = ROOT / 'Du_lieu_khao_sat/20261117_070909_628598'
sys.path.insert(0, str(ROOT / 'Code_HopAp_Demo'))
import phan_tich_reward as analysis


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def label(drawing, x, y, text, size=12, color='#26354A', anchor='start'):
    drawing.add(String(x, y, text, fontName='Helvetica', fontSize=size,
                       fillColor=colors.HexColor(color), textAnchor=anchor))


def plot(drawing, series, x, y, width, height, y_min, y_max, step, line_colors,
         x_max, y_title, show_x=False):
    p = LinePlot()
    p.x, p.y, p.width, p.height = x, y, width, height
    p.data = series
    p.joinedLines = 1
    p.xValueAxis.valueMin, p.xValueAxis.valueMax, p.xValueAxis.valueStep = 0, x_max, 5
    p.yValueAxis.valueMin, p.yValueAxis.valueMax, p.yValueAxis.valueStep = y_min, y_max, step
    for ax in (p.xValueAxis, p.yValueAxis):
        ax.labels.fontName, ax.labels.fontSize = 'Helvetica', 10
        ax.strokeColor = colors.HexColor('#A6B2C1')
    p.yValueAxis.visibleGrid = 1
    p.yValueAxis.gridStrokeColor = colors.HexColor('#E3E8EF')
    if not show_x:
        p.xValueAxis.labels.visible = False
    for i, color in enumerate(line_colors):
        p.lines[i].strokeColor = colors.HexColor(color)
        p.lines[i].strokeWidth = 1.6 if i == 0 else 1.3
    drawing.add(p)
    label(drawing, x, y + height + 13, y_title, 12)
    return p


def measured_plot(samples, raw, guards):
    d = Drawing(1100, 660)
    d.add(Rect(0, 0, 1100, 660, fillColor=colors.white, strokeColor=None))
    label(d, 65, 626, 'NHIỆT ĐỘ VÀ LỆNH ĐIỀU KHIỂN ĐO TRÊN HỘP', 20)
    label(d, 65, 602, '17/11/2026 · 3.037 mẫu · khung tô cam: 5 lần bảo vệ mềm', 12)
    x, width, x_max = 65, 980, 52
    y, height, lo, hi = 290, 260, 31, 39
    # Background band and guard windows share the chart's explicit coordinate ranges.
    d.add(Rect(x, y + (37-lo)/(hi-lo)*height, width, height/(hi-lo),
               fillColor=colors.HexColor('#ECF7F0'), strokeColor=None))
    for guard in guards:
        left = x + guard['start_s']/60/x_max*width
        w = guard['duration_s']/60/x_max*width
        d.add(Rect(left, y, w, height, fillColor=colors.HexColor('#FFF1DA'), strokeColor=None))
    data = [[(r['t']/60, r['temperature']) for r in samples],
            [(0, 37.5), (x_max, 37.5)], [(0, 37), (x_max, 37)], [(0, 38), (x_max, 38)]]
    p = plot(d, data, x, y, width, height, lo, hi, 1,
             ['#18678A', '#557C5A', '#96B69B', '#96B69B'], x_max, 'Nhiệt độ (°C)')
    p.lines[1].strokeDashArray = [5, 3]
    p.lines[2].strokeDashArray = [2, 4]
    p.lines[3].strokeDashArray = [2, 4]
    h, f = [], []
    previous = None
    for row in raw:
        t = float(row['elapsed_s'])/60
        pair = float(row['lamp_command_pct']), float(row['fan_command_pct'])
        if pair != previous or row is raw[-1]:
            if previous is not None:
                h.append((t, previous[0])); f.append((t, previous[1]))
            h.append((t, pair[0])); f.append((t, pair[1])); previous = pair
    plot(d, [h, f], x, 105, width, 125, 0, 105, 25,
         ['#C36C16', '#158275'], x_max, 'Duty lệnh (%)', show_x=True)
    label(d, 555, 65, 'Thời gian từ lúc chạy (phút)', 12, anchor='middle')
    d.add(Line(65, 35, 90, 35, strokeColor=colors.HexColor('#C36C16'), strokeWidth=2))
    label(d, 97, 31, 'Bóng', 11)
    d.add(Line(180, 35, 205, 35, strokeColor=colors.HexColor('#158275'), strokeWidth=2))
    label(d, 212, 31, 'Quạt', 11)
    label(d, 320, 31, '37–38°C là vùng mục tiêu trong cấu hình; duty chưa phải W hoặc RPM.', 11)
    renderSVG.drawToFile(d, str(OUT/'do_thi_thuc_do.svg'))


def simulation_plot(reward):
    d = Drawing(1100, 490)
    d.add(Rect(0, 0, 1100, 490, fillColor=colors.white, strokeColor=None))
    label(d, 65, 454, 'KẾT QUẢ ĐỐI CHIẾU TRONG MÔ PHỎNG', 20)
    label(d, 65, 429, '32 tình huống test × 600 giây; chưa phải điều khiển đo thực trên hộp', 12)
    entries = [('Thermostat', reward['baseline']['test'], '#267C80'),
               ('RL trung bình', reward['test_mean'], '#C16B28'),
               ('RL seed 11', reward['test_by_seed'][0]['metrics'], '#8D9BAB'),
               ('RL seed 29', reward['test_by_seed'][1]['metrics'], '#8D9BAB')]
    for panel, key, title, vmax, ticks, suffix in (
        (0, 'mae_c', 'Sai số tuyệt đối trung bình (°C)', 1.25, [0, .25, .5, .75, 1, 1.25], ''),
        (1, 'in_band_pct', 'Thời gian trong vùng 37–38°C (%)', 100, [0, 20, 40, 60, 80, 100], '%')):
        x, y, width, height = 65 + panel*540, 110, 430, 245
        label(d, x, 381, title, 14)
        for tick in ticks:
            yy = y + tick/vmax*height
            d.add(Line(x, yy, x+width, yy, strokeColor=colors.HexColor('#E3E8EF')))
            label(d, x-8, yy-3, f'{tick:g}', 10, anchor='end')
        for i, (name, metrics, color) in enumerate(entries):
            value = metrics[key]
            xx, w = x+16+i*105, 68
            d.add(Rect(xx, y, w, value/vmax*height, fillColor=colors.HexColor(color), strokeColor=None))
            label(d, xx+w/2, y+value/vmax*height+9, (f'{value:.3f}' if panel==0 else f'{value:.1f}%'), 12, anchor='middle')
            label(d, xx+w/2, y-20, name, 10, anchor='middle')
        if panel == 1:
            yy = y + .8*height
            d.add(Line(x, yy, x+width, yy, strokeColor=colors.HexColor('#9E4540'), strokeDashArray=[5, 3]))
            label(d, x+width, yy+8, 'Mốc kiểm tra 80%', 10, '#9E4540', anchor='end')
    label(d, 65, 48, 'Thermostat dùng cùng tập action đã được phép; tham số chọn trên validation.', 12)
    label(d, 65, 25, 'RL hiện chưa vượt điều kiện kiểm tra; chưa có Q-table đủ điều kiện triển khai.', 12)
    renderSVG.drawToFile(d, str(OUT/'doi_chieu_mo_phong.svg'))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    raw = load_csv(RUN/'du_lieu.csv')
    saved = json.loads((RUN/'phan_tich/phan_tich.json').read_text(encoding='utf-8'))
    cfg = json.loads((RUN/'cau_hinh.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256((RUN/'du_lieu.csv').read_bytes()).hexdigest()
    if digest != saved['sources'][0]['sha256']:
        raise ValueError('Copied CSV hash differs from the original analyzed CSV')
    session = analysis.read_log(RUN/'du_lieu.csv')
    blocks = analysis.summarize_phases([session])
    model, model_report, issues, actions, train = analysis.identify([session], 37.5, .5)
    if model is None or issues:
        raise ValueError(f'Model recheck failed: {issues}')
    assert max(abs(x-y) for x, y in zip(model.coefficients, saved['model']['selected']['coefficients'])) < 1e-12
    originals = load_csv(RUN/'phan_tich/dap_ung_tung_buoc.csv')
    assert len(originals) == len(blocks)
    assert max(abs(float(x['delta_c'])-y['delta_c']) for x,y in zip(originals, blocks)) < 1e-12
    measurements = [r for r in raw if r['event']=='MEASUREMENT']
    times = [float(r['elapsed_s'])-float(r['temperature_age_s']) for r in measurements]
    temps = [float(r['temperature_c']) for r in measurements]
    gaps = [b-a for a,b in zip(times,times[1:])]
    commands = [r for r in raw if r['event']=='COMMAND']
    guards = []
    for i, row in enumerate(commands):
        if row['phase'].startswith('bao_ve'):
            portion = [r for r in measurements if r['phase']==row['phase']]
            peak = max(portion, key=lambda r:float(r['temperature_c']))
            guards.append(dict(phase=row['phase'], start_s=float(row['elapsed_s']),
                duration_s=float(commands[i+1]['elapsed_s'])-float(row['elapsed_s']),
                peak_c=float(peak['temperature_c']), peak_after_off_s=float(peak['elapsed_s'])-float(row['elapsed_s']),
                resume_c=float(commands[i+1]['temperature_c'])))
    reward = saved['reward_search']
    diagnostics = []
    for seed in (11,29):
        q, visits = analysis.train_q(model, train, actions, 37.5, .5,
            reward['selected']['weights'], seed, 250)
        cells = [v for row in visits for v in row]
        observed = [v for v in cells if v]
        val = analysis.evaluate(model, actions, analysis.scenarios(model,train,37.5,140,16),
                                37.5,.5,q=q,visits=visits)
        test = analysis.evaluate(model, actions, analysis.scenarios(model,train,37.5,905,32),
                                 37.5,.5,q=q,visits=visits)
        expected = next(item['metrics'] for item in reward['test_by_seed'] if item['seed']==seed)
        assert max(abs(test[k]-expected[k]) for k in test) < 1e-12
        diagnostics.append(dict(seed=seed,updates=sum(cells),states_seen=sum(any(v) for v in visits),
            state_action_pairs_seen=len(observed),median_visits_among_seen=statistics.median(observed),
            total_cells=len(cells),validation=val,test=test))
    qa = dict(source_sha256=digest,source=str(RUN/'du_lieu.csv'),measurement_count=len(temps),
        duration_s=float(raw[-1]['elapsed_s']),temperature_min_c=min(temps),temperature_max_c=max(temps),
        sample_gap_max_s=max(gaps),sample_age_max_s=max(float(r['temperature_age_s']) for r in measurements),
        software_guards=guards,qualified_actions=len(actions),state_count=81*len(actions),
        complete_trial_blocks=sum(b['continuous_window_complete'] is True for b in blocks),
        model_and_selected_policy_reproduction_matches=True,training_diagnostics=diagnostics)
    (OUT/'kiem_tra_doc_lap.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    measured_plot(session['samples'],raw,guards)
    simulation_plot(reward)

    rows = []
    for h in (0,25,50,75,100):
        for f in (75,100):
            found = [b for b in blocks if b['phase'].startswith('thu_') and
                     b['lamp_requested_pct']==h and b['fan_requested_pct']==f]
            full = [b for b in found if b['continuous_window_complete']]
            slopes = [b['slope_c_per_min'] for b in full]
            text = ('—; chỉ có đoạn bị ngắt' if not slopes else
                    f'{min(slopes):+.3f} đến {max(slopes):+.3f}' if len(slopes)>1 else f'{slopes[0]:+.3f}')
            rows.append(f'| {h} | {f} | {len(full)}/2 | {text} |')
    guard_rows = [f"| {i} | {g['start_s']/60:.2f} | {g['duration_s']:.1f} | {g['peak_c']:.3f} | {g['resume_c']:.3f} |"
                  for i,g in enumerate(guards,1)]
    ts0 = datetime.fromisoformat(raw[0]['timestamp_utc'])+timedelta(hours=7)
    ts1 = datetime.fromisoformat(raw[-1]['timestamp_utc'])+timedelta(hours=7)
    measured_span = times[-1]-times[0]
    in_band = sum(dt for t,dt in zip(temps,gaps) if 37<=t<=38)/measured_span*100
    report = f'''# Phân tích khảo sát hộp ấp ngày 17/11/2026

Lượt đo: `20261117_070909_628598`. Phân tích hoàn toàn offline từ dữ liệu đã chép về laptop; giữ nguyên log và kết quả gốc.

## Kết luận chính

Hệ bóng–quạt tạo được đáp ứng nhiệt rõ ràng tại đầu dò: nhiệt độ đo được **31,500–38,125°C**. Lịch khảo sát đã hoàn tất, dữ liệu đọc liên tục, đủ khớp một mô hình dự báo nhiệt ngắn hạn theo các điều kiện đã đo. Tuy nhiên, **Q-learning hiện chưa đạt yêu cầu và đang thua đối chứng trong mô phỏng**. Chưa có cơ sở gọi bộ reward hoặc Q-table hiện tại là tối ưu, và chương trình đã không xuất Q-table triển khai.

Bước có ích ngay lúc này là kiểm tra giữ nhiệt quanh 37,5°C và cải thiện độ ổn định của huấn luyện offline. Chưa cần đo lại toàn bộ khảo sát chỉ vì chưa có Q-table.

## 1. Dữ liệu và chất lượng ghi nhận

| Nội dung | Kết quả |
|---|---:|
| Thời gian theo giờ Việt Nam | {ts0:%H:%M:%S}–{ts1:%H:%M:%S}, 17/11/2026 |
| Tổng thời gian từ khi bắt đầu chương trình đến END | {float(raw[-1]['elapsed_s']):.2f} giây, khoảng 50 phút 38 giây |
| Số mẫu nhiệt MEASUREMENT | {len(temps):,} |
| Khoảng cách lớn nhất giữa hai mẫu | {max(gaps):.3f} giây |
| Tuổi số đo lớn nhất khi được ghi | {qa['sample_age_max_s']:.3f} giây |
| Lỗi đọc cảm biến / ERROR trong log | Không ghi nhận |
| Tần số PWM quạt được ghi | 100 Hz |
| Lịch 20 lượt thử: 10 tổ hợp × 2 lần | Đã hoàn tất theo cấu hình |
| Số lượt thử đủ cửa sổ liên tục ~120 giây | {qa['complete_trial_blocks']}/20 |
| Tổ hợp có ít nhất một cửa sổ đủ liên tục | 9/10 |
| Số lần bảo vệ mềm | 5 |

Cửa sổ có 120 mẫu cách nhau khoảng một giây thường có khoảng cách mẫu đầu–cuối khoảng 119 giây; đây là lý do báo cáo ghi 119/120 và vẫn đánh dấu đủ. Khi bị bảo vệ mềm, chương trình dừng tính thời gian kích thích rồi tiếp tục phần còn lại. Vì vậy “lịch đã hoàn tất” không có nghĩa tất cả lượt đều có 120 giây không bị ngắt.

SHA-256 của CSV chép về trùng bản gốc đã được Pi phân tích: `{digest}`. Đã tái tính bảng đáp ứng, mô hình và hai chính sách được chọn với đúng seed/tham số; các chỉ số test trùng kết quả gốc trong sai số số học 1e-12.

![Nhiệt độ đo thực và duty lệnh](do_thi_thuc_do.png)

## 2. Từng mức bóng–quạt đang làm được gì?

Độ dốc dưới đây là hồi quy từ số đo sau khi bỏ 5 giây đầu mỗi đoạn. Bảng chỉ gộp các **đoạn đủ liên tục**, không cộng hai đoạn bị ngắt thành một đoạn dài. Đơn vị °C/phút. Đây là đáp ứng trong khoảng nhiệt ban đầu khác nhau, chưa phải phép so sánh nhân quả giữa hai mức quạt.

| Bóng (%) | Quạt (%) | Lượt đủ liên tục / 2 lượt dự kiến | Khoảng độ dốc từ lượt đủ (°C/phút) |
|---:|---:|---:|---:|
{chr(10).join(rows)}

Những quan sát quan trọng:

- **Bóng 0%:** nhiệt giảm khoảng 1,17–1,57°C/phút trong các đoạn thử đủ dài. Đây là tác dụng nguội tổng của hộp khi ngừng sưởi và quạt còn chạy; chưa tách được phần mất nhiệt tự nhiên và phần do quạt.
- **Bóng 25%:** phần lớn đoạn đang nguội, đặc biệt ở khoảng nhiệt cao. Ví dụ 25%/quạt 100% giảm từ 37,312 xuống 35,750°C. Ở khoảng 32°C, cùng tổ hợp lại gần ngang hoặc nhích lên. Không thể gắn một tốc độ cố định cho từng action.
- **Bóng 50%/quạt 75%:** ở lượt bắt đầu 37,500°C, kết thúc 37,812°C sau khoảng hai phút, dốc toàn đoạn +0,114°C/phút, 30 giây cuối +0,073°C/phút. Đây là điểm khởi đầu đáng thử cho giữ nhiệt quanh mục tiêu, chưa chứng minh giữ ổn định lâu dài.
- **Bóng 50%/quạt 100%:** một đoạn khoảng 36,062°C có thay đổi ròng gần 0; đoạn khác bắt đầu 34,875°C và kết thúc 34,625°C, nhưng 30 giây cuối đã tăng +0,219°C/phút. Lịch sử sưởi trước đó còn tác động; không thể kết luận 50% này luôn giữ đúng 37,5°C.
- **Bóng 75–100%:** nhiệt tăng rõ, phù hợp để khảo sát làm ấm trong phiên có giám sát. Gần mục tiêu, giữ các mức này liên tục dễ kích hoạt bảo vệ. Lượt 100%/quạt 75% tăng +2,485°C/phút khi bắt đầu từ 32,187°C; không dùng tốc độ đó để ngoại suy ở 37,5°C.
- Quạt 75% và 100% đều cần tiếp tục có mặt trong action phối hợp. Log có dấu hiệu mức quạt làm thay đổi đáp ứng, nhưng nhiệt ban đầu và lịch sử bóng khác nhau nên chưa xác định riêng được hiệu quả của việc tăng quạt. Một đầu dò cũng chưa đo được độ đồng đều nhiệt trong hộp.

Trong giai đoạn làm ấm 180 giây, nhiệt từ khoảng 31,56 lên 35,63°C, chưa chạm ngưỡng kết thúc làm ấm 37°C. Toàn lượt sau đó vẫn có số đo qua vùng mục tiêu; cờ `warm_target_reached=false` không có nghĩa toàn khảo sát thất bại.

## 3. Ngắt sưởi và quán tính nhiệt

| Lần bảo vệ mềm | Bắt đầu tại phút | Thời gian giữ bóng 0% / quạt 100% (s) | Đỉnh nhiệt trong đoạn (°C) | Nhiệt lúc tiếp tục (°C) |
|---:|---:|---:|---:|---:|
{chr(10).join(guard_rows)}

Mỗi lần, phần mềm chuyển sang bóng 0%/quạt 100% khi đầu dò đạt 38°C và chỉ tiếp tục khảo sát khi về 37°C. Có lần đầu dò vẫn tăng lên **38,125°C khoảng 7 giây sau lệnh tắt bóng**. Đây là bằng chứng thực nghiệm cần xét xu hướng nhiệt và lịch sử sưởi, thay vì chỉ chờ chạm ngưỡng rồi mới tắt.

Không có số đo chạm ngưỡng ngắt phần mềm cứng 40°C. Lượt này cũng không kiểm chứng được KSD301 đã tác động hay chưa. Các phần trăm trong log là lệnh GPIO/PWM; chưa có phép đo W, RPM hoặc phản hồi dòng điện để xác nhận độc lập từng cơ cấu chấp hành.

Tỷ lệ thời gian khảo sát nằm trong 37–38°C chỉ khoảng **{in_band:.1f}%**, tính có trọng số theo thời gian mẫu. Đây là lịch cố tình thử các mức tăng/giảm nhiệt, **không phải** chỉ số chất lượng một bộ điều khiển giữ nhiệt. Không dùng tỷ lệ này để so trực tiếp với RL hoặc thermostat ở phần mô phỏng.

## 4. Mô hình nhiệt: dùng được đến đâu?

Mô hình được khớp trên khoảng 60% dữ liệu đầu, chọn cấu hình bằng 20% tiếp theo và kiểm tra bằng 20% cuối, có khoảng cách 10 giây ở ranh giới. Ba phần vẫn thuộc cùng một lượt đo, chưa phải ba thí nghiệm độc lập.

| Chỉ số dự báo 30 giây | Validation | Test cuối lượt |
|---|---:|---:|
| RMSE mô hình (°C) | 0,0745 | 0,0725 |
| RMSE nếu giữ nguyên nhiệt hiện tại (°C) | 0,3072 | 0,4292 |

Mô hình có bộ nhớ sưởi dạng lọc với tham số 25 giây, tốt nhất trong ba giá trị đã thử 0/10/25 giây. **25 giây là tham số của mô hình được chọn**, chưa phải phép đo hằng số thời gian vật lý chính xác của hộp. Dự báo 30 giây khá sát số đo trong lượt này cũng chưa bảo đảm mô phỏng kín 10 phút luôn đúng, đặc biệt khi bố trí, nhiệt phòng hoặc tải trong hộp thay đổi.

Tổ hợp bóng 100%/quạt 100% chỉ có các đoạn liên tục tối đa khoảng 77 giây do bảo vệ. Công cụ loại tổ hợp này khỏi tập action ứng viên theo quy tắc đã đặt; hiện chỉ có **9 action**. Không tăng ngưỡng bảo vệ để cố lấy đủ đoạn. Các phần dữ liệu quá độ vẫn hữu ích cho nhận dạng.

Với cách mã hóa hiện tại, 9 action tạo **729 state và bảng 729×9**, gồm 9 mức sai lệch nhiệt × 3 xu hướng × 3 mức bộ nhớ sưởi × 9 action trước đó. Con số 810×10 chỉ áp dụng khi cả 10 action được phép.

## 5. Kết quả RL thực sự

Chương trình đã thử 18 bộ hệ số, mỗi bộ huấn luyện 250 episode cho từng seed 11 và 29. Mô phỏng test gồm 32 tình huống, mỗi tình huống 600 giây. Bảng sau hoàn toàn là kết quả mô phỏng trên mô hình vừa khớp, chưa có lượt RL/PID/thermostat điều khiển thật để so sánh.

| Bộ điều khiển | MAE (°C) | Thời gian trong vùng 37–38°C | Tỷ lệ tình huống ra ngoài miền mô hình |
|---|---:|---:|---:|
| Thermostat đối chứng | 0,157 | 95,70% | 0% |
| Q-learning, trung bình hai seed | 0,680 | 65,79% | 1,56% |
| Q-learning seed 11 | 1,115 | 44,48% | 3,125% |
| Q-learning seed 29 | 0,244 | 87,11% | 0% |

Đối chứng được chọn là thermostat có hysteresis ±0,1°C và quạt theo quy tắc xu hướng, dùng cùng tập action được phép; không phải PID. Tham số đối chứng cũng được chọn trên validation. Chỉ số MAE của các tình huống ra ngoài miền mô hình có phần phạt cho các bước chưa thể mô phỏng tiếp; không nên diễn giải toàn bộ 0,680°C như sai số đo trên thiết bị thật.

![Đối chiếu mô phỏng](doi_chieu_mo_phong.png)

Hệ số được xếp cao nhất trong lượt thử hiện tại là `hot=10`, `duty=0.2`, `switch=0.03`, với trọng số sai số nhiệt bằng 1. Tuy nhiên, validation chỉ đạt 70,03% trong vùng, thấp hơn điều kiện 80%; test cũng không đạt. Tất cả 18 bộ thử đều chưa đạt 80% thời gian trong vùng trên validation khi lấy trung bình hai seed. Vì vậy **đây không phải bộ hệ số đã tối ưu hoặc đủ điều kiện triển khai**.

## 6. Vì sao RL hiện còn kém?

Các điểm sau giải thích hướng điều tra, chưa phải bằng chứng chỉ có một nguyên nhân duy nhất:

1. **Độ ổn định huấn luyện còn thấp.** Cùng mô hình và reward nhưng hai seed cho 44,48% và 87,11% thời gian trong vùng trên test. Không được chỉ lấy seed 29 để công bố kết quả tốt.
2. **Bảng trạng thái lớn so với số lần cập nhật hữu ích.** Khi tái chạy đúng cấu hình, seed 11/29 có khoảng 29.240/29.431 cập nhật. Chỉ 2.675/2.685 cặp state–action được thăm trong tổng 6.561 ô; trung vị số lần thăm các ô đã thấy chỉ 5/4. Một phần state có thể không đạt tới nên không yêu cầu phủ hết bảng, nhưng số liệu này cùng chênh lệch seed cho thấy cần kiểm tra hội tụ trước khi kết luận về reward.
3. **Cách xếp hạng ưu tiên tuyệt đối mức vượt nhiệt trước tỷ lệ trong vùng.** Bộ đang chọn có diện tích vượt vùng trên validation 0,003773°C·phút, so với 0,004149°C·phút của bộ `10/0.2/0`; chênh khoảng 0,000376°C·phút đủ làm bộ đạt 70,03% được xếp trên bộ đạt 75,29%. Đây là hệ quả thứ tự tiêu chí hiện tại. Đổi xếp hạng riêng lẻ cũng chưa giải quyết việc cả 18 bộ chưa đạt mốc 80%.
4. **Mô hình mới được kiểm tra ngắn hạn trong một phiên.** RL có thể chọn chuỗi action ít giống lịch khảo sát; sai số mô hình ở chuỗi đó có thể khác. Chưa thể dùng mô phỏng để xác nhận cải tiến trên hộp thật.

## 7. Nên làm tiếp theo

1. **Giữ nguyên bộ dữ liệu này làm mốc.** Không cần mua thêm cảm biến hoặc thay linh kiện chỉ vì kết quả RL chưa đạt. Nếu có di chuyển đầu dò, bóng, quạt, thay nắp hoặc thêm nước/tải thì ghi rõ, vì điều đó tạo điều kiện khác.
2. **Kiểm tra giữ nhiệt quanh mục tiêu trong một lượt độc lập có giám sát.** Gợi ý quan sát bóng 50% với quạt 75% hoặc 100%, mỗi đoạn 5–10 phút nếu chưa chạm ngưỡng bảo vệ. Khi gần 38°C hoặc có lỗi đọc, vẫn phải ngắt sưởi theo chương trình. Mục tiêu là kiểm chứng vùng duy trì và quán tính, không cố đủ thời gian bằng cách bỏ bảo vệ. Chưa tự chạy khảo sát mới trong lần phân tích này.
3. **Cải thiện RL offline trên validation trước khi đưa lên Pi.** Kiểm tra đường học qua nhiều mức episode và nhiều seed; xem độ ổn định thay vì chỉ tăng một lần rồi chọn kết quả đẹp. Có thể thử mô hình trạng thái gọn hơn gồm sai lệch, xu hướng và bộ nhớ sưởi. Nếu bỏ action trước khỏi state, cần tạm bỏ hạng phạt đổi action hoặc đưa đủ thông tin đó về state. Đây là giả thuyết cần kiểm tra, không mặc định sẽ tốt hơn.
4. **Chốt tiêu chí đạt trước khi thử reward tiếp.** Đặt rõ điều kiện vượt nhiệt chấp nhận được, không ra ngoài miền mô hình, tỷ lệ giữ vùng và sai số; lọc theo điều kiện đạt rồi mới cân nhắc duty/chuyển mức. Các hệ số không thể được xác định duy nhất chỉ từ tốc độ tăng nhiệt.
5. **Dùng dữ liệu kiểm tra mới sau khi sửa thiết kế.** Tập test hiện đã được đọc trong báo cáo này. Không tiếp tục chỉnh theo test cũ rồi gọi đó là kiểm tra độc lập. Cuối cùng cần đo RL và đối chứng trên cùng phần cứng, cùng điều kiện đầu/nhiễu, với log riêng.

Độ ẩm chưa xuất hiện trong log. DHT11/SHT31 chỉ thêm khả năng quan sát nếu được lắp và tích hợp; kết quả hiện tại không đánh giá được điều khiển độ ẩm, độ đều nhiệt, tiết kiệm Wh hoặc tỷ lệ nở trứng.

## Nguồn và cách kiểm tra

- Đo thực: `../../Du_lieu_khao_sat/20261117_070909_628598/du_lieu.csv` và `cau_hinh.json`.
- Báo cáo tự động: thư mục `phan_tich` của cùng lượt, gồm `phan_tich.json`, `dap_ung_tung_buoc.csv`, `thu_he_so_reward.csv`.
- Kiểm tra độc lập kèm báo cáo: `kiem_tra_doc_lap.json`; đồ thị đo thực và mô phỏng được lưu riêng, mỗi đồ thị có PNG và SVG.
- Không dùng các kết quả mô phỏng giả định cũ hoặc dữ liệu kiểm thử SYNTHETIC làm kết quả thực nghiệm của lượt này.
'''
    (OUT/'PHAN_TICH_KHAO_SAT_17_11_2026.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(report=str(OUT/'PHAN_TICH_KHAO_SAT_17_11_2026.md'),
                         samples=len(temps),guards=len(guards),qualified_actions=len(actions),
                         complete_trials=qa['complete_trial_blocks'],source_hash_match=True,
                         reproduced_model_and_policy=True),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
