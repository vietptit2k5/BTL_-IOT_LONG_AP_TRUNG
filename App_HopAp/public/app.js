import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import {
  getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';
import {
  getDatabase, ref, onValue, query, orderByKey, limitToLast, get, set, serverTimestamp,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-database.js';
import { firebaseConfig } from './firebase-config.js';
import * as L from './logic.js';

const ROOT = 'hop_ap_01';
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getDatabase(app);
const $ = (id) => document.getElementById(id);

const state = {
  live: null, bridge: null, offset: 0, stopCmd: null,
  alertIds: null, sessions: null, historySig: '',
  selected: [], autoSelected: false, sampleCache: new Map(),
  samplesSid: null, series: [], range: 600,
  unsubs: [], samplesUnsub: null, confirmTimer: null,
  lich: null, dayCmd: null, dayConfirmTimer: null, dayInputTouched: false, doAm: null,
  batchCmd: null, runCmd: null, tayCmd: null,
};
const serverNow = () => Date.now() + state.offset;

// ------------------------------------------------------------------ màu & đồ thị
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const bandPlugin = {
  id: 'band',
  beforeDatasetsDraw(chart, _args, opts) {
    if (!opts) return;
    // spans: dải vùng mục tiêu đổi theo giai đoạn ấp; không có thì một dải cố định.
    const list = opts.spans && opts.spans.length ? opts.spans : (opts.band ? [{ band: opts.band }] : []);
    const { ctx, chartArea: a, scales: { x, y } } = chart;
    ctx.save();
    ctx.fillStyle = opts.color;
    for (const s of list) {
      const left = s.x0 == null ? a.left : Math.max(a.left, x.getPixelForValue(s.x0));
      const right = s.x1 == null ? a.right : Math.min(a.right, x.getPixelForValue(s.x1));
      const top = Math.max(a.top, y.getPixelForValue(s.band[1]));
      const bottom = Math.min(a.bottom, y.getPixelForValue(s.band[0]));
      if (right > left && bottom > top) ctx.fillRect(left, top, right - left, bottom - top);
    }
    ctx.restore();
  },
};

const charts = {};

function baseOptions({ yTitle, yMin, yMax, suggested = true, legend = false }) {
  const grid = { color: css('--grid') };
  const ticks = { color: css('--muted') };
  return {
    responsive: true, maintainAspectRatio: false, animation: false, parsing: false, normalized: true,
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
    plugins: {
      legend: { display: legend, labels: { color: css('--text'), boxWidth: 12 } },
      tooltip: { callbacks: { title: (items) => (items.length ? L.fmtDuration(items[0].parsed.x) : '') } },
      band: { band: null, color: css('--chart-band') },
    },
    scales: {
      x: { type: 'linear', grid, ticks: { ...ticks, maxTicksLimit: 7, callback: (v) => L.fmtDuration(v) } },
      y: {
        grid, ticks, title: { display: !!yTitle, text: yTitle, color: css('--muted') },
        ...(suggested ? { suggestedMin: yMin, suggestedMax: yMax } : { min: yMin, max: yMax }),
      },
    },
  };
}

function lineDataset(label, color, extra = {}) {
  return { label, data: [], borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, ...extra };
}

function buildCharts() {
  if (!window.Chart) return;
  Object.values(charts).forEach((c) => c.destroy());
  const tempOpts = baseOptions({ yTitle: '°C', yMin: 37.0, yMax: 38.0 });
  tempOpts.plugins.tooltip.callbacks.label = (c) => ` ${L.fmtTemp(c.parsed.y, 3)}`;
  charts.temp = new Chart($('temp-chart'), {
    type: 'line', data: { datasets: [lineDataset('Nhiệt độ', css('--chart-temp'))] },
    options: tempOpts, plugins: [bandPlugin],
  });
  const pwmOpts = baseOptions({ yTitle: '% lệnh', yMin: 0, yMax: 100, suggested: false, legend: true });
  pwmOpts.plugins.tooltip.callbacks.label = (c) => ` ${c.dataset.label}: ${L.fmtPct(c.parsed.y)}`;
  charts.pwm = new Chart($('pwm-chart'), {
    type: 'line',
    data: { datasets: [
      lineDataset('Bóng', css('--chart-lamp'), { stepped: true }),
      lineDataset('Quạt', css('--chart-fan'), { stepped: true, borderDash: [5, 3] }),
    ] },
    options: pwmOpts,
  });
  const cmpOpts = baseOptions({ yTitle: '°C', yMin: 37.0, yMax: 38.0, legend: true });
  cmpOpts.scales.x.min = 0;
  cmpOpts.scales.x.max = 600;
  cmpOpts.plugins.tooltip.callbacks.label = (c) => ` ${c.dataset.label}: ${L.fmtTemp(c.parsed.y, 3)}`;
  charts.compare = new Chart($('compare-chart'), {
    type: 'line', data: { datasets: [] }, options: cmpOpts, plugins: [bandPlugin],
  });
  renderLiveChart();
  renderCompare();
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#1c1917' : '#b45309';
  try { localStorage.setItem('hop-ap-theme', theme); } catch (_e) { /* chế độ riêng tư: chỉ không nhớ lựa chọn */ }
  if (charts.temp) buildCharts();
}
$('theme').addEventListener('click', () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});
document.querySelector('meta[name="theme-color"]').content =
  document.documentElement.dataset.theme === 'dark' ? '#1c1917' : '#b45309';

// ------------------------------------------------------------------ đăng nhập
const AUTH_ERRORS = {
  'auth/invalid-credential': 'Sai email hoặc mật khẩu.',
  'auth/invalid-email': 'Email không hợp lệ.',
  'auth/too-many-requests': 'Thử sai quá nhiều lần, hãy đợi một lúc.',
  'auth/network-request-failed': 'Không có kết nối mạng.',
};

$('login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('login-error').textContent = '';
  try {
    await signInWithEmailAndPassword(auth, $('email').value.trim(), $('password').value);
  } catch (error) {
    $('login-error').textContent = AUTH_ERRORS[error.code] || `Không đăng nhập được (${error.code || error.message}).`;
  }
});

