"""Experimental incubation schedule. Pure calendar/config only; NEVER opens GPIO."""
from datetime import datetime, timezone
from copy import deepcopy
import argparse
import json

PROFILE = {
    'name': 'CHICKEN_3_STAGE_ENGINEERING_DEMO_V1',
    'deploy_allowed': False,
    'biological_tolerance_validated': False,
    'source': 'https://khuyennongvn.gov.vn/data/documents/0/2026/11/09/hangweb/ban-tin-khuyen-nong-so-4-2026.pdf#page=43',
    'bands_note': 'Proposed engineering bands, NOT biological tolerances specified by the source.',
    'guard_off_c': 38., 'guard_resume_c': 37.,
    'stages': [
        {'id':0,'days':[1,10],'target_c':37.8,'lower_c':37.6,'upper_c':38.,
         'source_temperature_c':[37.8,38.], 'guard_overlap':True},
        {'id':1,'days':[11,17],'target_c':37.5,'lower_c':37.3,'upper_c':37.7,
         'source_temperature_c':[37.5,37.5], 'guard_overlap':False},
        {'id':2,'days':[18,21],'target_c':37.2,'lower_c':37.,'upper_c':37.4,
         'source_temperature_c':[37.2,37.2], 'guard_overlap':False},
    ],
}


def stage_for_day(day):
    if type(day) is not int or not 1 <= day <= 21:
        raise ValueError('Ngày ấp phải là số nguyên 1–21; sau ngày 21 không tự lặp lại.')
    return next(deepcopy(s) for s in PROFILE['stages'] if s['days'][0] <= day <= s['days'][1])


def stage_at(start, now):
    if start.tzinfo is None or now.tzinfo is None:
        raise ValueError('Thời điểm phải có múi giờ rõ ràng.')
    seconds=(now.astimezone(timezone.utc)-start.astimezone(timezone.utc)).total_seconds()
    if seconds < 0:
        raise ValueError('Mẻ chưa bắt đầu.')
    day=int(seconds//86400)+1
    return day,stage_for_day(day)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--ngay',type=int)
    group.add_argument('--bat-dau',help='ISO8601 có múi giờ, ví dụ 2026-11-20T08:00:00+07:00')
    p.add_argument('--tai',help='Thời điểm kiểm tra ISO8601; bỏ trống dùng giờ UTC hiện tại.')
    args=p.parse_args(argv)
    try:
        if args.ngay is not None:
            if args.tai:p.error('--tai dùng cùng --bat-dau.')
            day,stage=args.ngay,stage_for_day(args.ngay)
        else:
            now=datetime.fromisoformat(args.tai) if args.tai else datetime.now(timezone.utc)
            day,stage=stage_at(datetime.fromisoformat(args.bat_dau),now)
        print(json.dumps(dict(day=day,stage=stage,deploy_allowed=False,
                              note='Xem lịch demo, không gửi lệnh tới bóng/quạt.'),ensure_ascii=True,indent=2))
        return 0
    except ValueError as exc:
        p.exit(1,str(exc)+'\n')


if __name__=='__main__':raise SystemExit(main())
