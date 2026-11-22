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
const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};

// Lần mở chuông gần nhất (chỉ là tiện ích trên máy này; mất thì coi như đã đọc hết trước 6 giờ qua).
const SEEN_KEY = 'hop-ap-alerts-seen';
function loadSeen() {
  try {
    const v = Number(localStorage.getItem(SEEN_KEY));
    if (v > 0) return v;
  } catch (_e) { /* trình duyệt chặn lưu trữ */ }
  return Date.now() - 6 * 3600 * 1000;
}

const state = {
  live: null, bridge: null, offset: 0, stopCmd: null,
  alertIds: null, alerts: [], alertFilter: 'all', seenTs: loadSeen(), seenAtOpen: null,
  sessions: null, historySig: '', selected: [], autoSelected: false, sampleCache: new Map(),
  samplesSid: null, series: [], range: 600,
  unsubs: [], samplesUnsub: null,
  lich: null, dayCmd: null, dayInputTouched: false, doAm: null,
  batchCmd: null, runCmd: null, tayCmd: null,
  tab: null, scrollTo: null, role: null, roleUnsub: null,
  nao: null, thuCmd: null, tests: [], health: null,
};
const controller = () => L.canControl(state.role);
const serverNow = () => Date.now() + state.offset;
const hasBatch = () => !!state.lich && state.lich.co_me === true;
const connection = () => L.connectionState(state.bridge, state.live, serverNow());

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

function baseOptions({ yTitle, yMin, yMax, suggested = true, legend = false, xTicks = 7 }) {
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
      x: { type: 'linear', grid, ticks: { ...ticks, maxTicksLimit: xTicks, callback: (v) => L.fmtDuration(v) } },
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
  const miniOpts = baseOptions({ yMin: 37.0, yMax: 38.0, xTicks: 4 });
  miniOpts.plugins.tooltip.callbacks.label = (c) => ` ${L.fmtTemp(c.parsed.y, 2)}`;
  charts.mini = new Chart($('mini-chart'), {
    type: 'line', data: { datasets: [lineDataset('Nhiệt độ', css('--chart-temp'))] },
    options: miniOpts, plugins: [bandPlugin],
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

// ------------------------------------------------------------------ giao diện sáng/tối
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#1c1917' : '#b45309';
  $('theme-label').textContent = theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối';
  try { localStorage.setItem('hop-ap-theme', theme); } catch (_e) { /* chế độ riêng tư: chỉ không nhớ lựa chọn */ }
  if (charts.temp) buildCharts();
}
$('theme').addEventListener('click', () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});
document.querySelector('meta[name="theme-color"]').content =
  document.documentElement.dataset.theme === 'dark' ? '#1c1917' : '#b45309';
$('theme-label').textContent = document.documentElement.dataset.theme === 'dark'
  ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối';

// ------------------------------------------------------------------ điều hướng giữa các mục (#/ten-muc)
function showTab(tab) {
  const changed = tab !== state.tab;
  state.tab = tab;
  document.querySelectorAll('[data-view]').forEach((v) => { v.hidden = v.dataset.view !== tab; });
  document.querySelectorAll('[data-tab]').forEach((a) => a.setAttribute('aria-current', a.dataset.tab === tab ? 'page' : 'false'));
  // Đồ thị trong mục vừa ẩn có kích thước 0: vẽ lại theo khung mới.
  requestAnimationFrame(() => Object.values(charts).forEach((c) => c.resize()));
  const target = state.scrollTo && $(state.scrollTo);
  state.scrollTo = null;
  if (target) requestAnimationFrame(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  else if (changed) window.scrollTo(0, 0);
}
const route = () => showTab(L.tabFromHash(location.hash, L.tabsFor(state.role)));
window.addEventListener('hashchange', route);
document.addEventListener('click', (event) => {
  const link = event.target.closest('a[href^="#/"]');
  if (!link) return;
  state.scrollTo = link.dataset.scroll || null;
  if (link.getAttribute('href') === location.hash) { event.preventDefault(); route(); }  // cùng mục: chỉ cuộn
});

// ------------------------------------------------------------------ bảng nổi: chuông thông báo, tài khoản
const POPS = { bell: 'alert-panel', 'menu-btn': 'menu-panel' };

function setPop(btnId, open) {
  $(POPS[btnId]).hidden = !open;
  $(btnId).setAttribute('aria-expanded', String(open));
  if (btnId === 'bell') {
    state.seenAtOpen = open ? state.seenTs : null;  // giữ tô sáng tin mới trong lúc bảng đang mở
    if (open) markSeen();
    renderAlertPanel();
  }
}
function closePops(except) {
  Object.keys(POPS).forEach((b) => { if (b !== except && !$(POPS[b]).hidden) setPop(b, false); });
}
Object.keys(POPS).forEach((b) => $(b).addEventListener('click', (event) => {
  event.stopPropagation();
  const open = $(POPS[b]).hidden;
  closePops(b);
  setPop(b, open);
}));
document.addEventListener('click', (event) => {
  if (!event.target.closest('.popover') && !event.target.closest('.pop-wrap .icon-btn')) closePops();
});
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closePops(); });

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

$('logout').addEventListener('click', () => { closePops(); signOut(auth); });

