#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo tải CPU để Raspberry Pi nóng lên (làm 'nguồn nhiệt' cho bài toán quạt).
Chạy:  python3 tao_tai.py --cores 4 --on 180 --off 120 --lap 5
  --cores: số lõi chạy hết công suất;  --on/--off: giây bật/tắt tải;  --lap: số chu kỳ (0 = chạy mãi)
Nhấn Ctrl+C để dừng.
"""
import argparse
import multiprocessing as mp
import time


def burn(stop_at):
    x = 0
    while time.monotonic() < stop_at:
        x += 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cores", type=int, default=4)
    ap.add_argument("--on", type=int, default=180)
    ap.add_argument("--off", type=int, default=120)
    ap.add_argument("--lap", type=int, default=5)
    a = ap.parse_args()
    k = 0
    try:
        while a.lap == 0 or k < a.lap:
            print("Chu kỳ %d: BẬT tải %d giây" % (k + 1, a.on))
            end = time.monotonic() + a.on
            ps = [mp.Process(target=burn, args=(end,)) for _ in range(a.cores)]
            [p.start() for p in ps]
            [p.join() for p in ps]
            print("Chu kỳ %d: TẮT tải %d giây" % (k + 1, a.off))
            time.sleep(a.off)
            k += 1
    except KeyboardInterrupt:
        print("Dừng.")