$('logout').addEventListener('click', () => signOut(auth));

onAuthStateChanged(auth, (user) => {
  const signedIn = !!user;
  $('login-view').hidden = signedIn;
  $('app-view').hidden = !signedIn;
  $('logout').hidden = !signedIn;
  stopListening();
  if (signedIn) {
    $('password').value = '';
    if (!charts.temp) buildCharts();
    startListening();
  } else {
    setChip('Chưa đăng nhập', 'idle');
  }
});

// ------------------------------------------------------------------ đăng ký nghe dữ liệu
function listen(path, cb, q) {
  const target = q || ref(db, path);
  state.unsubs.push(onValue(target, (snap) => cb(snap.val()), (error) => {
    console.error(path, error);
    if (String(error.code || '').includes('permission')) setChip('Không có quyền đọc dữ liệu', 'bad');
  }));
}

function startListening() {
  listen('.info/serverTimeOffset', (v) => { state.offset = Number(v) || 0; });
  listen(`${ROOT}/trang_thai/bridge`, (v) => { state.bridge = v; renderStatus(); });
  listen(`${ROOT}/live`, (v) => { state.live = v; renderLive(); });
  listen(`${ROOT}/commands/stop`, (v) => { state.stopCmd = v; renderStop(); });
  listen(`${ROOT}/lich`, (v) => { state.lich = v; renderLich(); });
  listen(`${ROOT}/do_am`, (v) => { state.doAm = v; renderHumidity(); renderLich(); });
  listen(`${ROOT}/commands/ngay_ap`, (v) => { state.dayCmd = v; renderLich(); });
  listen(`${ROOT}/commands/me_ap`, (v) => { state.batchCmd = v; renderControls(); });
  listen(`${ROOT}/commands/luot`, (v) => { state.runCmd = v; renderControls(); });
  listen(`${ROOT}/commands/tay`, (v) => { state.tayCmd = v; renderControls(); });
  listen(`${ROOT}/alerts`, renderAlerts, query(ref(db, `${ROOT}/alerts`), orderByKey(), limitToLast(30)));
  listen(`${ROOT}/sessions`, (v) => { state.sessions = v; renderHistory(); });
}