onAuthStateChanged(auth, (user) => {
  const signedIn = !!user;
  $('login-view').hidden = signedIn;
  $('app-view').hidden = !signedIn;
  ['tabs', 'bell-wrap', 'menu-wrap'].forEach((id) => { $(id).hidden = !signedIn; });
  $('user-email').textContent = user ? user.email : '--';
  $('user-uid').textContent = user ? user.uid : '--';
  closePops();
  stopListening();
  watchRole(user);
  if (signedIn) {
    $('password').value = '';
    route();
    if (!charts.temp) buildCharts();
    startListening();
  } else {
    $('stopbar').hidden = true;
    document.body.classList.remove('has-stopbar');
    setChip('Chưa đăng nhập', 'idle');
  }
});

// ------------------------------------------------------------------ phân quyền (chỉ xem / điều khiển)
function applyRole(role) {
  state.role = role;
  document.body.classList.toggle('viewer', !controller());
  $('role').textContent = `Quyền: ${L.roleLabel(role)}`;
  $('role').className = `badge ${controller() ? 'ok' : 'idle'}`;
  route();  // tài khoản chỉ xem đang ở #/dieu-khien thì về Tổng quan
  if (state.unsubs.length) renderStatus();
}

function watchRole(user) {
  if (state.roleUnsub) state.roleUnsub();
  state.roleUnsub = null;
  applyRole(user ? null : 'xem');
  if (!user) return;
  // Đọc quyen/<uid> của chính mình; lỗi hoặc không có thì coi là chỉ xem.
  state.roleUnsub = onValue(ref(db, `quyen/${user.uid}`),
    (snap) => applyRole(snap.val() === 'dieu_khien' ? 'dieu_khien' : 'xem'),
    () => applyRole('xem'));
}

// ------------------------------------------------------------------ đăng ký nghe dữ liệu
function listen(path, cb, q) {
  const target = q || ref(db, path);
  state.unsubs.push(onValue(target, (snap) => cb(snap.val()), (error) => {
    console.error(path, error);
    if (String(error.code || '').includes('permission')) setChip('Không có quyền đọc', 'bad');
  }));
}

