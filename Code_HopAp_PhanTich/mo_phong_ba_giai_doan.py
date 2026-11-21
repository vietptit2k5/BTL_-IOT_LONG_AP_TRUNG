#!/usr/bin/env python3
"""Mô phỏng ap_trung.ApTrungPolicy (đúng code chạy trên Pi) theo 3 giai đoạn và khi ĐỔI NGÀY giữa chừng.

Mô hình nhiệt: mô hình 5 s đã nhận dạng từ lượt đo 20/11 (trong goi_rl_moi_20261120.json), có hạng
c1·(T−37,5) nên mất nhiệt phụ thuộc nhiệt độ tuyệt đối — mốc 37,8 và 37,2 °C không giống hệt 37,5.
So với thermostat đối chứng (chinh_sach_nhiet.ReferenceController, cấu hình doi_chung_kiem_tra.json)
đổi mốc theo cùng lịch. CHỈ LÀ MÔ PHỎNG: mô hình chưa kiểm chứng trên hộp thật ở 37,8/37,2 °C.

    python Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py --out outputs/mo_phong_ba_giai_doan
"""
import argparse
import json
import math
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Code_HopAp_Demo'))
import ap_trung  # noqa: E402
import me_ap  # noqa: E402
from thu_rl_du_lieu_moi import read_package  # noqa: E402

DT = 5.0
WALL0 = 1_800_000_000.0


class Model:
    def __init__(self, m, rng):
        self.c, self.center, self.fc, self.tau, self.sd = m['coefficients'], m['center'], m['fan_center'], m['tau'], m['noise_sd']
        self.rng = rng

    def step(self, t, d, mem, heat, fan):
        c = self.c
        nm = mem + (heat - mem) * (1 - math.exp(-DT / self.tau))
        f = fan - self.fc
        nd = c[0] + c[1] * (t - self.center) + c[2] * d + c[3] * nm + c[4] * f + c[5] * nm * f + self.rng.gauss(0, self.sd)
        return t + nd, nd, nm


def run(controller, package, seed, minutes, changes, start_day, t0=29.5):
    """Chạy đúng ap_trung.ApTrungPolicy (rl hoặc thermostat). changes: [(phút sau khi giao điều khiển, ngày mới)]."""
    rng = random.Random(seed)
    model = Model(package['model'], rng)
    with tempfile.TemporaryDirectory() as tmp:
        lich = Path(tmp) / 'lich.json'
        clock = {'now': 0.0}
        wall = lambda: WALL0 + clock['now']
        me_ap.start_batch(lich, now=wall(), ngay=start_day)
        policy = ap_trung.ApTrungPolicy(package, minutes, lich, wall_clock=wall, controller=controller)
        policy.bind_sensor(package['sensor_id'])
        t, d, mem = t0, 0.0, 0.0
        lamp, fan = 0.0, 100.0
        policy.observe_output(0.0, lamp, fan)
        trace, hold_at, pending, stop = [], None, sorted(changes), None
        for _ in range(int((ap_trung.WARM_LIMIT_S + minutes * 60) / DT) + 2):
            now = clock['now']
            if hold_at is not None and pending and now - hold_at >= pending[0][0] * 60:
                me_ap.set_day(pending.pop(0)[1], lich, now=wall())
            if t >= me_ap.DUNG_CUNG_C:
                stop = 'dung_cung'
                break
            try:
                dec = policy(now, SimpleNamespace(temperature=t, at=now))
            except ValueError as exc:
                stop = f'loi: {exc}'
                break
            if dec is None:
                break
            lamp, fan, phase = dec.lamp, dec.fan, dec.phase
            info = policy.info
            mode = 'lam_am' if phase == 'lam_am_ap' else 'bao_ve' if 'bao_ve' in phase else 'giu'
            policy.observe_output(now, lamp, fan)
            if hold_at is None and mode != 'lam_am':
                hold_at = now
            trace.append({'t': now, 'T': t, 'L': lamp, 'F': fan, 'ngay': info['ngay'], 'gd': info['giai_doan'],
                          'muc': info['muc_tieu_c'], 'lo': info['vung_c'][0], 'hi': info['vung_c'][1],
                          'mode': mode, 'hold': hold_at is not None, 'phase': phase, 'note': dec.note})
            t, d, mem = model.step(t, d, mem, lamp / 100, fan / 100)
            clock['now'] += DT
    return trace, stop, policy.stats


