#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Short empty-box comparison: fan 0% vs 75%, heater at most 50% for at most 30s.

python3 thu_quat_lam_am.py do --quat 75 --dry-run
python3 thu_quat_lam_am.py do --quat 75
python3 thu_quat_lam_am.py do --quat 0
python3 thu_quat_lam_am.py so-sanh --lan1 FILE75.csv --lan2 FILE0.csv --out NEW_FOLDER
"""
import argparse
import csv
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import sys

import do_nhiet_hop as core
import phan_tich_reward as study


class WarmFanTrial:
    def __init__(self,fan,heat_seconds=30,lamp=50,reference=None):
        if fan not in (0,75):
            raise ValueError('Chỉ thử quạt 0% hoặc 75%.')
        core.finite_range(heat_seconds,15,30,'Thời gian sưởi thử')
        core.finite_range(lamp,1,50,'Bóng thử')
        if fan==0 and reference is None:
            raise ValueError('Cần chạy lượt quạt 75% làm mốc nhiệt trước khi thử quạt 0%.')
        if reference is not None and (reference['lamp_pct']!=lamp or reference['requested_heat_s']!=heat_seconds):
            raise ValueError('Mức bóng/thời gian phải giống lượt 75% đã làm mốc.')
        self.reference=reference
        self.fan,self.seconds,self.lamp=fan,heat_seconds,lamp
        self.started=self.heat_started=self.mix_started=None
        self.initial_temperature=self.heat_initial_temperature=None
        self.actual_heat_s=None
        self.shortened=False;self.completed=False
        self.baseline_points=[]
        self.baseline_slope=None;self.baseline_span=None;self.baseline_stable=False

    def bind_sensor(self,sensor_id):
        if self.reference is not None and self.reference['sensors']!=[sensor_id]:
            raise ValueError('Cần dùng đúng đầu dò của lượt làm mốc nhiệt.')

    def __call__(self,now,reading):
        t=reading.temperature
        if t is None or not math.isfinite(t):
            raise core.SensorError('Thử quạt cần số đo hợp lệ.')
        if self.started is None:
            if t>30:
                raise RuntimeError('Để hộp nguội gần điều kiện đầu của lượt đối chứng; yêu cầu ban đầu ≤30°C.')
            self.started=now;self.initial_temperature=t
        if self.heat_started is None:
            if not self.baseline_points or reading.at>self.baseline_points[-1][0]:
                self.baseline_points.append((reading.at,t))
        if now-self.started<20:
            return core.AutoDecision('nen_truoc_thu',0,75,'Cả hai lượt cùng trộn khí 75% trong 20s, bóng tắt.')
        if now-self.started<23:
            return core.AutoDecision('chuan_bi_muc_quat_thu',0,self.fan,'Bóng tắt thêm 3s để quạt về mức thử.')
        if self.heat_started is None:
            if t>30:
                raise RuntimeError('Nhiệt trước khi bật bóng trên 30°C; dừng phép so sánh.')
            tail=[p for p in self.baseline_points if p[0]>=reading.at-15]
            self.baseline_slope=study.slope(tail)
            self.baseline_span=max(v for _,v in tail)-min(v for _,v in tail)
            self.baseline_stable=(len(tail)>=8 and self.baseline_slope is not None
                                  and abs(self.baseline_slope)<=.15 and self.baseline_span<=.2)
            if not self.baseline_stable:
                raise RuntimeError('Nhiệt nền còn trôi; chưa bật bóng. Để cả hộp nguội và ổn định rồi chạy lại.')
            if self.reference is not None:
                target=self.reference['heat_sample_temperature_c']
                if abs(t-target)>.1+1e-9:
                    raise RuntimeError(f'Nhiệt trước bật bóng {t:.3f}°C khác mốc {target:.3f}°C quá 0,10°C; chưa bật bóng.')
            self.heat_started=now;self.heat_initial_temperature=t
        if self.mix_started is None:
            if now-self.heat_started>=self.seconds or t>=33:
                self.actual_heat_s=now-self.heat_started
                self.shortened=t>=33 and self.actual_heat_s<self.seconds
                self.mix_started=now
            else:
                return core.AutoDecision('thu_lam_am',self.lamp,self.fan,
                    'Thử ngắn hộp rỗng; ngoại lệ quạt 0 chỉ có trong phiên này.',fan_off_trial=self.fan==0)
        if now-self.mix_started<60:
            fan=100 if now-self.mix_started<1 else 75
            return core.AutoDecision('tron_khi_sau_thu',0,fan,
                'Bóng tắt; cả hai lượt trộn 100% trong 1s rồi 75% đến hết 60s.')
        self.completed=True
        return None

    def metadata(self):
        return dict(kind='BOUNDED_WARMUP_FAN_0_VS_75',fan_trial_pct=self.fan,lamp_pct=self.lamp,
            requested_heat_s=self.seconds,baseline_s=20,baseline_fan_pct=75,
            fan_settling_before_heat_s=3,mixing_s=60,mixing_initial_fan100_s=1,
            initial_temperature_c=self.initial_temperature,heat_initial_temperature_c=self.heat_initial_temperature,
            actual_heat_s=self.actual_heat_s,shortened_at_33c=self.shortened,
            completed=self.completed,soft_stop_heating_c=33,hard_stop_c=35,
            max_fan_off_heating_s=30,max_lamp_pct=50,
            baseline_stable=self.baseline_stable,baseline_slope_c_per_min=self.baseline_slope,
            baseline_temperature_span_c=self.baseline_span,
            reference_heat_temperature_c=self.reference['heat_sample_temperature_c'] if self.reference else None,
            reference_source_sha256=self.reference['source_sha256'] if self.reference else None,
            max_start_difference_c=.1,
            evidence='Empty-box transient at one probe; not full warmup, spatial uniformity or incubation validation')


def summarize(log):
    config=json.loads((log.parent/'cau_hinh.json').read_text(encoding='utf-8'))
    profile=config['profile']
    if profile.get('kind')!='BOUNDED_WARMUP_FAN_0_VS_75':
        raise ValueError('Không phải log phép thử quạt 0/75 ngắn.')
    session=study.read_log(log)
    with log.open(encoding='utf-8-sig',newline='') as stream:raw=list(csv.DictReader(stream))
    heat=[r for r in raw if r['event']=='COMMAND' and r['phase']=='thu_lam_am']
    mix=[r for r in raw if r['event']=='COMMAND' and r['phase']=='tron_khi_sau_thu']
    if not heat:
        raise ValueError('Chưa có giai đoạn bật bóng; giữ CSV để kiểm tra lỗi khởi tạo/nhiệt ban đầu.')
    start=float(heat[0]['elapsed_s'])
    stops=[float(r['elapsed_s']) for r in raw if r['event'] in ('ERROR','STOP') and float(r['elapsed_s'])>=start]
    end=float(mix[0]['elapsed_s']) if mix else min(stops) if stops else float(raw[-1]['elapsed_s'])
    samples=session['samples'];times=[r['t'] for r in samples]
    if not times or start<times[0] or end>times[-1]:
        raise ValueError('Thiếu số đo bao phủ giai đoạn sưởi; không ngoại suy nhiệt qua phần lỗi/mất cảm biến.')
    points=[(r['t'],r['temperature']) for r in samples if start<=r['t']<=end]
    if len(points)<3:
        raise ValueError('Quá ít mẫu nhiệt trong giai đoạn bật bóng.')
    initial=study.interpolate(samples,times,start)
    final=study.interpolate(samples,times,end)
    after=[r for r in samples if end<=r['t']<=end+60]
    h,f=study.mean_input(session['commands'],start,end)
    complete=(profile['completed'] and not session['issues'] and config.get('hardware_program_exit_code')==0)
    return dict(status='COMPLETED_SHORT_TRANSIENT' if complete else 'INCOMPLETE_SHORT_TRANSIENT',
        source=str(log),source_sha256=session['sha256'],fan_trial_pct=profile['fan_trial_pct'],
        lamp_pct=profile['lamp_pct'],requested_heat_s=profile['requested_heat_s'],actual_heat_s=end-start,
        initial_c=initial,end_heating_c=final,delta_c=final-initial,
        slope_c_per_min=study.slope(points),slope_after_first_5s_c_per_min=study.slope([(t,v) for t,v in points if t>=start+5]),
        peak_after_mixing_c=max((r['temperature'] for r in after),default=None),
        extra_rise_after_mixing_c=max((r['temperature'] for r in after),default=final)-final,
        mean_applied_lamp_pct=100*h,mean_applied_fan_pct=100*f,
        shortened_at_33c=profile['shortened_at_33c'],sensors=session['sensors'],frequencies=session['frequencies'],
        issues=session['issues'],initial_before_baseline_c=profile['initial_temperature_c'],
        heat_sample_temperature_c=profile['heat_initial_temperature_c'],
        baseline_stable=profile.get('baseline_stable',False),
        reference_source_sha256=profile.get('reference_source_sha256'),
        limit='One-probe transient only; no spatial/bulk-mean temperature or time-to-37.5 claim')


def write_report(log,folder):
    r=summarize(log);folder.mkdir(parents=True,exist_ok=False)
    study.write_json(folder/'ket_qua.json',r)
    text=['# Thử ngắn quạt trong giai đoạn làm ấm','',f'Trạng thái: **{r["status"]}**.',
        f'Quạt {r["fan_trial_pct"]:g}%, bóng {r["lamp_pct"]:g}%, bật bóng thực {r["actual_heat_s"]:.2f}s.',
        f'Nhiệt tại đầu dò {r["initial_c"]:.3f} → {r["end_heating_c"]:.3f}°C; ΔT {r["delta_c"]:+.3f}°C.',
        f'Độ dốc toàn đoạn: {r["slope_c_per_min"]}°C/phút; bỏ 5s đầu: {r["slope_after_first_5s_c_per_min"]}°C/phút.',
        f'Đỉnh sau khi tắt bóng và trộn khí: {r["peak_after_mixing_c"]}°C.',
        '', 'Không dùng một đầu dò để kết luận độ đều nhiệt, điểm nóng gần bóng hoặc nhiệt trung bình toàn hộp.',
        'Không ngoại suy tuyến tính đoạn 30s thành thời gian làm ấm tới 37,5°C. Quạt tắt không được thêm vào Q-table từ phép đo ngắn này.']
    (folder/'KET_QUA.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return r


def load_reference(path):
    reference=json.loads(path.read_text(encoding='utf-8'))
    if reference.get('kind')!='MATCHED_TEMPERATURE_FAN_REFERENCE_V2' or reference.get('fan_trial_pct')!=75:
        raise ValueError('File mốc không phải lượt quạt 75% của giao thức cùng nhiệt độ.')
    source=Path(reference['source_csv'])
    r=summarize(source)
    if (r['source_sha256']!=reference['source_sha256'] or r['status']!='COMPLETED_SHORT_TRANSIENT'
            or r['shortened_at_33c'] or not r['baseline_stable'] or r['fan_trial_pct']!=75
            or abs(r['heat_sample_temperature_c']-reference['heat_sample_temperature_c'])>1e-9
            or r['lamp_pct']!=reference['lamp_pct'] or r['requested_heat_s']!=reference['requested_heat_s']
            or r['sensors']!=reference['sensors'] or r['frequencies']!=[100.]):
        raise ValueError('Log nguồn không khớp hoặc chưa đạt điều kiện tạo mốc nhiệt.')
    return reference


def save_reference(path,log,result):
    if (result['fan_trial_pct']!=75 or result['status']!='COMPLETED_SHORT_TRANSIENT'
            or result['shortened_at_33c'] or not result['baseline_stable']):
        raise ValueError('Lượt 75% chưa đủ điều kiện tạo mốc; giữ log và kiểm tra trước khi thử 0%.')
    reference=dict(kind='MATCHED_TEMPERATURE_FAN_REFERENCE_V2',fan_trial_pct=75,
        source_csv=str(log.resolve()),source_sha256=result['source_sha256'],
        heat_sample_temperature_c=result['heat_sample_temperature_c'],lamp_pct=result['lamp_pct'],
        requested_heat_s=result['requested_heat_s'],sensors=result['sensors'],frequencies=result['frequencies'])
    with path.open('x',encoding='utf-8') as stream:json.dump(reference,stream,ensure_ascii=False,indent=2)
    return reference


def compare(first,second,out):
    a,b=summarize(first),summarize(second)
    by_fan={r['fan_trial_pct']:r for r in (a,b)}
    if set(by_fan)!={0,75} or a['source_sha256']==b['source_sha256']:
        raise ValueError('Cần đúng hai lượt khác nhau: quạt 0% và 75%.')
    warnings=[]
    if any(r['status']!='COMPLETED_SHORT_TRANSIENT' or r['shortened_at_33c'] for r in (a,b)):
        warnings.append('Có lượt chưa hoàn tất hoặc bị rút ngắn; không so như hai thời lượng bằng nhau.')
    if a['lamp_pct']!=b['lamp_pct'] or abs(a['actual_heat_s']-b['actual_heat_s'])>.15:
        warnings.append('Mức bóng hoặc thời gian sưởi không tương đương.')
    initial_difference=abs(a['heat_sample_temperature_c']-b['heat_sample_temperature_c'])
    if initial_difference>.1+1e-9:
        warnings.append('Nhiệt ngay trước bật bóng lệch quá 0,10°C; chưa phải so sánh cùng mức nhiệt đầu.')
    if not a['baseline_stable'] or not b['baseline_stable']:
        warnings.append('Chưa xác nhận nhiệt nền ổn định ở cả hai lượt.')
    if by_fan[0]['reference_source_sha256']!=by_fan[75]['source_sha256']:
        warnings.append('Lượt 0% không liên kết mốc với chính lượt 75% đang so sánh.')
    if a['sensors']!=b['sensors'] or a['frequencies']!=b['frequencies']:
        warnings.append('Đã đổi đầu dò hoặc tần số PWM.')
    out.mkdir(parents=True,exist_ok=False)
    result=dict(status='SHORT_TRANSIENT_COMPARISON_ONLY',runs=by_fan,warnings=warnings,
        initial_temperature_difference_c=initial_difference,
        initial_conditions_within_0_1c=initial_difference<=.1+1e-9,
        comparison_conditions_accepted=not warnings,
        no_global_fan_off_permission=True,no_rl_policy_change=True)
    study.write_json(out/'so_sanh.json',result)
    rows=[dict(fan_pct=k,initial_c=r['initial_c'],delta_c=r['delta_c'],slope_c_per_min=r['slope_c_per_min'],
               mixed_peak_c=r['peak_after_mixing_c'],heat_s=r['actual_heat_s']) for k,r in sorted(by_fan.items())]
    study.write_csv(out/'so_sanh.csv',rows,list(rows[0]))
    lines=['# So sánh quạt 0% và 75% khi sưởi ngắn','',
        '| Quạt | Nhiệt đầu °C | ΔT °C | Dốc °C/phút | Đỉnh sau trộn °C |','|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["fan_pct"]} | {r["initial_c"]:.3f} | {r["delta_c"]:+.3f} | {r["slope_c_per_min"]} | {r["mixed_peak_c"]} |')
    lines+=['','## Điều kiện và giới hạn','']+[f'- {w}' for w in warnings]
    lines+=['- Bố trí, nắp, lỗ thông gió và nhiệt phòng cần tương đương. Một cặp thử chưa loại được ảnh hưởng thứ tự/nhiệt dư.',
        '- Nhiệt tăng tại một đầu dò khi quạt tắt không chứng minh nhiệt toàn hộp tăng nhanh hoặc đồng đều hơn.',
        '- Tăng nhiệt sau khi bật quạt trộn là dữ liệu cần xem xét về phân bố/lưu nhiệt, không tự xác định được nhiệt độ cực đại gần bóng.',
        '- Chưa thử toàn bộ giai đoạn làm ấm và không bổ sung action quạt 0% vào chính sách RL.']
    (out/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    live=sub.add_parser('do');live.add_argument('--quat',type=int,choices=(0,75),required=True)
    live.add_argument('--bong',type=float,default=50);live.add_argument('--giay',type=float,default=30)
    live.add_argument('--sensor');live.add_argument('--khong-oled',action='store_true')
    live.add_argument('--dry-run',action='store_true');live.add_argument('--out',type=Path)
    live.add_argument('--moc-so-sanh',type=Path,default=Path(__file__).with_name('moc_thu_quat_0_75.json'),
                      help='Lượt 75%% đầu tiên tạo file mốc mới; lượt 0%% phải khớp nhiệt và log nguồn của file này.')
    offline=sub.add_parser('so-sanh');offline.add_argument('--lan1',type=Path,required=True)
    offline.add_argument('--lan2',type=Path,required=True);offline.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.command=='so-sanh':
            compare(args.lan1,args.lan2,args.out)
            print(f'BÁO CÁO: {args.out / "KET_QUA.md"}');return 0
        if not args.moc_so_sanh.is_absolute():
            args.moc_so_sanh=Path(__file__).resolve().parent/args.moc_so_sanh
        reference=load_reference(args.moc_so_sanh) if args.moc_so_sanh.is_file() else None
        if args.quat==0 and reference is None and not args.dry_run:
            raise ValueError('Chưa có mốc nhiệt. Chạy quạt 75% hoàn tất trước; không bật bóng cho lượt 0%.')
        # A dry-run without a reference only describes the plan and never opens GPIO.
        if args.dry_run and args.quat==0 and reference is None:
            core.finite_range(args.giay,15,30,'Thời gian sưởi thử')
            core.finite_range(args.bong,1,50,'Bóng thử')
            policy=None
        else:
            policy=WarmFanTrial(args.quat,args.giay,args.bong,reference)
        if args.dry_run:
            print(f'KHÔNG GPIO: trộn nền 75% trong 20s, về mức thử 3s, bóng {args.bong:g}% / quạt {args.quat}% tối đa {args.giay:g}s, rồi tắt bóng và trộn khí 60s.')
            print('Ban đầu ≤30°C; ngừng sưởi sớm ở 33°C; ngắt cứng 35°C/mất số đo 3s. Ngoại lệ không áp dụng chế độ cũ.')
            if reference:
                print(f'Mốc trước bật bóng: {reference["heat_sample_temperature_c"]:.3f}°C; chênh tối đa 0,10°C và nền phải ổn định.')
            else:
                print('Chưa có mốc: lượt 75% hợp lệ sẽ tạo mốc; lượt 0% thật từ chối chạy khi chưa có mốc.')
            return 0
        folder=args.out or Path(__file__).resolve().parent/'ket_qua_thu_quat'/(
            datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+f'_quat{args.quat}')
        folder.mkdir(parents=True,exist_ok=False)
        config={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
        config['profile']=policy.metadata()
        cfg=folder/'cau_hinh.json';study.write_json(cfg,config)
        command=['giu','--bong','0','--quat','0','--giay',str(20+3+args.giay+60+2),
            '--ngat-nhiet','35','--tan-so-quat','100','--csv',str(folder/'du_lieu.csv')]
        if args.sensor:command+=['--sensor',args.sensor]
        if args.khong_oled:command.append('--khong-oled')
        print(f'KẾT QUẢ: {folder}\nHỘP RỖNG, THEO DÕI TRỰC TIẾP; bóng gắn chắc, tách khỏi xốp. Ctrl+C để dừng.',flush=True)
        code=core.main(command,control_policy=policy,fan_off_trial_limits=core.FanOffTrialLimits())
        config.update(profile=policy.metadata(),hardware_program_exit_code=code)
        study.write_json(cfg,config)
        report_ok=False
        if (folder/'du_lieu.csv').is_file():
            try:
                result=write_report(folder/'du_lieu.csv',folder/'phan_tich')
                print(f'{result["status"]}\nBÁO CÁO: {folder / "phan_tich/KET_QUA.md"}')
                if args.quat==75 and reference is None:
                    created=save_reference(args.moc_so_sanh,folder/'du_lieu.csv',result)
                    print(f'MỐC CẶP THỬ: {created["heat_sample_temperature_c"]:.3f}°C; {args.moc_so_sanh}')
                report_ok=True
            except ValueError as exc:print(f'Chưa đủ dữ liệu thử: {exc}')
        return code or (0 if policy.completed and report_ok else 1)
    except (ValueError,OSError,KeyError) as exc:p.exit(1,f'Lỗi: {exc}\n')


if __name__=='__main__':raise SystemExit(main())
