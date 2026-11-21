#!/usr/bin/env python3
"""Phân tích lượt ap_trung.py (RL hoặc thermostat, 3 giai đoạn, có đổi ngày) từ CSV thật trên Pi.

    python Code_HopAp_PhanTich/phan_tich_ap_trung.py Du_lieu_giu_nhiet/ket_qua_ap_trung/<lượt_rl> \\
        Du_lieu_giu_nhiet/ket_qua_ap_trung/<lượt_thermostat> --out outputs/phan_tich_ap_trung

Mỗi lượt được tách thành các ĐOẠN theo ngày ấp (pha ap_ngayNN_gdK). Với mỗi đoạn: mốc, vùng ±0,2 °C, thời gian
vào vùng sau khi đổi ngày, % thời gian trong vùng và MAE TÍNH TỪ LÚC ĐÃ VÀO VÙNG, độ lệch chuẩn, số lần đổi mức
/10 phút, thời gian bảo vệ. Chỉ số theo trọng số thời gian (mỗi mẫu tối đa 5 s). CSV có sensor_id MO_PHONG hoặc
cau_hinh.json có "mo_phong": true được ghi rõ là MÔ PHỎNG.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Code_HopAp_Demo'))
from cloud_bridge import HOLD, classify, describe_controller, num, read_run_config, stage_of  # noqa: E402

MAX_WEIGHT_S = 5.0


def load_run(path):
    path = Path(path)
    csv_path = path / 'du_lieu.csv' if path.is_dir() else path
    with csv_path.open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    config = read_run_config(csv_path)
    simulated = bool(config.get('mo_phong')) or any(r.get('sensor_id') == 'MO_PHONG' for r in rows[:5])
    return {'ten': csv_path.parent.name, 'csv': str(csv_path), 'rows': rows, 'config': config,
            'bo_dieu_khien': describe_controller(config), 'mo_phong': simulated}


def hold_samples(rows):
    """Mẫu MEASUREMENT trong giai đoạn điều khiển (từ lúc giao cho RL/thermostat), có ngày/giai đoạn."""
    out, started = [], False
    for r in rows:
        cls = classify(r.get('phase'))
        stage = stage_of(r.get('phase'))
        if cls == 'giu_nhiet' and stage:
            started = True
        if not started or r.get('event') != 'MEASUREMENT' or cls not in HOLD or not stage:
            continue
        t, temp = num(r.get('elapsed_s')), num(r.get('temperature_c'))
        if t is None or temp is None:
            continue
        out.append({'t': t, 'T': temp, 'L': num(r.get('lamp_command_pct')), 'F': num(r.get('fan_command_pct')),
                    'bao_ve': cls == 'bao_ve', **stage})
    for a, b in zip(out, out[1:]):
        a['w'] = max(0.0, min(b['t'] - a['t'], MAX_WEIGHT_S))
    if out:
        out[-1]['w'] = min(1.0, MAX_WEIGHT_S)
    return out


def segment_metrics(seg):
    lo, hi = seg[0]['vung_c']
    target = seg[0]['muc_tieu_c']
    start = seg[0]['t']
    first = next((i for i, p in enumerate(seg) if lo <= p['T'] <= hi), None)
    settled = seg[first:] if first is not None else []
    weight = sum(p['w'] for p in settled)
    duration = seg[-1]['t'] - start + seg[-1]['w']
    changes = sum(1 for a, b in zip(seg, seg[1:]) if (a['L'], a['F']) != (b['L'], b['F']))
    result = {
        'ngay': seg[0]['ngay'], 'giai_doan': seg[0]['giai_doan'], 'muc_tieu_c': target, 'vung_c': [lo, hi],
        'bat_dau_s': round(start, 1), 'thoi_luong_s': round(duration, 1),
        'vao_vung_sau_s': None if first is None else round(seg[first]['t'] - start, 1),
        'doi_muc_moi_10_phut': round(changes / max(duration, 1) * 600, 1),
        'bao_ve_s': round(sum(p['w'] for p in seg if p['bao_ve']), 1),
        'bong_tb_pct': round(sum(p['L'] * p['w'] for p in seg if p['L'] is not None) / max(sum(p['w'] for p in seg), 1e-9), 1),
    }
    if weight > 0:
        mean = sum(p['T'] * p['w'] for p in settled) / weight
        result.update(
            trong_vung_pct=round(100 * sum(p['w'] for p in settled if lo <= p['T'] <= hi) / weight, 2),
            mae_c=round(sum(abs(p['T'] - target) * p['w'] for p in settled) / weight, 4),
            do_lech_chuan_c=round(math.sqrt(sum((p['T'] - mean) ** 2 * p['w'] for p in settled) / weight), 4),
            nhiet_min_c=round(min(p['T'] for p in settled), 3), nhiet_max_c=round(max(p['T'] for p in settled), 3))
    else:
        result.update(trong_vung_pct=None, mae_c=None, do_lech_chuan_c=None, nhiet_min_c=None, nhiet_max_c=None)
    return result


def analyze(run):
    samples = hold_samples(run['rows'])
    segments, current = [], []
    for p in samples:
        if current and p['ngay'] != current[-1]['ngay']:
            segments.append(current)
            current = []
        current.append(p)
    if current:
        segments.append(current)
    seg_metrics = [segment_metrics(s) for s in segments]
    by_stage = {}
    for gd in sorted({s['giai_doan'] for s in seg_metrics}):
        pts = [p for s in segments if s[0]['giai_doan'] == gd for p in s]
        m = segment_metrics(pts) if pts else {}
        by_stage[str(gd)] = {k: m.get(k) for k in ('muc_tieu_c', 'vung_c', 'thoi_luong_s', 'trong_vung_pct', 'mae_c',
                                                   'do_lech_chuan_c', 'doi_muc_moi_10_phut', 'bao_ve_s')}
    ended = any(r.get('event') == 'END' for r in run['rows'])
    errors = [r.get('note') for r in run['rows'] if r.get('event') == 'ERROR']
    return {'ten': run['ten'], 'csv': run['csv'], 'bo_dieu_khien': run['bo_dieu_khien'], 'mo_phong': run['mo_phong'],
            'ket_thuc': ended, 'loi': errors, 'so_mau_dieu_khien': len(samples),
            'doan_theo_ngay': seg_metrics, 'theo_giai_doan': by_stage, '_samples': samples}


def fmt(v, digits=1):
    return '--' if v is None else f'{v:.{digits}f}'.replace('.', ',')


def report_md(results):
    sim = any(r['mo_phong'] for r in results)
    lines = ['# Phân tích lượt ấp 3 giai đoạn', '']
    if sim:
        lines += ['> **Có lượt MÔ PHỎNG** (đánh dấu ⚠). Không dùng các số đó như số đo thật.', '']
    lines += ['Chỉ số trong vùng/MAE/độ lệch chuẩn tính **từ lúc nhiệt đã vào vùng** của đoạn (sau khi đổi ngày cần '
              'thời gian chuyển mốc, được báo riêng ở cột "Vào vùng sau"). Trọng số theo thời gian.', '',
              '## Theo từng đoạn ngày', '',
              '| Lượt | Bộ điều khiển | Ngày | GĐ | Mốc °C | Dài (s) | Vào vùng sau (s) | Trong vùng (%) | MAE (°C) '
              '| Độ lệch chuẩn (°C) | Đổi mức/10 phút | Bảo vệ (s) |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        mark = ' ⚠' if r['mo_phong'] else ''
        for s in r['doan_theo_ngay']:
            lines.append(f"| {r['ten']}{mark} | {r['bo_dieu_khien']} | {s['ngay']} | {s['giai_doan']} | "
                         f"{fmt(s['muc_tieu_c'])} | {fmt(s['thoi_luong_s'], 0)} | {fmt(s['vao_vung_sau_s'], 0)} | "
                         f"{fmt(s['trong_vung_pct'])} | {fmt(s['mae_c'], 3)} | {fmt(s['do_lech_chuan_c'], 3)} | "
                         f"{fmt(s['doi_muc_moi_10_phut'])} | {fmt(s['bao_ve_s'], 0)} |")
    lines += ['', '## So sánh theo giai đoạn', '',
              '| Giai đoạn | Mốc °C | ' + ' | '.join(f"{r['bo_dieu_khien']}{' ⚠' if r['mo_phong'] else ''}: trong vùng % / MAE °C / đổi mức"
                                                   for r in results) + ' |',
              '|---|---:|' + '---|' * len(results)]
    for gd in sorted({g for r in results for g in r['theo_giai_doan']}):
        target = next(r['theo_giai_doan'][gd]['muc_tieu_c'] for r in results if gd in r['theo_giai_doan'])
        cells = []
        for r in results:
            s = r['theo_giai_doan'].get(gd)
            cells.append('--' if not s else f"{fmt(s['trong_vung_pct'])} / {fmt(s['mae_c'], 3)} / {fmt(s['doi_muc_moi_10_phut'])}")
        lines.append(f'| {gd} | {fmt(target)} | ' + ' | '.join(cells) + ' |')
    lines += ['', '## Tình trạng lượt', '']
    for r in results:
        lines.append(f"- {r['ten']} ({r['bo_dieu_khien']}): {'kết thúc bình thường' if r['ket_thuc'] else 'CHƯA có END'}; "
                     f"{len(r['loi'])} lỗi; {r['so_mau_dieu_khien']} mẫu điều khiển.")
    return '\n'.join(lines) + '\n'


def plot(results, out):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    files = []
    colors = ['#c2410c', '#2563eb', '#15803d', '#7c3aed']
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    for i, r in enumerate(results):
        s = r['_samples']
        if not s:
            continue
        t0 = s[0]['t']
        xs = [(p['t'] - t0) / 60 for p in s]
        label = f"{r['bo_dieu_khien']}{' (MÔ PHỎNG)' if r['mo_phong'] else ''}"
        axes[0].plot(xs, [p['T'] for p in s], color=colors[i % 4], lw=1.2, label=label)
        axes[1].step(xs, [p['L'] for p in s], color=colors[i % 4], lw=1, where='post', label=f'Bóng · {label}')
        if i == 0:
            for a, b in zip(s, s[1:]):
                axes[0].fill_between([(a['t'] - t0) / 60, (b['t'] - t0) / 60], *a['vung_c'], color='#16a34a', alpha=0.13, lw=0)
            for seg in r['doan_theo_ngay']:
                x = (seg['bat_dau_s'] - t0) / 60
                axes[0].axvline(x, color='#57534e', lw=0.8, ls='--')
                axes[0].text(x + 0.2, seg['vung_c'][1] + 0.12, f"Ngày {seg['ngay']} · {fmt(seg['muc_tieu_c'])} °C", fontsize=8)
    axes[0].set_ylabel('°C')
    axes[0].legend(loc='lower left', fontsize=8)
    title = 'Lượt ấp 3 giai đoạn (dải xanh = vùng ±0,2 °C của giai đoạn)'
    if any(r['mo_phong'] for r in results):
        title = 'CÓ DỮ LIỆU MÔ PHỎNG — ' + title
    axes[0].set_title(title, fontsize=11)
    axes[1].set_ylabel('% bóng')
    axes[1].set_xlabel('Phút kể từ lúc giao điều khiển')
    axes[1].legend(loc='upper right', fontsize=7)
    fig.tight_layout()
    path = out / 'AP_TRUNG_SO_SANH.png'
    fig.savefig(path, dpi=130)
    plt.close(fig)
    files.append(path.name)
    return files


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('luot', nargs='+', type=Path, help='Thư mục lượt (chứa du_lieu.csv) hoặc file CSV')
    p.add_argument('--out', type=Path, default=ROOT / 'outputs' / 'phan_tich_ap_trung')
    args = p.parse_args(argv)
    results = [analyze(load_run(path)) for path in args.luot]
    if not any(r['doan_theo_ngay'] for r in results):
        print('Không có đoạn ap_ngayNN_gdK nào: đây có phải lượt ap_trung.py không?', file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'KET_QUA.md').write_text(report_md(results), encoding='utf-8')
    (args.out / 'ket_qua.json').write_text(json.dumps([{k: v for k, v in r.items() if not k.startswith('_')}
                                                       for r in results], ensure_ascii=False, indent=2), encoding='utf-8')
    images = plot(results, args.out)
    print(report_md(results))
    print(f'Đã ghi {args.out / "KET_QUA.md"}, ket_qua.json' + (f', {", ".join(images)}' if images else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