function startListening() {
  listen('.info/serverTimeOffset', (v) => { state.offset = Number(v) || 0; });
  listen(`${ROOT}/trang_thai/bridge`, (v) => { state.bridge = v; renderStatus(); });
  listen(`${ROOT}/live`, (v) => { state.live = v; renderLive(); });
  listen(`${ROOT}/commands/stop`, (v) => { state.stopCmd = v; renderControls(); });
  listen(`${ROOT}/lich`, (v) => { state.lich = v; renderLich(); });
  listen(`${ROOT}/do_am`, (v) => { state.doAm = v; renderHumidity(); renderLich(); });
  listen(`${ROOT}/commands/ngay_ap`, (v) => { state.dayCmd = v; renderControls(); });
  listen(`${ROOT}/commands/me_ap`, (v) => { state.batchCmd = v; renderControls(); });
  listen(`${ROOT}/commands/luot`, (v) => { state.runCmd = v; renderControls(); });
  listen(`${ROOT}/commands/tay`, (v) => { state.tayCmd = v; renderControls(); });
  listen(`${ROOT}/commands/thu_nhieu`, (v) => { state.thuCmd = v; renderControls(); });
  listen(`${ROOT}/nao_rl`, (v) => { state.nao = v; renderBrain(); });
  listen(`${ROOT}/suc_khoe`, (v) => { state.health = v; renderHealth(); });
  listen(`${ROOT}/thu_nhieu`, (v) => { state.tests = L.testList(v); renderTests(); renderControls(); },
    query(ref(db, `${ROOT}/thu_nhieu`), orderByKey(), limitToLast(30)));
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

// ------------------------------------------------------------------ tổng quan
function setChip(text, tone, title = text) {
  const chip = $('conn');
  chip.textContent = text;
  chip.title = title;
  chip.className = `chip ${tone}`;
}

function currentBand() {
  if (state.live && state.live.vung_c) return L.bandOf(state.live);
  return hasBatch() ? L.bandOf(state.lich) : L.DEFAULT_BAND;
}

function renderStatus() {
  const c = connection();
  setChip(c.short, c.tone, c.label);
  const h = L.runHeadline(c, state.live, hasBatch());
  $('hero-title').textContent = h.title;
  $('hero-detail').textContent = h.detail;
  $('hero-dot').className = `dot ${h.tone}${c.running ? ' pulse' : ''}`;
  const cta = $('hero-cta');
  cta.hidden = c.running || !c.piOnline || !controller();
  cta.textContent = hasBatch() ? 'Bắt đầu lượt' : 'Tạo mẻ ấp';
  cta.dataset.scroll = hasBatch() ? 'card-luot' : 'card-me';
  const live = state.live;
  $('updated').textContent = live && live.ts
    ? `Số đo lúc ${L.fmtClock(live.ts)} · ${L.ago(live.ts, serverNow())}${c.running ? '' : ' · không có lượt đang chạy'}`
    : 'Chưa có số đo';
  $('hero').classList.toggle('stale', !c.running);
  renderBrain();
  renderHealth();
  document.querySelector('.view.overview').classList.toggle('stale', !c.running);
  renderControls();
}

function renderLive() {
  const live = state.live || {};
  const band = currentBand();
  $('temp').textContent = L.fmtNum(live.nhiet_c, 2);
  const b = L.bandStatus(live.nhiet_c, band);
  $('band').textContent = b.text;
  $('band').className = `badge ${b.tone}`;
  const target = typeof live.muc_tieu_c === 'number' ? live.muc_tieu_c : (hasBatch() ? state.lich.muc_tieu_c : null);
  $('target').textContent = target == null ? '--'
    : `${L.fmtNum(target, 1, ' °C')} (${L.fmtNum(band[0], 1)}–${L.fmtNum(band[1], 1)})`;
  const tr = L.trendInfo(live.xu_huong_c_phut);
  $('trend-arrow').textContent = tr.arrow;
  $('trend-arrow').className = `trend-arrow ${tr.tone}`;
  $('trend').textContent = tr.text;

  const pos = (v) => L.gaugePos(v);
  $('gauge-band').style.left = `${pos(band[0])}%`;
  $('gauge-band').style.width = `${pos(band[1]) - pos(band[0])}%`;
  $('gauge-guard').style.left = `${pos(L.GAUGE.guard)}%`;
  $('gauge-stop').style.left = `${pos(L.GAUGE.stop)}%`;
  const marker = pos(live.nhiet_c);
  $('gauge-marker').hidden = marker === null;
  if (marker !== null) $('gauge-marker').style.left = `${marker}%`;

  renderHumidity();
  $('lamp').textContent = L.fmtPct(live.bong_pct);
  $('fan').textContent = L.fmtPct(live.quat_pct);
  $('lamp-bar').style.width = `${typeof live.bong_pct === 'number' ? live.bong_pct : 0}%`;
  $('fan-bar').style.width = `${typeof live.quat_pct === 'number' ? live.quat_pct : 0}%`;
  $('phase').textContent = live.giai_doan_ten || '--';
  $('controller').textContent = live.bo_dieu_khien || '--';
  $('session-name').textContent = live.phien ? `${live.phien}${live.nguon === 'phat_lai' ? ' (phát lại)' : ''}` : '--';
  $('band-note').textContent = `Vùng mục tiêu ${L.fmtNum(band[0], 1)}–${L.fmtNum(band[1], 1)} °C, đổi theo giai đoạn ấp. `
    + '% bóng/quạt là mức lệnh PWM, không phải công suất đo được.';
  followSession(live.phien || null);
  renderLich();
  renderStatus();
}

function renderHumidity() {
  const rh = L.currentRh(state.live, state.doAm, serverNow());
  $('rh').textContent = L.fmtPct(rh.value);
  $('rh-note').textContent = rh.note;
}

// ------------------------------------------------------------------ biểu đồ
function windowed(series, range) {
  const last = series.length ? series[series.length - 1].t : 0;
  const min = range > 0 ? Math.max(0, last - range) : (series.length ? series[0].t : 0);
  return { shown: series.filter((s) => s.t >= min), min, last };
}

function drawTemp(chart, { shown, min, last }) {
  chart.data.datasets[0].data = shown.map((s) => ({ x: s.t, y: s.T }));
  chart.options.plugins.band.band = currentBand();
  chart.options.plugins.band.spans = L.bandSpans(shown, currentBand());
  chart.options.scales.x.min = shown.length ? min : undefined;
  chart.options.scales.x.max = shown.length ? last : undefined;
  chart.update('none');
}

function renderLiveChart() {
  if (!charts.temp) return;
  const series = state.series;
  const empty = series.length === 0;
  const main = windowed(series, state.range);
  drawTemp(charts.temp, main);
  drawTemp(charts.mini, windowed(series, 600));
  charts.pwm.data.datasets[0].data = main.shown.filter((s) => typeof s.L === 'number').map((s) => ({ x: s.t, y: s.L }));
  charts.pwm.data.datasets[1].data = main.shown.filter((s) => typeof s.F === 'number').map((s) => ({ x: s.t, y: s.F }));
  charts.pwm.options.scales.x.min = main.shown.length ? main.min : undefined;
  charts.pwm.options.scales.x.max = main.shown.length ? main.last : undefined;
  charts.pwm.update('none');
  document.querySelector('.chart-card').classList.toggle('is-empty', empty);
  document.querySelector('.mini-card').classList.toggle('is-empty', empty);
  $('chart-empty').hidden = !empty;
  $('mini-empty').hidden = !empty;
}

document.querySelectorAll('#range-seg button').forEach((btn) => btn.addEventListener('click', () => {
  state.range = Number(btn.dataset.range);
  document.querySelectorAll('#range-seg button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
  renderLiveChart();
}));

// ------------------------------------------------------------------ thông báo (chuông)
function markSeen() {
  const newest = state.alerts.length ? state.alerts[0].ts : 0;
  if (newest > state.seenTs) {
    state.seenTs = newest;
    try { localStorage.setItem(SEEN_KEY, String(newest)); } catch (_e) { /* không nhớ được: chỉ đếm lại lần sau */ }
  }
  renderBell();
}

function renderBell() {
  const info = L.unreadInfo(state.alerts, state.seenTs);
  const badge = $('bell-count');
  badge.hidden = info.count === 0;
  badge.textContent = info.label;
  badge.className = `count ${info.worst || ''}`;
  $('bell').setAttribute('aria-label', info.count ? `Thông báo, ${info.count} chưa đọc` : 'Thông báo');
}

function renderAlertPanel() {
  const ul = $('alerts');
  const seen = state.seenAtOpen ?? state.seenTs;
  const list = state.alertFilter === 'important' ? state.alerts.filter((a) => a.muc !== 'thong_tin') : state.alerts;
  ul.replaceChildren();
  if (!list.length) ul.append(make('li', 'empty', state.alerts.length ? 'Không có cảnh báo quan trọng.' : 'Chưa có thông báo.'));
  for (const a of list) {
    const li = make('li', `${a.muc || ''}${a.ts > seen ? ' unread' : ''}`);
    const meta = make('div', 'meta');
    meta.append(make('strong', '', L.LEVEL_LABEL[a.muc] || a.muc || ''),
      make('span', '', `${L.ago(a.ts, serverNow())} · ${L.fmtClock(a.ts)}`));
    const text = make('div');
    text.append(meta, make('div', 'body', a.noi_dung || a.loai));
    li.append(make('span', 'lv'), text);
    ul.append(li);
  }
}

document.querySelectorAll('#alert-panel [data-filter]').forEach((btn) => btn.addEventListener('click', () => {
  state.alertFilter = btn.dataset.filter;
  document.querySelectorAll('#alert-panel [data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
  renderAlertPanel();
}));
$('mark-read').addEventListener('click', () => { state.seenAtOpen = null; markSeen(); renderAlertPanel(); });

function renderAlerts(value) {
  const list = L.alertList(value, 30);
  const fresh = L.newAlerts(state.alertIds, list);
  state.alertIds = new Set(list.map((a) => a.id));
  state.alerts = list;
  if (!$('alert-panel').hidden) markSeen();
  renderBell();
  renderAlertPanel();
  fresh.filter((a) => a.muc !== 'thong_tin' || a.loai === 'KET_THUC').forEach((a) => { toast(a); notify(a); });
}

/** Thông báo nổi góc phải khi app đang mở; chạm để mở chuông. */
function toast(alert) {
  if (!$('alert-panel').hidden) return;  // bảng chuông đang mở: tin mới đã nằm trong danh sách
  const box = $('toasts');
  while (box.children.length >= 3) box.firstElementChild.remove();
  const el = make('div', `toast ${alert.muc || ''}`);
  el.setAttribute('role', alert.muc === 'nguy_hiem' ? 'alert' : 'status');
  const text = make('div');
  text.append(make('strong', '', L.LEVEL_LABEL[alert.muc] || 'Thông báo'), make('p', '', alert.noi_dung || alert.loai));
  const close = make('button', '', '×');
  close.type = 'button';
  close.setAttribute('aria-label', 'Đóng thông báo');
  el.append(text, close);
  const remove = () => el.remove();
  close.addEventListener('click', (event) => { event.stopPropagation(); remove(); });
  el.addEventListener('click', (event) => { event.stopPropagation(); remove(); closePops('bell'); setPop('bell', true); });
  box.append(el);
  setTimeout(remove, alert.muc === 'nguy_hiem' ? 15000 : 7000);
}

const canNotify = 'Notification' in window;
function notifyLabel() {
  if (!canNotify) { $('notify').hidden = true; return; }
  $('notify').textContent = Notification.permission === 'granted' ? 'Thông báo trình duyệt: đang bật'
    : Notification.permission === 'denied' ? 'Thông báo trình duyệt bị chặn' : 'Bật thông báo trình duyệt';
}
$('notify').addEventListener('click', async () => {
  if (canNotify && Notification.permission === 'default') await Notification.requestPermission();
  notifyLabel();
});
notifyLabel();

async function notify(alert) {
  if (!canNotify || Notification.permission !== 'granted' || document.visibilityState === 'visible') return;
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

// ------------------------------------------------------------------ lịch ấp 21 ngày
function renderLich() {
  const lich = state.lich;
  const has = hasBatch();
  $('lich-day').textContent = has ? `Ngày ${lich.ngay}/${L.TOTAL_DAYS}` : 'Chưa có mẻ ấp';
  $('lich-target').textContent = has
    ? `Mốc ${L.fmtNum(lich.muc_tieu_c, 1, ' °C')} · vùng ${L.fmtNum(lich.vung_c[0], 1)}–${L.fmtNum(lich.vung_c[1], 1)} °C`
      + (lich.het_lich ? ' · đã hết 21 ngày' : '')
    : 'Vào mục Điều khiển để tạo mẻ (Pi phải online).';
  $('lich-stage').textContent = has ? `Giai đoạn ${lich.giai_doan}` : '--';
  $('lich-stage').className = `badge ${has ? 'ok' : 'idle'}`;
  const marker = $('lich-marker');
  marker.hidden = !has;
  if (has) marker.style.left = `${((lich.ngay - 0.5) / L.TOTAL_DAYS) * 100}%`;
  const speed = has && lich.rut_gon
    ? `Demo: 1 ngày = ${lich.giay_moi_ngay} s · ${lich.tam_dung ? 'lịch đang dừng, chạy khi RL giữ nhiệt' : 'lịch đang chạy'}`
    : (has ? 'Thời gian thật' : '');
  $('lich-speed').textContent = speed;
  $('lich-speed').hidden = !speed;
  const rh = L.rhAdvice(L.currentRh(state.live, state.doAm, serverNow()).value, has ? lich.do_am_khuyen_nghi : null);
  $('lich-rh').textContent = `Độ ẩm: ${rh.text}`;
  $('lich-rh').className = `badge ${rh.tone} small`;
  $('lich-rh').hidden = !has;
  $('batch-summary').textContent = has ? `Đang có mẻ: ${L.lichText(lich)}${speed ? ` · ${speed}` : ''}.`
    : 'Chưa có mẻ ấp. Tạo mẻ mới để bắt đầu.';
  if (has && !state.dayInputTouched && document.activeElement !== $('day-input')) $('day-input').value = lich.ngay;
  renderControls();
}

// ------------------------------------------------------------------ nút 2 bước & gửi lệnh
/** Nút bấm 2 lần trong 5 giây mới gửi lệnh. Trả hàm reset để gọi khi nút bị khóa. */
function twoStep(btn, idleText, confirmText, statusEl, action) {
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
    if (!controller()) return;  // phòng hờ: tài khoản chỉ xem không gửi lệnh (Firebase cũng chặn)
    btn.disabled = true;
    try {
      await action();
    } catch (error) {
      statusEl.textContent = `Không gửi được: ${error.code || error.message}`;
      statusEl.className = 'status bad-text';
    }
    renderControls();
  });
  return reset;
}

function sendCommand(name, data) {
  return set(ref(db, `${ROOT}/commands/${name}`),
    { ...data, ts: serverTimestamp(), by: auth.currentUser.email, da_xu_ly: false });
}

const pick = (name) => document.querySelector(`input[name="${name}"]:checked`)?.value;
const toneClass = (tone) => `status${tone === 'warn' ? ' warn-text' : tone === 'bad' ? ' bad-text' : ''}`;
function renderChecks(el, checks) {
  el.replaceChildren(...checks.map((c) => make('li', c.ok ? 'pass' : 'miss', c.label)));
}

// ---- mẻ ấp và đổi ngày
const resetCreate = twoStep($('batch-create'), 'Tạo mẻ mới',
  () => `Bấm lần nữa: từ ngày ${$('batch-day').value}, ${L.DEMO_SPEEDS[$('batch-speed').value]}${hasBatch() ? ' (thay mẻ cũ)' : ''}`,
  $('batch-status'),
  () => sendCommand('me_ap', { hanh_dong: 'tao', ngay: Number($('batch-day').value), giay_moi_ngay: Number($('batch-speed').value) }));
const resetEnd = twoStep($('batch-end'), 'Kết thúc mẻ', () => 'Bấm lần nữa để kết thúc', $('batch-status'),
  () => sendCommand('me_ap', { hanh_dong: 'ket_thuc' }));
const resetDay = twoStep($('day-send'), 'Đổi ngày',
  () => {
    const day = Number($('day-input').value);
    const stage = L.stageForDay(day);
    return `Bấm lần nữa: ngày ${day} → GĐ${stage}, mốc ${L.fmtNum(L.STAGES[stage].target, 1, ' °C')}`;
  },
  $('day-status'),
  async () => {
    await set(ref(db, `${ROOT}/commands/ngay_ap`), {
      ngay: Number($('day-input').value), ts: serverTimestamp(), by: auth.currentUser.email, da_xu_ly: false,
    });
    state.dayInputTouched = false;
  });

function setDayInput(value) {
  $('day-input').value = Math.min(L.TOTAL_DAYS, Math.max(1, value));
  state.dayInputTouched = true;
  resetDay();
  renderControls();
}
$('day-input').addEventListener('input', () => { state.dayInputTouched = true; resetDay(); renderControls(); });
document.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => {
  setDayInput((Number($('day-input').value) || 1) + Number(b.dataset.step));
}));
document.querySelectorAll('.chipbtn[data-day]').forEach((b) => b.addEventListener('click', () => setDayInput(Number(b.dataset.day))));

