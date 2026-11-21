#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate a frozen model/policy on a new hold log; never fits Q or opens GPIO."""
import argparse
from dataclasses import asdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

import phan_tich_reward as study
import kiem_tra_giu_nhiet as hold
import toi_uu_rl_offline as rl


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_digest(policy):
    return hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def evaluate(log,candidate,folder,unchanged_layout=False,pilot_path=None):
    bundle=json.loads(candidate.read_text(encoding='utf-8'))
    # Fixed first original training seed; never select a seed by this new log or stress result.
    selected=next(p for p in bundle['policies'] if p['seed']==11)
    if bundle.get('status')!='SIMULATION_ONLY_NOT_HARDWARE_VALIDATED':
        raise ValueError('Cần ứng viên mô phỏng đã chốt, không nhận policy tùy ý.')
    model=study.ThermalModel(**bundle['model'])
    session=study.read_log(log)
    summary=hold.summarize(log)
    cfg=json.loads((log.parent/'cau_hinh.json').read_text(encoding='utf-8'))
    with log.open(encoding='utf-8-sig',newline='') as stream:
        raw=list(csv.DictReader(stream))
    start=min(float(r['elapsed_s']) for r in raw if r['event']=='COMMAND' and r['phase'].startswith('kiem_tra'))
    end=min(float(r['elapsed_s']) for r in raw if r['event']=='STOP' and float(r['elapsed_s'])>=start)
    rows=[r for r in study.transitions(session,model.tau) if r['t']>=start and r['t']+study.DT<=end]
    if len(rows)<60:
        raise ValueError('Chưa đủ dữ liệu để kiểm tra mô hình giữ nhiệt.')
    in_domain=all(model.low<=r[k]<=model.high for r in rows for k in ('temperature','next_temperature'))
    metrics=study.model_metrics(model,[rows])
    first=rows[0]
    t,d,m=first['temperature'],first['previous_delta'],first['memory_before']
    open_errors,residuals,predictions=[],[],[]
    for r in rows:
        one=model.step(r['temperature'],r['previous_delta'],r['memory_before'],r['h'],r['f'])[0]
        residuals.append(r['next_temperature']-one)
        t,d,m=model.step(t,d,m,r['h'],r['f'])
        open_errors.append(t-r['next_temperature'])
        predictions.append(dict(hold_seconds=r['t']+5-start,measured_c=r['next_temperature'],
                                one_step_prediction_c=one,open_loop_prediction_c=t,
                                mean_lamp_pct=100*r['h'],mean_fan_pct=100*r['f']))
    actions=bundle['protocol']['actions']
    shadows=[]
    for policy in bundle['policies']:
        missed=0;states=set();suggestions={}
        for r in rows:
            s=rl.state(r['temperature'],r['previous_delta'],r['memory_before'],False,37.5,.5,max(h for h,f in actions))
            states.add(s)
            seen=[i for i,n in enumerate(policy['visits'][s]) if n]
            if not seen:
                missed+=1
            else:
                index=max(seen,key=lambda i:policy['q'][s][i])
                label=f'{100*actions[index][0]:g}/{100*actions[index][1]:g}'
                suggestions[label]=suggestions.get(label,0)+1
        shadows.append(dict(seed=policy['seed'],unknown_states_steps=missed,unique_states=len(states),
                            action_suggestions_counts=suggestions))
    # New-log residual block resampling is a sensitivity experiment, not a new hardware trajectory.
    rng=random.Random(17110846)
    cases=[]
    for _ in range(64):
        initial=rng.choice(rows);noise=[]
        while len(noise)<rl.HORIZON:
            k=rng.randrange(len(residuals)-5)
            noise.extend(residuals[k:k+6])
        cases.append(dict(initial=initial,noise=noise[:rl.HORIZON]))
    baseline=rl.evaluate(model,actions,cases,37.5,.5,baseline=bundle['selection']['baseline'])
    stress=[dict(seed=p['seed'],metrics=rl.evaluate(model,actions,cases,37.5,.5,q=p['q'],visits=p['visits']))
            for p in bundle['policies']]
    stress_mean=rl.aggregate([p['metrics'] for p in stress])
    source=bundle['protocol']['sources'][0]
    source_path=Path(source['path'])
    if not source_path.is_absolute():
        source_path=Path(__file__).resolve().parent.parent/source_path
    original=study.read_log(source_path)
    source_matches=digest(source_path)==source['sha256']
    sensor_matches=session['sensors']==original['sensors']
    frequency_matches=session['frequencies']==original['frequencies']==[100.]
    matched_reference=(cfg.get('bo_dieu_khien')=='doi-chung'
        and cfg.get('reference',{}).get('configuration')==bundle['selection']['baseline']
        and cfg.get('reference',{}).get('actions')==actions)
    short_pass=(in_domain and metrics['rollout_30s_rmse_c'] is not None
                and metrics['rollout_30s_rmse_c']<=.3
                and metrics['rollout_30s_rmse_c']<.95*metrics['persistence_30s_rmse_c'])
    selected_shadow=next(s for s in shadows if s['seed']==11)
    allowed=(summary['status']=='COMPLETED_HARDWARE_HOLD_TEST' and not session['issues']
             and source_matches and sensor_matches and frequency_matches and matched_reference and unchanged_layout
             and digest(log)!=source['sha256'] and short_pass and stress_mean['eligible']
             and selected_shadow['unknown_states_steps']==0)
    result=dict(status='PASS_SHORT_HORIZON_ONLY' if short_pass else 'MODEL_REQUIRES_REVIEW',
        evidence='NEW_MEASURED_THERMOSTAT_LOG; no measured RL trajectory',summary=summary,
        hold_start_s=start,hold_end_s=end,model_rows=len(rows),frozen_model=asdict(model),
        model_short_horizon=metrics,hold_inside_model_domain=in_domain,
        open_loop=dict(rmse_c=math.sqrt(statistics.mean(e*e for e in open_errors)),
                       bias_c=statistics.mean(open_errors),max_abs_c=max(map(abs,open_errors))),
        residuals=dict(mean_c_per_5s=statistics.mean(residuals),std_c_per_5s=statistics.pstdev(residuals)),
        source_hash_verified=source_matches,same_sensor=sensor_matches,same_frequency=frequency_matches,
        matched_frozen_reference=matched_reference,
        user_confirmed_same_layout_empty_box=unchanged_layout,shadow=shadows,
        sensitivity_simulation=dict(method='64 cases; residual blocks of 6 x 5s; seed 17110846',
            limitation='Residuals depend on this controller/conditions; not a policy-invariant plant or hardware RL test',
            baseline=baseline,rl_by_seed=stress,rl_mean=stress_mean),
        supervised_pilot_allowed=bool(allowed),automatic_deploy_allowed=False,
        candidate_sha256=digest(candidate),new_log_sha256=digest(log))
    folder.mkdir(parents=True,exist_ok=False)
    study.write_json(folder/'danh_gia.json',result)
    study.write_csv(folder/'doi_chieu_du_bao.csv',predictions,list(predictions[0]))
    lines=['# Đánh giá lượt giữ nhiệt độc lập ngày 17/11/2026','',
        'Thermostat đã hoàn tất 10 phút trên hộp thật. Các phép kiểm tra mô hình/policy bên dưới hoàn toàn offline; giữ nguyên Q-table.',
        '', '| Chỉ số đo thực | Kết quả |','|---|---:|',
        f'| MAE so với 37,5°C | {summary["mae_c"]:.3f}°C |',
        f'| Trong vùng 37–38°C | {summary["in_band_pct"]:.1f}% |',
        f'| Nhiệt nhỏ nhất / lớn nhất | {summary["min_c"]:.3f} / {summary["max_c"]:.3f}°C |',
        f'| Thời gian được đánh giá | {summary["covered_s"]:.1f}s |',
        f'| Bảo vệ mềm | {summary["soft_guard_count"]} lần |',
        '', '## Mô hình đóng băng có còn phù hợp?', '',
        f'- RMSE dự báo 5 giây: {metrics["one_step_rmse_c"]:.3f}°C.',
        f'- RMSE các đường dự báo 30 giây: {metrics["rollout_30s_rmse_c"]:.3f}°C; giữ nguyên nhiệt hiện tại: {metrics["persistence_30s_rmse_c"]:.3f}°C.',
        f'- Khi phát lại gần 10 phút bằng lệnh đã ghi, không đặt lại nhiệt theo số đo: RMSE {result["open_loop"]["rmse_c"]:.3f}°C, lệch trung bình {result["open_loop"]["bias_c"]:+.3f}°C.',
        '- Mô hình qua điều kiện kiểm tra ngắn hạn không chứng minh mọi chuỗi action hoặc mô phỏng 10 phút đều chính xác.',
        f'- Nhiệt ban đầu {cfg["profile"]["initial_temperature_c"]:.3f}°C. Không dùng đoạn khởi động lạnh ngoài miền nhận dạng để tuyên bố mô hình đã được kiểm tra; các chỉ số mô hình ở đây chỉ dùng giai đoạn giữ nhiệt trong miền.',
        '', '## Kiểm tra policy và độ nhạy', '',
        f'- Cùng đầu dò/tần số: {sensor_matches}/{frequency_matches}; xác nhận hộp rỗng, bố trí không đổi: {unchanged_layout}.',
        f'- Shadow trên log thật: số bước gặp state chưa học theo từng seed là {[(s["seed"],s["unknown_states_steps"]) for s in shadows]}. Các khuyến nghị này chưa tạo ra nhiệt đo mới.',
        f'- Stress mô phỏng dùng phần dư của lượt mới: thermostat MAE {baseline["mae_c"]:.3f}°C; RL trung bình ba seed {stress_mean["mae_c"]:.3f}°C.',
        '- Phần dư được lấy lại theo block 30 giây để giữ tương quan ngắn hạn. Không coi phép này là chứng minh hiệu năng RL trên hộp thật.',
        '', '## Bước thử tiếp theo', '',
        f'Cho phép chuẩn bị pilot hộp rỗng có giám sát: **{allowed}**. Triển khai tự động: **False**.',
        'Seed pilot cố định là 11, seed đầu tiên của ứng viên ban đầu; không chọn seed đẹp nhất theo lượt mới hoặc stress test.',
        'Giữ nguyên Q-table, chỉ suy luận; bảo vệ mềm 38→37°C, dừng cứng 40°C/mất số đo 3 giây. State ngoài miền/chưa học thì dừng pilot.',
        'Thermostat đã đạt 100% trong vùng ±0,5°C ở lượt này. RL cần chứng minh lợi ích ở sai số, độ dao động hoặc mức hoạt động; không thể tăng tỷ lệ này lên trên 100%. Chưa đo Wh nên không tuyên bố tiết kiệm điện.',
        '', 'Lượt RL sắp chạy mới cung cấp phép so thực nghiệm. Hai lượt liên tiếp vẫn chịu ảnh hưởng nhiệt phòng và điều kiện đầu; cần lặp/đổi thứ tự nếu muốn kết luận chắc.',
        '', f'Log mới SHA-256: `{digest(log)}`. Không gộp lượt kiểm tra vào train hoặc chọn lại reward trong bước này.']
    (folder/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if pilot_path is not None:
        if not allowed:
            raise ValueError('Không qua điều kiện pilot; đã lưu báo cáo, không xuất gói chạy.')
        package=dict(purpose='SUPERVISED_EMPTY_BOX_PILOT_ONLY',version=1,
            supervised_pilot_allowed=True,automatic_deploy_allowed=False,
            original_candidate_deploy_allowed=bundle.get('deploy_allowed'),target_c=37.5,band_c=.5,
            state_encoder='9e_3d_3m_guard_v2',state_count=162,dt_s=5,fan_pwm_hz=100,
            sensor_id=session['sensors'][0],model=asdict(model),actions=actions,policy=selected,
            policy_sha256=policy_digest(selected),max_initial_temperature_c=30,
            independent_validation=dict(status=result['status'],log_sha256=digest(log),
                candidate_sha256=digest(candidate),report_sha256=digest(folder/'danh_gia.json'),
                note='Short-horizon validation only; limited supervised experiment, not automatic deployment'))
        with pilot_path.open('x',encoding='utf-8') as stream:
            json.dump(package,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return result


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log',type=Path,required=True);p.add_argument('--ung-vien',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--bo-tri-khong-doi',action='store_true')
    p.add_argument('--xuat-goi-thu',type=Path)
    a=p.parse_args()
    try:r=evaluate(a.log,a.ung_vien,a.out,a.bo_tri_khong_doi,a.xuat_goi_thu)
    except (OSError,ValueError,KeyError,StopIteration) as exc:p.exit(1,f'Lỗi: {exc}\n')
    print(f'{r["status"]}; supervised_pilot_allowed={r["supervised_pilot_allowed"]}; automatic_deploy_allowed=false')
    return 0


if __name__=='__main__':raise SystemExit(main())
