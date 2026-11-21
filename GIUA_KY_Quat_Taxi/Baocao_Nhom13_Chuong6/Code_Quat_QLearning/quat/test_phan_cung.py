#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra phần cứng TRƯỚC khi chạy Q-learning: (1) đọc cảm biến, (2) quạt chạy các mức PWM.
Chạy:  python3 test_phan_cung.py            (đọc cảm biến 10 lần, rồi thử 4 mức quạt)
       python3 test_phan_cung.py --chi-cam-bien
"""
import sys
import time
from fan_qlearning import read_ds18b20, DUTY

print("== 1. Đọc DS18B20 (10 lần, cách nhau 1 giây) ==")
for i in range(10):
    print("  lần %2d: %.2f °C" % (i + 1, read_ds18b20()))
    time.sleep(1)

if "--chi-cam-bien" in sys.argv:
    sys.exit(0)

from gpiozero import PWMOutputDevice
fan = PWMOutputDevice(18, frequency=100)       # GPIO18 (chân vật lý 12)
print("== 2. Thử quạt: mỗi mức 6 giây. Nghe/nhìn xem quạt có quay nhanh dần không ==")
try:
    for lv, d in enumerate(DUTY):
        fan.value = d
        print("  mức %d  (PWM %.0f%%)  nhiệt độ: %.2f °C" % (lv, d * 100, read_ds18b20()))
        time.sleep(6)
finally:
    fan.value = 0
    fan.close()
print("Xong. Nếu quạt không quay ở mức 1 (45%%), tăng DUTY[1] trong fan_qlearning.py lên 0.55-0.6.")
