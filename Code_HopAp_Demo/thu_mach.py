#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thử bóng 12 V qua MOSFET và một trong hai mạch quạt đã thống nhất.

Mặc định: quạt 5 V qua S8050. --cau-hinh 12v-mosfet: quạt 12 V qua MOSFET.
Chưa cần cảm biến, LED hay màn hình. Các đầu vào driver đều kích mức cao 3,3 V.

Chạy trực tiếp trên Pi 4: python3 thu_mach.py quat --giay 5
Xem kế hoạch trên máy tính: python3 thu_mach.py tu-dong --dry-run
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import signal
import sys
import time


# Số BCM, KHÔNG phải số chân vật lý.
LAMP_GPIO = 23  # Chân vật lý 16 -> PWM module bóng.
FAN_GPIO = 18   # Chân 12 -> điện trở base S8050 hoặc PWM module MOSFET quạt.
LAMP_PWM_HZ = 100
MAX_LAMP_SECONDS = 5.0
MAX_FAN_SECONDS = 10.0
MAX_SESSION_SECONDS = 45.0
WIRING_PROFILES = {
    "5v-s8050": {
        "fan_label": "QUẠT 5 V / S8050",
        "power_off": (
            "Nếu tải không tắt theo lệnh: ngắt nguồn 12 V của bóng và nguồn 5 V của quạt. "
            "Nếu quạt lấy 5 V từ Pi thì nguồn quạt là nguồn USB-C của Pi."
        ),
    },
    "12v-mosfet": {
        "fan_label": "QUẠT 12 V / MOSFET",
        "power_off": (
            "Nếu bóng hoặc quạt không tắt theo lệnh: rút adapter 12 V cấp cho hai tải."
        ),
    },
}


@dataclass(frozen=True)
class Step:
    label: str
    lamp: float
    fan: bool
    seconds: float

    def __post_init__(self):
        if not math.isfinite(self.lamp) or not 0 <= self.lamp <= 1:
            raise ValueError("Mức PWM bóng phải nằm trong khoảng 0–100%.")
        if not math.isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError("Thời gian phải là số hữu hạn lớn hơn 0.")
        limit = MAX_LAMP_SECONDS if self.lamp > 0 else MAX_FAN_SECONDS
        if self.seconds > limit:
            raise ValueError(f"Bước thử này chỉ cho phép tối đa {limit:g} giây.")


class StopRequested(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(signal.Signals(signum).name)


def stop_on_signal(signum, _frame):
    raise StopRequested(signum)


class DryOutput:
    """Đầu ra giả: không đọc hoặc ghi GPIO."""

    def __init__(self):
        self.value = 0

    def on(self):
        self.value = 1

    def off(self):
        self.value = 0

    def close(self):
        self.off()


class Circuit:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.lamp = None
        self.fan = None
        self.factory = None

    def open(self):
        if self.dry_run:
            self.lamp = DryOutput()
            self.fan = DryOutput()
            return

        # Import muộn để --help và --dry-run chạy được trên máy không có GPIO.
        try:
            from gpiozero import DigitalOutputDevice, PWMOutputDevice
            from gpiozero.pins.lgpio import LGPIOFactory
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu thư viện. Trên Raspberry Pi OS chạy: "
                "sudo apt install python3-gpiozero python3-lgpio"
            ) from exc

        # Dùng GPIO cục bộ của Pi 4; không tự chuyển sang remote/mock backend.
        self.factory = LGPIOFactory(chip=0)
        self.lamp = PWMOutputDevice(
            LAMP_GPIO, active_high=True, initial_value=0,
            frequency=LAMP_PWM_HZ, pin_factory=self.factory,
        )
        # Cả S8050 và module MOSFET đã chọn đều kích mức cao; thử quạt ở 100%.
        self.fan = DigitalOutputDevice(
            FAN_GPIO, active_high=True, initial_value=False,
            pin_factory=self.factory,
        )

    def apply(self, lamp, fan):
        # Ngắt bóng trước khi đổi trạng thái quạt hoặc áp dụng bước tiếp theo.
        self.lamp.off()
        if fan:
            self.fan.on()
        else:
            self.fan.off()
        self.lamp.value = lamp

    def shutdown(self):
        """Thử tắt cả hai tải, kể cả khi một thao tác bị lỗi."""
        errors = []
        for name, output in (("bóng", self.lamp), ("quạt", self.fan)):
            if output is not None:
                try:
                    output.off()
                except Exception as exc:
                    errors.append(f"Không gửi được lệnh tắt {name}: {exc}")

        for name, resource in (
            ("GPIO bóng", self.lamp),
            ("GPIO quạt", self.fan),
            ("GPIO factory", self.factory),
        ):
            if resource is not None:
                try:
                    resource.close()
                except Exception as exc:
                    errors.append(f"Không giải phóng được {name}: {exc}")
        return errors


