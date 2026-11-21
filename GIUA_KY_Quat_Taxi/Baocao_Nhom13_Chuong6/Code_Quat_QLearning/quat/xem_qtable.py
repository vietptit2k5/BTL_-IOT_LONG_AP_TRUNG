import numpy as np, fan_qlearning as f
Q = np.load("q_quat.npy"); T = 52
print("Hàng = khoảng nhiệt độ, cột = mức quạt hiện tại 0..3, ô = hành động có Q cao nhất")
for b in range(f.N_TEMP):
    lo = "<%d" % (T+f.TEMP_OFFSETS[0]) if b == 0 else (">=%d" % (T+f.TEMP_OFFSETS[-1]) if b == f.N_TEMP-1 else "%d-%d" % (T+f.TEMP_OFFSETS[b-1], T+f.TEMP_OFFSETS[b]))
    row = [f.ACTION_NAME[int(np.argmax(Q[b*f.N_LEVEL+l]))] for l in range(f.N_LEVEL)]
    print("%-8s" % lo, " | ".join("%-5s" % x for x in row))
print("\nGiá trị Q của 1 state, vd 53-56 °C + quạt mức 1 (giảm, giữ, tăng):")
print(np.round(Q[4*f.N_LEVEL+1], 2))
