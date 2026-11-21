"""Create a complete measurement plan. Never runs SSH, GPIO or measurement commands."""
import argparse
import csv
import json
from pathlib import Path

from do_dap_ung_bo_sung import ResponseSurvey
from lich_ap_ba_giai_doan import stage_for_day


def build_plan(repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError('Số lượt lặp phải từ 1 đến 3.')
    batches=[]
    for repeat in range(1,repeats+1):
        stages=(2,3,1) if repeat%2 else (1,3,2)
        heats=(0,25,50,75,100) if repeat%2 else (100,75,50,25,0)
        for stage in stages:
            reference=stage_for_day({1:1,2:11,3:18}[stage])
            for heat in heats:
                reverse=repeat%2==0
                policy=ResponseSurvey(reverse=reverse,dwell=1200,target=reference['target_c'],
                    heat_levels=(heat,),prepare_seconds=600,post_seconds=300,warm_seconds=900)
                command=(f'.venv/bin/python do_dap_ung_bo_sung.py do --giai-doan {stage}'
                         f' --do-dai --muc-bong {heat}'+(' --dao-thu-tu' if reverse else ''))
                batches.append(dict(batch=len(batches)+1,repeat=repeat,stage=stage,
                    target_c=reference['target_c'],lamp_pct=heat,fan_order=[f for _,f in policy.pairs],
                    seconds_per_combination=1200,post_seconds=300,limit_s=policy.limit,
                    command=command,executed=False))
    return batches


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lap',type=int,default=1)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        batches=build_plan(args.lap)
        args.out.mkdir(parents=True,exist_ok=False)
        payload=dict(purpose='PLAN_ONLY_NOT_MEASURED_DATA',runs=batches,
            combinations_per_repeat=30,total_combinations=30*args.lap,
            max_total_session_s=sum(b['limit_s']+10 for b in batches),
            extra_cooldown_and_manual_setup_not_included=True,
            note='Each batch starts empty box <=30C with direct supervision; never execute all commands unattended.')
        (args.out/'ke_hoach.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        with (args.out/'ma_tran.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f)
            w.writerow(['batch','repeat','stage','target_c','lamp_pct','fan_pct','requested_s','measured','source_csv',
                        'actual_probe_s','full_duration','end_reason'])
            for b in batches:
                for fan in b['fan_order']:
                    w.writerow([b['batch'],b['repeat'],b['stage'],b['target_c'],b['lamp_pct'],fan,1200,'NO','','','',''])
        lines=['# Kế hoạch đo đầy đủ — chưa phải dữ liệu thực','',
               f"{len(batches)} đợt, {30*args.lap} phép kích thích; quạt75/100, bóng0/25/50/75/100 tại ba mốc.",
               f"Tổng giới hạn các đợt khoảng {payload['max_total_session_s']/3600:.2f} giờ; chưa tính để hộp nguội và thao tác.",'',
               'Mỗi đợt bắt đầu hộp rỗng ≤30°C, giữ nguyên bố trí, có người theo dõi. Chạy từng lệnh, lấy dữ liệu và để hộp nguội trước đợt sau; không dán toàn bộ lệnh chạy liên tục.',
               'Dừng sớm do giới hạn nhiệt phải ghi là rút ngắn. Không bỏ bảo vệ để lấy đủ20phút; mức100/100 được khảo sát như kích thích, chưa mặc định là action RL đã có bằng chứng.',
               'Tên giai đoạn chỉ chọn mốc nhiệt khảo sát, chưa tái tạo sinh nhiệt của phôi. 20phút chưa chắc đủ cân bằng.', '',
               '|Đợt|Lặp|Mốc °C|Bóng %|Thứ tự quạt %|Lệnh chạy trên Pi|',
               '|---|---|---|---|---|---|']
        for b in batches:
            lines.append(f"|{b['batch']}|{b['repeat']}|{b['target_c']}|{b['lamp_pct']}|{b['fan_order']}|`{b['command']}`|")
        lines += ['', 'Thêm --dry-run vào một lệnh để kiểm tra kế hoạch, không bật tải. Thêm --dht11 nếu cần ghi RH.',
                  'Một lượt chỉ xác nhận độ phủ; muốn kiểm tra độ lặp lại thì tạo kế hoạch --lap2. Lượt chẵn đảo thứ tự các đợt và cặp quạt.',
                  'Sau đo, điền đường dẫn CSV thật và trạng thái vào ma_tran.csv; không đổi measured thành YES chỉ vì kế hoạch đã tạo hoặc mô phỏng đạt.',
                  'Chọn thêm mức25/50% quạt hoặc quạt0% là một bài khác; không thuộc ma trận này và không tự nới giới hạn của thử quạt0.']
        (args.out/'KE_HOACH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(f'Created plan only: {args.out}; {len(batches)} batches, {30*args.lap} combinations.')
        return 0
    except (ValueError,OSError) as exc:
        p.exit(1,str(exc)+'\n')


if __name__=='__main__':raise SystemExit(main())
