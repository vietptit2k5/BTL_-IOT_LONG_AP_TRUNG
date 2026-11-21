#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gửi lệnh bật đồng thời bóng và quạt 12 V qua hai MOSFET.

Mặc định: cả hai 100% trong 3 giây, tắt bóng, giữ quạt 5 giây rồi tắt hết.
Không có câu hỏi y/n. Cần file thu_mach.py trong cùng thư mục.
"""

import argparse

from thu_mach import main as run_circuit


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Bật cùng bóng 12 V/MOSFET GPIO23 (chân 16) và quạt 12 V/MOSFET "
            "GPIO18 (chân 12) ở 100%. Mặc định 3 giây, tối đa 5 giây."
        ),
    )
    parser.add_argument(
        "--giay", type=float, default=3.0,
        help="Thời gian bật cả hai tải: lớn hơn 0, tối đa 5 giây; mặc định 3.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chỉ in kế hoạch; không phát tín hiệu GPIO và không chờ thời gian thực.",
    )
    args = parser.parse_args(argv)
    command = [
        "ca-hai", "--muc", "100", "--giay", str(args.giay),
        "--cau-hinh", "12v-mosfet",
    ]
    if args.dry_run:
        command.append("--dry-run")
    return run_circuit(command)


if __name__ == "__main__":
    raise SystemExit(main())