def make_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Thử mạch chưa có cảm biến: bóng 12 V/MOSFET GPIO23/chân 16, "
            "quạt GPIO18/chân 12. Chọn đúng --cau-hinh. Mặc định chỉ gửi lệnh tắt."
        ),
        epilog=(
            "Ví dụ: python3 thu_mach.py quat --giay 5 | "
            "python3 thu_mach.py den --giay 2 --muc 50 | "
            "python3 thu_mach.py tu-dong --dry-run"
        ),
    )
    parser.add_argument(
        "che_do", nargs="?", default="tat",
        choices=("tat", "quat", "den", "ca-hai", "tu-dong"),
    )
    parser.add_argument("--giay", type=float, help="Thời gian bật tải trong một lần thử.")
    parser.add_argument("--muc", type=float, help="PWM bóng 1–100%%; không áp dụng cho quạt.")
    parser.add_argument(
        "--cau-hinh", choices=tuple(WIRING_PROFILES), default="5v-s8050",
        help="Mạch quạt thực tế; mặc định 5v-s8050. Dùng 12v-mosfet cho sơ đồ hai MOSFET.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chỉ in kế hoạch, không điều khiển GPIO và không chờ theo thời gian thực.",
    )
    return parser


def make_plan(args):
    mode = args.che_do
    if mode in ("tat", "tu-dong") and (args.giay is not None or args.muc is not None):
        raise ValueError("Chế độ tat/tu-dong không nhận --giay hoặc --muc.")
    if mode == "quat" and args.muc is not None:
        raise ValueError("Quạt chỉ thử ở 100%; --muc chỉ dùng cho den/ca-hai.")

    if mode == "tat":
        return [Step("Gửi lệnh tắt cả hai tải", 0, False, 1)]

    start = Step("Ban đầu: cả hai tải phải tắt", 0, False, 1)
    if mode == "tu-dong":
        return [
            start,
            Step("Thử riêng quạt", 0, True, 5),
            Step("Tắt quạt", 0, False, 1),
            Step("Bóng PWM 25%", 0.25, False, 1),
            Step("Tắt bóng", 0, False, 1),
            Step("Bóng PWM 50%", 0.50, False, 1),
            Step("Tắt bóng", 0, False, 1),
            Step("Bóng PWM 100%", 1.00, False, 1),
            Step("Tắt bóng", 0, False, 1),
            Step("Thử đồng thời: bóng 50%, quạt 100%", 0.50, True, 3),
            Step("Tắt bóng, giữ quạt thêm", 0, True, 5),
            Step("Kết thúc: tắt cả hai tải", 0, False, 1),
        ]

    default_seconds = {"quat": 5, "den": 2, "ca-hai": 3}
    seconds = default_seconds[mode] if args.giay is None else args.giay
    if args.muc is not None and (
        not math.isfinite(args.muc) or not 1 <= args.muc <= 100
    ):
        raise ValueError("--muc phải nằm trong khoảng 1–100%.")
    level = (100 if mode == "den" else 50) if args.muc is None else args.muc
    lamp = 0 if mode == "quat" else level / 100
    fan = mode in ("quat", "ca-hai")
    plan = [start, Step("Thử tải đã chọn", lamp, fan, seconds)]
    if lamp > 0:
        plan.append(Step("Tắt bóng, giữ quạt thêm", 0, True, 5))
    plan.append(Step("Kết thúc: tắt cả hai tải", 0, False, 1))
    return plan