function stopListening() {
  state.unsubs.forEach((u) => u());
  state.unsubs = [];
  if (state.samplesUnsub) state.samplesUnsub();
  state.samplesUnsub = null;
  state.samplesSid = null;
  state.alertIds = null;
}

function followSession(sid) {
  if (sid === state.samplesSid) return;
  if (state.samplesUnsub) state.samplesUnsub();
  state.samplesSid = sid;
  state.series = [];
  state.samplesUnsub = null;
  if (!sid) { renderLiveChart(); return; }
  const q = query(ref(db, `${ROOT}/sessions/${sid}/samples`), orderByKey(), limitToLast(480));
  state.samplesUnsub = onValue(q, (snap) => {
    state.series = L.samplesToSeries(snap.val());
    renderLiveChart();
  });
}

// ------------------------------------------------------------------ hiển thị
function setChip(text, tone) {
  const chip = $('conn');
  chip.textContent = text;
  chip.className = `chip ${tone}`;
}

function connection() {
  return L.connectionState(state.bridge, state.live, serverNow());
}

function renderStatus() {
  const c = connection();
  setChip(c.label, c.tone);
  const live = state.live;
  $('updated').textContent = live && live.ts
    ? `Đo lúc ${L.fmtClock(live.ts)} · ${L.ago(live.ts, serverNow())}` : 'Chưa có số đo';
  document.querySelector('.now').classList.toggle('stale', !c.running);
  renderStop();
  renderDayControl();
  renderControls();
}

function renderLive() {
  const live = state.live || {};
  const band = L.bandOf(live);
  $('temp').textContent = L.fmtTemp(live.nhiet_c);
  const b = L.bandStatus(live.nhiet_c, band);
  $('band').textContent = b.text;
  $('band').className = `badge ${b.tone}`;
  const trend = live.xu_huong_c_phut;
  $('trend').textContent = typeof trend === 'number' ? `${trend >= 0 ? '+' : ''}${L.fmtNum(trend, 2, ' °C/phút')}` : '--';
  renderHumidity();
  $('lamp').textContent = L.fmtPct(live.bong_pct);
  $('fan').textContent = L.fmtPct(live.quat_pct);
  $('phase').textContent = live.giai_doan_ten || '--';
  $('controller').textContent = live.bo_dieu_khien || '--';
  $('elapsed').textContent = L.fmtDuration(live.elapsed_s);
  $('session-name').textContent = live.phien ? `${live.phien}${live.nguon === 'phat_lai' ? ' (phát lại)' : ''}` : '--';
  $('band-note').textContent = `Vùng mục tiêu ${L.fmtNum(band[0], 1)}–${L.fmtNum(band[1], 1)} °C. `
    + '% bóng/quạt là mức lệnh PWM, không phải công suất đo được.';
  followSession(live.phien || null);
  renderLich();
  renderStatus();
}

function renderLiveChart() {
  if (!charts.temp) return;
  const series = state.series;
  const last = series.length ? series[series.length - 1].t : 0;
  const min = state.range > 0 ? Math.max(0, last - state.range) : (series.length ? series[0].t : 0);
  const shown = series.filter((s) => s.t >= min);
  charts.temp.data.datasets[0].data = shown.map((s) => ({ x: s.t, y: s.T }));
  charts.temp.options.plugins.band.band = L.bandOf(state.live);
  charts.temp.options.plugins.band.spans = L.bandSpans(shown, L.bandOf(state.live));
  charts.pwm.data.datasets[0].data = shown.filter((s) => typeof s.L === 'number').map((s) => ({ x: s.t, y: s.L }));
  charts.pwm.data.datasets[1].data = shown.filter((s) => typeof s.F === 'number').map((s) => ({ x: s.t, y: s.F }));
  for (const c of [charts.temp, charts.pwm]) {
    c.options.scales.x.min = shown.length ? min : undefined;
    c.options.scales.x.max = shown.length ? last : undefined;
    c.update('none');
  }
  $('chart-empty').hidden = series.length > 0;
}