function renderBatchAndDay(c) {
  const batch = L.commandStatus(state.batchCmd, '');
  $('batch-status').textContent = batch.text;
  $('batch-status').className = toneClass(batch.tone);
  $('batch-create').disabled = !(c.piOnline && !batch.pending && L.stageForDay(Number($('batch-day').value)) !== null);
  $('batch-end').disabled = !(c.piOnline && hasBatch() && !c.running && !batch.pending);
  if ($('batch-create').disabled) resetCreate();
  if ($('batch-end').disabled) resetEnd();

  const dayCmd = L.dayCommandStatus(state.dayCmd);
  $('day-status').textContent = state.dayCmd ? dayCmd.text : '';
  $('day-status').className = 'status';
  const day = Number($('day-input').value);
  const stage = L.stageForDay(day);
  $('day-preview').textContent = stage === null ? 'Ngày phải từ 1 đến 21.'
    : `Ngày ${day} thuộc giai đoạn ${stage}: mốc ${L.fmtNum(L.STAGES[stage].target, 1, ' °C')}, vùng `
      + `${L.fmtNum(L.STAGES[stage].band[0], 1)}–${L.fmtNum(L.STAGES[stage].band[1], 1)} °C.`;
  $('day-send').disabled = !(c.piOnline && !dayCmd.pending && stage !== null);
  if ($('day-send').disabled) resetDay();
}