def write_csv(trace, path, controller):
    """Ghi vết mô phỏng theo định dạng CSV của do_nhiet_hop (để thử phân tích/phát lại). Đánh dấu MO_PHONG."""
    import csv
    from datetime import datetime, timezone
    from cloud_bridge import CSV_FIELDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        w = csv.writer(stream)
        w.writerow(CSV_FIELDS)
        prev = None
        for p in trace:
            stamp = datetime.fromtimestamp(WALL0 + p['t'], timezone.utc).isoformat(timespec='milliseconds')
            base = [stamp, f"{p['t']:.3f}", None, p['phase'], 'MO_PHONG', f"{p['T']:.4f}", '0.000', 1,
                    p['L'], p['F'], p['L'], p['F'], 100, me_ap.DUNG_CUNG_C, '', '', '', '', '']
            key = (p['phase'], p['L'], p['F'])
            if key != prev:
                w.writerow(base[:2] + ['COMMAND'] + base[3:15] + [p['note'][:150]] + base[16:])
                prev = key
            w.writerow(base[:2] + ['MEASUREMENT'] + base[3:])
        last = trace[-1]
        w.writerow([datetime.fromtimestamp(WALL0 + last['t'] + 1, timezone.utc).isoformat(timespec='milliseconds'),
                    f"{last['t'] + 1:.3f}", 'END', 'giu_quat_cuoi', 'MO_PHONG', f"{last['T']:.4f}", '0.000', 1,
                    0, 0, 0, 0, 100, me_ap.DUNG_CUNG_C, '', 'MO PHONG - khong phai so do that', '', '', ''])
    (path.parent / 'cau_hinh.json').write_text(json.dumps(
        {'bo_dieu_khien': ap_trung.CONFIG_KEYS[controller], 'mo_phong': True,
         'ghi_chu': 'CSV MÔ PHỎNG từ mo_phong_ba_giai_doan.py, không phải số đo thật.'}, ensure_ascii=False), encoding='utf-8')


def segments(trace):
    """Tách giai đoạn giữ nhiệt theo ngày; chỉ số cho từng đoạn."""
    hold = [p for p in trace if p['hold']]
    out, cur = [], []
    for p in hold:
        if cur and p['ngay'] != cur[-1]['ngay']:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    result = []
    for seg in out:
        inside = [p['lo'] <= p['T'] <= p['hi'] for p in seg]
        first = next((i for i, v in enumerate(inside) if v), None)
        settled = seg[first:] if first is not None else []
        changes = sum(1 for a, b in zip(seg, seg[1:]) if (a['L'], a['F']) != (b['L'], b['F']))
        result.append({
            'ngay': seg[0]['ngay'], 'giai_doan': seg[0]['gd'], 'muc_tieu_c': seg[0]['muc'],
            'thoi_luong_s': len(seg) * DT,
            'vao_vung_sau_s': None if first is None else first * DT,
            'trong_vung_pct_sau_khi_vao': None if not settled else 100 * sum(p['lo'] <= p['T'] <= p['hi'] for p in settled) / len(settled),
            'mae_sau_khi_vao_c': None if not settled else sum(abs(p['T'] - p['muc']) for p in settled) / len(settled),
            'doi_muc_moi_10_phut': changes / max(1, len(seg) * DT / 600),
            'buoc_bao_ve': sum(p['mode'] == 'bao_ve' for p in seg),
        })
    return result


SCENARIOS = {
    'giu_ngay_05_gd1': dict(start_day=5, minutes=30, changes=[]),
    'giu_ngay_14_gd2': dict(start_day=14, minutes=30, changes=[]),
    'giu_ngay_19_gd3': dict(start_day=19, minutes=30, changes=[]),
    'demo_5_12_19': dict(start_day=5, minutes=30, changes=[(10, 12), (20, 19)]),
    'nhay_nguoc_19_5': dict(start_day=19, minutes=30, changes=[(10, 5)]),
}


