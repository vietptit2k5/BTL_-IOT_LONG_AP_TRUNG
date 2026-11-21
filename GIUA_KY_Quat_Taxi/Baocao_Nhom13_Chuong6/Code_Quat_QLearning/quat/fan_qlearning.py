#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Q-learning (Q-table) điều khiển tốc độ quạt - bám theo ví dụ Taxi drop-off
trong Chương 6 "Reinforcement Learning for IoT" (Hands-On AI for IoT).

Cách chạy:
    python3 fan_qlearning.py train                 # học trong MÔ PHỎNG (chạy được trên laptop)
    python3 fan_qlearning.py real --q q_quat.npy   # chạy thật trên Raspberry Pi
    python3 fan_qlearning.py plot --log log_real.csv

Đối chiếu với code Taxi trong sách:
    Taxi                                   Quạt (file này)
    -------------------------------------  ---------------------------------------
    env = gym.make('Taxi-v2')              env = SimFanEnv()  hoặc  RealFanEnv()
    m = env.observation_space.n  (500)     m = env.observation_space.n  (32)
    n = env.action_space.n       (6)       n = env.action_space.n       (3)
    Q = np.zeros([m, n])                   Q = np.zeros([m, n])
    gamma=0.97, alpha=0.7, epsilon=0.3     gamma=0.97, alpha=0.7, epsilon=0.3
    max_episode=1000, max_steps=100        max_episode=1000, max_steps=100
    cập nhật Bellman                       cập nhật Bellman (y hệt)