// ---- lượt chạy
const ctrlLabel = () => (pick('run-ctrl') === 'rl' ? 'Q-learning' : 'Thermostat');
const resetRun = twoStep($('run-start'), 'Bắt đầu lượt',
  () => `Bấm lần nữa: ${ctrlLabel()} ${pick('run-min')} phút`, $('run-status'),
  async () => {
    await sendCommand('luot', { hanh_dong: 'bat_dau', bo_dieu_khien: pick('run-ctrl'),
      phut: Number(pick('run-min')), co_nguoi: $('run-ack').checked });
    $('run-ack').checked = false;  // Mỗi lượt phải xác nhận lại.
  });

function renderRun(c) {
  const run = L.commandStatus(state.runCmd, '');
  const gate = L.canStartRun({ piOnline: c.piOnline, running: c.running, hasBatch: hasBatch(),
    ack: $('run-ack').checked, pending: run.pending });
  renderChecks($('run-checks'), gate.checks);
  $('run-start').disabled = !gate.ok;
  if (!gate.ok) resetRun();
  $('run-status').textContent = run.text;
  $('run-status').className = toneClass(run.tone);
}

// ---- chỉnh tay
const tayPick = () => ({ lamp: Number(pick('tay-bong')), fan: Number(pick('tay-quat')), seconds: Number(pick('tay-han')) });
const resetTay = twoStep($('tay-apply'), 'Áp dụng chỉnh tay',
  () => { const p = tayPick(); return `Bấm lần nữa: bóng ${p.lamp} %, quạt ${p.fan} %, ${L.MANUAL_SECONDS[p.seconds]}`; },
  $('tay-status'),
  () => { const p = tayPick(); return sendCommand('tay', { hanh_dong: 'dat', bong: p.lamp, quat: p.fan, thoi_han_s: p.seconds }); });