def mean(values):
    values = [v for v in values if v is not None]
    return None if not values else sum(values) / len(values)


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / 'outputs' / 'mo_phong_ba_giai_doan')
    p.add_argument('--seeds', type=int, default=20)
    args = p.parse_args(argv)
    package = read_package(ROOT / 'Code_HopAp_Demo' / 'goi_rl_moi_20261120.json')
    args.out.mkdir(parents=True, exist_ok=True)
    report, example = {}, {}
    for name, sc in SCENARIOS.items():
        for ctrl in ('rl', 'thermostat'):
            per_seed, stops, fallbacks = [], [], 0
            for seed in range(args.seeds):
                trace, stop, stats = run(ctrl, package, 1000 + seed, sc['minutes'], sc['changes'], sc['start_day'])
                per_seed.append(segments(trace))
                stops.append(stop)
                fallbacks += stats.get('du_phong_lam_mat', 0)
                if seed == 0:
                    example[(name, ctrl)] = trace
                    if name == 'demo_5_12_19':
                        write_csv(trace, args.out / 'csv_MO_PHONG' / f'MO_PHONG_demo_{ctrl}' / 'du_lieu.csv', ctrl)
            n_seg = min(len(s) for s in per_seed)
            segs = []
            for i in range(n_seg):
                rows = [s[i] for s in per_seed]
                segs.append({k: (rows[0][k] if k in ('ngay', 'giai_doan', 'muc_tieu_c') else mean([r[k] for r in rows]))
                             for k in rows[0]})
            report.setdefault(name, {})[ctrl] = {'doan': segs, 'so_lan_dung': sum(s is not None for s in stops),
                                                 'ly_do_dung': sorted({s for s in stops if s}),
                                                 'du_phong_lam_mat': fallbacks}
    (args.out / 'ket_qua.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Mô phỏng ấp 3 giai đoạn — Q2 dịch mốc so với thermostat', '',
             f'CHỈ MÔ PHỎNG ({args.seeds} seed/kịch bản), mô hình 5 s nhận dạng từ lượt đo 20/11 ở 37,5 °C. '
             'Chưa kiểm chứng trên hộp thật ở 37,8/37,2 °C. Mỗi đoạn tính từ lúc đổi ngày (hoặc giao điều khiển).', '',
             '| Kịch bản | Ngày | Mốc °C | Bộ điều khiển | Vào vùng sau (s) | Trong vùng sau khi vào (%) | MAE (°C) | Đổi mức/10 phút | Bước bảo vệ |',
             '|---|---:|---:|---|---:|---:|---:|---:|---:|']
    fmt = lambda v, d=1: '--' if v is None else f'{v:.{d}f}'
    for name, ctrls in report.items():
        for ctrl, r in ctrls.items():
            for s in r['doan']:
                lines.append(f'| {name} | {s["ngay"]} | {s["muc_tieu_c"]:.1f} | {"Q2 dịch mốc" if ctrl == "rl" else "Thermostat"} | '
                             f'{fmt(s["vao_vung_sau_s"], 0)} | {fmt(s["trong_vung_pct_sau_khi_vao"])} | '
                             f'{fmt(s["mae_sau_khi_vao_c"], 3)} | {fmt(s["doi_muc_moi_10_phut"])} | {fmt(s["buoc_bao_ve"])} |')
    lines += ['', '## Dừng sớm / dự phòng', '']
    for name, ctrls in report.items():
        for ctrl, r in ctrls.items():
            lines.append(f'- {name} / {ctrl}: dừng {r["so_lan_dung"]}/{args.seeds} lượt {r["ly_do_dung"] or ""}; '
                         f'dự phòng làm mát {r["du_phong_lam_mat"]} lần')
    (args.out / 'KET_QUA.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        for ctrl, color, label in (('rl', '#c2410c', 'Q2 dịch mốc'), ('thermostat', '#2563eb', 'Thermostat')):
            tr = example[('demo_5_12_19', ctrl)]
            t0 = next(p['t'] for p in tr if p['hold'])
            xs = [(p['t'] - t0) / 60 for p in tr]
            axes[0].plot(xs, [p['T'] for p in tr], color=color, lw=1.4, label=label)
            axes[1].step(xs, [p['L'] for p in tr], color=color, lw=1.1, where='post', label=f'Bóng ({label})')
        tr = example[('demo_5_12_19', 'rl')]
        t0 = next(p['t'] for p in tr if p['hold'])
        for p, q in zip(tr, tr[1:]):
            if p['hold']:
                axes[0].axvspan((p['t'] - t0) / 60, (q['t'] - t0) / 60, ymin=0, ymax=1, color='none')
                axes[0].fill_between([(p['t'] - t0) / 60, (q['t'] - t0) / 60], p['lo'], p['hi'], color='#16a34a', alpha=0.15, lw=0)
        for x, txt in ((0, 'Ngày 5 · 37,8 °C'), (10, 'Ngày 12 · 37,5 °C'), (20, 'Ngày 19 · 37,2 °C')):
            axes[0].axvline(x, color='#57534e', lw=0.8, ls='--')
            axes[0].text(x + 0.3, 38.15, txt, fontsize=9, color='#44403c')
        axes[0].set_ylim(36.6, 38.3)
        axes[0].set_xlim(-6, 30)
        axes[0].set_ylabel('°C')
        axes[0].legend(loc='lower left', fontsize=9)
        axes[0].set_title('MÔ PHỎNG: đổi ngày ấp khi đang chạy (dải xanh = vùng mục tiêu theo giai đoạn)', fontsize=11)
        axes[1].set_ylabel('% bóng')
        axes[1].set_xlabel('Phút kể từ lúc giao cho bộ điều khiển (âm = làm ấm)')
        axes[1].legend(loc='upper right', fontsize=8)
        fig.tight_layout()
        fig.savefig(args.out / 'DOI_NGAY_MO_PHONG.png', dpi=130)
    except ImportError:
        pass
    print((args.out / 'KET_QUA.md').read_text(encoding='utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
