#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent empty-box temperature-hold test, with bounded warm-up and soft guard.

python3 kiem_tra_giu_nhiet.py do --dry-run
python3 kiem_tra_giu_nhiet.py do --bo-dieu-khien doi-chung
python3 kiem_tra_giu_nhiet.py do --bo-dieu-khien co-dinh --bong 50 --quat 75
python3 kiem_tra_giu_nhiet.py do --bo-dieu-khien co-dinh --bong 50 --quat 75 --bat-dau-giu 37.5
python3 kiem_tra_giu_nhiet.py do --bo-dieu-khien thu-rl --dry-run
python3 kiem_tra_giu_nhiet.py phan-tich --log FILE.csv
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import do_nhiet_hop as core
from chinh_sach_nhiet import SoftGuard,ReferenceController
from chinh_sach_rl import FrozenPilot,read_pilot


class WarmupTimeout(RuntimeError):
    pass


def read_reference(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('purpose')!='REFERENCE_CONTROLLER_ONLY':
        raise ValueError('Cần cấu hình đối chứng, không nhận file Q-table.')
    if data.get('target_c')!=37.5 or data.get('band_c')!=.5 or data.get('fan_pwm_hz')!=100:
        raise ValueError('Cấu hình kiểm tra này yêu cầu 37,5±0,5°C và PWM 100 Hz.')
    actions = [tuple(a) for a in data['actions']]
    if not actions or any(len(a)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in a)
                          or not 0<=a[0]<=1 or a[1] not in (.75,1.) for a in actions):
        raise ValueError('Tập action đối chứng không hợp lệ.')
    if (0.,1.) not in actions:
        raise ValueError('Thiếu action tắt sưởi / quạt 100%.')
    c = data['configuration']
    if c.get('kind') not in ('thermostat','pid') or c.get('fan_mode') not in ('low','high','trend'):
        raise ValueError('Loại đối chứng không hợp lệ.')
    if c['kind']=='thermostat':
        core.finite_range(c['band'],.05,1.,'Hysteresis đối chứng')
    else:
        for k in ('kp','ki','kd'):
            core.finite_range(c[k],0,10,k)
    return data,actions


