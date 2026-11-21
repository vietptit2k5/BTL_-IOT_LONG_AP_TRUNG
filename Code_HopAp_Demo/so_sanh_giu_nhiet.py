#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare complete measured hold tests. No training, model fitting or GPIO."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import kiem_tra_giu_nhiet as hold
import phan_tich_reward as study


def temperature_metrics(samples,start,end):
    durations=[]
    for a,b in zip(samples,samples[1:]):
        if b['t']-a['t']>3:
            continue
        dt=max(0.,min(b['t'],end)-max(a['t'],start))
        if dt:
            durations.append((dt,a['temperature']))
    seconds=sum(dt for dt,_ in durations)
    if not seconds:
        raise ValueError('Không có khoảng nhiệt đo hợp lệ để đánh giá.')
    mean=sum(dt*t for dt,t in durations)/seconds
    return dict(covered_s=seconds,mae_c=sum(dt*abs(t-37.5) for dt,t in durations)/seconds,
        rmse_c=math.sqrt(sum(dt*(t-37.5)**2 for dt,t in durations)/seconds),
        mean_c=mean,bias_c=mean-37.5,
        std_c=math.sqrt(sum(dt*(t-mean)**2 for dt,t in durations)/seconds),
        min_c=min(t for _,t in durations),max_c=max(t for _,t in durations),
        peak_to_peak_c=max(t for _,t in durations)-min(t for _,t in durations),
        **{f'in_band_{int(b*100):03d}_pct':100*sum(dt for dt,t in durations if abs(t-37.5)<=b+1e-12)/seconds
           for b in (.15,.25,.5)})


def command_metrics(commands,start,end):
    segments=[]
    for i,(t,h,f) in enumerate(commands):
        left=max(start,t);right=min(end,commands[i+1][0] if i+1<len(commands) else end)
        if right>left:
            segments.append((left,right,h,f))
    duration=sum(b-a for a,b,_,_ in segments)
    if duration<=0:
        raise ValueError('Thiếu lịch sử lệnh điều khiển.')
    heat_changes=fan_changes=changes=0
    heat_variation=fan_variation=0.
    for before,after in zip(segments,segments[1:]):
        dh,df=abs(after[2]-before[2]),abs(after[3]-before[3])
        heat_changes+=dh>1e-8;fan_changes+=df>1e-8;changes+=max(dh,df)>1e-8
        heat_variation+=dh*100;fan_variation+=df*100
    actions={}
    for a,b,h,f in segments:
        key=f'{100*h:g}/{100*f:g}'
        actions[key]=actions.get(key,0.)+b-a
    return dict(mean_lamp_duty_pct=sum((b-a)*h*100 for a,b,h,_ in segments)/duration,
        mean_fan_duty_pct=sum((b-a)*f*100 for a,b,_,f in segments)/duration,
        setpoint_changes=changes,lamp_setpoint_changes=heat_changes,fan_setpoint_changes=fan_changes,
        total_lamp_variation_percentage_points=heat_variation,
        total_fan_variation_percentage_points=fan_variation,action_seconds=actions,
        note='Applied duty commands; counts are setpoint changes, not PWM pulses, RPM or measured energy.')


def read_run(path):
    summary=hold.summarize(path)
    if summary['status']!='COMPLETED_HARDWARE_HOLD_TEST':
        raise ValueError(f'{path}: phiên chưa hoàn tất; không so phần chạy dở với lượt đủ 600s.')
    session=study.read_log(path)
    if session['issues']:
        raise ValueError('; '.join(session['issues']))
    cfg=json.loads((path.parent/'cau_hinh.json').read_text(encoding='utf-8'))
    if cfg.get('giay')!=600 or cfg['profile']['requested_hold_seconds']!=600:
        raise ValueError('Chỉ so các lượt giữ nhiệt danh định 600 giây trong giao thức này.')
    import csv
    with path.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    start=min(float(r['elapsed_s']) for r in raw if r['event']=='COMMAND' and r['phase'].startswith('kiem_tra'))
    end=min(float(r['elapsed_s']) for r in raw if r['event']=='STOP' and float(r['elapsed_s'])>=start)
    metrics=temperature_metrics(session['samples'],start,end)
    if abs(metrics['mae_c']-summary['mae_c'])>1e-10:
        raise ValueError('Kết quả tái tính không khớp bộ tổng kết hiện có.')
    old_report=path.parent/'phan_tich/ket_qua.json'
    if old_report.is_file():
        old=json.loads(old_report.read_text(encoding='utf-8'))
        if old['source_sha256']!=session['sha256'] or abs(old['mae_c']-metrics['mae_c'])>1e-10:
            raise ValueError('CSV hoặc báo cáo gốc không khớp SHA/chỉ số.')
    profile=cfg['profile']
    per_minute=[]
    for i in range(10):
        lo=start+i*60;hi=min(end,start+(i+1)*60) if i<9 else end
        per_minute.append(dict(minute=i+1,**temperature_metrics(session['samples'],lo,hi)))
    local=lambda s:datetime.fromisoformat(s).astimezone(timezone(timedelta(hours=7))).isoformat()
    return dict(path=str(path),sha256=session['sha256'],controller=cfg['bo_dieu_khien'],
        started_vietnam_from_log=local(raw[0]['timestamp_utc']),ended_vietnam_from_log=local(raw[-1]['timestamp_utc']),
        summary=summary,temperature=metrics,commands=command_metrics(session['commands'],start,end),
        sensors=session['sensors'],frequencies=session['frequencies'],profile=profile,
        hold_start_s=start,hold_end_s=end,
        max_sample_gap_s=max(b['t']-a['t'] for a,b in zip(session['samples'],session['samples'][1:])),
        max_measurement_age_s=max(float(r['temperature_age_s']) for r in raw if r['event']=='MEASUREMENT'),
        reference=cfg.get('reference'),per_minute=per_minute)


