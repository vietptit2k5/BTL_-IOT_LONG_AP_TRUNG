"""Render reproducible Nov20 measured/model/pilot results, without GPIO."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def measurements(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        return [r for r in csv.DictReader(stream) if r['event']=='MEASUREMENT' and r['temperature_c'] and float(r['temperature_age_s'])<3]


def actual_action_spans(path,prefix='kiem_tra_rl_moi'):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:raw=list(csv.DictReader(stream))
    commands=[r for r in raw if r['event'] in ('COMMAND','OUTPUT_CHANGE') and r['phase'].startswith(prefix)]
    if not commands:return None
    start=float(commands[0]['elapsed_s'])
    end=min(float(r['elapsed_s']) for r in raw if r['event'] in ('STOP','ERROR','END') and float(r['elapsed_s'])>=start)
    spans=[];at=start;pair=None
    for row in commands:
        now=float(row['elapsed_s'])
        new=float(row['lamp_command_pct']),float(row['fan_command_pct'])
        if pair is None:pair=new
        elif new!=pair:
            spans.append(dict(start_s=at,seconds=now-at,lamp_pct=pair[0],fan_pct=pair[1]))
            at=now;pair=new
    spans.append(dict(start_s=at,seconds=end-at,lamp_pct=pair[0],fan_pct=pair[1]))
    totals={}
    for s in spans:
        key=f"{s['lamp_pct']:g}/{s['fan_pct']:g}"
        totals[key]=totals.get(key,0)+s['seconds']
    lengths=[s['seconds'] for s in spans]
    return dict(spans=spans,action_seconds=totals,max_unchanged_s=max(lengths),median_unchanged_s=float(np.median(lengths)),
        mean_unchanged_s=float(np.mean(lengths)),pair_changes=len(spans)-1,
        pct_time_in_spans_at_least_30s=100*sum(v for v in lengths if v>=30)/sum(lengths))


def historical_reference():
    path=ROOT/'Du_lieu_giu_nhiet/ket_qua_giu_nhiet/20261117_092305_477345/du_lieu.csv'
    if not path.is_file():return None
    spans=actual_action_spans(path,'kiem_tra')
    start=spans['spans'][0]['start_s'];end=start+sum(s['seconds'] for s in spans['spans'])
    rows=measurements(path);covered=inside=error=0.
    for a,b in zip(rows,rows[1:]):
        t=float(a['elapsed_s'])-float(a['temperature_age_s']);tn=float(b['elapsed_s'])-float(b['temperature_age_s'])
        dt=max(0,min(end,tn)-max(start,t));v=float(a['temperature_c'])
        if tn-t>3 or not dt:continue
        covered+=dt;inside+=dt*(abs(v-37.5)<=.2+1e-9);error+=dt*abs(v-37.5)
    changes=lambda key:sum(a[key]!=b[key] for a,b in zip(spans['spans'],spans['spans'][1:]))
    return dict(source=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        covered_s=covered,in_band_pct=inside/covered*100,mae_c=error/covered,
        lamp_changes=changes('lamp_pct'),fan_changes=changes('fan_pct'),pair_changes=spans['pair_changes'])


def plot_measurement(rows,path,title,hold_start=None):
    x=np.array([float(r['elapsed_s'])-float(r['temperature_age_s']) for r in rows])/60
    t=np.array([float(r['temperature_c']) for r in rows])
    h=np.array([float(r['lamp_command_pct']) for r in rows])
    f=np.array([float(r['fan_command_pct']) for r in rows])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axes=plt.subplots(2,1,figsize=(11,6.3),sharex=True,gridspec_kw={'height_ratios':[2,1]},layout='constrained')
    axes[0].axhspan(37.3,37.7,color='#d8eee4',label='Vùng 37,3–37,7°C')
    axes[0].axhline(37.5,color='#377d61',ls='--',lw=1)
    axes[0].plot(x,t,color='#184c77',lw=1.2,label='DS18B20 thực đo')
    axes[0].set_ylabel('Nhiệt độ (°C)');axes[0].set_title(title,loc='left',fontweight='bold')
    axes[0].legend(loc='lower right',frameon=False)
    axes[1].step(x,h,where='post',label='Bóng',color='#bd5424')
    axes[1].step(x,f,where='post',label='Quạt',color='#237b75',alpha=.8)
    axes[1].set_yticks([0,25,50,75,100]);axes[1].set_ylim(-4,104)
    axes[1].set_ylabel('Lệnh PWM (%)');axes[1].set_xlabel('Thời gian từ đầu lượt (phút)')
    axes[1].legend(loc='lower right',ncol=2,frameon=False)
    for ax in axes:
        ax.grid(alpha=.15)
        if hold_start is not None:ax.axvline(hold_start/60,color='#555',ls=':',lw=1)
    if hold_start is not None:
        axes[0].text(hold_start/60+.1,28,'Bắt đầu 10 phút kiểm tra',fontsize=9,rotation=90)
    fig.savefig(path,dpi=180);plt.close(fig)


def main():
    sys.stdout.reconfigure(encoding='utf8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pilot',type=Path)
    args=p.parse_args();out=args.out.resolve()
    if args.pilot:args.pilot=args.pilot.resolve()
    audit=read(out/'phan_tich_du_lieu.json');model=read(out/'nhan_dang_mo_hinh.json');rl=read(out/'ket_qua_huan_luyen.json')
    protocol=read(out/'giao_thuc_huan_luyen.json')
    plot_measurement(measurements(ROOT/'Du_lieu_dap_ung/du_lieu.csv'),out/'khao_sat_thuc_te.png','Khảo sát thực tế: 10 tổ hợp quanh mốc 37,5°C')
    source_rows=measurements(ROOT/'Du_lieu_dap_ung/du_lieu.csv')
    steady=[r for r in source_rows if r['phase']=='id_02_kich_thich']
    plot_measurement(steady,out/'bong50_quat100_thuc_te.png','Bóng 50% / quạt 100%: đoạn đo đủ 20 phút')
    a=rl['candidate'];b=rl['old_q_on_new_model'];choice=rl['selection']
    lines=['# Phân tích và huấn luyện từ lượt đo ngày 20/11/2026','',
        '## Dữ liệu thực tế','',
        f"Nguồn: `Du_lieu_dap_ung/du_lieu.csv`. SHA256: `{audit['source_sha256']}`.",
        f"Có {audit['samples']} mẫu nhiệt, đúng đầu dò {audit['sensor_ids'][0]}; không có lỗi cảm biến hoặc khoảng mất mẫu trên 3 giây.",
        'Lượt này chỉ đo mốc 37,5°C (mốc giữa trong kế hoạch ba giai đoạn). Chưa xác nhận các chính sách 37,8°C và 37,2°C bằng dữ liệu tương ứng.',
        'Đã chạy hết 10 tổ hợp nhưng chỉ bóng 50% / quạt 100% đủ 1.200 giây. Các tổ hợp khác dừng kích thích khi chạm giới hạn 36,5 hoặc 37,9°C; thời gian ngắn không phải lỗi thu thập.',
        'Không suy cân bằng nhiệt dài hạn từ các đoạn kích thích ngắn. Các điều kiện đầu chưa giống hoàn toàn, nên chưa khẳng định độc lập tác dụng của quạt chỉ từ so cặp.',
        '', '| Bóng | Quạt | Kích thích thực (s) | Đủ 20 phút | Nhiệt trung bình (°C) | Trong vùng (%) |',
        '|---:|---:|---:|:---:|---:|---:|']
    for trial in audit['trials']:
        lines.append(f"| {trial['lamp']}% | {trial['fan']}% | {trial['actual_probe_s']:.1f} | {'Có' if trial['full_duration'] else 'Không'} | {trial['observed_mean_c']:.3f} | {trial['observed_in_373_377_pct']:.1f} |")
    lines += ['', 'Các phần chuẩn bị có mức bóng 30/35/40% là dữ liệu bộ điều khiển chuẩn bị; chúng không được ghi thành action RL mới.',
        '', '![Khảo sát](khao_sat_thuc_te.png)','',
        '## Nhận dạng mô hình','',
        'Mô hình 5 giây dự đoán thay đổi nhiệt từ nhiệt hiện tại, thay đổi nhiệt bước trước, bộ nhớ sưởi, mức quạt và tương tác sưởi–quạt. Bộ nhớ sưởi dùng PWM đã áp dụng, không phải công suất đo bằng watt.',
        'Chọn thời hằng bằng cách giữ nguyên từng chu kỳ chuẩn bị–kích thích–sau tắt khi chia tập. Chu kỳ 1–8 dùng chọn mô hình; chu kỳ 9–10 giữ lại đến khi chốt thời hằng. Sau đánh giá mới khớp lại toàn bộ để huấn luyện.',
        f"Thời hằng chọn: {model['tau_s']:g}s. RMSE trung bình giữa các chu kỳ: {model['cv30_rmse_c']:.3f}°C cho dự đoán tự chạy 30s; {model['cv60_rmse_c']:.3f}°C cho 60s.",
        'Đây là kiểm tra giữa các đoạn trong cùng lượt đo; vẫn cần thử vật lý độc lập. Môi trường ngoài chưa đo, không có dữ liệu trứng thật hoặc mô hình độ ẩm.',
        '', '## Huấn luyện Q-learning','',
        'Mục tiêu 37,3–37,7°C, tâm 37,5°C. 2.430 trạng thái gồm sai số, xu hướng nhiệt, bộ nhớ sưởi, action trước và cờ bảo vệ. Tập 9 action cũ giữ nguyên; tổ hợp 100%/100% chưa đưa vào pilot mới.',
        'Reward thưởng ở trong vùng, phạt xa vùng và chậm quay về; phạt đổi tổ hợp và biên độ đổi. Trong vùng đổi mức bị phạt mạnh hơn ngoài vùng. Bảo vệ mềm ghi nhận trong thời gian kiểm tra.',
        f"Đã thử 24 ứng viên: 4 hệ số phạt đổi × 3 seed × 2 cách quyết định (5s hoặc SMDP danh định 30s trong vùng/10s ngoài vùng). Mỗi ứng viên {protocol['episodes']:,} episode, mỗi episode tối đa 10 phút mô phỏng. Chọn trên 128 tình huống validation, sau đó đánh giá 192 tình huống test với cùng nhiễu và điều kiện đầu cho các bộ điều khiển.",
        f"Chọn `{choice['kind']}`, hệ số đổi={choice['switch_weight']:g}, hệ số quay về=4, seed={choice['seed']}. Xét action mỗi 5 giây; không ép thay đổi mỗi 5 giây. Chưa khóa cứng action khi nhiệt ở trong vùng.",
        '', '| Chỉ số mô phỏng / 10 phút | Q mới | Q cũ trên cùng mô hình mới |',
        '|---|---:|---:|',
        f"| Thời gian trong vùng | {a['in_band_pct']:.2f}% | {b['in_band_pct']:.2f}% |",
        f"| MAE so với 37,5°C | {a['mae_c']:.3f}°C | {b['mae_c']:.3f}°C |",
        f"| Lần đổi mức bóng | {a['lamp_changes']:.2f} | {b['lamp_changes']:.2f} |",
        f"| Lần đổi mức quạt | {a['fan_changes']:.2f} | {b['fan_changes']:.2f} |",
        f"| Lần đổi tổ hợp | {a['pair_changes']:.2f} | {b['pair_changes']:.2f} |",
        f"| Đoạn ở trong vùng liên tục dài nhất, trung bình | {a['longest_in_band_s']:.1f}s | {b['longest_in_band_s']:.1f}s |",
        '', 'Các số trên là kết quả mô phỏng có điều kiện theo mô hình đã khớp. Không dùng chúng như số đo máy thật hoặc chứng minh tăng tỷ lệ nở.',
        'Bộ thermostat tham chiếu ở đây chỉ là relay vùng chết dùng cùng action đã hỗ trợ; chưa đại diện cho mọi PID/thermostat đã tinh chỉnh.',
        '', '## Chạy thử trên Pi','']
    if args.pilot:
        hardware=read(args.pilot/'ket_qua.json');cfg=read(args.pilot/'cau_hinh.json')
        spans=actual_action_spans(args.pilot/'du_lieu.csv')
        (out/'thoi_gian_giu_action_thuc_te.json').write_text(json.dumps(spans,ensure_ascii=False,indent=2),encoding='utf8')
        if spans:
            # New physical pilot is NOT added to training. Test model drift on it.
            sys.path[:0]=[str(ROOT/'Code_HopAp_Demo'),str(ROOT/'Code_HopAp_PhanTich')]
            import phan_tich_reward as measured
            from hoc_du_lieu_moi import metrics
            thermal=measured.ThermalModel(**model['final_model'])
            session=measured.read_log(args.pilot/'du_lieu.csv')
            transitions=measured.transitions(session,thermal.tau)
            start=spans['spans'][0]['start_s'];end=start+sum(s['seconds'] for s in spans['spans'])
            hold_rows=[r for r in transitions if start<=r['t'] and r['t']+5<=end]
            independent={str(seconds)+'s':metrics(thermal,hold_rows,seconds//5) for seconds in (5,30,60)}
            if hold_rows:
                t=hold_rows[0]['temperature'];d=hold_rows[0]['previous_delta'];m=hold_rows[0]['memory_before'];errors=[]
                for row in hold_rows:
                    t,d,m=thermal.step(t,d,m,row['h'],row['f'])
                    errors.append(t-row['next_temperature'])
                independent['whole_hold_open_loop']=dict(seconds=len(errors)*5,rmse_c=float(np.sqrt(np.mean(np.square(errors)))),final_bias_c=errors[-1])
            (out/'mo_hinh_kiem_tra_tren_pilot.json').write_text(json.dumps(independent,indent=2),encoding='utf8')
        rows=measurements(args.pilot/'du_lieu.csv')
        plot_measurement(rows,out/'thu_pi_thuc_te.png','Thử Q-table mới trên Pi: dữ liệu thực',cfg['profile']['warm_elapsed_s'])
        if spans:
            detail=[r for r in rows if start<=float(r['elapsed_s'])-float(r['temperature_age_s'])<end]
            plot_measurement(detail,out/'giu_nhiet_pi_chi_tiet.png','Chi tiết 10 phút giữ nhiệt trên Pi')
        lines += [f"Trạng thái: **{hardware['status']}**. Nguồn CSV: `{args.pilot.relative_to(ROOT)}/du_lieu.csv`.",
            f"SHA256: `{hardware['source_sha256']}`."]
        if hardware.get('covered_s'):
            lines += [f"Làm ấm {cfg['profile']['warm_elapsed_s']:.1f}s, dữ liệu giữ nhiệt {hardware['covered_s']:.1f}s.",
                f"Trong vùng: **{hardware['in_band_pct']:.2f}%**; MAE **{hardware['mae_c']:.3f}°C**; min–max **{hardware['min_c']:.3f}–{hardware['max_c']:.3f}°C**.",
                f"Đổi bóng **{hardware['lamp_changes']}** lần; đổi quạt **{hardware['fan_changes']}** lần; đổi tổ hợp **{hardware['pair_changes']}** lần. Không tính lệnh đầu vào giai đoạn giữ nhiệt.",
                f"Đoạn trong vùng liên tục dài nhất: **{hardware['longest_in_band_s']:.1f}s**; bảo vệ mềm cả phiên: **{hardware['soft_guard_count']}** lần."]
            if hardware['fan_changes']==0:
                lines += ['Trong lượt này quạt không đổi mức: kết quả chủ yếu kiểm tra việc chọn mức bóng và giảm đổi bóng; chưa chứng minh lợi ích riêng của đổi tốc độ quạt.']
        if spans:
            lines += [f"Giữ nguyên một tổ hợp: trung bình **{spans['mean_unchanged_s']:.1f}s**, trung vị **{spans['median_unchanged_s']:.1f}s**, dài nhất **{spans['max_unchanged_s']:.1f}s**.",
                f"{spans['pct_time_in_spans_at_least_30s']:.1f}% thời gian giữ nhiệt thuộc các đoạn giữ nguyên action ít nhất 30s.",
                '', '| Bóng/quạt (%) | Thời gian áp dụng thực (s) |','|---|---:|']
            lines += [f'| {action} | {seconds:.1f} |' for action,seconds in sorted(spans['action_seconds'].items(),key=lambda x:-x[1])]
        lines += ['', '![Lượt thử Pi](thu_pi_thuc_te.png)','']
        if spans:lines += ['![Chi tiết giữ nhiệt](giu_nhiet_pi_chi_tiet.png)','']
        if spans and hold_rows:
            lines += [f"Kiểm tra mô hình trên lượt Pi độc lập này: RMSE dự đoán tự chạy 30s = {independent['30s']['rmse_c']:.3f}°C; 60s = {independent['60s']['rmse_c']:.3f}°C; cả đoạn {independent['whole_hold_open_loop']['seconds']:g}s không hiệu chỉnh bằng số đo = {independent['whole_hold_open_loop']['rmse_c']:.3f}°C.",
                'Đây là chẩn đoán sau thử; lượt Pi chưa được thêm vào huấn luyện. Chất lượng giữ nhiệt thực tế và sai số mô hình được báo cáo riêng.']
            if independent['whole_hold_open_loop']['rmse_c']>.2:
                lines += ['Mô hình tích lũy sai số đáng kể sau nhiều phút: chưa dùng để dự báo dài hạn hoặc khẳng định chính sách tối ưu. Cần bổ sung nhiều lượt giữ nhiệt ở các điều kiện nền và đánh giá lại trên lượt độc lập trước khi chốt phiên bản cuối.']
        humidity=[r for r in rows if r.get('humidity_pct')]
        lines += [f"Độ ẩm: có {len(humidity)} mẫu đọc được. DHT11 không đưa vào state/action/reward; lỗi độ ẩm không thay số đo nhiệt.",
            'Chỉ có một lượt thử hộp rỗng; so với dữ liệu Q cũ khác ngày chưa tách được tác động nhiệt độ phòng. Muốn kết luận hiệu quả thực tế cần chạy đối chứng cùng điều kiện và lặp lại.',
            'Q-table giữ nguyên trong lượt thử, không học online. Chương trình ngắt mềm 38→37°C; dừng cứng 38,5°C, sai đầu dò hoặc mất số đo 3s.']
        previous=historical_reference()
        if previous:
            (out/'doi_chieu_luot_pi_cu.json').write_text(json.dumps(previous,indent=2),encoding='utf8')
            lines += ['', '### Đối chiếu tham khảo với lượt Q cũ ngày 17/11','',
                f"Nguồn cũ: `{previous['source']}`, SHA256 `{previous['sha256']}`. Dùng cùng vùng và cách đếm đổi mức, loại làm ấm/quạt cuối.",
                '', '| Số đo thực / 10 phút | Lượt Q mới | Lượt Q cũ |','|---|---:|---:|',
                f"| Trong 37,3–37,7°C | {hardware['in_band_pct']:.2f}% | {previous['in_band_pct']:.2f}% |",
                f"| MAE | {hardware['mae_c']:.3f}°C | {previous['mae_c']:.3f}°C |",
                f"| Đổi mức bóng | {hardware['lamp_changes']} | {previous['lamp_changes']} |",
                f"| Đổi mức quạt | {hardware['fan_changes']} | {previous['fan_changes']} |",
                f"| Đổi tổ hợp | {hardware['pair_changes']} | {previous['pair_changes']} |",'',
                'Bản mới ít đổi mức hơn nhưng giữ vùng kém hơn lượt cũ này. Hai lượt khác ngày, chưa kiểm soát nhiệt môi trường nên đây là đối chiếu tham khảo, chưa chứng minh quan hệ nhân quả hoặc RL tốt hơn mọi bộ điều khiển thông thường.']
    else:lines += ['Chưa tổng kết lượt vật lý đang chạy.']
    lines += ['', '## Chạy lại đúng bản đã thử','',
        'Trong Terminal Pi:', '', '```bash','cd /home/pi/Code_HopAp_Demo','.venv/bin/python thu_rl_du_lieu_moi.py --dry-run',
        '.venv/bin/python thu_rl_du_lieu_moi.py --dht11','```','',
        'Bắt đầu khi hộp rỗng, nhiệt không quá 30°C, giữ nguyên bố trí và có người theo dõi. Bỏ `--dht11` nếu chưa nối cảm biến ẩm. OLED mặc định bật. Ctrl+C dừng và tắt sưởi.',
        'Lệnh cũ `kiem_tra_giu_nhiet.py ... --bo-dieu-khien thu-rl` vẫn dùng gói Q cũ; muốn thử gói mới phải chạy chương trình phía trên.']
    (out/'BAO_CAO.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    sources=[ROOT/'Code_HopAp_PhanTich'/name for name in ('hoc_du_lieu_moi.py','bao_cao_du_lieu_moi.py','hoc_vung_on_dinh.py','hoc_action_keo_dai.py','hoc_ba_giai_doan.py')]
    sources += [ROOT/'Code_HopAp_Demo'/name for name in ('phan_tich_reward.py','rl_vung_on_dinh.py','giu_hanh_dong_rl.py','thu_rl_du_lieu_moi.py','do_nhiet_hop.py','goi_rl_moi_20261120.json','goi_thu_rl_20261117.json')]
    (out/'nguon_sha256.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2),encoding='utf8')
    print(out/'BAO_CAO.md')


if __name__=='__main__':main()