class HoldPolicy:
    def __init__(self,mode='co-dinh',seconds=600,warm_timeout=600,lamp=50,fan=75,reference=None,pilot=None,hold_start_c=37.,warm_fan=100):
        core.finite_range(seconds,60,1200,'Thời gian kiểm tra')
        core.finite_range(warm_timeout,30,900,'Giới hạn làm ấm')
        core.finite_range(lamp,0,75,'Bóng cố định')
        if fan not in (75,100):
            raise ValueError('Chỉ dùng quạt 75% hoặc 100% đã khảo sát.')
        if warm_fan not in (75,100):
            raise ValueError('Quạt làm ấm chỉ dùng 75% hoặc 100% đã khảo sát.')
        if mode not in ('co-dinh','doi-chung','thu-rl'):
            raise ValueError('Không có chế độ này.')
        core.finite_range(hold_start_c,37,37.5,'Nhiệt bắt đầu giữ mức')
        if mode!='co-dinh' and hold_start_c!=37.:
            raise ValueError('--bat-dau-giu chỉ thay đổi ngưỡng bắt đầu của phép thử co-dinh; giữ nguyên giao thức RL/đối chứng.')
        if mode!='co-dinh' and warm_fan!=100:
            raise ValueError('--quat-lam-am 75 chỉ dùng cho phép thử co-dinh; giao thức RL/đối chứng cũ vẫn dùng 100%.')
        if mode=='thu-rl' and seconds!=600:
            raise ValueError('Pilot RL đầu tiên được cố định 600 giây.')
        self.mode,self.seconds,self.warm_timeout = mode,seconds,warm_timeout
        self.lamp,self.fan = lamp,fan
        self.hold_start_c=hold_start_c
        self.warm_fan=warm_fan
        self.guard = SoftGuard()
        self.started=self.hold_started=self.last_control=self.last_sample=None
        self.last_temperature=self.decision=None
        self.completed=False
        self.initial_temperature=self.hold_initial_temperature=None
        self.reference=reference
        self.pilot=FrozenPilot(pilot) if pilot else None
        self.controller = ReferenceController(reference['configuration'],37.5,reference['actions']) if reference else None
        if mode=='doi-chung' and self.controller is None:
            raise ValueError('Thiếu cấu hình đối chứng.')
        if mode=='thu-rl' and self.pilot is None:
            raise ValueError('Thiếu gói pilot đã kiểm tra độc lập.')

    def bind_sensor(self,sensor_id):
        if self.mode=='thu-rl':
            self.pilot.bind_sensor(sensor_id)

    def observe_output(self,now,lamp_pct,fan_pct):
        if self.mode=='thu-rl':
            self.pilot.observe_output(now,lamp_pct,fan_pct)

    def __call__(self,now,reading):
        temperature=reading.temperature
        if temperature is None or not math.isfinite(temperature):
            raise core.SensorError('Kiểm tra giữ nhiệt cần số đo hợp lệ.')
        if self.started is None:
            if self.mode=='thu-rl':
                self.pilot.check_initial(temperature)
            self.started=now
            self.initial_temperature=temperature
        was_guard=self.guard.active
        self.guard.update(temperature)
        if self.hold_started is None:
            if now-self.started>=self.warm_timeout:
                raise WarmupTimeout('Hết thời gian làm ấm mà chưa vào điều kiện bắt đầu kiểm tra.')
            if not self.guard.active and temperature>=self.hold_start_c:
                self.hold_started=now
                self.hold_initial_temperature=temperature
            else:
                if not self.guard.active and self.mode=='co-dinh' and self.hold_start_c>37 and temperature>=37:
                    return core.AutoDecision('lam_am_tiep_can_muc_co_dinh',self.lamp,self.fan,
                        'Tiếp cận mục tiêu bằng đúng mức cần kiểm tra; chưa tính thời gian giữ mức.')
                return core.AutoDecision('lam_am_bao_ve' if self.guard.active else 'lam_am_truoc_kiem_tra',
                                         0 if self.guard.active else 75,100 if self.guard.active else self.warm_fan,
                                         'Làm ấm có giới hạn; chưa tính vào thời gian giữ nhiệt.')
        if now-self.hold_started>=self.seconds:
            self.completed=True
            return None
        # The hold timer runs during protection: guarded time is not removed from the results.
        if self.guard.active:
            self.last_control=None
            return core.AutoDecision('kiem_tra_bao_ve',0,100,'Ngắt mềm 38°C, trở lại 37°C; vẫn tính thời gian kiểm tra.')
        if was_guard:
            self.last_control=None
        if self.last_control is None or now-self.last_control>=5:
            delta=(0. if self.last_sample is None or reading.at<=self.last_sample else
                   (temperature-self.last_temperature)*5/(reading.at-self.last_sample))
            if self.mode=='co-dinh':
                lamp,fan=self.lamp,self.fan
            elif self.mode=='thu-rl':
                index,state=self.pilot.select(temperature,delta)
                h,f=self.pilot.actions[index]
                lamp,fan=100*h,100*f
            else:
                index=self.controller.select(temperature,delta)
                h,f=self.reference['actions'][index]
                lamp,fan=100*h,100*f
            self.decision=core.AutoDecision('kiem_tra_giu_nhiet',lamp,fan,
                f'{self.mode}; cập nhật 5s; dT5={delta:+.4f}°C; duty lệnh, chưa đo W/RPM.')
            self.last_control,self.last_sample,self.last_temperature=now,reading.at,temperature
        return self.decision

    def metadata(self):
        return dict(completed=self.completed,soft_guard_count=self.guard.count,
            requested_hold_seconds=self.seconds,warm_timeout_s=self.warm_timeout,
            hold_start_threshold_c=self.hold_start_c,
            warm_fan_pct=self.warm_fan,
            initial_temperature_c=self.initial_temperature,hold_initial_temperature_c=self.hold_initial_temperature,
            warm_elapsed_s=(self.hold_started-self.started if self.hold_started is not None else None),
            control_period_s=5,soft_guard_off_c=38,soft_guard_resume_c=37,hard_cutoff_c=40,
            pilot=self.pilot.metadata() if self.mode=='thu-rl' else None,
            note='Guard intervals remain part of the hold test; supervised experiment only, no online learning.')


