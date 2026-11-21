// Logic thuần (không DOM, không Firebase) — kiểm thử bằng: node --test tests/
export const DEFAULT_BAND = [37.3, 37.7];
export const DEFAULT_TARGET = 37.5;
export const BRIDGE_TIMEOUT_MS = 15000;   // Bridge gửi nhịp mỗi 5 s; quá 15 s coi như mất kết nối.
export const LIVE_TIMEOUT_MS = 20000;
export const SAMPLE_TIMEOUT_MS = 30000;  // Số đo cũ hơn: lượt không còn chạy thật.

export const LEVEL_LABEL = { thong_tin: 'Thông tin', canh_bao: 'Cảnh báo', nguy_hiem: 'Nguy hiểm' };
export const SOURCE_LABEL = { truc_tiep: 'Trực tiếp', phat_lai: 'Phát lại', tai_len: 'Lịch sử' };

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

export function fmtTemp(v, digits = 2) {
  return isNum(v) ? `${v.toFixed(digits).replace('.', ',')} °C` : '-- °C';
}

export function fmtNum(v, digits = 2, unit = '') {
  return isNum(v) ? `${v.toFixed(digits).replace('.', ',')}${unit}` : '--';
}

export function fmtPct(v) {
  return isNum(v) ? `${Math.round(v)} %` : '-- %';
}

export function fmtDuration(seconds) {
  if (!isNum(seconds) || seconds < 0) return '--';
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, '0'), ss = String(r).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

export function fmtClock(ts) {
  if (!isNum(ts)) return '--';
  return new Date(ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function fmtDateTime(ts) {
  if (!isNum(ts) || ts <= 0) return '--';
  const d = new Date(ts);
  return `${d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })} ${d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}`;
}

export function ago(ts, now) {
  if (!isNum(ts)) return 'chưa có dữ liệu';
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 60) return `${s} giây trước`;
  if (s < 3600) return `${Math.floor(s / 60)} phút trước`;
  if (s < 86400) return `${Math.floor(s / 3600)} giờ trước`;
  return `${Math.floor(s / 86400)} ngày trước`;
}

/** Tình trạng kết nối từ nhịp bridge và số đo live; now là giờ máy chủ (đã bù lệch đồng hồ). */
export function connectionState(bridge, live, now) {
  const piOnline = !!bridge && isNum(bridge.ts) && now - bridge.ts <= BRIDGE_TIMEOUT_MS;
  const fresh = !!live && isNum(live.bridge_ts) && now - live.bridge_ts <= LIVE_TIMEOUT_MS;
  // Số đo phải còn mới: bridge vẫn gửi nhịp nhưng CSV đứng nghĩa là chương trình điều khiển đã chết.
  const samplesFresh = !!live && isNum(live.ts) && now - live.ts <= SAMPLE_TIMEOUT_MS;
  const claimed = piOnline && fresh && live.trang_thai === 'DANG_CHAY';
  const running = claimed && samplesFresh;
  let label, tone;
  if (!piOnline) { label = 'Pi mất kết nối'; tone = 'bad'; }
  else if (claimed && !samplesFresh) { label = 'Mất dữ liệu lượt (chương trình trên Pi dừng?)'; tone = 'bad'; }
  else if (running) { label = live.nguon === 'phat_lai' ? 'Đang phát lại' : 'Đang chạy'; tone = 'ok'; }
  else { label = 'Pi online · không có lượt chạy'; tone = 'idle'; }
  const stale = claimed && !samplesFresh;
  const short = !piOnline ? 'Mất kết nối' : stale ? 'Mất dữ liệu'
    : running ? (live.nguon === 'phat_lai' ? 'Phát lại' : 'Đang chạy') : 'Online';
  return { piOnline, running, stale, label, short, tone };
}

/** Dòng tiêu đề lớn ở Tổng quan: hộp đang làm gì, bằng lời dễ hiểu. */
export function runHeadline(c, live, hasBatch) {
  if (!c.piOnline) {
    return { title: 'Pi mất kết nối', detail: 'Kiểm tra nguồn và Wi-Fi của Raspberry Pi. Nếu đang chạy, Pi vẫn tự điều khiển cục bộ.', tone: 'bad' };
  }
  if (c.stale) return { title: 'Mất dữ liệu lượt', detail: 'Chương trình điều khiển trên Pi có thể đã dừng.', tone: 'bad' };
  if (c.running) {
    const g = (live && live.giai_doan) || '';
    const tone = g === 'bao_ve' ? 'bad' : (g === 'tay' || g === 'lam_am') ? 'warn' : 'ok';
    return {
      title: (live && live.giai_doan_ten) || 'Đang chạy',
      detail: `${(live && live.bo_dieu_khien) || 'Bộ điều khiển'} · đã chạy ${fmtDuration(live && live.elapsed_s)}`,
      tone,
    };
  }
  return hasBatch
    ? { title: 'Hộp đang nghỉ', detail: 'Mẻ ấp đã sẵn sàng. Bắt đầu một lượt để bật sưởi.', tone: 'idle' }
    : { title: 'Chưa có mẻ ấp', detail: 'Tạo mẻ ấp trước, rồi bắt đầu lượt chạy.', tone: 'idle' };
}

/** Thang nhiệt ở Tổng quan: vị trí % (0–100) của một nhiệt độ trên [lo, hi]. */
export const GAUGE = { lo: 36.5, hi: 39.0, guard: 38.3, stop: 38.8 };
export function gaugePos(v, lo = GAUGE.lo, hi = GAUGE.hi) {
  if (!isNum(v)) return null;
  return Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100));
}