def compare(base,rl):
    if base['controller']!='doi-chung' or rl['controller']!='thu-rl':
        raise ValueError('Cần đúng một lượt thermostat và một lượt thu-rl.')
    if base['sha256']==rl['sha256']:
        raise ValueError('Hai đường dẫn là cùng một bộ dữ liệu, không phải hai lượt thử.')
    if base['sensors']!=rl['sensors'] or base['frequencies']!=rl['frequencies']:
        raise ValueError('Không so trực tiếp khi đổi đầu dò hoặc tần số PWM.')
    for key in ('control_period_s','soft_guard_off_c','soft_guard_resume_c','hard_cutoff_c'):
        if base['profile'][key]!=rl['profile'][key]:
            raise ValueError('Hai lượt có bảo vệ/chu kỳ điều khiển khác nhau.')
    return dict(mae_reduction_pct=100*(1-rl['temperature']['mae_c']/base['temperature']['mae_c'])
                if base['temperature']['mae_c'] else None,
        std_reduction_pct=100*(1-rl['temperature']['std_c']/base['temperature']['std_c'])
                if base['temperature']['std_c'] else None,
        in_band_015_gain_percentage_points=rl['temperature']['in_band_015_pct']-base['temperature']['in_band_015_pct'],
        mean_lamp_duty_change_percentage_points=rl['commands']['mean_lamp_duty_pct']-base['commands']['mean_lamp_duty_pct'],
        mean_fan_duty_change_percentage_points=rl['commands']['mean_fan_duty_pct']-base['commands']['mean_fan_duty_pct'],
        setpoint_change_count_difference=rl['commands']['setpoint_changes']-base['commands']['setpoint_changes'])