$('tay-return').addEventListener('click', async () => {
  if (!controller()) return;
  $('tay-return').disabled = true;
  try {
    await sendCommand('tay', { hanh_dong: 'tra_ve' });
  } catch (error) {
    $('tay-status').textContent = `Không gửi được: ${error.code || error.message}`;
  }
  renderControls();
});

function renderManual(c) {
  const cmd = L.commandStatus(state.tayCmd, '');
  const live = state.live || {};
  const m = L.manualState(state.tayCmd, serverNow());
  const active = m.active && c.running && L.isHoldPhase(live.pha);
  const fan100 = document.querySelector('input[name="tay-quat"][value="100"]');
  fan100.disabled = Number(pick('tay-bong')) === 100;  // 100/100 không có trong 9 hành động đã khảo sát.
  if (fan100.disabled && fan100.checked) document.querySelector('input[name="tay-quat"][value="75"]').checked = true;
  const p = tayPick();
  const gate = L.canManual({ piOnline: c.piOnline, running: c.running, pha: live.pha, pending: cmd.pending, ...p });
  renderChecks($('tay-checks'), gate.checks);
  $('tay-apply').disabled = !gate.ok;
  if (!gate.ok) resetTay();
  $('tay-return').disabled = !(active && c.piOnline && !cmd.pending);
  $('tay-active').textContent = active ? m.text : (c.running ? 'RL / thermostat đang điều khiển.' : 'Chưa có lượt chạy.');
  $('tay-active').className = `banner ${active ? 'warn' : c.running ? 'ok' : 'idle'}`;
  $('tay-status').textContent = cmd.text;
  $('tay-status').className = toneClass(cmd.tone);
  $('tay-banner').hidden = !active;
  $('tay-banner-text').textContent = m.text;
}

// ---- dừng khẩn cấp: thanh dưới cùng, hiện ở mọi mục khi đang chạy
const resetStop = twoStep($('stop'), 'Dừng khẩn cấp', () => 'Bấm lần nữa để DỪNG', $('stop-status'),
  () => set(ref(db, `${ROOT}/commands/stop`), { value: true, ts: serverTimestamp(), by: auth.currentUser.email }));

function renderStop(c) {
  const s = L.stopStatus(state.stopCmd);
  const live = state.live || {};
  $('stop-status').textContent = state.stopCmd && (s.pending || state.stopCmd.ket_qua) ? `Dừng khẩn cấp: ${s.text}` : '';
  const show = (c.running || s.pending) && controller();  // tài khoản chỉ xem: không có nút dừng
  $('stopbar').hidden = !show;
  document.body.classList.toggle('has-stopbar', show);
  $('stopbar-text').textContent = s.pending ? 'Đã gửi lệnh dừng, chờ Pi…'
    : `${live.bo_dieu_khien || 'Đang chạy'} · ${L.fmtDuration(live.elapsed_s)}`;
  const allowed = c.running && !s.pending;
  $('stop').disabled = !allowed;
  if (!allowed) resetStop();
}

// ---- thử nhiễu
const resetThu = twoStep($('thu-start'), 'Bắt đầu thử nhiễu',
  () => `Bấm lần nữa: ${L.THU_KIEU[pick('thu-kieu')]} trong ${Number(pick('thu-han')) / 60} phút`, $('thu-status'),
  () => sendCommand('thu_nhieu', { hanh_dong: 'bat_dau', kieu: pick('thu-kieu'), thoi_han_s: Number(pick('thu-han')) }));
$('thu-cancel').addEventListener('click', async () => {
  if (!controller()) return;
  $('thu-cancel').disabled = true;
  try {
    await sendCommand('thu_nhieu', { hanh_dong: 'huy' });
  } catch (error) {
    $('thu-status').textContent = `Không gửi được: ${error.code || error.message}`;
  }
  renderControls();
});

function renderDisturbance(c) {
  const cmd = L.commandStatus(state.thuCmd, '');
  const active = L.activeTest(state.tests);
  const gate = L.canDisturb({ piOnline: c.piOnline, running: c.running, live: state.live, active,
    manualActive: L.manualState(state.tayCmd, serverNow()).active, pending: cmd.pending });
  renderChecks($('thu-checks'), gate.checks);
  $('thu-start').disabled = !gate.ok;
  if (!gate.ok) resetThu();
  $('thu-cancel').disabled = !(active && c.piOnline && !cmd.pending);
  const prog = L.testProgress(active || state.tests[0], serverNow());
  $('thu-progress').textContent = prog.text;
  $('thu-progress').className = `banner ${prog.tone}`;
  $('thu-status').textContent = cmd.text;
  $('thu-status').className = toneClass(cmd.tone);
  $('thu-banner').hidden = !active;
  if (active) $('thu-banner-text').textContent = prog.text;
}

