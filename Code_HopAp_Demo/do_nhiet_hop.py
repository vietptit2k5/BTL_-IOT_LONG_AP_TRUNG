#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo DS18B20, hiển thị OLED và khảo sát hai MOSFET 12 V; không huấn luyện RL.

python3 do_nhiet_hop.py doc --giay 30
python3 do_nhiet_hop.py giu --bong 35 --quat 100 --giay 120
python3 do_nhiet_hop.py tay --giay 600
python3 do_nhiet_hop.py kich-ban --tep kich_ban_do_nhiet.csv

Mọi phần trăm là duty PWM được yêu cầu, không phải W hoặc RPM đo được.
OLED SSD1306 I2C bật mặc định; --khong-oled để chỉ dùng Terminal/CSV.
"""

from __future__ import annotations

import argparse
import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import queue
import re
import signal
import sys
import threading
import time

from oled_hop_ap import OLEDDisplay, OLEDFrame, address_arg


LAMP_GPIO = 23                 # BCM23, chân vật lý 16.
FAN_GPIO = 18                  # BCM18, chân vật lý 12.
SAMPLE_SECONDS = 1.0
SENSOR_TIMEOUT = 3.0
MAX_SECONDS = 600.0
MAX_SURVEY_SECONDS = 7200.0     # Chỉ khảo sát tự động có callback và bảo vệ cảm biến.
MAX_SINGLE_TEMPERATURE_SECONDS = 25200.0  # Chỉ phép đo đủ ma trận một mốc, có giới hạn riêng.
FAN_KICK_SECONDS = 1.0
COOLDOWN_SECONDS = 10.0
W1_ROOT = Path('/sys/bus/w1/devices')
CSV_FIELDS = (
    'timestamp_utc', 'elapsed_s', 'event', 'phase', 'sensor_id',
    'temperature_c', 'temperature_age_s', 'gpio_control', 'lamp_requested_pct',
    'fan_requested_pct', 'lamp_command_pct', 'fan_command_pct', 'fan_pwm_hz',
    'cutoff_c', 'trend_c_per_min', 'note',
    'humidity_pct', 'humidity_age_s', 'humidity_error',
)


class SensorError(RuntimeError):
    pass


class StopRun(RuntimeError):
    pass


class SignalStop(Exception):
    def __init__(self, number):
        self.number = number


def finite_range(value, lower, upper, name):
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f'{name} phải là số hữu hạn từ {lower:g} đến {upper:g}.')


def check_levels(lamp, fan, *, fan_off_trial=False):
    finite_range(lamp, 0, 100, 'Mức bóng')
    finite_range(fan, 0, 100, 'Mức quạt')
    if lamp > 0 and fan == 0 and not (fan_off_trial and lamp<=50):
        raise ValueError('Trong phép thử hộp này, bóng > 0% cần quạt > 0%.')


@dataclass(frozen=True)
class FanOffTrialLimits:
    """Internal opt-in for short, supervised empty-box comparisons, never a general CLI override."""
    max_lamp_pct: float = 50.
    max_total_fan_off_s: float = 30.

    def __post_init__(self):
        finite_range(self.max_lamp_pct,.1,50,'Bóng trong phép thử quạt tắt')
        finite_range(self.max_total_fan_off_s,.1,30,'Tổng thời gian sưởi khi quạt tắt')


def temperature_rate(points):
    """Hệ số góc OLS, °C/phút; chưa đủ 10 giây thì chưa kết luận xu hướng."""
    if len(points) < 5 or points[-1][0] - points[0][0] < 10:
        return None
    mt = sum(t for t, _ in points) / len(points)
    my = sum(value for _, value in points) / len(points)
    denominator = sum((t - mt) ** 2 for t, _ in points)
    return 60 * sum((t - mt) * (value - my) for t, value in points) / denominator


@dataclass(frozen=True)
class AutoDecision:
    phase: str
    lamp: float
    fan: float
    note: str = ''
    fan_off_trial: bool = False

    def __post_init__(self):
        check_levels(self.lamp, self.fan,fan_off_trial=self.fan_off_trial)


@dataclass(frozen=True)
class Phase:
    name: str
    seconds: float
    lamp: float
    fan: float

    def __post_init__(self):
        finite_range(self.seconds, 0.1, MAX_SECONDS, 'Thời gian mỗi bước')
        check_levels(self.lamp, self.fan)
        if not self.name.strip():
            raise ValueError('Tên bước không được trống.')


def load_plan(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['ten', 'giay', 'bong_pct', 'quat_pct']:
            raise ValueError('CSV kịch bản cần đúng tiêu đề: ten,giay,bong_pct,quat_pct')
        phases = []
        for number, row in enumerate(reader, 2):
            try:
                if None in row:
                    raise ValueError('Thừa cột trong dòng CSV.')
                phases.append(Phase(row['ten'], float(row['giay']),
                                    float(row['bong_pct']), float(row['quat_pct'])))
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f'Lỗi kịch bản tại dòng {number}: {exc}') from exc
    if not phases or sum(p.seconds for p in phases) > MAX_SECONDS:
        raise ValueError('Kịch bản phải có bước và tổng thời gian không quá 600 giây.')
    return phases


def find_sensor(sensor_id=None, root=W1_ROOT):
    if sensor_id is not None:
        if not re.fullmatch(r'28-[0-9a-fA-F]{12}', sensor_id):
            raise SensorError('--sensor cần mã DS18B20 dạng 28-xxxxxxxxxxxx.')
        files = [root / sensor_id / 'w1_slave']
        files = [path for path in files if path.is_file()]
    else:
        files = sorted(root.glob('28-*/w1_slave'))
    if not files:
        raise SensorError('Không thấy DS18B20. Kiểm tra dây, trở 4,7 kΩ và bật 1-Wire.')
    if len(files) != 1:
        ids = ', '.join(path.parent.name for path in files)
        raise SensorError(f'Có nhiều đầu dò ({ids}). Chọn đúng đầu dò hộp bằng --sensor MÃ.')
    return files[0]


def parse_temperature(text):
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].split() or lines[0].split()[-1] != 'YES':
        raise SensorError('DS18B20 lỗi CRC hoặc dữ liệu không đầy đủ.')
    match = re.search(r'(?:^|\s)t=(-?\d+)(?:\s|$)', lines[1])
    if match is None:
        raise SensorError('DS18B20 thiếu trường t= hợp lệ.')
    temp = int(match.group(1)) / 1000.0
    if not -55 <= temp <= 125 or temp == 85.0:
        raise SensorError(f'Số đo bất thường {temp:g}°C; có thể lỗi nguồn/cảm biến.')
    return temp


@dataclass(frozen=True)
class Reading:
    at: float
    temperature: float | None
    error: str = ''


class SensorWorker:
    """Đọc sysfs ở luồng riêng để phép đọc treo không chặn giám sát thời gian."""

    def __init__(self, path):
        self.path = path
        self.messages = queue.Queue(maxsize=2)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _publish(self, reading):
        try:
            self.messages.put_nowait(reading)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            self.messages.put_nowait(reading)

    def _run(self):
        while not self.stop.is_set():
            began = time.monotonic()
            try:
                value = parse_temperature(self.path.read_text(encoding='ascii'))
                reading = Reading(time.monotonic(), value)
            except Exception as exc:
                self._publish(Reading(time.monotonic(), None, str(exc)))
                return
            self._publish(reading)
            self.stop.wait(max(0, SAMPLE_SECONDS - (time.monotonic() - began)))

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=0.05)


class Outputs:
    def __init__(self, enabled, fan_hz=100,fan_off_trial_limits=None):
        self.enabled = enabled
        self.fan_hz = fan_hz
        self.lamp = self.fan = self.factory = None
        self.requested_lamp = self.requested_fan = 0.0
        self.lamp_pct = self.fan_pct = 0.0
        self.kick_until = 0.0
        self.had_heat = False
        self.fan_off_trial_limits=fan_off_trial_limits
        self.fan_off_heating_s=0.
        self._fan_off_accounted_at=None

    def open(self):
        if not self.enabled:
            return
        try:
            from gpiozero import PWMOutputDevice
            from gpiozero.pins.lgpio import LGPIOFactory
        except ImportError as exc:
            raise RuntimeError('Trên Pi cài: sudo apt install python3-gpiozero python3-lgpio') from exc
        self.factory = LGPIOFactory(chip=0)
        self.lamp = PWMOutputDevice(LAMP_GPIO, initial_value=0, active_high=True,
                                    frequency=100, pin_factory=self.factory)
        self.fan = PWMOutputDevice(FAN_GPIO, initial_value=0, active_high=True,
                                   frequency=self.fan_hz, pin_factory=self.factory)

    def _apply(self, lamp, fan):
        if not self.enabled:
            return
        # Khi thay đổi quạt, ngắt bóng trước; đặt quạt rồi mới đặt bóng.
        if fan != self.fan_pct:
            self.lamp.off()
            self.lamp_pct = 0.0
            self.fan.value = fan / 100.0
            self.fan_pct = fan
        if lamp != self.lamp_pct:
            self.had_heat |= lamp > 0
            self.lamp.value = lamp / 100.0
            self.lamp_pct = lamp

    def command(self, lamp, fan, now):
        check_levels(lamp, fan,fan_off_trial=self.fan_off_trial_limits is not None)
        if self.fan_off_trial_limits is not None and lamp>self.fan_off_trial_limits.max_lamp_pct:
            raise ValueError('Vượt giới hạn mức bóng của phép thử quạt tắt.')
        self._account_fan_off(now)
        if not self.enabled and (lamp or fan):
            raise RuntimeError('Chế độ doc không điều khiển GPIO.')
        was_off = self.requested_fan == 0
        self.requested_lamp, self.requested_fan = lamp, fan
        if fan == 0:
            self.kick_until = 0.0
        elif was_off:
            self.kick_until = now + FAN_KICK_SECONDS
        self.tick(now)

    def tick(self, now):
        self._account_fan_off(now)
        if (self.fan_off_trial_limits is not None and self.requested_lamp>0 and self.requested_fan==0
                and self.fan_off_heating_s>=self.fan_off_trial_limits.max_total_fan_off_s):
            self.heater_off()
            raise StopRun('Hết ngân sách sưởi khi quạt tắt; không cho kéo dài hoặc khởi động lại ngân sách.')
        if self.requested_fan > 0 and now < self.kick_until:
            self._apply(0, 100)  # Khởi động quạt 100%, bóng tạm tắt trong 1 giây.
        else:
            self._apply(self.requested_lamp, self.requested_fan)

    def _account_fan_off(self,now):
        if self.fan_off_trial_limits is None:
            return
        if self._fan_off_accounted_at is not None:
            dt=now-self._fan_off_accounted_at
            if dt<0:
                raise ValueError('Đồng hồ thử quạt tắt không tăng.')
            if self.lamp_pct>0 and self.fan_pct==0:
                self.fan_off_heating_s+=dt
        self._fan_off_accounted_at=now

    def heater_off(self):
        self.requested_lamp = 0.0
        if self.lamp is not None:
            self.lamp.off()
        self.lamp_pct = 0.0

    def shutdown(self):
        self.requested_lamp = self.requested_fan = 0.0
        errors = []
        for name, item in (('bóng', self.lamp), ('quạt', self.fan)):
            if item is not None:
                try:
                    item.off()
                    if name == 'bóng':
                        self.lamp_pct = 0.0
                    else:
                        self.fan_pct = 0.0
                except Exception as exc:
                    errors.append(f'Không tắt được {name}: {exc}')
        for item in (self.lamp, self.fan, self.factory):
            if item is not None:
                try:
                    item.close()
                except Exception as exc:
                    errors.append(f'Không giải phóng được GPIO: {exc}')
        return errors


class Recorder:
    def __init__(self, path, sensor_id, outputs, cutoff=40.0):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('x', encoding='utf-8-sig', newline='')
        try:
            self.writer = csv.writer(self.stream)
            self.writer.writerow(CSV_FIELDS)
            self.stream.flush()
        except Exception:
            self.stream.close()
            raise
        self.sensor_id = sensor_id
        self.outputs = outputs
        self.cutoff = cutoff
        self.started = time.monotonic()
        self.latest = None
        self.phase = 'cho_cam_bien'
        self.display = None
        self.mode = 'doc'
        self.fault_status = None
        self.temperature_history = deque()
        self.trend = None
        self.humidity_worker = None

    def humidity(self, now):
        return self.humidity_worker.snapshot(now) if self.humidity_worker else (None, None, '')

    def show_oled(self, status=None):
        if self.display is None:
            return
        now = time.monotonic()
        if self.fault_status:
            status = self.fault_status
        elif status is None:
            if self.latest is None:
                status = 'WAIT SENSOR'
            elif self.phase.startswith('bao_ve_mem_'):
                status = 'SOFT GUARD'
            elif self.phase == 'lam_am_co_gioi_han':
                status = 'WARMUP'
            elif self.phase == 'giu_quat_cuoi':
                status = 'FAN POSTRUN'
            elif self.outputs.requested_fan > 0 and now < self.outputs.kick_until:
                status = 'FAN START'
            else:
                status = 'RUN' if self.outputs.enabled else 'READ ONLY'
        humidity, age, _ = self.humidity(now)
        self.display.update(OLEDFrame(
            self.latest.temperature if self.latest is not None else None,
            self.latest.at if self.latest is not None else None,
            self.outputs.lamp_pct if self.outputs.enabled else None,
            self.outputs.fan_pct if self.outputs.enabled else None,
            self.mode, now - self.started, status, now,
            humidity, None if age is None else now - age, self.humidity_worker is not None,
        ))

    def row(self, event, note='', reading=None):
        now = time.monotonic()
        sample = reading if reading is not None else self.latest
        humidity, humidity_age, humidity_error = self.humidity(now)
        temp = sample.temperature if sample is not None else None
        if event == 'MEASUREMENT' and sample is not None and temp is not None:
            if self.temperature_history and sample.at - self.temperature_history[-1][0] >= SENSOR_TIMEOUT:
                self.temperature_history.clear()
            if not self.temperature_history or sample.at > self.temperature_history[-1][0]:
                self.temperature_history.append((sample.at, temp))
            while self.temperature_history and sample.at - self.temperature_history[0][0] > 30:
                self.temperature_history.popleft()
            self.trend = temperature_rate(self.temperature_history)
        self.show_oled({'STOP': 'STOPPING', 'END': 'DONE', 'ERROR': 'ERROR'}.get(event))
        self.writer.writerow([
            datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            f'{now - self.started:.3f}', event, self.phase, self.sensor_id,
            '' if temp is None else f'{temp:.4f}',
            '' if sample is None else f'{max(0, now - sample.at):.3f}',
            int(self.outputs.enabled),
            f'{self.outputs.requested_lamp:g}' if self.outputs.enabled else '',
            f'{self.outputs.requested_fan:g}' if self.outputs.enabled else '',
            f'{self.outputs.lamp_pct:g}' if self.outputs.enabled else '',
            f'{self.outputs.fan_pct:g}' if self.outputs.enabled else '',
            f'{self.outputs.fan_hz:g}' if self.outputs.enabled else '',
            f'{self.cutoff:g}' if self.outputs.enabled else '',
            '' if self.trend is None else f'{self.trend:.5f}', note,
            '' if humidity is None else f'{humidity:.1f}',
            '' if humidity_age is None else f'{humidity_age:.3f}', humidity_error,
        ])
        self.stream.flush()
        if event == 'MEASUREMENT':
            state = (f'Lệnh bóng {self.outputs.lamp_pct:g}% | Lệnh quạt {self.outputs.fan_pct:g}%'
                     if self.outputs.enabled else 'Chỉ đọc nhiệt, không điều khiển GPIO')
            rate = '--' if self.trend is None else f'{self.trend:+.3f}'
            rh = '' if self.humidity_worker is None else (f' | RH={humidity:.0f}%' if humidity is not None else f' | RH=-- ({humidity_error})')
            print(f'[{now - self.started:6.1f}s] T={temp:6.2f}°C | dT={rate}°C/phút | {state} | {self.phase}{rh}', flush=True)

    def close(self):
        self.stream.close()


def stdin_worker(messages):
    try:
        for line in sys.stdin:
            messages.put(line.strip())
    finally:
        messages.put(None)  # EOF/đóng phiên nhập phải dừng phép thử.


def apply_text(line, outputs, now):
    words = line.lower().split()
    if not words:
        return 'empty'
    if words == ['thoat']:
        return 'stop'
    if words in (['help'], ['?']):
        return 'help'
    if words == ['tat']:
        outputs.command(0, 0, now)
    elif len(words) == 3 and words[0] == 'dat':
        outputs.command(float(words[1]), float(words[2]), now)
    elif len(words) == 2 and words[0] == 'bong':
        outputs.command(float(words[1]), outputs.requested_fan, now)
    elif len(words) == 2 and words[0] == 'quat':
        outputs.command(outputs.requested_lamp, float(words[1]), now)
    else:
        raise ValueError('Dùng: dat BÓNG QUẠT | bong MỨC | quat MỨC | tat | thoat')
    return 'changed'


HELP = 'Lệnh: dat 35 100 | bong 0 | quat 75 | tat | thoat. Nhấn Enter sau mỗi lệnh.'


def receive_reading(worker, recorder, cutoff, controlling):
    try:
        sample = worker.messages.get_nowait()
    except queue.Empty:
        return False
    if sample.error:
        # Không ghi đĩa trước khi bên gọi ngắt sưởi: ghi CSV có thể chậm/lỗi.
        recorder.latest = sample
        raise SensorError(sample.error)
    recorder.latest = sample
    if time.monotonic() - sample.at >= SENSOR_TIMEOUT:
        raise SensorError('Số đo nhận được đã quá hạn.')
    if controlling and sample.temperature >= cutoff:
        raise StopRun(f'T={sample.temperature:.2f}°C đạt ngưỡng dừng {cutoff:g}°C.')
    recorder.row('MEASUREMENT')
    return True


def observe_policy_output(policy, outputs, now):
    """Provide applied command history to an optional observer; never grants GPIO access."""
    observer=getattr(policy,'observe_output',None)
    if callable(observer):
        observer(now,outputs.lamp_pct,outputs.fan_pct)


def run_session(args, phases, outputs, worker, recorder, control_policy=None):
    startup_deadline = time.monotonic() + SENSOR_TIMEOUT
    print('Chờ số đo DS18B20 hợp lệ. ' + (
        'Các đầu ra điều khiển được giữ tắt.' if outputs.enabled else
        'Chế độ doc không truy cập GPIO; rút adapter 12 V khi kiểm tra cảm biến.'), flush=True)
    while not receive_reading(worker, recorder, args.ngat_nhiet, outputs.enabled):
        if time.monotonic() >= startup_deadline:
            raise SensorError('DS18B20 không trả số đo trong 3 giây; không cho phép sưởi.')
        time.sleep(0.05)
    started = time.monotonic()
    if started - recorder.latest.at >= SENSOR_TIMEOUT:
        raise SensorError('Số đo đã quá hạn trước khi áp dụng mức đầu tiên.')
    if outputs.fan_off_trial_limits is not None and recorder.latest.temperature>30:
        raise RuntimeError('Phép thử quạt tắt cần nhiệt ban đầu không quá 30°C; để hộp nguội rồi thử lại.')
    deadline = started + args.giay
    if control_policy is not None:
        phases = []
        recorder.mode = 'khao-sat'
    messages = queue.Queue()
    if args.che_do == 'tay':
        threading.Thread(target=stdin_worker, args=(messages,), daemon=True).start()
        print(HELP, flush=True)
    index = 0
    phase_end = started + phases[0].seconds if phases else deadline
    recorder.phase = phases[0].name if phases else args.che_do
    if phases:
        outputs.command(phases[0].lamp, phases[0].fan, started)
        recorder.row('COMMAND', 'Bắt đầu bước 1; duty yêu cầu, không phải W/RPM đo được.')
    last_decision = None
    while time.monotonic() < deadline:
        receive_reading(worker, recorder, args.ngat_nhiet, outputs.enabled)
        now = time.monotonic()
        if now - recorder.latest.at >= SENSOR_TIMEOUT:
            raise SensorError('Mất số đo nhiệt hợp lệ quá 3 giây.')
        if control_policy is not None:
            observe_policy_output(control_policy,outputs,now)
            decision = control_policy(now, recorder.latest)
            if decision is None:
                outputs.heater_off()
                recorder.row('STOP', 'Đã hoàn thành khảo sát tự động.')
                return
            key = decision.phase, decision.lamp, decision.fan
            if key != last_decision:
                check_levels(decision.lamp, decision.fan,fan_off_trial=(outputs.fan_off_trial_limits is not None
                                                                     and getattr(decision,'fan_off_trial',False)))
                recorder.phase = decision.phase
                outputs.command(decision.lamp, decision.fan, now)
                observe_policy_output(control_policy,outputs,now)
                recorder.row('COMMAND', decision.note)
                last_decision = key
        if phases and now >= phase_end:
            while index + 1 < len(phases) and now >= phase_end:
                index += 1
                phase_end += phases[index].seconds
            recorder.phase = phases[index].name
            outputs.command(phases[index].lamp, phases[index].fan, now)
            recorder.row('COMMAND', f'Chuyển sang bước {index + 1}.')
        if args.che_do == 'tay':
            # Giới hạn mỗi vòng để việc nhập dồn không chặn kiểm tra cảm biến.
            for _ in range(10):
                try:
                    line = messages.get_nowait()
                except queue.Empty:
                    break
                if line is None:
                    outputs.heater_off()
                    recorder.row('STOP', 'EOF: kết thúc phiên nhập.')
                    return
                try:
                    result = apply_text(line, outputs, now)
                except ValueError as exc:
                    print(f'Lệnh không hợp lệ: {exc}', flush=True)
                    continue
                if result == 'stop':
                    outputs.heater_off()
                    recorder.row('STOP', 'Người dùng nhập thoat.')
                    return
                if result == 'help':
                    print(HELP, flush=True)
                elif result == 'changed':
                    recorder.row('COMMAND', line)
        old_levels = outputs.lamp_pct, outputs.fan_pct
        outputs.tick(now)
        if control_policy is not None:
            observe_policy_output(control_policy,outputs,now)
        if old_levels != (outputs.lamp_pct, outputs.fan_pct):
            recorder.row('OUTPUT_CHANGE', 'Kết thúc xung khởi động quạt.')
        time.sleep(0.05)
    outputs.heater_off()
    recorder.row('STOP', 'Đã hết thời gian thử.')


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('che_do', nargs='?', default='doc', choices=('doc', 'giu', 'tay', 'kich-ban'))
    parser.add_argument('--bong', type=float, default=None, help='Duty bóng 0–100%%; dùng với giu.')
    parser.add_argument('--quat', type=float, default=None, help='Duty quạt 0–100%%; dùng với giu.')
    parser.add_argument('--giay', type=float, default=None, help='Thời gian tối đa 600 giây, không tính 10 giây giữ quạt cuối.')
    parser.add_argument('--tep', type=Path, help='CSV kịch bản; chỉ dùng với kich-ban.')
    parser.add_argument('--sensor', help='Mã đầu dò 28-xxxxxxxxxxxx; bắt buộc nếu có nhiều đầu dò.')
    parser.add_argument('--csv', type=Path, help='Đường dẫn file mới; từ chối ghi đè file đã tồn tại.')
    parser.add_argument('--ngat-nhiet', type=float, default=40.0, help='Ngưỡng dừng thử hộp rỗng, tối đa 40°C; mặc định 40.')
    parser.add_argument('--tan-so-quat', type=float, default=100.0, help='PWM quạt, Hz; mặc định thử 100, cần kiểm tra với quạt thực.')
    parser.add_argument('--dry-run', action='store_true', help='Chỉ in kế hoạch, không GPIO/cảm biến và không tạo dữ liệu đo.')
    parser.add_argument('--khong-oled', action='store_true', help='Không dùng OLED; vẫn có Terminal/CSV.')
    parser.add_argument('--dht11', action='store_true', help='Đọc thêm độ ẩm DHT11 ở BCM17/chân 11; không dùng điều khiển nhiệt.')
    parser.add_argument('--do-am-file', type=Path, default=None,
                        help='Lấy độ ẩm từ file do do_am.py ghi (không mở GPIO17); không dùng cùng --dht11.')
    parser.add_argument('--oled-dia-chi', type=address_arg, default=None, help='0x3c hoặc 0x3d; mặc định thử cả hai địa chỉ.')
    parser.add_argument('--oled-cao', type=int, choices=(32, 64), default=64, help='Chiều cao OLED SSD1306; mặc định 128x64.')
    return parser


def prepare(args, max_session_seconds=MAX_SECONDS, automatic=False):
    finite_range(args.ngat_nhiet, 1, 40, '--ngat-nhiet')
    finite_range(args.tan_so_quat, 1, 1000, '--tan-so-quat')
    if args.che_do == 'kich-ban':
        if args.tep is None or any(value is not None for value in (args.bong, args.quat, args.giay)):
            raise ValueError('kich-ban cần --tep, không nhận --bong/--quat/--giay.')
        phases = load_plan(args.tep)
        args.giay = sum(p.seconds for p in phases)
    else:
        if args.tep is not None:
            raise ValueError('--tep chỉ dùng với kich-ban.')
        if args.che_do != 'giu' and (args.bong is not None or args.quat is not None):
            raise ValueError('--bong/--quat chỉ dùng với giu. Chế độ tay dùng lệnh dat khi đang chạy.')
        args.giay = args.giay if args.giay is not None else (600.0 if args.che_do == 'tay' else 60.0)
        finite_range(args.giay, 0.1, max_session_seconds, '--giay')
        phases = []
        if args.che_do == 'giu':
            if args.bong is None or args.quat is None:
                raise ValueError('giu cần cả --bong và --quat, tính bằng phần trăm.')
            check_levels(args.bong, args.quat)
            if not automatic:
                phases = [Phase('giu_co_dinh', args.giay, args.bong, args.quat)]
    return phases


def main(argv=None, control_policy=None, max_session_seconds=MAX_SECONDS,fan_off_trial_limits=None,
         single_temperature_matrix=False):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        cap = MAX_SINGLE_TEMPERATURE_SECONDS if single_temperature_matrix else MAX_SURVEY_SECONDS
        finite_range(max_session_seconds, 1, cap, 'Giới hạn nội bộ')
        if single_temperature_matrix:
            required={(h,f) for h in (0,25,50,75,100) for f in (75,100)}
            pairs=getattr(control_policy,'pairs',())
            if (control_policy is None or getattr(control_policy,'single_target_full_matrix',False) is not True
                or len(pairs)!=10 or set(pairs)!=required or args.che_do!='giu'
                or args.bong!=0 or args.quat!=100 or args.ngat_nhiet>38.5
                or fan_off_trial_limits is not None):
                raise ValueError('Phiên dài chỉ dành cho ma trận10 tổ hợp một mốc, ban đầu bóng0/quạt100, ngắt cứng ≤38.5°C; không dùng ngoại lệ quạt tắt.')
        if control_policy is None and max_session_seconds != MAX_SECONDS:
            raise ValueError('Chỉ bộ khảo sát tự động được dùng giới hạn thời gian mở rộng.')
        phases = prepare(args, max_session_seconds=max_session_seconds, automatic=control_policy is not None)
        if control_policy is not None and args.che_do != 'giu':
            raise ValueError('Bộ khảo sát tự động dùng cấu hình đầu ra của chế độ giu.')
        if fan_off_trial_limits is not None:
            if (not isinstance(fan_off_trial_limits,FanOffTrialLimits) or control_policy is None
                    or args.che_do!='giu' or args.bong!=0 or args.quat!=0
                    or args.giay>120 or args.ngat_nhiet>35):
                raise ValueError('Ngoại lệ quạt tắt chỉ dành cho callback thử riêng: ban đầu 0/0, cả phiên ≤120s, ngắt nhiệt ≤35°C.')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(f'KẾ HOẠCH: {args.che_do}, {args.giay:g} giây; không truy cập phần cứng, không tạo CSV.')
        for phase in phases:
            print(f'{phase.name}: {phase.seconds:g}s, bóng {phase.lamp:g}%, quạt {phase.fan:g}%')
        return 0
    output_options=dict(enabled=args.che_do != 'doc',fan_hz=args.tan_so_quat)
    if fan_off_trial_limits is not None:
        output_options['fan_off_trial_limits']=fan_off_trial_limits
    outputs = Outputs(**output_options)
    display = OLEDDisplay(enabled=not args.khong_oled, address=args.oled_dia_chi, height=args.oled_cao)
    recorder = worker = humidity_worker = None
    handlers = {}
    exit_code = 0
    try:
        def on_signal(number, _frame):
            raise SignalStop(number)
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGHUP] if hasattr(signal, 'SIGHUP') else [])):
            handlers[number] = signal.signal(number, on_signal)
        display.update(OLEDFrame(None, None, None, None, args.che_do, 0, 'WAIT SENSOR', time.monotonic()))
        display.start()
        sensor_path = find_sensor(args.sensor)
        bind_sensor=getattr(control_policy,'bind_sensor',None)
        if callable(bind_sensor):
            bind_sensor(sensor_path.parent.name)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        path = args.csv or Path(__file__).resolve().parent / 'logs' / f'do_nhiet_{stamp}.csv'
        recorder = Recorder(path, sensor_path.parent.name, outputs, args.ngat_nhiet)
        recorder.display = display
        recorder.mode = args.che_do
        if args.dht11 and args.do_am_file is not None:
            raise ValueError('Chọn một: --dht11 (tự đọc GPIO17) hoặc --do-am-file (đọc file của do_am.py).')
        if args.dht11:
            from do_am_dht11 import HumidityWorker
            humidity_worker = HumidityWorker()
            humidity_worker.start()
            recorder.humidity_worker = humidity_worker
            print('DHT11: DATA BCM17/chân 11; độ ẩm chỉ để theo dõi.', flush=True)
        elif args.do_am_file is not None:
            from do_am_dht11 import FileHumiditySource
            humidity_worker = FileHumiditySource(args.do_am_file)
            recorder.humidity_worker = humidity_worker
            print(f'Độ ẩm: đọc {args.do_am_file.name} do do_am.py ghi (không mở GPIO17); chỉ để theo dõi.', flush=True)
        print(f'CSV: {path.resolve()}\nDS18B20: {sensor_path.parent.name}', flush=True)
        print('BCM23/chân 16: bóng; BCM18/chân 12: quạt. DQ cảm biến: BCM4/chân 7.', flush=True)
        print('THỬ HỘP RỖNG, THEO DÕI TRỰC TIẾP. Nếu tải không tắt: rút adapter 12 V.', flush=True)
        print('Trả PWM module về GPIO18/23 nếu trước đó đã nối vào chân nguồn 3,3 V để thử.', flush=True)
        outputs.open()
        worker = SensorWorker(sensor_path)
        worker.start()
        run_session(args, phases, outputs, worker, recorder, control_policy=control_policy)
    except SignalStop as exc:
        try:
            outputs.heater_off()
        except Exception:
            pass  # finally tiếp tục thử tắt/đóng cả hai, kể cả khi một đầu ra lỗi.
        print(f'Dừng theo tín hiệu {exc.number}.', file=sys.stderr, flush=True)
        if recorder is not None:
            recorder.show_oled('STOPPING')
        exit_code = 128 + exc.number
    except (Exception, KeyboardInterrupt) as exc:
        try:
            outputs.heater_off()
        except Exception:
            pass
        print(f'DỪNG: {exc}', file=sys.stderr, flush=True)
        exit_code = 130 if isinstance(exc, KeyboardInterrupt) else 1
        if recorder is not None:
            recorder.fault_status = ('OVER TEMP' if isinstance(exc, StopRun) else
                                     'SENSOR ERROR' if isinstance(exc, SensorError) else 'ERROR')
            recorder.show_oled()
            try:
                recorder.row('ERROR', str(exc))
            except Exception:
                pass
        else:
            display.update(OLEDFrame(None, None, None, None, args.che_do, 0, 'SENSOR ERROR' if isinstance(exc, SensorError) else 'ERROR', time.monotonic()))
    finally:
        for number in handlers:
            signal.signal(number, signal.SIG_IGN)
        try:
            outputs.heater_off()
            if outputs.had_heat and outputs.fan is not None:
                outputs.requested_fan = 100.0
                outputs._apply(0, 100)
                print('Đã gửi lệnh tắt bóng; giữ quạt 100% thêm 10 giây rồi tắt hết.', flush=True)
                end = time.monotonic() + COOLDOWN_SECONDS
                if recorder is not None:
                    recorder.phase = 'giu_quat_cuoi'
                    recorder.row('COMMAND', 'Bóng 0%, quạt 100%; không phải xác nhận tải đã tắt/chạy.')
                while time.monotonic() < end:
                    if worker is not None and recorder is not None:
                        try:
                            # Bóng đã bị yêu cầu tắt; chỉ ghi tiếp nếu còn số đo hợp lệ.
                            receive_reading(worker, recorder, args.ngat_nhiet, controlling=False)
                        except SensorError:
                            pass
                    time.sleep(0.05)
        except Exception as exc:
            print(f'Lỗi khi tắt bóng/giữ quạt: {exc}. RÚT ADAPTER 12 V.', file=sys.stderr, flush=True)
            exit_code = 1
        errors = outputs.shutdown()
        if worker is not None:
            worker.close()
        if recorder is not None:
            try:
                recorder.row('END', '; '.join(errors) or 'Đã gửi lệnh tắt cả hai và giải phóng GPIO.')
                recorder.close()
            except Exception as exc:
                print(f'Lỗi kết thúc CSV: {exc}', file=sys.stderr)
                exit_code = 1
        display.close()
        if humidity_worker is not None:
            humidity_worker.close()
        for number, old in handlers.items():
            signal.signal(number, old)
        if errors:
            print('\n'.join(errors) + '\nRÚT ADAPTER 12 V.', file=sys.stderr, flush=True)
            exit_code = 1
        print('Đã kết thúc. Kiểm tra thực tế hai tải đã tắt; ngưỡng phần mềm không thay bộ ngắt phần cứng.', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