export function trendInfo(v) {
  if (!isNum(v)) return { arrow: '', text: '--', tone: 'flat' };
  const text = `${v >= 0 ? '+' : ''}${fmtNum(v, 2, ' °C/phút')}`;
  if (v > 0.02) return { arrow: '↑', text, tone: 'up' };
  if (v < -0.02) return { arrow: '↓', text, tone: 'down' };
  return { arrow: '→', text, tone: 'flat' };
}

/** Tab điều hướng từ địa chỉ #/ten-tab. */
export const TABS = ['tong-quan', 'dieu-khien', 'bieu-do', 'lich-su'];
export function tabFromHash(hash) {
  const t = String(hash || '').replace(/^#\/?/, '');
  return TABS.includes(t) ? t : TABS[0];
}

export function bandOf(obj) {
  const v = obj && obj.vung_c;
  return Array.isArray(v) && v.length === 2 && isNum(v[0]) && isNum(v[1]) ? v : DEFAULT_BAND;
}

export function bandStatus(temp, band = DEFAULT_BAND) {
  if (!isNum(temp)) return { text: 'Không có số đo', tone: 'idle' };
  if (temp < band[0]) return { text: `Thấp hơn vùng ${fmtNum(band[0] - temp, 2, ' °C')}`, tone: 'warn' };
  if (temp > band[1]) return { text: `Cao hơn vùng ${fmtNum(temp - band[1], 2, ' °C')}`, tone: 'warn' };
  return { text: 'Trong vùng mục tiêu', tone: 'ok' };
}

/** {"000005": {t,T,RH,L,F,g}, ...} -> mảng đã sắp theo t. */
export function samplesToSeries(samples) {
  if (!samples || typeof samples !== 'object') return [];
  return Object.values(samples)
    .filter((s) => s && isNum(s.t) && isNum(s.T))
    .sort((a, b) => a.t - b.t);
}

/** Căn theo thời điểm bắt đầu giữ nhiệt để so sánh các lượt; trả [{x, T}] trong [0, maxS]. */
export function alignOnHold(series, maxS = 600) {
  const start = series.find((s) => s.g === 'giu_nhiet');
  if (!start) return [];
  return series
    .map((s) => ({ x: s.t - start.t, T: s.T }))
    .filter((p) => p.x >= 0 && p.x <= maxS);
}

export function sessionRows(sessions, { includeReplay = false } = {}) {
  if (!sessions || typeof sessions !== 'object') return [];
  return Object.entries(sessions)
    .map(([id, s]) => ({ id, meta: (s && s.meta) || {}, summary: (s && s.summary) || null }))
    // Ẩn mặc định: phiên phát lại và phiên không có giai đoạn giữ nhiệt (log đọc thử/khảo sát).
    .filter((r) => includeReplay || (r.meta.nguon !== 'phat_lai'
      && !(r.summary && r.summary.trang_thai === 'CHUA_CO_GIU_NHIET')))
    .sort((a, b) => (b.meta.bat_dau_ts || 0) - (a.meta.bat_dau_ts || 0));
}

export function alertList(alerts, limit = 30) {
  if (!alerts || typeof alerts !== 'object') return [];
  return Object.entries(alerts)
    .map(([id, a]) => ({ id, ...a }))
    .filter((a) => isNum(a.ts))
    .sort((a, b) => b.ts - a.ts)
    .slice(0, limit);
}

/** Số thông báo chưa đọc (mới hơn lần mở chuông gần nhất) và mức nặng nhất trong số đó. */
export function unreadInfo(list, seenTs) {
  const unread = list.filter((a) => a.ts > (isNum(seenTs) ? seenTs : 0));
  const worst = unread.some((a) => a.muc === 'nguy_hiem') ? 'nguy_hiem'
    : unread.some((a) => a.muc === 'canh_bao') ? 'canh_bao' : unread.length ? 'thong_tin' : null;
  return { count: unread.length, worst, label: unread.length > 9 ? '9+' : String(unread.length) };
}

/** Cảnh báo mới xuất hiện sau lần xem trước (để bật thông báo trình duyệt). */
export function newAlerts(previousIds, list) {
  if (previousIds === null) return [];  // Lần tải đầu: không thông báo lại các cảnh báo cũ.
  return list.filter((a) => !previousIds.has(a.id));
}

// ------------------------------------------------------------------ ấp 3 giai đoạn (khớp me_ap.py)
export const TOTAL_DAYS = 21;
export const STAGES = {
  1: { days: [1, 10], target: 37.8, band: [37.6, 38.0], rh: [60, 60] },
  2: { days: [11, 17], target: 37.5, band: [37.3, 37.7], rh: [55, 55] },
  3: { days: [18, 21], target: 37.2, band: [37.0, 37.4], rh: [65, 70] },
};

export function stageForDay(day) {
  if (!Number.isInteger(day) || day < 1 || day > TOTAL_DAYS) return null;
  return Number(Object.keys(STAGES).find((k) => day >= STAGES[k].days[0] && day <= STAGES[k].days[1]));
}

/** Gộp các mẫu liên tiếp cùng vùng mục tiêu thành dải [x0, x1] để vẽ nền đồ thị. */
export function bandSpans(series, fallback = DEFAULT_BAND) {
  const spans = [];
  series.forEach((s, i) => {
    const band = s.k && STAGES[s.k] ? STAGES[s.k].band : fallback;
    const x1 = i + 1 < series.length ? series[i + 1].t : s.t;
    const last = spans[spans.length - 1];
    if (last && last.band[0] === band[0] && last.band[1] === band[1]) last.x1 = x1;
    else spans.push({ x0: s.t, x1, band });
  });
  return spans;
}

export function lichText(lich) {
  if (!lich || lich.co_me !== true) return 'Chưa có mẻ ấp';
  return `Ngày ${lich.ngay}/${TOTAL_DAYS} · Giai đoạn ${lich.giai_doan} · mốc ${fmtNum(lich.muc_tieu_c, 1, ' °C')}`;
}

export function rhAdvice(rh, recommended) {
  if (!Array.isArray(recommended)) return { text: '--', tone: 'idle' };
  const rec = recommended[0] === recommended[1] ? `${recommended[0]} %` : `${recommended[0]}–${recommended[1]} %`;
  if (!isNum(rh)) return { text: `Khuyến nghị ${rec} · chưa có số đo ẩm`, tone: 'idle' };
  if (rh < recommended[0] - 5) return { text: `Khuyến nghị ${rec} · hiện ${Math.round(rh)} % (thấp)`, tone: 'warn' };
  if (rh > recommended[1] + 5) return { text: `Khuyến nghị ${rec} · hiện ${Math.round(rh)} % (cao)`, tone: 'warn' };
  return { text: `Khuyến nghị ${rec} · hiện ${Math.round(rh)} %`, tone: 'ok' };
}

/** Độ ẩm hiển thị: ưu tiên số trong lượt đang chạy, nếu không thì từ do_am.py (dịch vụ nền). */
export function currentRh(live, doAm, now) {
  if (live && isNum(live.do_am_pct) && isNum(live.bridge_ts) && now - live.bridge_ts <= LIVE_TIMEOUT_MS) {
    return { value: live.do_am_pct, source: 'luot', note: 'trong lượt đang chạy' };
  }
  if (doAm && isNum(doAm.bridge_ts) && now - doAm.bridge_ts <= 40000 && doAm.con_cap_nhat) {
    if (isNum(doAm.do_am_pct)) {
      const rate = isNum(doAm.ty_le_ok_pct) ? ` · đọc tốt ${Math.round(doAm.ty_le_ok_pct)} %` : '';
      return { value: doAm.do_am_pct, source: 'cam_bien', note: `DHT11 ${ago(doAm.ts_doc_ok_cuoi, now)}${rate}` };
    }
    return { value: null, source: 'loi', note: doAm.loi_cuoi || 'DHT11 chưa đọc được' };
  }
  return { value: null, source: null, note: 'Chưa có số đo độ ẩm' };
}

const DAY_RESULT = {
  DA_DOI: 'Pi đã đổi ngày; RL chuyển sang mốc mới trong ≤ 5 giây.',
  KHONG_HOP_LE: 'Ngày không hợp lệ (phải 1–21).',
  BO_QUA_LENH_CU: 'Lệnh quá cũ nên Pi bỏ qua.',
};

export function dayCommandStatus(cmd) {
  if (!cmd || typeof cmd !== 'object') return { text: 'Chưa đổi ngày từ app.', pending: false };
  if (cmd.da_xu_ly !== true) return { text: `Đã gửi yêu cầu ngày ${cmd.ngay}, đang chờ Pi…`, pending: true };
  const r = cmd.ket_qua || '';
  const text = DAY_RESULT[r] || r;
  return { text: `Ngày ${cmd.ngay} (${cmd.yeu_cau_boi || '?'}, ${fmtDateTime(cmd.xu_ly_ts)}): ${text}`, pending: false };
}

// ------------------------------------------------------------------ tạo mẻ / bắt đầu lượt từ app
export const RUN_MINUTES = [10, 20, 30, 45, 60];
export const DEMO_SPEEDS = { 86400: 'Thời gian thật', 300: 'Demo: 1 ngày = 5 phút', 120: 'Demo: 1 ngày = 2 phút', 60: 'Demo: 1 ngày = 1 phút' };

const COMMAND_RESULT = {
  DA_TAO: 'Pi đã tạo mẻ mới.',
  DA_KET_THUC: 'Pi đã kết thúc mẻ (file lịch được lưu lại).',
  KHONG_CO_ME: 'Không có mẻ nào để kết thúc.',
  KHONG_HOP_LE: 'Tham số không hợp lệ.',
  BO_QUA_LENH_CU: 'Lệnh quá cũ nên Pi bỏ qua.',
  DA_AP_DUNG: 'Pi đã áp dụng lệnh chỉnh tay.',
  DA_TRA_VE: 'Đã trả quyền cho bộ điều khiển tự động.',
};

/** Trạng thái lệnh me_ap / luot: đang chờ Pi, hoặc kết quả đã xử lý (kể cả lý do từ chối). */
export function commandStatus(cmd, idle = 'Chưa gửi lệnh.') {
  if (!cmd || typeof cmd !== 'object') return { text: idle, pending: false, tone: 'idle' };
  if (cmd.da_xu_ly !== true) return { text: 'Đã gửi, đang chờ Pi kiểm tra…', pending: true, tone: 'idle' };
  const r = String(cmd.ket_qua || '');
  let text = COMMAND_RESULT[r] || r;
  let tone = 'ok';
  if (r.startsWith('DA_BAT_DAU')) text = 'Pi đã kiểm tra an toàn và bắt đầu lượt.';
  else if (r.startsWith('TU_CHOI:')) { text = `Pi từ chối: ${r.slice(8).trim()}.`; tone = 'warn'; }
  else if (r.startsWith('LOI_KHOI_DONG')) { text = `Lỗi khởi động: ${r.slice(14)}`; tone = 'bad'; }
  else if (r === 'KHONG_HOP_LE' || r === 'BO_QUA_LENH_CU' || r === 'KHONG_CO_ME') tone = 'warn';
  return { text: `${fmtDateTime(cmd.xu_ly_ts)} · ${text}`, pending: false, tone };
}

/** Nút "Bắt đầu lượt": bấm được khi nào, nếu không thì vì sao. Pi vẫn tự kiểm tra lại mọi điều kiện. */
/** Danh sách điều kiện (để hiện dạng ✓/○) + lý do gộp cho dòng trạng thái. */
function gate(checks) {
  const missing = checks.filter((c) => !c.ok).map((c) => c.need);
  return { ok: missing.length === 0, reason: missing.length ? `Cần: ${missing.join(' · ')}` : '', checks };
}

export function canStartRun({ piOnline, running, hasBatch, ack, pending }) {
  return gate([
    { label: 'Pi đang online', need: 'Pi online', ok: !!piOnline },
    { label: 'Không có lượt khác đang chạy', need: 'không có lượt đang chạy', ok: !running },
    { label: 'Đã có mẻ ấp', need: 'đã tạo mẻ ấp', ok: !!hasBatch },
    { label: 'Đã xác nhận có người ở cạnh hộp', need: 'tích xác nhận có người ở cạnh hộp', ok: !!ack },
    ...(pending ? [{ label: 'Lệnh trước đã xử lý xong', need: 'chờ lệnh trước xử lý xong', ok: false }] : []),
  ]);
}

// ---- chỉnh tay: chỉ 9 cặp (bóng, quạt) đã khảo sát = 9 hành động của Q-table; bóng bật thì quạt không tắt.
export const MANUAL_LAMP = [0, 25, 50, 75, 100];
export const MANUAL_FAN = [75, 100];
export const MANUAL_SECONDS = { 60: '1 phút', 120: '2 phút', 300: '5 phút' };
export const isManualPair = (lamp, fan) => MANUAL_LAMP.includes(lamp) && MANUAL_FAN.includes(fan) && !(lamp === 100 && fan === 100);
/** Lượt ap_trung đã vào giữ nhiệt (pha ap_ngayNN_gdK...): làm ấm và chương trình khác không nhận lệnh tay. */
export const isHoldPhase = (pha) => /^ap_ngay\d{2}_gd[123]/.test(String(pha || ''));

/** Lệnh tay đang có hiệu lực trên Pi? Dựa vào phản hồi DA_AP_DUNG + het_han_ms (đồng hồ máy chủ). */
export function manualState(cmd, now) {
  const on = !!cmd && cmd.da_xu_ly === true && cmd.ket_qua === 'DA_AP_DUNG' && isNum(cmd.het_han_ms) && cmd.het_han_ms > now;
  if (!on) return { active: false, text: 'RL / thermostat đang điều khiển.' };
  const left = Math.ceil((cmd.het_han_ms - now) / 1000);
  const mmss = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
  return { active: true, left, text: `Đang chỉnh tay: bóng ${cmd.bong} %, quạt ${cmd.quat} % · còn ${mmss} (${cmd.yeu_cau_boi || '?'})` };
}

/** Nút "Áp dụng chỉnh tay": bấm được khi nào. Pi vẫn tự kiểm tra lại. */
export function canManual({ piOnline, running, pha, pending, lamp, fan }) {
  return gate([
    { label: 'Pi đang online', need: 'Pi online', ok: !!piOnline },
    { label: 'Có lượt đang chạy', need: 'có lượt đang chạy', ok: !!running },
    ...(running ? [{ label: 'Lượt ap_trung đã qua làm ấm', need: 'lượt ap_trung đã qua làm ấm', ok: isHoldPhase(pha) }] : []),
    ...(pending ? [{ label: 'Lệnh trước đã xử lý xong', need: 'chờ lệnh trước xử lý xong', ok: false }] : []),
    { label: 'Cặp bóng/quạt đã khảo sát', need: 'cặp bóng/quạt đã khảo sát (bóng 100 % chỉ đi với quạt 75 %)', ok: isManualPair(lamp, fan) },
  ]);
}

const STOP_RESULT = {
  KHONG_CO_LUOT_DANG_CHAY: 'Không có lượt nào đang chạy.',
  MO_PHONG_KHONG_GUI_TIN_HIEU: 'Đang phát lại/mô phỏng: không gửi tín hiệu tới phần cứng.',
  KHONG_TIM_THAY_TIEN_TRINH: 'Không tìm thấy chương trình điều khiển đang ghi dữ liệu.',
  BO_QUA_LENH_CU: 'Lệnh quá cũ nên Pi bỏ qua.',
};

export function stopStatus(cmd) {
  if (!cmd || typeof cmd !== 'object') return { text: 'Chưa gửi lệnh dừng nào.', pending: false };
  if (cmd.value === true) return { text: `Đã gửi lệnh dừng (${cmd.by || '?'}), đang chờ Pi xử lý…`, pending: true };
  const r = cmd.ket_qua;
  if (!r) return { text: 'Chưa gửi lệnh dừng nào.', pending: false };
  const text = r.startsWith('DA_GUI_SIGTERM') ? 'Pi đã tắt bóng, tắt quạt và dừng lượt chạy.' : (STOP_RESULT[r] || r);
  return { text: `Lần gần nhất (${fmtDateTime(cmd.xu_ly_ts)}): ${text}`, pending: false };
}

// ------------------------------------------------------------------ so sánh 2 lượt
export const METRICS = [
  { key: 'mae_c', label: 'Sai số trung bình (MAE)', fmt: (v) => fmtNum(v, 3, ' °C'), better: 'low' },
  { key: 'trong_vung_pct', label: 'Thời gian trong vùng', fmt: (v) => fmtNum(v, 1, ' %'), better: 'high' },
  { key: 'do_lech_chuan_c', label: 'Độ lệch chuẩn', fmt: (v) => fmtNum(v, 3, ' °C'), better: 'low' },
  { key: 'so_lan_doi_muc', label: 'Số lần đổi mức', fmt: (v) => (isNum(v) ? String(v) : '--'), better: 'low' },
  { key: 'lam_am_s', label: 'Thời gian làm ấm', fmt: (v) => fmtDuration(v), better: 'low' },
];

/** Bảng chỉ số 2 lượt cạnh nhau; win = lượt tốt hơn ở chỉ số đó (null nếu hòa hoặc thiếu số). */
export function compareMetrics(a, b) {
  return METRICS.map((m) => {
    const va = a && a[m.key];
    const vb = b && b[m.key];
    let win = null;
    if (isNum(va) && isNum(vb) && va !== vb) win = (m.better === 'low' ? va < vb : va > vb) ? 'a' : 'b';
    return { key: m.key, label: m.label, a: m.fmt(va), b: m.fmt(vb), win };
  });
}