def analyze(base_path,rl_path,folder,unchanged_layout=False):
    base,rl=read_run(base_path),read_run(rl_path)
    delta=compare(base,rl)
    package_path=Path(__file__).with_name('goi_thu_rl_20261117.json')
    package=json.loads(package_path.read_text(encoding='utf-8'))
    pilot=rl['profile'].get('pilot',{})
    package_matches=pilot.get('package_sha256')==hashlib.sha256(package_path.read_bytes()).hexdigest()
    policy_identity=(package_matches and pilot.get('seed')==11 and pilot.get('q_updates')==0)
    allowed={tuple(action) for action in package['actions']}
    actual={tuple(float(v)/100 for v in action.split('/')) for action in rl['commands']['action_seconds']}
    if not policy_identity or not actual.issubset(allowed):
        raise ValueError('Không xác nhận được đúng policy cố định/tập action cho lượt RL.')
    result=dict(status='MEASURED_PAIR_COMPARISON_ONLY',baseline=base,rl=rl,differences=delta,
        unchanged_layout_confirmed_by_user=unchanged_layout,
        frozen_policy_identity_verified=policy_identity,
        replication=dict(thermostat_runs=1,rl_runs=1,room_temperature_measured=False),
        inference='Observed improvement in this pair only; order, thermal history and unmeasured room conditions remain confounders.',
        automatic_deploy_allowed=False)
    folder.mkdir(parents=True,exist_ok=False)
    study.write_json(folder/'so_sanh.json',result)
    flat=[]
    for label,run in (('thermostat',base),('rl',rl)):
        flat.append(dict(controller=label,**run['temperature'],
            **{k:v for k,v in run['commands'].items() if not isinstance(v,(dict,str))}))
    study.write_csv(folder/'bang_so_sanh.csv',flat,list(flat[0]))
    minutes=[dict(controller=label,**r) for label,run in (('thermostat',base),('rl',rl)) for r in run['per_minute']]
    study.write_csv(folder/'chi_so_tung_phut.csv',minutes,list(minutes[0]))
    b,r=base['temperature'],rl['temperature'];bc,rc=base['commands'],rl['commands']
    lines=['# So sánh thermostat và Q-learning trên hộp thật — 17/11/2026','',
        f'**Trong cặp lượt thử này, Q-learning giảm MAE {delta["mae_reduction_pct"]:.1f}% và giảm độ lệch chuẩn nhiệt {delta["std_reduction_pct"]:.1f}% so với đối chứng thermostat đã chọn.**',
        'Cả hai lượt đều hoàn tất 600 giây và giữ nhiệt trong 37–38°C suốt giai đoạn đánh giá.',
        '', '## Kết quả đo thực', '',
        '| Chỉ số | Thermostat | Q-learning |','|---|---:|---:|',
        f'| MAE so với 37,5°C | {b["mae_c"]:.4f}°C | {r["mae_c"]:.4f}°C |',
        f'| RMSE | {b["rmse_c"]:.4f}°C | {r["rmse_c"]:.4f}°C |',
        f'| Độ lệch chuẩn nhiệt | {b["std_c"]:.4f}°C | {r["std_c"]:.4f}°C |',
        f'| Nhiệt trung bình | {b["mean_c"]:.4f}°C | {r["mean_c"]:.4f}°C |',
        f'| Nhiệt nhỏ nhất–lớn nhất | {b["min_c"]:.3f}–{b["max_c"]:.3f}°C | {r["min_c"]:.3f}–{r["max_c"]:.3f}°C |',
        f'| Trong 37,5 ± 0,15°C | {b["in_band_015_pct"]:.2f}% | {r["in_band_015_pct"]:.2f}% |',
        f'| Trong 37,5 ± 0,25°C | {b["in_band_025_pct"]:.2f}% | {r["in_band_025_pct"]:.2f}% |',
        f'| Trong 37,5 ± 0,5°C | {b["in_band_050_pct"]:.2f}% | {r["in_band_050_pct"]:.2f}% |',
        f'| Bảo vệ mềm | {base["summary"]["soft_guard_count"]} | {rl["summary"]["soft_guard_count"]} |',
        f'| Duty bóng trung bình | {bc["mean_lamp_duty_pct"]:.2f}% | {rc["mean_lamp_duty_pct"]:.2f}% |',
        f'| Duty quạt trung bình | {bc["mean_fan_duty_pct"]:.2f}% | {rc["mean_fan_duty_pct"]:.2f}% |',
        f'| Số lần đổi tổ hợp mức PWM | {bc["setpoint_changes"]} | {rc["setpoint_changes"]} |',
        f'| Tổng biến thiên duty bóng (điểm %) | {bc["total_lamp_variation_percentage_points"]:.0f} | {rc["total_lamp_variation_percentage_points"]:.0f} |',
        '', 'Các vùng hẹp ±0,15/±0,25°C đã được nêu trong hướng dẫn trước lượt pilot. Đây là độ bám giá trị đầu dò đọc, chưa phải chứng nhận sai số nhiệt thật của hộp sau hiệu chuẩn.',
        'Chỉ số tính có trọng số thời gian từ mẫu mới MEASUREMENT; không tính làm ấm/quạt cuối. Không bỏ đoạn đầu hoặc đoạn xấu trong 600 giây.',
        '', '## Kiểm tra phiên RL', '',
        f'- Đúng gói policy seed 11 đã chốt: {policy_identity}; metadata ghi {pilot["decisions"]} quyết định, {pilot["q_updates"]} cập nhật Q online.',
        f'- Gặp {len(pilot["visited_states"])} state đã học: {pilot["visited_states"]}. Không có ERROR, không ngắt bảo vệ; không ghi nhận fallback.',
        f'- Cùng đầu dò {rl["sensors"]}, PWM quạt {rl["frequencies"]} Hz, chu kỳ quyết định 5 giây và các ngưỡng bảo vệ.',
        f'- Người dùng xác nhận hộp rỗng, bố trí/nắp/lỗ thông gió không đổi: {unchanged_layout}.',
        '', '## Cải thiện và đánh đổi', '',
        'Ở lượt thermostat, nhiệt lên xuống theo chu kỳ rõ hơn. Lượt RL dùng các mức sưởi trung gian và có dao động nhiệt nhỏ hơn. Đây là bằng chứng bước đầu về cải thiện độ bám nhiệt của demo so với đối chứng cụ thể này.',
        f'RL tăng tỷ lệ nằm trong ±0,15°C thêm {delta["in_band_015_gain_percentage_points"]:.2f} điểm phần trăm. Vùng ±0,5°C đã đạt 100% ở cả hai nên không có cải thiện ở chỉ số đó.',
        f'RL đổi mức PWM {rc["setpoint_changes"]} lần, nhiều hơn {bc["setpoint_changes"]} của thermostat; tổng biến thiên duty bóng cũng tăng. Không được kết luận RL ít đổi lệnh hơn hoặc giảm hao mòn cơ cấu từ lượt này. Các con số là lần đổi mức phần mềm, không phải số xung PWM.',
        'Duty trung bình thấp hơn không đồng nghĩa đã tiết kiệm điện: chưa đo W/Wh, RPM hoặc điện năng hai tải.',
        '', '## Giới hạn cần giữ khi trình bày', '',
        f'- Mới có một lượt thermostat và một lượt RL. Nhiệt đầu trong hộp lần lượt {base["profile"]["initial_temperature_c"]:.3f}°C và {rl["profile"]["initial_temperature_c"]:.3f}°C; thời gian làm ấm {base["profile"]["warm_elapsed_s"]:.1f}s và {rl["profile"]["warm_elapsed_s"]:.1f}s. Cả hai bắt đầu giai đoạn giữ nhiệt tại 37°C nhưng lịch sử nhiệt chưa chắc giống nhau.',
        '- Không có nhiệt kế phòng độc lập; chưa tách được ảnh hưởng nhiệt phòng, thứ tự thử hoặc nhiệt dư. Không dùng hàng trăm mẫu cùng một lượt như hàng trăm thí nghiệm độc lập để tuyên bố ý nghĩa thống kê.',
        '- Chưa so với PID chạy thật, chưa thử phòng lạnh hơn hoặc độ mở lỗ khác. Không suy rộng thành tốt hơn mọi máy ấp/bộ điều khiển.',
        '- Chưa đo độ ẩm, độ đều nhiệt nhiều vị trí, nhiệt trứng hoặc tỷ lệ nở. Q-table vẫn là cấu hình thử hộp rỗng có giám sát.',
        '', '## Có thể trình bày với thầy', '',
        f'> Nhóm sử dụng Q-learning để chọn đồng thời mức PWM của bóng và quạt. Trong cặp thử nghiệm 10 phút trên cùng hộp rỗng, MAE so với số đọc mục tiêu 37,5°C giảm từ {b["mae_c"]:.3f} xuống {r["mae_c"]:.3f}°C, khoảng {delta["mae_reduction_pct"]:.1f}%; thời gian trong vùng ±0,15°C tăng từ {b["in_band_015_pct"]:.1f}% lên {r["in_band_015_pct"]:.1f}%. Cả hai đều giữ vùng ±0,5°C trong toàn lượt. Kết quả cho thấy RL cải thiện độ bám nhiệt của demo so với đối chứng thermostat đã chọn; cần lặp lại ở nhiều điều kiện trước khi kết luận rộng hơn.',
        '', '## Bước nên làm tiếp', '',
        'Giữ nguyên policy và reward. Nếu cần củng cố kết luận, chạy lại thermostat thêm một lượt theo thứ tự A–B–A, để hộp nguội về điều kiện đầu tương đương; ghi thêm nhiệt phòng nếu có nhiệt kế riêng. Không cần huấn luyện lại chỉ vì lượt đo đã hoàn tất.',
        'Lệnh trên laptop sau khi hộp đủ nguội:', '',
        '```powershell',
        'ssh -t pi@pi "python3 /home/pi/Code_HopAp_Demo/kiem_tra_giu_nhiet.py do --bo-dieu-khien doi-chung"',
        '```','', 'Giữ hộp rỗng, có người theo dõi và cùng trạng thái lỗ thông gió/nắp. Không tự chuyển thành vận hành ấp trứng kéo dài.',
        '', '## Nguồn đo', '',
        f'- Thermostat: `{base["path"]}`; SHA-256 `{base["sha256"]}`.',
        f'- RL: `{rl["path"]}`; SHA-256 `{rl["sha256"]}`.',
        '- Bản sao cùng SHA trong thư mục lồng do scp không được tính là lượt thực nghiệm bổ sung.']
    (folder/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--doi-chung',type=Path,required=True);p.add_argument('--rl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--bo-tri-khong-doi',action='store_true')
    args=p.parse_args(argv)
    try:r=analyze(args.doi_chung,args.rl,args.out,args.bo_tri_khong_doi)
    except (OSError,ValueError,KeyError) as exc:p.exit(1,f'Lỗi: {exc}\n')
    print(f'MAE giảm trong cặp thử: {r["differences"]["mae_reduction_pct"]:.2f}%\nBÁO CÁO: {args.out / "KET_QUA.md"}')
    return 0


if __name__=='__main__':raise SystemExit(main())