function renderTests() {
  const list = state.tests;
  $('thu-count').textContent = list.length ? `${list.length} lần` : '';
  $('thu-empty').hidden = list.length > 0;
  $('thu-table-wrap').hidden = list.length === 0;
  const sum = $('thu-summary');
  sum.replaceChildren(...L.testSummary(list).map((g) => {
    const row = make('div', 'row');
    row.append(make('span', '', `${g.key} (${g.n} lần)`),
      make('b', '', `về vùng TB ${L.fmtDuration(g.ve)} · ổn định ${L.fmtDuration(g.on)} · lệch ${L.fmtNum(g.lech, 2, ' °C')}`));
    return row;
  }));
  const tbody = $('thu-rows');
  tbody.replaceChildren();
  for (const t of list) {
    const tr = tbody.insertRow();
    tr.insertCell().textContent = L.fmtDateTime(t.bat_dau_ts);
    const who = tr.insertCell();
    who.append(document.createTextNode(`${t.bo_dieu_khien || '?'}`),
      make('span', 'note', `${L.THU_KIEU[t.kieu] || t.kieu}, ${t.thoi_han_s / 60} phút${t.bao_ve ? ' · có bảo vệ' : ''}`));
    const done = t.trang_thai === 'XONG';
    if (done && t.ra_vung) {
      tr.insertCell().textContent = L.fmtDuration(t.ve_vung_s);
      tr.insertCell().textContent = L.fmtDuration(t.on_dinh_s);
    } else {
      const cell = tr.insertCell();
      cell.colSpan = 2;
      cell.textContent = L.THU_ACTIVE.includes(t.trang_thai) ? 'đang chạy…' : L.testResultText(t).split(';')[0];
    }
    tr.insertCell().textContent = L.fmtNum(t.lech_max_c, 2, ' °C');
  }
}

// ---- sức khỏe thiết bị
function renderHealth() {
  const v = L.healthView(state.health, state.doAm, serverNow());
  $('health-badge').textContent = v.badge;
  $('health-badge').className = `badge ${v.tone}`;
  $('health-note').textContent = v.note;
  $('health-list').replaceChildren(...v.items.map((i) => {
    const d = make('div', `h-${i.tone}`);  // không dùng .ok/.warn chung: chúng tô cả nền và chữ
    const dd = make('dd', '', i.v);
    if (i.hint) dd.append(make('span', 'hint', i.hint));
    d.append(make('dt', '', i.k), dd);
    return d;
  }));
}

// ---- RL đang nghĩ gì
function renderBrain() {
  const v = L.brainView(state.nao, connection().running, serverNow());
  $('brain-badge').textContent = v.badge;
  $('brain-badge').className = `badge ${v.tone}`;
  $('brain-text').textContent = v.text;
  $('brain-detail').hidden = v.kind !== 'q';
  if (v.kind !== 'q') return;
  $('brain-chips').replaceChildren(...v.chips.map((ch) => {
    const d = make('div');
    d.append(make('dt', '', ch.k), make('dd', '', ch.v));
    return d;
  }));
  $('brain-bars').replaceChildren(...v.bars.map((b) => {
    const row = make('div', `qbar${b.chosen ? ' chosen' : ''}${b.known ? '' : ' unknown'}`);
    row.setAttribute('role', 'listitem');
    row.title = `${b.title}${b.visits != null ? ` · đã thử ${b.visits} lần khi huấn luyện` : ''}`;
    const track = make('span', 'track');
    const fill = make('span', 'fill');
    fill.style.width = `${b.width}%`;
    track.append(fill);
    row.append(make('span', 'lab', b.label), track, make('span', 'val', b.chosen ? `${b.value} ✓` : b.value));
    return row;
  }));
  $('brain-shift').textContent = v.shift;
}

function renderControls() {
  const c = connection();
  renderBatchAndDay(c);
  renderRun(c);
  renderManual(c);
  renderDisturbance(c);
  renderStop(c);
}

['batch-speed', 'run-ack'].forEach((id) => $(id).addEventListener('change', renderControls));
$('batch-day').addEventListener('input', renderControls);
document.querySelectorAll('.choices input').forEach((r) => r.addEventListener('change', renderControls));

// ------------------------------------------------------------------ lịch sử & so sánh
const cmpColors = () => [css('--chart-a'), css('--chart-b')];