"""
import argparse
import csv
import glob
import time
import numpy as np

# ----------------------------------------------------------------------
# 1. ĐỊNH NGHĨA BÀI TOÁN (state / action / reward)
# ----------------------------------------------------------------------
T_TARGET = 50.0                                   # nhiệt độ mục tiêu (°C) - chỉnh theo thực tế
TEMP_OFFSETS = [-8, -5, -2, 1, 4, 7, 10]          # biên các khoảng nhiệt, tính từ T_TARGET
N_TEMP = len(TEMP_OFFSETS) + 1                    # 8 khoảng nhiệt độ
DUTY = [0.0, 0.45, 0.70, 1.00]                    # 4 mức quạt: tắt / nhẹ / vừa / mạnh (PWM)
N_LEVEL = len(DUTY)
N_STATE = N_TEMP * N_LEVEL                        # 8 x 4 = 32 state
N_ACTION = 3                                      # 0 = giảm, 1 = giữ, 2 = tăng
ACTION_NAME = ["giảm", "giữ", "tăng"]
W_POWER = 0.8                                     # hệ số phạt điện năng trong reward


def temp_to_bin(temp, target=T_TARGET):
    edges = [target + o for o in TEMP_OFFSETS]
    return int(np.digitize(temp, edges))          # 0..7


def encode(temp, level, target=T_TARGET):
    """(nhiệt độ, mức quạt) -> chỉ số state 0..31 (tương đương số 0..499 của Taxi)."""
    return temp_to_bin(temp, target) * N_LEVEL + level


def reward_fn(temp, level, target=T_TARGET):
    """Phạt khi lệch nhiệt độ mục tiêu, phạt thêm khi quạt chạy mạnh (tốn điện)."""
    return -abs(temp - target) / 2.0 - W_POWER * level


class _Space:
    """Giả lập env.observation_space / env.action_space của Gym."""
    def __init__(self, n):
        self.n = n

    def sample(self):
        return np.random.randint(self.n)


def apply_action(level, a):
    """a: 0 giảm, 1 giữ, 2 tăng -> mức quạt mới (kẹp trong 0..3)."""
    return int(min(max(level + (a - 1), 0), N_LEVEL - 1))


# ----------------------------------------------------------------------
# 2. MÔI TRƯỜNG MÔ PHỎNG (giao diện giống Gym: reset / step)
# ----------------------------------------------------------------------
class SimFanEnv:
    """
    Mô hình nhiệt đơn giản của vật được làm mát (ví dụ tản nhiệt của Pi):
        T_cân_bằng = T_phòng + P*tải / (1 + h1*duty)
        T(t+1)     = T(t) + (dt/tau) * (T_cân_bằng - T(t)) + nhiễu
    Tham số lấy từ 3 phép đo thật (xem file hướng dẫn, Bước 5):
        t_amb : nhiệt độ lúc nghỉ, t_max0: nóng nhất khi tải 100% và tắt quạt,
        t_max3: nhiệt độ khi tải 100% và quạt chạy hết công suất.
    """
    def __init__(self, t_amb=28.0, t_max0=70.0, t_max3=46.0, dt=5.0, tau=60.0,
                 max_steps=100, noise=0.2, target=T_TARGET, seed=None):
        self.t_amb, self.dt, self.tau = t_amb, dt, tau
        self.P = t_max0 - t_amb                              # (h0 = 1)
        self.h1 = self.P / (t_max3 - t_amb) - 1.0            # duty = 1.0 -> t_max3
        self.max_steps, self.noise, self.target = max_steps, noise, target
        self.rng = np.random.RandomState(seed)
        self.observation_space = _Space(N_STATE)
        self.action_space = _Space(N_ACTION)

    def _state(self):
        return encode(self.temp, self.level, self.target)

    def reset(self):
        self.load = self.rng.uniform(0.4, 1.0)               # tải (ẩn, agent không biết)
        self.temp = self.rng.uniform(self.t_amb + 12, self.t_amb + 38)
        self.level = 1
        self.t = 0
        return self._state()

    def step(self, a):
        self.level = apply_action(self.level, a)
        if self.rng.rand() < 0.02:                           # thỉnh thoảng tải đổi
            self.load = self.rng.uniform(0.4, 1.0)
        duty = DUTY[self.level]
        t_ss = self.t_amb + self.P * self.load / (1.0 + self.h1 * duty)
        self.temp += (self.dt / self.tau) * (t_ss - self.temp) + self.rng.randn() * self.noise
        self.t += 1
        r = reward_fn(self.temp, self.level, self.target)
        done = self.t >= self.max_steps
        return self._state(), r, done, {"temp": self.temp}


# ----------------------------------------------------------------------
# 3. MÔI TRƯỜNG THẬT: DS18B20 (1-Wire) + quạt PWM qua transistor (Raspberry Pi)
# ----------------------------------------------------------------------
def read_ds18b20(retries=5):
    """Đọc nhiệt độ (°C) từ DS18B20 qua sysfs, không cần thư viện ngoài."""
    files = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")
    if not files:
        raise RuntimeError("Không thấy DS18B20. Kiểm tra dây và bật 1-Wire (raspi-config).")
    for _ in range(retries):
        with open(files[0]) as f:
            lines = f.read().strip().split("\n")
        if lines[0].endswith("YES") and "t=" in lines[1]:
            return int(lines[1].split("t=")[1]) / 1000.0
        time.sleep(0.2)
    raise RuntimeError("Đọc DS18B20 lỗi CRC nhiều lần liên tiếp.")


def read_cpu_temp():
    """Phương án dự phòng: đọc cảm biến nhiệt độ có sẵn trong chip của Raspberry Pi (không cần mua DS18B20)."""
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read().strip()) / 1000.0


class RealFanEnv:
    def __init__(self, step_seconds=5.0, max_steps=100, fan_pin=18,
                 safety_temp=70.0, target=T_TARGET, read_temp=read_ds18b20, fan=None):
        self.step_seconds, self.max_steps = step_seconds, max_steps
        self.safety_temp, self.target, self.read_temp = safety_temp, target, read_temp
        if fan is None:
            from gpiozero import PWMOutputDevice          # chỉ import khi chạy trên Pi
            fan = PWMOutputDevice(fan_pin, frequency=100)
        self.fan = fan
        self.observation_space = _Space(N_STATE)
        self.action_space = _Space(N_ACTION)
        self.level, self.t, self.temp = 1, 0, None

    def _set_fan(self, level):
        self.fan.value = DUTY[level]

    def reset(self):
        self.level, self.t = 1, 0
        self._set_fan(self.level)
        time.sleep(self.step_seconds)
        self.temp = self.read_temp()
        return encode(self.temp, self.level, self.target)

    def step(self, a):
        self.level = apply_action(self.level, a)
        self._set_fan(self.level)
        time.sleep(self.step_seconds)
        self.temp = self.read_temp()
        if self.temp >= self.safety_temp:                 # AN TOÀN: quá nóng -> quạt 100%
            self.level = N_LEVEL - 1
            self._set_fan(self.level)
        self.t += 1
        r = reward_fn(self.temp, self.level, self.target)
        done = self.t >= self.max_steps
        return encode(self.temp, self.level, self.target), r, done, {"temp": self.temp}

    def close(self):
        self.fan.value = 1.0                              # thoát chương trình: bật hết quạt cho an toàn
        self.fan.close()


# ----------------------------------------------------------------------
# 4. Q-LEARNING (giống từng dòng với code Taxi trong sách)
# ----------------------------------------------------------------------
def q_learning(env, max_episode=1000, max_steps=100, gamma=0.97, alpha=0.7, epsilon=0.3,
               Q=None, verbose=True, eps_min=None):
    # eps_min=None: epsilon cố định như sách (Taxi). Nếu đặt, epsilon giảm tuyến tính tới eps_min
    # (ý tưởng 'epsilon giảm dần' trong phần DQN của sách).
    eps0 = epsilon
    m = env.observation_space.n
    n = env.action_space.n
    if verbose:
        print("The Q-table will have {} rows and {} columns, resulting in total {} entries".format(m, n, m * n))
    if Q is None:
        Q = np.zeros([m, n])
    rewards = []
    for i in range(max_episode):
        if eps_min is not None:
            epsilon = max(eps_min, eps0 - (eps0 - eps_min) * i / (0.8 * max_episode))
        s = env.reset()
        rtot = 0.0
        for _ in range(max_steps):
            p = np.random.rand()
            # Sách viết "if p > epsilon", nghĩa là khám phá 70% thời gian (ngược ý định epsilon-greedy).
            # Ở đây dùng "p < epsilon": khám phá với xác suất epsilon, khai thác với 1-epsilon.
            if p < epsilon or (not np.any(Q[s, :])):
                a = env.action_space.sample()             # explore
            else:
                a = np.argmax(Q[s, :])                    # exploit
            s_new, r, done, _ = env.step(a)
            Q[s, a] = (1 - alpha) * Q[s, a] + alpha * (r + gamma * np.max(Q[s_new, :]))   # Bellman
            s = s_new
            rtot += r
            if done:
                break
        rewards.append(rtot)
        if verbose and (i + 1) % 100 == 0:
            print("episode {:4d}  reward trung bình 100 episode gần nhất: {:8.1f}".format(
                i + 1, np.mean(rewards[-100:])))
    return Q, rewards


def run_policy(env, policy, episodes=100, max_steps=100):
    """Chạy một chính sách cố định, trả về (reward TB, nhiệt độ TB, mức quạt TB, % thời gian |T-mục tiêu|<=3)."""
    R, T, L, OK = [], [], [], []
    for _ in range(episodes):
        s = env.reset()
        rt = 0.0
        for _ in range(max_steps):
            a = policy(s)
            s, r, done, info = env.step(a)
            rt += r
            T.append(info["temp"])
            L.append(env.level)
            OK.append(abs(info["temp"] - env.target) <= 3.0)
            if done:
                break
        R.append(rt)
    return np.mean(R), np.mean(T), np.mean(L), 100.0 * np.mean(OK)


def fixed_level_policy(env, level):
    def pol(s):
        return 2 if env.level < level else (0 if env.level > level else 1)
    return pol


def thermostat_policy(env, low=-1.0, high=2.0):
    """Luật if-else cố định: nóng hơn mục tiêu +2 thì tăng, mát hơn mục tiêu -1 thì giảm."""
    def pol(s):
        if env.temp > env.target + high:
            return 2
        if env.temp < env.target + low:
            return 0
        return 1
    return pol


# ----------------------------------------------------------------------
# 5. CÁC LỆNH
# ----------------------------------------------------------------------
def cmd_train(args):
    np.random.seed(args.seed)
    env = SimFanEnv(t_amb=args.tamb, t_max0=args.tmax0, t_max3=args.tmax3,
                    target=args.target, seed=args.seed)
    Q, rewards = q_learning(env, args.episodes, 100, args.gamma, args.alpha, args.epsilon,
                            eps_min=args.eps_min)
    np.save(args.out, Q)
    np.save(args.out.replace(".npy", "_rewards.npy"), np.array(rewards))
    print("Đã lưu Q-table vào", args.out)

    # So sánh trên môi trường mô phỏng mới (cùng seed khác)
    ev = SimFanEnv(t_amb=args.tamb, t_max0=args.tmax0, t_max3=args.tmax3,
                   target=args.target, seed=args.seed + 1)
    rows = [("Q-learning (đã học)", run_policy(ev, lambda s: int(np.argmax(Q[s, :]))))]
    rows.append(("Luật if-else (thermostat)", run_policy(ev, thermostat_policy(ev))))
    for lv in range(N_LEVEL):
        rows.append(("Quạt cố định mức %d" % lv, run_policy(ev, fixed_level_policy(ev, lv))))
    print("\n{:28s} {:>10s} {:>8s} {:>8s} {:>12s}".format(
        "Chính sách", "Reward/ep", "T TB", "Mức TB", "% gần mục tiêu"))
    for name, (R, T, L, OK) in rows:
        print("{:28s} {:10.1f} {:8.1f} {:8.2f} {:11.1f}%".format(name, R, T, L, OK))
    print("\nBảng Q (hàng = state, cột = giảm/giữ/tăng) - chính sách học được ở các state:")
    for b in range(N_TEMP):
        line = []
        for lv in range(N_LEVEL):
            s = b * N_LEVEL + lv
            line.append(ACTION_NAME[int(np.argmax(Q[s]))] if np.any(Q[s]) else "  -  ")
        lo = "<%.0f" % (args.target + TEMP_OFFSETS[0]) if b == 0 else (
            ">=%.0f" % (args.target + TEMP_OFFSETS[-1]) if b == N_TEMP - 1 else
            "%.0f-%.0f" % (args.target + TEMP_OFFSETS[b - 1], args.target + TEMP_OFFSETS[b]))
        print("  nhiệt độ {:9s} | quạt mức 0..3: {}".format(lo, " | ".join("%-4s" % x for x in line)))


def cmd_real(args):
    Q = np.load(args.q)
    env = RealFanEnv(step_seconds=args.step, max_steps=10 ** 9, target=args.target,
                     safety_temp=args.safety,
                     read_temp=read_cpu_temp if args.sensor == "cpu" else read_ds18b20)
    eps = args.epsilon if (args.learn and args.policy == "q") else 0.0
    if args.policy == "q":
        choose = lambda s: int(np.argmax(Q[s, :]))
    elif args.policy == "thermostat":
        choose = thermostat_policy(env)
    else:                                              # fixed0..fixed3: so sánh với quạt chạy mức cố định
        choose = fixed_level_policy(env, int(args.policy[-1]))
    t_end = time.time() + args.minutes * 60
    s = env.reset()
    print("Bắt đầu chạy thật %.0f phút. Nhấn Ctrl+C để dừng." % args.minutes)
    try:
        with open(args.log, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["giay", "nhiet_do", "muc_quat", "hanh_dong", "reward", "dau_do_ds18b20"])
            t0 = time.time()
            while time.time() < t_end:
                if args.policy == "q" and (np.random.rand() < eps or not np.any(Q[s, :])):
                    a = env.action_space.sample()
                else:
                    a = choose(s)
                s_new, r, _, info = env.step(a)
                if args.learn and args.policy == "q":     # tiếp tục học khi chạy thật, alpha nhỏ cho đỡ nhiễu
                    Q[s, a] = (1 - args.alpha) * Q[s, a] + args.alpha * (r + args.gamma * np.max(Q[s_new, :]))
                try:                                      # ghi thêm đầu dò ngoài DS18B20 (chỉ để theo dõi)
                    probe = "%.2f" % read_ds18b20(retries=2)
                except Exception:
                    probe = ""
                w.writerow(["%.0f" % (time.time() - t0), "%.2f" % info["temp"], env.level, ACTION_NAME[a], "%.2f" % r, probe])
                f.flush()
                print("t={:5.0f}s  T={:5.1f}°C  đầu dò {}  quạt mức {}  (hành động: {})  reward {:.2f}".format(
                    time.time() - t0, info["temp"], probe or "-", env.level, ACTION_NAME[a], r))
                s = s_new
    except KeyboardInterrupt:
        pass
    finally:
        env.close()
        if args.learn and args.policy == "q":
            np.save(args.q.replace(".npy", "_sau_khi_chay_that.npy"), Q)


def cmd_plot(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if args.log:
        sec, temp, lvl, rew = [], [], [], []
        with open(args.log) as f:
            for row in csv.DictReader(f):
                sec.append(float(row["giay"]))
                temp.append(float(row["nhiet_do"]))
                lvl.append(int(row["muc_quat"]))
                rew.append(float(row["reward"]))
        T = np.array(temp)
        print("Số bước: %d | nhiệt độ TB: %.1f °C | cao nhất: %.1f °C | mức quạt TB: %.2f | "
              "%% thời gian |T - mục tiêu| <= 3 °C: %.1f%% | reward TB/bước: %.2f" % (
                  len(T), T.mean(), T.max(), np.mean(lvl),
                  100.0 * np.mean(np.abs(T - args.target) <= 3.0), np.mean(rew)))
        fig, ax = plt.subplots(2, 1, figsize=(8, 5), sharex=True)
        ax[0].plot(sec, temp)
        ax[0].axhline(args.target, ls="--", c="gray")
        ax[0].set_ylabel("Nhiệt độ (°C)")
        ax[1].step(sec, lvl, where="post")
        ax[1].set_ylabel("Mức quạt")
        ax[1].set_xlabel("Thời gian (giây)")
        fig.tight_layout()
        fig.savefig(args.png, dpi=150)
    else:
        r = np.load(args.rewards)
        k = 20
        avg = np.convolve(r, np.ones(k) / k, mode="valid")
        plt.figure(figsize=(8, 4))
        plt.plot(r, alpha=0.3, label="reward mỗi episode")
        plt.plot(np.arange(k - 1, len(r)), avg, label="trung bình trượt %d episode" % k)
        plt.xlabel("Episode")
        plt.ylabel("Tổng reward")
        plt.legend()
        plt.tight_layout()
        plt.savefig(args.png, dpi=150)
    print("Đã lưu", args.png)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--target", type=float, default=T_TARGET)
        p.add_argument("--gamma", type=float, default=0.97)
        p.add_argument("--alpha", type=float, default=0.7)
        p.add_argument("--epsilon", type=float, default=0.3)

    p1 = sp.add_parser("train")
    common(p1)
    p1.add_argument("--episodes", type=int, default=1000)
    p1.add_argument("--out", default="q_quat.npy")
    p1.add_argument("--seed", type=int, default=0)
    p1.add_argument("--eps_min", type=float, default=None, help="nếu đặt: epsilon giảm dần tới giá trị này")
    p1.add_argument("--tamb", type=float, default=28.0)
    p1.add_argument("--tmax0", type=float, default=70.0)
    p1.add_argument("--tmax3", type=float, default=46.0)
    p1.set_defaults(fn=cmd_train)

    p2 = sp.add_parser("real")
    common(p2)
    p2.set_defaults(alpha=0.1, epsilon=0.05)
    p2.add_argument("--q", default="q_quat.npy")
    p2.add_argument("--minutes", type=float, default=15)
    p2.add_argument("--step", type=float, default=5.0)
    p2.add_argument("--safety", type=float, default=70.0)
    p2.add_argument("--policy", default="q",
                    choices=["q", "thermostat", "fixed0", "fixed1", "fixed2", "fixed3"],
                    help="q = dùng Q-table đã học; còn lại là các chính sách so sánh")
    p2.add_argument("--sensor", default="ds18b20", choices=["ds18b20", "cpu"])
    p2.add_argument("--learn", action="store_true", help="tiếp tục cập nhật Q-table khi chạy thật")
    p2.add_argument("--log", default="log_real.csv")
    p2.set_defaults(fn=cmd_real)

    p3 = sp.add_parser("plot")
    p3.add_argument("--target", type=float, default=T_TARGET)
    p3.add_argument("--log")
    p3.add_argument("--rewards", default="q_quat_rewards.npy")
    p3.add_argument("--png", default="bieu_do.png")
    p3.set_defaults(fn=cmd_plot)

    args = ap.parse_args()
    args.fn(args)
