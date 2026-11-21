#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chạy thử sơ đồ bóng 12 V + quạt 12 V, mỗi tải qua một MOSFET.

Giữ file này cùng thư mục với thu_mach.py.
Ví dụ: python3 thu_mach_12v.py quat --giay 5
"""

import sys

from thu_mach import main


if __name__ == "__main__":
    # Khóa lựa chọn vào đúng mạch 12 V khi chạy file này.
    sys.exit(main([*sys.argv[1:], "--cau-hinh", "12v-mosfet"]))