function renderHistory() {
  const rows = L.sessionRows(state.sessions, { includeReplay: $('show-replay').checked });
  const sig = JSON.stringify([rows.map((r) => [r.id, r.meta, r.summary]), state.selected]);
  if (sig === state.historySig) return;
  state.historySig = sig;
  if (!state.autoSelected && rows.length) {
    state.autoSelected = true;  // Mặc định: so thermostat với Q-learning mới nhất, nếu có.
    // Chỉ chọn sẵn lượt đã có tóm tắt (lượt đang chạy chưa có số để so).
    const done = rows.filter((r) => r.summary && typeof r.summary.mae_c === 'number');
    const ts = done.find((r) => r.meta.bo_dieu_khien === 'Thermostat');
    const q = done.find((r) => String(r.meta.bo_dieu_khien || '').startsWith('Q-learning'));
    state.selected = [ts, q].filter(Boolean).map((r) => r.id);
    state.historySig = '';
    renderHistory();
    renderCompare();
    return;
  }
  $('history-count').textContent = rows.length ? `${rows.length} lượt` : '';
  const list = $('history');
  list.replaceChildren();
  if (!rows.length) { list.append(make('p', 'empty-state', 'Chưa có lượt nào.')); return; }
  const colors = cmpColors();
  for (const r of rows) {
    const s = r.summary || {};
    const idx = state.selected.indexOf(r.id);
    const btn = make('button', 'run-item');
    btn.type = 'button';
    btn.setAttribute('aria-pressed', String(idx >= 0));
    if (idx >= 0) btn.style.setProperty('--sel', colors[idx]);
    const main = make('span');
    main.append(make('strong', '', r.meta.bo_dieu_khien || r.id),
      make('span', 'sub', `${L.fmtDateTime(r.meta.bat_dau_ts)} · ${L.SOURCE_LABEL[r.meta.nguon] || r.meta.nguon || ''}`));
    const nums = make('span', 'nums');
    nums.append(make('b', '', L.fmtNum(s.trong_vung_pct, 1, ' %')), make('span', 'muted', `MAE ${L.fmtNum(s.mae_c, 3, ' °C')}`));
    btn.append(make('span', 'pick'), main, nums);
    btn.title = 'Chọn để so sánh';
    btn.addEventListener('click', () => toggleSelect(r.id, idx < 0));
    const dl = make('button', 'dl-btn');
    dl.type = 'button';
    dl.setAttribute('aria-label', `Tải CSV lượt ${r.meta.bo_dieu_khien || r.id} ${L.fmtDateTime(r.meta.bat_dau_ts)}`);
    dl.title = 'Tải CSV (mẫu 5 giây)';
    dl.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>';
    dl.addEventListener('click', () => downloadRun(r.id, dl));
    const rowEl = make('div', 'run-row');
    rowEl.append(btn, dl);
    list.append(rowEl);
  }
}

$('show-replay').addEventListener('change', () => { state.historySig = ''; renderHistory(); });

/** Tải mẫu 5 s của một lượt từ Firebase rồi lưu thành file CSV trên máy đang xem. */
async function downloadRun(sid, btn) {
  const status = $('history-status');
  btn.disabled = true;
  status.textContent = 'Đang tải dữ liệu…';
  status.className = 'status';
  try {
    const snap = await get(ref(db, `${ROOT}/sessions/${sid}/samples`));
    const meta = sessionOf(sid).meta || {};
    const csv = L.sessionCsv(meta, snap.val());
    const rows = csv.split('\r\n').length - 2;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = L.csvFileName(sid);
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status.textContent = `Đã tạo ${a.download} (${rows} dòng).`;
  } catch (error) {
    status.textContent = `Không tải được: ${error.code || error.message}`;
    status.className = 'status bad-text';
  }
  btn.disabled = false;
}
$('compare-clear').addEventListener('click', () => { state.selected = []; state.historySig = ''; renderHistory(); renderCompare(); });

function toggleSelect(sid, on) {
  state.selected = state.selected.filter((x) => x !== sid);
  if (on) state.selected.push(sid);
  if (state.selected.length > 2) state.selected.shift();
  state.historySig = '';
  renderHistory();
  renderCompare();
}

function sessionOf(sid) {
  return (state.sessions && state.sessions[sid]) || {};
}

function renderCompareTable() {
  const [a, b] = state.selected.map(sessionOf);
  const colors = cmpColors();
  const head = (el, s, i, fallback) => {
    el.replaceChildren();
    if (!s) { el.textContent = fallback; return; }
    const sw = make('span', 'swatch');
    sw.style.background = colors[i];
    el.append(sw, document.createTextNode(`${(s.meta && s.meta.bo_dieu_khien) || '?'} · ${L.fmtDateTime(s.meta && s.meta.bat_dau_ts)}`));
  };
  head($('cmp-a'), a, 0, '--');
  head($('cmp-b'), b, 1, 'Chọn thêm 1 lượt');
  const tbody = $('compare-table');
  tbody.replaceChildren();
  for (const row of L.compareMetrics(a && a.summary, b && b.summary)) {
    const tr = tbody.insertRow();
    tr.insertCell().textContent = row.label;
    const ca = tr.insertCell();
    ca.textContent = row.a;
    ca.classList.toggle('win', row.win === 'a');
    const cb = tr.insertCell();
    cb.textContent = b ? row.b : '';
    cb.classList.toggle('win', row.win === 'b');
  }
}

async function renderCompare() {
  const n = state.selected.length;
  $('compare-empty').hidden = n > 0;
  $('compare-body').hidden = n === 0;
  $('compare-clear').hidden = n === 0;
  if (n) renderCompareTable();
  if (!charts.compare) return;
  const colors = cmpColors();
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
    const meta = sessionOf(sid).meta || {};
    datasets.push(lineDataset(`${meta.bo_dieu_khien || sid} · ${L.fmtDateTime(meta.bat_dau_ts)}`, colors[i], {
      data: state.sampleCache.get(sid).map((p) => ({ x: p.x, y: p.T })),
    }));
  }
  charts.compare.data.datasets = datasets;
  const first = state.selected[0] && sessionOf(state.selected[0]);
  charts.compare.options.plugins.band.band = L.bandOf(first && first.meta);
  charts.compare.update('none');
  requestAnimationFrame(() => charts.compare.resize());
}

// ------------------------------------------------------------------ nhịp 1 s & PWA
let tick = 0;
setInterval(() => {
  if (!auth.currentUser) return;
  renderStatus();  // đồng hồ "x giây trước", đếm ngược chỉnh tay, trạng thái nút
  if (++tick % 15 === 0 && !$('alert-panel').hidden) renderAlertPanel();
}, 1000);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(console.error));
}