document.querySelectorAll('.seg button').forEach((btn) => btn.addEventListener('click', () => {
  state.range = Number(btn.dataset.range);
  document.querySelectorAll('.seg button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
  renderLiveChart();
}));

function renderAlerts(value) {
  const list = L.alertList(value, 30);
  const fresh = L.newAlerts(state.alertIds, list);
  state.alertIds = new Set(list.map((a) => a.id));
  const ul = $('alerts');
  ul.replaceChildren();
  if (!list.length) {
    const li = document.createElement('li');
    li.className = 'muted';
    li.textContent = 'Chưa có cảnh báo.';
    ul.append(li);
  }
  for (const a of list) {
    const li = document.createElement('li');
    li.className = a.muc || '';
    const meta = document.createElement('div');
    meta.className = 'meta';
    const level = document.createElement('strong');
    level.textContent = L.LEVEL_LABEL[a.muc] || a.muc || '';
    const when = document.createElement('span');
    when.textContent = `${L.fmtDateTime(a.ts)}:${new Date(a.ts).getSeconds().toString().padStart(2, '0')}`;
    meta.append(level, when);
    const body = document.createElement('div');
    body.textContent = a.noi_dung || a.loai;
    li.append(meta, body);
    ul.append(li);
  }
  fresh.filter((a) => a.muc !== 'thong_tin' || a.loai === 'KET_THUC').forEach(notify);
}

function renderStop() {
  const s = L.stopStatus(state.stopCmd);
  $('stop-status').textContent = s.text;
  const btn = $('stop');
  const allowed = connection().running && !s.pending;
  btn.disabled = !allowed;
  if (!allowed) resetConfirm();
}

function resetConfirm() {
  clearTimeout(state.confirmTimer);
  state.confirmTimer = null;
  const btn = $('stop');
  btn.classList.remove('confirm');
  btn.textContent = 'Dừng lượt đang chạy';
}

$('stop').addEventListener('click', async () => {
  const btn = $('stop');
  if (!state.confirmTimer) {
    btn.classList.add('confirm');
    btn.textContent = 'Bấm lần nữa trong 5 giây để xác nhận DỪNG';
    state.confirmTimer = setTimeout(resetConfirm, 5000);
    return;
  }
  resetConfirm();
  btn.disabled = true;
  try {
    await set(ref(db, `${ROOT}/commands/stop`), {
      value: true, ts: serverTimestamp(), by: auth.currentUser.email,
    });
  } catch (error) {
    $('stop-status').textContent = `Không gửi được lệnh dừng: ${error.code || error.message}`;
    btn.disabled = false;
  }
});

// ------------------------------------------------------------------ độ ẩm (chỉ giám sát)
function renderHumidity() {
  const rh = L.currentRh(state.live, state.doAm, serverNow());
  $('rh').textContent = L.fmtPct(rh.value);
  $('rh').title = rh.note;
  $('rh-note').textContent = rh.note;
}

// ------------------------------------------------------------------ lịch ấp 21 ngày
function renderLich() {
  const lich = state.lich;
  const has = !!lich && lich.co_me === true;
  $('lich-day').textContent = has ? `Ngày ${lich.ngay}/${L.TOTAL_DAYS}` : 'Chưa có mẻ ấp';
  $('lich-target').textContent = has
    ? `Mốc ${L.fmtNum(lich.muc_tieu_c, 1, ' °C')} · vùng ${L.fmtNum(lich.vung_c[0], 1)}–${L.fmtNum(lich.vung_c[1], 1)} °C`
      + (lich.het_lich ? ' · đã hết 21 ngày' : '')
    : 'Chọn ngày bên dưới để tạo mẻ (Pi phải online).';
  $('lich-stage').textContent = has ? `Giai đoạn ${lich.giai_doan}` : '--';
  $('lich-stage').className = `badge ${has ? 'ok' : 'idle'}`;
  const marker = $('lich-marker');
  marker.hidden = !has;
  if (has) marker.style.left = `${((lich.ngay - 0.5) / L.TOTAL_DAYS) * 100}%`;
  $('lich-speed').textContent = has && lich.rut_gon
    ? `Demo: 1 ngày = ${lich.giay_moi_ngay} s · ${lich.tam_dung ? 'lịch đang dừng, chạy khi RL giữ nhiệt' : 'lịch đang chạy'}`
    : (has ? 'Thời gian thật' : '');
  const rh = L.rhAdvice(L.currentRh(state.live, state.doAm, serverNow()).value, has ? lich.do_am_khuyen_nghi : null);
  $('lich-rh').textContent = `Độ ẩm: ${rh.text}`;
  $('lich-rh').className = `badge ${rh.tone} small`;
  if (has && !state.dayInputTouched && document.activeElement !== $('day-input')) $('day-input').value = lich.ngay;
  $('day-status').textContent = L.dayCommandStatus(state.dayCmd).text;
  renderDayControl();
}

function renderDayControl() {
  const pending = L.dayCommandStatus(state.dayCmd).pending;
  const day = Number($('day-input').value);
  const ok = connection().piOnline && !pending && L.stageForDay(day) !== null;
  $('day-send').disabled = !ok;
  if (!ok) resetDayConfirm();
}

function resetDayConfirm() {
  clearTimeout(state.dayConfirmTimer);
  state.dayConfirmTimer = null;
  $('day-send').classList.remove('confirm');
  $('day-send').textContent = 'Đổi ngày';
}

$('day-input').addEventListener('input', () => { state.dayInputTouched = true; resetDayConfirm(); renderDayControl(); });
document.querySelectorAll('.chipbtn[data-day]').forEach((b) => b.addEventListener('click', () => {
  $('day-input').value = b.dataset.day;
  state.dayInputTouched = true;
  resetDayConfirm();
  renderDayControl();
}));

$('day-send').addEventListener('click', async () => {
  const day = Number($('day-input').value);
  const stage = L.stageForDay(day);
  if (stage === null) return;
  const btn = $('day-send');
  if (!state.dayConfirmTimer) {
    btn.classList.add('confirm');
    btn.textContent = `Bấm lần nữa: ngày ${day} → giai đoạn ${stage}, mốc ${L.fmtNum(L.STAGES[stage].target, 1, ' °C')}`;
    state.dayConfirmTimer = setTimeout(resetDayConfirm, 5000);
    return;
  }
  resetDayConfirm();
  btn.disabled = true;
  try {
    await set(ref(db, `${ROOT}/commands/ngay_ap`), {
      ngay: day, ts: serverTimestamp(), by: auth.currentUser.email, da_xu_ly: false,
    });
    state.dayInputTouched = false;
  } catch (error) {
    $('day-status').textContent = `Không gửi được: ${error.code || error.message}`;
    btn.disabled = false;
  }
});

// ------------------------------------------------------------------ tạo mẻ / kết thúc mẻ / bắt đầu lượt
/** Nút bấm 2 lần trong 5 giây mới gửi lệnh. Trả hàm reset để gọi khi nút bị khóa. */
function twoStep(btn, idleText, confirmText, statusEl, action) {
  if (!btn || !statusEl) return () => {};  // HTML cũ trong cache: không làm hỏng cả app.
  let timer = null;
  const reset = () => {
    clearTimeout(timer);
    timer = null;
    btn.classList.remove('confirm');
    btn.textContent = idleText;
  };
  btn.addEventListener('click', async () => {
    if (!timer) {
      btn.classList.add('confirm');
      btn.textContent = confirmText();
      timer = setTimeout(reset, 5000);
      return;
    }
    reset();
    btn.disabled = true;
    try {
      await action();
    } catch (error) {
      statusEl.textContent = `Không gửi được: ${error.code || error.message}`;
    }
    renderControls();
  });
  return reset;
}

function sendCommand(name, data) {
  return set(ref(db, `${ROOT}/commands/${name}`),
    { ...data, ts: serverTimestamp(), by: auth.currentUser.email, da_xu_ly: false });
}

const hasBatch = () => !!state.lich && state.lich.co_me === true;
const speedLabel = () => L.DEMO_SPEEDS[$('batch-speed').value];
const ctrlLabel = () => ($('run-ctrl').value === 'rl' ? 'Q-learning' : 'Thermostat');

const resetCreate = twoStep($('batch-create'), 'Tạo mẻ mới',
  () => `Bấm lần nữa: mẻ từ ngày ${$('batch-day').value}, ${speedLabel()}${hasBatch() ? ' (thay mẻ hiện tại)' : ''}`,
  $('batch-status'),
  () => sendCommand('me_ap', { hanh_dong: 'tao', ngay: Number($('batch-day').value), giay_moi_ngay: Number($('batch-speed').value) }));
const resetEnd = twoStep($('batch-end'), 'Kết thúc mẻ', () => 'Bấm lần nữa để kết thúc mẻ', $('batch-status'),
  () => sendCommand('me_ap', { hanh_dong: 'ket_thuc' }));
const resetRun = twoStep($('run-start'), 'Bắt đầu lượt',
  () => `Bấm lần nữa: ${ctrlLabel()} ${$('run-min').value} phút — bạn đang ở cạnh hộp`, $('run-status'),
  async () => {
    await sendCommand('luot', { hanh_dong: 'bat_dau', bo_dieu_khien: $('run-ctrl').value,
      phut: Number($('run-min').value), co_nguoi: $('run-ack').checked });
    $('run-ack').checked = false;  // Mỗi lượt phải xác nhận lại.
  });

const tayPick = () => ({ lamp: Number($('tay-bong')?.value), fan: Number($('tay-quat')?.value),
  seconds: Number($('tay-han')?.value) });
const resetTay = twoStep($('tay-apply'), 'Áp dụng chỉnh tay',
  () => { const p = tayPick(); return `Bấm lần nữa: bóng ${p.lamp} %, quạt ${p.fan} % trong ${L.MANUAL_SECONDS[p.seconds]}`; },
  $('tay-status'),
  () => { const p = tayPick(); return sendCommand('tay', { hanh_dong: 'dat', bong: p.lamp, quat: p.fan, thoi_han_s: p.seconds }); });
$('tay-return')?.addEventListener('click', async () => {
  $('tay-return').disabled = true;
  try {
    await sendCommand('tay', { hanh_dong: 'tra_ve' });
  } catch (error) {
    $('tay-status').textContent = `Không gửi được: ${error.code || error.message}`;
  }
  renderControls();
});

function renderManual(c) {
  if (!$('tay-apply')) return;  // HTML cũ trong cache.
  const cmd = L.commandStatus(state.tayCmd, 'Chưa chỉnh tay.');
  const live = state.live || {};
  const m = L.manualState(state.tayCmd, serverNow());
  const active = m.active && c.running && L.isHoldPhase(live.pha);
  const p = tayPick();
  const fan100 = $('tay-quat').querySelector('option[value="100"]');
  fan100.disabled = p.lamp === 100;  // 100/100 không có trong 9 hành động đã khảo sát.
  if (fan100.disabled && $('tay-quat').value === '100') { $('tay-quat').value = '75'; p.fan = 75; }
  const gate = L.canManual({ piOnline: c.piOnline, running: c.running, pha: live.pha, pending: cmd.pending, ...p });
  $('tay-apply').disabled = !gate.ok;
  if (!gate.ok) resetTay();
  $('tay-return').disabled = !(active && c.piOnline && !cmd.pending);
  $('tay-active').textContent = active ? m.text : (c.running ? 'RL / thermostat đang điều khiển.' : '--');
  $('tay-active').className = `small ${active ? 'warn-text' : 'muted'}`;
  $('tay-status').textContent = gate.ok || cmd.pending ? cmd.text : `${cmd.text} — ${gate.reason}`;
  $('tay-status').className = `small ${cmd.tone === 'warn' ? 'warn-text' : cmd.tone === 'bad' ? 'bad-text' : 'muted'}`;
}

function renderControls() {
  if (!$('batch-create') || !$('run-start')) return;  // HTML cũ trong cache.
  const c = connection();
  const batch = L.commandStatus(state.batchCmd, 'Chưa tạo mẻ từ app.');
  $('batch-status').textContent = batch.text;
  const day = Number($('batch-day').value);
  $('batch-create').disabled = !(c.piOnline && !batch.pending && L.stageForDay(day) !== null);
  $('batch-end').disabled = !(c.piOnline && hasBatch() && !c.running && !batch.pending);
  if ($('batch-create').disabled) resetCreate();
  if ($('batch-end').disabled) resetEnd();

  const run = L.commandStatus(state.runCmd, 'Chưa bắt đầu lượt từ app.');
  const gate = L.canStartRun({ piOnline: c.piOnline, running: c.running, hasBatch: hasBatch(),
    ack: $('run-ack').checked, pending: run.pending });
  $('run-start').disabled = !gate.ok;
  $('run-status').textContent = gate.ok || run.pending ? run.text : `${run.text} — ${gate.reason}`;
  $('run-status').className = `small ${run.tone === 'warn' ? 'warn-text' : run.tone === 'bad' ? 'bad-text' : 'muted'}`;
  if (!gate.ok) resetRun();
  renderManual(c);
}

['batch-day', 'batch-speed', 'run-ack', 'run-ctrl', 'run-min', 'tay-bong', 'tay-quat', 'tay-han'].forEach((id) =>
  $(id)?.addEventListener(id === 'batch-day' ? 'input' : 'change', renderControls));

// ------------------------------------------------------------------ lịch sử & so sánh
function renderHistory() {
  const rows = L.sessionRows(state.sessions, { includeReplay: $('show-replay').checked });
  const sig = JSON.stringify([rows.map((r) => [r.id, r.meta, r.summary]), state.selected]);
  if (sig === state.historySig) return;
  state.historySig = sig;
  if (!state.autoSelected && rows.length) {
    state.autoSelected = true;  // Mặc định: so thermostat với Q-learning mới nhất, nếu có.
    const ts = rows.find((r) => r.meta.bo_dieu_khien === 'Thermostat');
    const q = rows.find((r) => String(r.meta.bo_dieu_khien || '').startsWith('Q-learning'));
    state.selected = [ts, q].filter(Boolean).map((r) => r.id);
    state.historySig = '';
    renderHistory();
    renderCompare();
    return;
  }
  const tbody = $('history');
  tbody.replaceChildren();
  if (!rows.length) {
    const tr = tbody.insertRow();
    const td = tr.insertCell();
    td.colSpan = 8;
    td.className = 'muted';
    td.textContent = 'Chưa có lượt nào.';
    return;
  }
  const colors = [css('--chart-a'), css('--chart-b')];
  for (const r of rows) {
    const s = r.summary || {};
    const tr = tbody.insertRow();
    const idx = state.selected.indexOf(r.id);
    tr.classList.toggle('selected', idx >= 0);
    const pick = tr.insertCell();
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = idx >= 0;
    box.setAttribute('aria-label', `Chọn ${r.id} để so sánh`);
    box.addEventListener('change', () => toggleSelect(r.id, box.checked));
    pick.append(box);
    const when = tr.insertCell();
    when.textContent = L.fmtDateTime(r.meta.bat_dau_ts);
    const src = document.createElement('span');
    src.className = 'src';
    src.textContent = L.SOURCE_LABEL[r.meta.nguon] || r.meta.nguon || '';
    when.append(src);
    const ctrl = tr.insertCell();
    if (idx >= 0) {
      const sw = document.createElement('span');
      sw.className = 'swatch';
      sw.style.background = colors[idx];
      ctrl.append(sw);
    }
    ctrl.append(document.createTextNode(r.meta.bo_dieu_khien || '--'));
    const cells = [
      [L.fmtNum(s.mae_c, 3, ' °C'), ''], [L.fmtNum(s.trong_vung_pct, 1, ' %'), ''],
      [L.fmtNum(s.do_lech_chuan_c, 3, ' °C'), 'wide-only'],
      [typeof s.so_lan_doi_muc === 'number' ? String(s.so_lan_doi_muc) : '--', ''],
      [L.fmtDuration(s.lam_am_s), 'wide-only'],
    ];
    for (const [text, extra] of cells) {
      const td = tr.insertCell();
      td.className = `num ${extra}`.trim();
      td.textContent = text;
    }
  }
}

$('show-replay').addEventListener('change', () => { state.historySig = ''; renderHistory(); });

function toggleSelect(sid, on) {
  state.selected = state.selected.filter((x) => x !== sid);
  if (on) state.selected.push(sid);
  if (state.selected.length > 2) state.selected.shift();
  state.historySig = '';
  renderHistory();
  renderCompare();
}

async function renderCompare() {
  if (!charts.compare) return;
  const colors = [css('--chart-a'), css('--chart-b')];
  const datasets = [];
  for (const [i, sid] of state.selected.entries()) {
    if (!state.sampleCache.has(sid)) {
      try {
        const snap = await get(ref(db, `${ROOT}/sessions/${sid}/samples`));
        state.sampleCache.set(sid, L.alignOnHold(L.samplesToSeries(snap.val())));
      } catch (error) {
        console.error(error);
        continue;
      }
    }
    const meta = (state.sessions && state.sessions[sid] && state.sessions[sid].meta) || {};
    datasets.push(lineDataset(`${meta.bo_dieu_khien || sid} · ${L.fmtDateTime(meta.bat_dau_ts)}`, colors[i], {
      data: state.sampleCache.get(sid).map((p) => ({ x: p.x, y: p.T })),
    }));
  }
  charts.compare.data.datasets = datasets;
  const first = state.selected[0] && state.sessions && state.sessions[state.selected[0]];
  charts.compare.options.plugins.band.band = L.bandOf(first && first.meta);
  charts.compare.update('none');
  $('compare-empty').hidden = datasets.length > 0;
}

// ------------------------------------------------------------------ thông báo trình duyệt
const canNotify = 'Notification' in window;
function notifyLabel() {
  if (!canNotify) { $('notify').hidden = true; return; }
  $('notify').textContent = Notification.permission === 'granted' ? 'Thông báo: bật'
    : Notification.permission === 'denied' ? 'Thông báo bị chặn' : 'Bật thông báo';
}
$('notify').addEventListener('click', async () => {
  if (canNotify && Notification.permission === 'default') await Notification.requestPermission();
  notifyLabel();
});
notifyLabel();

async function notify(alert) {
  if (!canNotify || Notification.permission !== 'granted') return;
  const title = `${L.LEVEL_LABEL[alert.muc] || 'Cảnh báo'} · Hộp ấp`;
  const options = { body: alert.noi_dung || alert.loai, tag: alert.id, icon: 'icons/icon-192.png' };
  try {
    const reg = await navigator.serviceWorker?.getRegistration();
    if (reg) await reg.showNotification(title, options);
    else new Notification(title, options);
  } catch (error) {
    console.error(error);
  }
}

// ------------------------------------------------------------------ nhịp 1 s & PWA
setInterval(() => { if (auth.currentUser) { renderStatus(); renderControls(); } }, 1000);  // đếm ngược chỉnh tay

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(console.error));
}