def summarize(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        raw=list(csv.DictReader(stream))
    starts=[float(r['elapsed_s']) for r in raw if r['event']=='COMMAND' and r['phase'].startswith('kiem_tra')]
    if not starts:
        raise ValueError('Chưa có giai đoạn kiểm tra giữ nhiệt trong CSV.')
    start=min(starts)
    stops=[float(r['elapsed_s']) for r in raw if r['event'] in ('STOP','ERROR') and float(r['elapsed_s'])>=start]
    stop=min(stops) if stops else max(float(r['elapsed_s']) for r in raw)
    samples=[]
    for r in raw:
        if r['event']!='MEASUREMENT' or not r['temperature_c']:
            continue
        age=float(r['temperature_age_s']);t=float(r['elapsed_s'])-age;v=float(r['temperature_c'])
        if math.isfinite(t) and math.isfinite(v) and 0<=age<3 and -55<=v<=125 and v!=85:
            if not samples or t>samples[-1][0]:
                samples.append((t,v))
    duration=error=in_band=above=below=0.
    used=[]
    for (t,v),(tn,_) in zip(samples,samples[1:]):
        if tn-t>3:
            continue
        dt=max(0.,min(tn,stop)-max(t,start))
        if not dt:
            continue
        used.append(v)
        duration+=dt
        error+=abs(v-37.5)*dt
        in_band+=dt*(37<=v<=38)
        above+=dt*(v>38)
        below+=dt*(v<37)
    if not duration:
        raise ValueError('Không đủ khoảng mẫu để tính chỉ số.')
    cfg_path=path.parent/'cau_hinh.json'
    cfg=json.loads(cfg_path.read_text(encoding='utf-8')) if cfg_path.is_file() else {}
    profile=cfg.get('profile',{})
    ended=any(r['event']=='END' for r in raw)
    errors=[r.get('note','') for r in raw if r['event']=='ERROR']
    complete=(ended and not errors and profile.get('completed') is True
              and cfg.get('hardware_program_exit_code')==0 and duration>=.98*profile.get('requested_hold_seconds',600))
    return dict(status='COMPLETED_HARDWARE_HOLD_TEST' if complete else 'INCOMPLETE_HOLD_TEST',
        source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        controller=cfg.get('bo_dieu_khien','unknown'),target_c=37.5,band_c=.5,
        hold_span_s=stop-start,covered_s=duration,coverage_pct=100*duration/(stop-start),
        mae_c=error/duration,in_band_pct=100*in_band/duration,
        above_band_s=above,below_band_s=below,min_c=min(used),max_c=max(used),
        soft_guard_count=profile.get('soft_guard_count'),errors=errors,
        note='Measured single-probe temperature; warm-up/post-cooling excluded; guard time included. No energy/RH/hatch claim.')


def write_summary(log,folder):
    result=summarize(log)
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'ket_qua.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'KET_QUA.md').write_text(
        '# Kiểm tra giữ nhiệt độc lập\n\n'
        f'Trạng thái: **{result["status"]}**. Bộ điều khiển: {result["controller"]}.\n\n'
        f'- Thời gian có số đo: {result["covered_s"]:.1f}s; độ phủ: {result["coverage_pct"]:.1f}%.\n'
        f'- MAE: {result["mae_c"]:.3f}°C; trong 37–38°C: {result["in_band_pct"]:.1f}%.\n'
        f'- Nhiệt đo: {result["min_c"]:.3f}–{result["max_c"]:.3f}°C.\n'
        f'- Thời gian trên 38°C: {result["above_band_s"]:.1f}s; dưới 37°C: {result["below_band_s"]:.1f}s.\n'
        f'- Số lần bảo vệ mềm cả phiên: {result["soft_guard_count"]}.\n\n'
        'Không tính giai đoạn làm ấm và quạt cuối; vẫn tính thời gian bảo vệ trong giai đoạn giữ nhiệt. '
        'Phiên bị dừng/lỗi hoặc thiếu mẫu không được ghi là đã hoàn thành. '
        'Một đầu dò chưa xác nhận độ đều nhiệt hoặc hiệu quả ấp trứng.\n',encoding='utf-8')
    return result


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    live=sub.add_parser('do')
    live.add_argument('--bo-dieu-khien',choices=('doi-chung','co-dinh','thu-rl'),default='doi-chung')
    live.add_argument('--goi-thu-rl',type=Path,default=Path(__file__).with_name('goi_thu_rl_20261117.json'))
    live.add_argument('--cau-hinh-doi-chung',type=Path,default=Path(__file__).with_name('doi_chung_kiem_tra.json'))
    live.add_argument('--bong',type=float,default=50)
    live.add_argument('--quat',type=float,choices=(75,100),default=75)
    live.add_argument('--giay',type=float,default=600)
    live.add_argument('--lam-am-toi-da',type=float,default=600)
    live.add_argument('--bat-dau-giu',type=float,default=37.,
                      help='Chỉ co-dinh: ngưỡng bắt đầu giữ 37–37.5°C; từ 37°C tiếp cận bằng mức cố định đã chọn.')
    live.add_argument('--quat-lam-am',type=float,choices=(75,100),default=100,
                      help='Chỉ co-dinh cho phép đổi quạt làm ấm từ mặc định 100%% sang 75%%.')
    live.add_argument('--sensor')
    live.add_argument('--khong-oled',action='store_true')
    live.add_argument('--dht11',action='store_true',
                      help='Đo/hiển thị/ghi RH ở BCM17; không đưa độ ẩm vào policy Q-table.')
    live.add_argument('--dry-run',action='store_true')
    live.add_argument('--out',type=Path)
    offline=sub.add_parser('phan-tich')
    offline.add_argument('--log',type=Path,required=True)
    offline.add_argument('--out',type=Path)
    args=p.parse_args(argv)
    try:
        if args.command=='phan-tich':
            folder=args.out or args.log.parent/('phan_tich_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
            print(json.dumps(write_summary(args.log,folder),ensure_ascii=False,indent=2))
            return 0
        reference=None
        if args.bo_dieu_khien=='doi-chung':
            reference,_=read_reference(args.cau_hinh_doi_chung)
        pilot=read_pilot(args.goi_thu_rl) if args.bo_dieu_khien=='thu-rl' else None
        policy=HoldPolicy(args.bo_dieu_khien,args.giay,args.lam_am_toi_da,args.bong,args.quat,reference,pilot,args.bat_dau_giu,args.quat_lam_am)
        if args.dry_run:
            print(f'KHÔNG GPIO: làm ấm tối đa {args.lam_am_toi_da:g}s, sau đó kiểm tra {args.giay:g}s; '
                  f'{args.bo_dieu_khien}; ngắt mềm 38→37°C, dừng cứng 40°C, mất số đo 3s thì dừng.')
            if reference:
                print(json.dumps(reference,ensure_ascii=False,indent=2))
            if pilot:
                print('Pilot seed 11, 162 state / 9 action; không học online. Nhiệt ban đầu tối đa 30°C; state chưa học/ngoài miền thì dừng.')
            if args.dht11:
                print('DHT11 BCM17/chân 11: RH trên Terminal, OLED và CSV; không đổi state/action/reward/Q-table.')
            if args.bo_dieu_khien=='co-dinh':
                print(f'Bóng {args.bong:g}% / quạt {args.quat:g}%; bắt đầu giữ mức tại {args.bat_dau_giu:g}°C.')
                if args.bat_dau_giu>37:
                    print(f'Dưới 37°C: bóng 75%/quạt {args.quat_lam_am:g}%; từ 37°C: tiếp cận bằng mức cố định. Không đạt ngưỡng trong thời gian làm ấm thì dừng.')
            return 0
        folder=args.out or Path(__file__).resolve().parent/'ket_qua_giu_nhiet'/datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        folder.mkdir(parents=True,exist_ok=False)
        log=folder/'du_lieu.csv'
        config={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
        config.update(profile=policy.metadata(),reference=reference)
        config_path=folder/'cau_hinh.json'
        config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'KẾT QUẢ: {folder}\nKiểm tra hộp rỗng có giám sát; Ctrl+C để dừng. Làm ấm chưa tính vào {args.giay:g}s giữ nhiệt.\n'
              f'Ngưỡng bắt đầu giữ nhiệt: {args.bat_dau_giu:g}°C.',flush=True)
        command=['giu','--bong','0','--quat','100','--giay',str(args.lam_am_toi_da+args.giay+5),
                 '--csv',str(log),'--ngat-nhiet','40','--tan-so-quat','100']
        if args.sensor:
            command+=['--sensor',args.sensor]
        if args.khong_oled:
            command.append('--khong-oled')
        if args.dht11:
            command.append('--dht11')
        code=core.main(command,control_policy=policy,max_session_seconds=core.MAX_SURVEY_SECONDS)
        config.update(profile=policy.metadata(),hardware_program_exit_code=code)
        config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        if log.is_file():
            try:
                result=write_summary(log,folder/'phan_tich')
                print(f'{result["status"]}\nBÁO CÁO: {folder / "phan_tich/KET_QUA.md"}',flush=True)
            except ValueError as exc:
                print(f'Chưa đủ số đo giữ nhiệt: {exc}',flush=True)
        return code if code else 0 if policy.completed else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        p.exit(1,f'Lỗi: {exc}\n')


if __name__=='__main__':
    raise SystemExit(main())