def wait_step(seconds, session_deadline):
    end = time.monotonic() + seconds
    while True:
        now = time.monotonic()
        if now >= session_deadline:
            raise TimeoutError("Hết giới hạn thời gian của lượt thử.")
        remaining = end - now
        if remaining <= 0:
            return
        time.sleep(min(0.1, remaining, session_deadline - now))


def run_plan(circuit, plan, dry_run=False):
    deadline = time.monotonic() + MAX_SESSION_SECONDS
    for index, step in enumerate(plan, 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Hết giới hạn thời gian của lượt thử.")
        circuit.apply(step.lamp, step.fan)
        print(
            f"[{index:02d}/{len(plan):02d}] {step.label}: "
            f"lệnh bóng {step.lamp * 100:.0f}%, "
            f"quạt {'100%' if step.fan else '0%'} — {step.seconds:g} giây",
            flush=True,
        )
        if not dry_run:
            wait_step(step.seconds, deadline)


def main(argv=None):
    # Giữ tiếng Việt đọc được cả khi chạy --dry-run qua pipe trên Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        plan = make_plan(args)
    except ValueError as exc:
        parser.error(str(exc))

    profile = WIRING_PROFILES[args.cau_hinh]
    print(
        "BÓNG 12 V / MOSFET: BCM23 / chân 16 | "
        f"{profile['fan_label']}: BCM18 / chân 12",
        flush=True,
    )
    if args.dry_run:
        print("MÔ PHỎNG: không truy cập GPIO, không chờ thời gian thực.", flush=True)
    else:
        print(
            "THỬ NGẮN, CHƯA CÓ CẢM BIẾN: mở nắp, hộp rỗng, theo dõi trực tiếp.\n"
            "Ctrl+C để dừng. " + profile["power_off"],
            flush=True,
        )

    circuit = Circuit(dry_run=args.dry_run)
    previous_handlers = {}
    exit_code = 0
    try:
        stop_signals = [signal.SIGINT, signal.SIGTERM]
        # Phiên SSH đóng có thể gửi SIGHUP trên Pi/Linux.
        if hasattr(signal, "SIGHUP"):
            stop_signals.append(signal.SIGHUP)
        for signum in stop_signals:
            previous_handlers[signum] = signal.signal(signum, stop_on_signal)
        circuit.open()
        run_plan(circuit, plan, dry_run=args.dry_run)
    except StopRequested as exc:
        print(f"\nDừng theo {exc}.", file=sys.stderr, flush=True)
        exit_code = 128 + exc.signum
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr, flush=True)
        exit_code = 1
    finally:
        # Tránh Ctrl+C lần hai ngắt dở quá trình tắt tải và giải phóng GPIO.
        for signum in previous_handlers:
            signal.signal(signum, signal.SIG_IGN)
        errors = circuit.shutdown()
        for signum, old_handler in previous_handlers.items():
            signal.signal(signum, old_handler)
        if errors:
            for error in errors:
                print(error, file=sys.stderr, flush=True)
            print(profile["power_off"], file=sys.stderr, flush=True)
            exit_code = 1
        else:
            if args.dry_run:
                message = "Mô phỏng hoàn tất; không có lệnh GPIO thực."
            elif circuit.lamp is None and circuit.fan is None:
                message = "Chưa khởi tạo được đầu ra GPIO; chương trình đã dừng."
            else:
                message = (
                    "Đã yêu cầu tắt các đầu ra đã khởi tạo và giải phóng GPIO. "
                    "Kiểm tra thực tế bóng và quạt đã tắt."
                )
            print(message, flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
