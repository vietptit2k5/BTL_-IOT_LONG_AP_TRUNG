import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../public/logic.js';

test('định dạng số kiểu Việt Nam', () => {
  assert.equal(L.fmtTemp(37.456), '37,46 °C');
  assert.equal(L.fmtTemp(null), '-- °C');
  assert.equal(L.fmtPct(49.6), '50 %');
  assert.equal(L.fmtDuration(65), '1:05');
  assert.equal(L.fmtDuration(3725), '1:02:05');
  assert.equal(L.fmtDuration(-1), '--');
});

test('trạng thái kết nối', () => {
  const now = 1_000_000;
  const live = { ts: now - 4000, bridge_ts: now - 3000, trang_thai: 'DANG_CHAY', nguon: 'truc_tiep' };
  assert.deepEqual(L.connectionState({ ts: now - 4000 }, live, now).running, true);
  assert.equal(L.connectionState({ ts: now - 4000 }, live, now).label, 'Đang chạy');
  assert.equal(L.connectionState({ ts: now - 60000 }, live, now).tone, 'bad');
  assert.equal(L.connectionState({ ts: now - 1000 }, { ...live, trang_thai: 'KET_THUC' }, now).running, false);
  assert.equal(L.connectionState({ ts: now - 1000 }, { ...live, bridge_ts: now - 60000 }, now).running, false);
  assert.equal(L.connectionState(null, null, now).piOnline, false);
  const dead = L.connectionState({ ts: now - 1000 }, { ...live, ts: now - 300000 }, now);
  assert.equal(dead.running, false);
  assert.match(dead.label, /Mất dữ liệu lượt/);
  assert.equal(L.connectionState({ ts: now }, { ...live, nguon: 'phat_lai' }, now).label, 'Đang phát lại');
});

test('vùng mục tiêu', () => {
  assert.equal(L.bandStatus(37.5).tone, 'ok');
  assert.equal(L.bandStatus(37.2).tone, 'warn');
  assert.match(L.bandStatus(37.9).text, /^Cao hơn vùng 0,20/);
  assert.deepEqual(L.bandOf({ vung_c: [37, 38] }), [37, 38]);
  assert.deepEqual(L.bandOf({}), L.DEFAULT_BAND);
});

test('chuỗi mẫu và căn theo lúc bắt đầu giữ nhiệt', () => {
  const samples = {
    '000010': { t: 10, T: 30, g: 'lam_am' },
    '000000': { t: 0, T: 26, g: 'lam_am' },
    '000020': { t: 20, T: 37, g: 'giu_nhiet' },
    '000025': { t: 25, T: 37.1, g: 'giu_nhiet' },
    'hong': { t: 'x' },
  };
  const s = L.samplesToSeries(samples);
  assert.deepEqual(s.map((p) => p.t), [0, 10, 20, 25]);
  assert.deepEqual(L.alignOnHold(s), [{ x: 0, T: 37 }, { x: 5, T: 37.1 }]);
  assert.deepEqual(L.alignOnHold([{ t: 0, T: 30, g: 'lam_am' }]), []);
});

test('danh sách phiên: bỏ phát lại, mới nhất trước', () => {
  const rows = L.sessionRows({
    a: { meta: { bat_dau_ts: 1, nguon: 'tai_len' }, summary: {} },
    b: { meta: { bat_dau_ts: 3, nguon: 'phat_lai' } },
    c: { meta: { bat_dau_ts: 2, nguon: 'truc_tiep' } },
  });
  assert.deepEqual(rows.map((r) => r.id), ['c', 'a']);
  assert.equal(L.sessionRows({ b: { meta: { nguon: 'phat_lai' } } }, { includeReplay: true }).length, 1);
  const probe = { d: { meta: { nguon: 'truc_tiep' }, summary: { trang_thai: 'CHUA_CO_GIU_NHIET' } } };
  assert.equal(L.sessionRows(probe).length, 0);
  assert.equal(L.sessionRows(probe, { includeReplay: true }).length, 1);
});

test('cảnh báo: mới nhất trước, không thông báo lại ở lần tải đầu', () => {
  const list = L.alertList({ x: { ts: 1 }, y: { ts: 3 }, z: { ts: 2 }, bad: {} });
  assert.deepEqual(list.map((a) => a.id), ['y', 'z', 'x']);
  assert.deepEqual(L.newAlerts(null, list), []);
  assert.deepEqual(L.newAlerts(new Set(['x', 'z']), list).map((a) => a.id), ['y']);
});

test('ấp 3 giai đoạn: ngày → giai đoạn, dải nền theo giai đoạn', () => {
  assert.equal(L.stageForDay(1), 1);
  assert.equal(L.stageForDay(10), 1);
  assert.equal(L.stageForDay(11), 2);
  assert.equal(L.stageForDay(18), 3);
  assert.equal(L.stageForDay(22), null);
  assert.equal(L.stageForDay(2.5), null);
  const spans = L.bandSpans([
    { t: 0, T: 37, k: 1 }, { t: 5, T: 37.8, k: 1 }, { t: 10, T: 37.7, k: 2 }, { t: 15, T: 37.5, k: 2 }, { t: 20, T: 37.5 },
  ]);
  assert.deepEqual(spans.map((s) => [s.x0, s.x1, s.band[0]]), [[0, 10, 37.6], [10, 20, 37.3]]);
  assert.equal(L.lichText({ co_me: true, ngay: 12, giai_doan: 2, muc_tieu_c: 37.5 }), 'Ngày 12/21 · Giai đoạn 2 · mốc 37,5 °C');
  assert.equal(L.lichText({ co_me: false }), 'Chưa có mẻ ấp');
});

test('độ ẩm khuyến nghị và lệnh đổi ngày', () => {
  assert.equal(L.rhAdvice(58, [55, 55]).tone, 'ok');
  assert.equal(L.rhAdvice(40, [55, 55]).tone, 'warn');
  assert.equal(L.rhAdvice(null, [65, 70]).text, 'Khuyến nghị 65–70 % · chưa có số đo ẩm');
  assert.equal(L.dayCommandStatus({ ngay: 12, da_xu_ly: false }).pending, true);
  assert.match(L.dayCommandStatus({ ngay: 12, da_xu_ly: true, ket_qua: 'DA_DOI', yeu_cau_boi: 'a@b.c', xu_ly_ts: 1 }).text, /đổi ngày/);
});

test('độ ẩm: ưu tiên lượt đang chạy, rồi tới dịch vụ do_am, báo lỗi DHT', () => {
  const now = 1_000_000;
  const live = { do_am_pct: 57, bridge_ts: now - 2000 };
  const doAm = { do_am_pct: 60, bridge_ts: now - 3000, con_cap_nhat: true, ts_doc_ok_cuoi: now - 4000, ty_le_ok_pct: 90 };
  assert.equal(L.currentRh(live, doAm, now).value, 57);
  assert.equal(L.currentRh({ ...live, bridge_ts: now - 60000 }, doAm, now).value, 60);
  assert.match(L.currentRh(null, doAm, now).note, /đọc tốt 90 %/);
  assert.equal(L.currentRh(null, { ...doAm, do_am_pct: null, loi_cuoi: 'DHT sensor not found' }, now).source, 'loi');
  assert.equal(L.currentRh(null, { ...doAm, bridge_ts: now - 90000 }, now).value, null);
});

test('lệnh tạo mẻ / bắt đầu lượt: chờ, thành công, từ chối', () => {
  assert.equal(L.commandStatus(null).pending, false);
  assert.equal(L.commandStatus({ da_xu_ly: false }).pending, true);
  assert.match(L.commandStatus({ da_xu_ly: true, ket_qua: 'DA_TAO', xu_ly_ts: 1 }).text, /tạo mẻ và bắt đầu ấp/);
  const refused = L.commandStatus({ da_xu_ly: true, ket_qua: 'TU_CHOI: hộp còn 31.5 °C > 30 °C, chờ nguội', xu_ly_ts: 1 });
  assert.equal(refused.tone, 'warn');
  assert.match(refused.text, /Pi từ chối: hộp còn 31.5/);
  assert.match(L.commandStatus({ da_xu_ly: true, ket_qua: 'DA_BAT_DAU (tmux:hopap_app)', xu_ly_ts: 1 }).text, /bắt đầu lượt/);
});

test('điều kiện nút bắt đầu lượt', () => {
  const ok = { piOnline: true, running: false, hasBatch: true, ack: true, pending: false };
  assert.equal(L.canStartRun(ok).ok, true);
  assert.match(L.canStartRun({ ...ok, ack: false }).reason, /xác nhận có người/);
  assert.match(L.canStartRun({ ...ok, running: true, hasBatch: false }).reason, /không có lượt đang chạy · đã tạo mẻ ấp/);
});

test('chỉnh tay: cặp hợp lệ, điều kiện nút, đếm ngược', () => {
  assert.equal(L.isManualPair(100, 75), true);
  assert.equal(L.isManualPair(100, 100), false);
  assert.equal(L.isManualPair(50, 0), false);
  assert.equal(L.isHoldPhase('ap_ngay05_gd1'), true);
  assert.equal(L.isHoldPhase('ap_ngay05_gd1_tay'), true);
  assert.equal(L.isHoldPhase('lam_am_ap'), false);
  assert.equal(L.isHoldPhase('giu_nhiet'), false);
  const ok = { piOnline: true, running: true, pha: 'ap_ngay12_gd2', pending: false, lamp: 0, fan: 75 };
  assert.equal(L.canManual(ok).ok, true);
  assert.match(L.canManual({ ...ok, pha: 'lam_am_ap' }).reason, /qua làm ấm/);
  assert.match(L.canManual({ ...ok, running: false }).reason, /có lượt đang chạy/);
  assert.match(L.canManual({ ...ok, lamp: 100, fan: 100 }).reason, /đã khảo sát/);
  const cmd = { da_xu_ly: true, ket_qua: 'DA_AP_DUNG', het_han_ms: 100000, bong: 0, quat: 75, yeu_cau_boi: 'a@b.c' };
  const m = L.manualState(cmd, 100000 - 65000);
  assert.equal(m.active, true);
  assert.match(m.text, /bóng 0 %, quạt 75 % · còn 1:05/);
  assert.equal(L.manualState(cmd, 100001).active, false);
  assert.equal(L.manualState({ ...cmd, ket_qua: 'DA_TRA_VE' }, 0).active, false);
  assert.match(L.commandStatus({ ...cmd, xu_ly_ts: 1 }).text, /áp dụng lệnh chỉnh tay/);
});

test('trạng thái lệnh dừng', () => {
  assert.equal(L.stopStatus(null).pending, false);
  assert.equal(L.stopStatus({ value: true, by: 'a@b.c' }).pending, true);
  assert.match(L.stopStatus({ value: false, ket_qua: 'DA_GUI_SIGTERM_PID_12', xu_ly_ts: 1 }).text, /đã tắt bóng/);
  assert.match(L.stopStatus({ value: false, ket_qua: 'KHONG_TIM_THAY_TIEN_TRINH', xu_ly_ts: 1 }).text, /Không tìm thấy/);
});

test('giao diện: tiêu đề trạng thái, thang nhiệt, xu hướng, tab', () => {
  const on = { piOnline: true, running: true, stale: false };
  assert.equal(L.runHeadline({ piOnline: false }, null, true).tone, 'bad');
  assert.equal(L.runHeadline({ piOnline: true, stale: true }, null, true).title, 'Mất dữ liệu lượt');
  const h = L.runHeadline(on, { giai_doan: 'tay', giai_doan_ten: 'Chỉnh tay', bo_dieu_khien: 'Q-learning v2', elapsed_s: 65 }, true);
  assert.equal(h.tone, 'warn');
  assert.match(h.detail, /Q-learning v2 · đã chạy 1:05/);
  assert.equal(L.runHeadline({ piOnline: true, running: false }, null, false).title, 'Chưa có mẻ ấp');
  assert.equal(L.gaugePos(36.0), 0);
  assert.equal(L.gaugePos(37.75), 50);
  assert.equal(L.gaugePos(null), null);
  assert.equal(L.trendInfo(0.1).arrow, '↑');
  assert.equal(L.trendInfo(-0.01).arrow, '→');
  assert.equal(L.tabFromHash('#/lich-su'), 'lich-su');
  assert.equal(L.tabFromHash('#/khong-co'), 'tong-quan');
  assert.equal(L.connectionState(null, null, 0).short, 'Mất kết nối');
});

test('chuông thông báo: đếm chưa đọc và mức nặng nhất', () => {
  const list = [{ ts: 30, muc: 'thong_tin' }, { ts: 20, muc: 'nguy_hiem' }, { ts: 10, muc: 'canh_bao' }];
  assert.deepEqual(L.unreadInfo(list, 15), { count: 2, worst: 'nguy_hiem', label: '2' });
  assert.equal(L.unreadInfo(list, 30).count, 0);
  assert.equal(L.unreadInfo(Array.from({ length: 12 }, (_, i) => ({ ts: i + 1, muc: 'thong_tin' })), 0).label, '9+');
});

test('danh sách điều kiện của nút bắt đầu lượt / chỉnh tay', () => {
  const g = L.canStartRun({ piOnline: true, running: false, hasBatch: false, ack: true, pending: false });
  assert.deepEqual(g.checks.map((c) => c.ok), [true, true, false, true]);
  const m = L.canManual({ piOnline: true, running: false, pha: '', pending: false, lamp: 0, fan: 75 });
  assert.equal(m.checks.some((c) => c.label.includes('làm ấm')), false);  // chưa chạy thì chưa hỏi làm ấm
});

test('so sánh chỉ số 2 lượt', () => {
  const rows = L.compareMetrics({ mae_c: 0.05, trong_vung_pct: 90, so_lan_doi_muc: 12 },
    { mae_c: 0.08, trong_vung_pct: 95, so_lan_doi_muc: 12 });
  const by = Object.fromEntries(rows.map((r) => [r.key, r]));
  assert.equal(by.mae_c.win, 'a');
  assert.equal(by.trong_vung_pct.win, 'b');
  assert.equal(by.so_lan_doi_muc.win, null);
  assert.equal(by.lam_am_s.a, '--');
  assert.equal(L.compareMetrics({ mae_c: 0.1 }, null)[0].win, null);
});

test('phân quyền: chỉ xem / điều khiển', () => {
  assert.equal(L.canControl('dieu_khien'), true);
  assert.equal(L.canControl('xem'), false);
  assert.equal(L.canControl(null), false);  // chưa đọc được quyền: chưa cho điều khiển
  assert.equal(L.roleLabel('xem'), 'Chỉ xem');
  assert.deepEqual(L.tabsFor('xem'), ['tong-quan', 'bieu-do', 'lich-su']);
  assert.equal(L.tabFromHash('#/dieu-khien', L.tabsFor('xem')), 'tong-quan');
  assert.equal(L.tabFromHash('#/dieu-khien', L.tabsFor('dieu_khien')), 'dieu-khien');
});

test('RL đang nghĩ gì: giải thích trạng thái và giá trị Q', () => {
  const now = 1_000_000;
  const nao = { ts: now - 3000, che_do: 'q', muc_tieu_c: 37.8, nhiet_c: 37.71, nhiet_dich_c: 37.41, dT5: -0.012,
    state: 1234, chon: 3, ly_do: 'q_max', thanh_phan: { sai_so: 3, xu_huong: 1, nho_nhiet: 2, truoc: 5, bao_ve: 0 },
    q: [1.2, 0.4, null, 2.5, 2.1, null, null, null, -0.3], so_lan: [10, 4, 0, 30, 22, 0, 0, 0, 2] };
  const v = L.brainView(nao, true, now);
  assert.equal(v.kind, 'q');
  assert.equal(v.bars.length, 9);
  assert.equal(v.bars[3].chosen && v.bars[3].best, true);
  assert.equal(v.bars[3].width, 100);
  assert.equal(v.bars[8].width, 10);
  assert.equal(v.bars[2].known, false);
  assert.match(v.text, /bóng 25 %, quạt 100 % vì có giá trị Q cao nhất \(2,50\) trong 5\/9/);
  assert.match(v.shift, /37,71 − \(37,8 − 37,5\) = 37,41/);
  assert.equal(v.chips[0].v, 'thấp hơn 0,08–0,2 °C');
  assert.match(v.chips[1].v, /gần như đứng yên \(-0,012 °C\)/);
  assert.equal(L.brainView(nao, false, now).kind, 'empty');
  assert.equal(L.brainView({ ...nao, ts: now - 60000 }, true, now).kind, 'empty');
  assert.equal(L.brainView({ ts: now, che_do: 'bao_ve' }, true, now).tone, 'bad');
  assert.match(L.brainView({ ts: now, che_do: 'thermostat', chon: 1 }, true, now).text, /bóng 0 %, quạt 100 %/);
  assert.match(L.brainView({ ...nao, ly_do: 'chua_hoc_lam_mat' }, true, now).text, /chưa gặp khi huấn luyện/);
});

test('thử nhiễu: tiến trình, kết quả, điều kiện, trung bình', () => {
  const base = { kieu: 'lanh', muc_tieu_c: 37.5, nhiet_c: 37.31, bat_dau_ts: 1000, het_han_ts: 61000, bo_dieu_khien: 'Q-learning 3 giai đoạn' };
  assert.match(L.testProgress({ ...base, trang_thai: 'DANG_NHIEU' }, 31000).text, /còn 0:30 · lệch hiện tại -0,19 °C/);
  assert.match(L.testProgress({ ...base, trang_thai: 'DANG_PHUC_HOI', ve_vung_s: 22 }, 91000).text, /Hết nhiễu 0:30 trước: đã về vùng sau 0:22/);
  const done = { ...base, trang_thai: 'XONG', ra_vung: true, ve_vung_s: 22, on_dinh_s: 30, lech_max_c: 0.31 };
  assert.match(L.testResultText(done), /Về vùng sau 0:22, ổn định sau 0:30; lệch tối đa 0,31 °C/);
  assert.match(L.testResultText({ ...done, ra_vung: false }), /không ra khỏi vùng/);
  const list = L.testList({ a: done, b: { ...done, bat_dau_ts: 5000, trang_thai: 'DANG_NHIEU' } });
  assert.equal(list[0].bat_dau_ts, 5000);
  assert.equal(L.activeTest(list).trang_thai, 'DANG_NHIEU');
  const live = { giai_doan: 'giu_nhiet', trong_vung: true };
  const ok = { piOnline: true, running: true, live, active: null, manualActive: false, pending: false };
  assert.equal(L.canDisturb(ok).ok, true);
  assert.equal(L.canDisturb({ ...ok, live: { ...live, trong_vung: false } }).ok, false);
  assert.equal(L.canDisturb({ ...ok, live: { giai_doan: 'tay', trong_vung: true } }).ok, false);
  const sum = L.testSummary([done, { ...done, ve_vung_s: 40 }, { ...done, bo_dieu_khien: 'Thermostat 3 giai đoạn', ve_vung_s: 70 }]);
  assert.deepEqual(sum.map((g) => [g.key, g.n, g.ve]), [['Q-learning 3 giai đoạn · nhiễu lạnh', 2, 31], ['Thermostat 3 giai đoạn · nhiễu lạnh', 1, 70]]);
  assert.match(L.commandStatus({ da_xu_ly: true, ket_qua: 'DANG_THU_NHIEU', xu_ly_ts: 1 }).text, /bắt đầu thử nhiễu/);
});

test('sức khỏe thiết bị', () => {
  const now = 10_000_000;
  const sk = { ts: now - 5000, cpu_c: 74.2, nguon: { yeu_hien_tai: false, tung_yeu: true, ma: '0x50000' }, wifi_dbm: -58,
    ip: '192.168.0.172', ram_dung_pct: 41.3, the_nho_trong_gb: 18.2, uptime_s: 93784, tai_1phut: 0.31,
    ds18b20: { doc: 200, loi: 1, ty_le_ok_pct: 99.5, dang_chay: true }, telegram: { bat: true, so_chat: 2, lan_cuoi_ok_ts: now - 120000 },
    bridge: '1.6', bridge_chay_s: 3600, may: 'pi' };
  const v = L.healthView(sk, { ty_le_ok_pct: 62 }, now);
  const by = Object.fromEntries(v.items.map((i) => [i.k, i]));
  assert.equal(by['Nhiệt CPU Pi'].tone, 'warn');
  assert.equal(by['Nguồn điện Pi'].v, 'Từng sụt áp');
  assert.equal(by['Wi-Fi'].v, '-58 dBm · mạnh');
  assert.equal(by['Pi chạy liên tục'].v, '1 ngày 2 giờ');
  assert.equal(by['DS18B20 (nhiệt)'].tone, 'ok');
  assert.equal(by['DHT11 (độ ẩm)'].tone, 'warn');
  assert.match(by.Telegram.hint, /2 phút trước/);
  assert.equal(v.badge, 'Cần chú ý');
  assert.equal(L.healthView({ ...sk, nguon: { yeu_hien_tai: true } }, null, now).badge, 'Có vấn đề');
  assert.equal(L.healthView({ ...sk, ts: now - 200000 }, null, now).stale, true);
  assert.equal(L.wifiQuality(-85).tone, 'bad');
  assert.equal(L.fmtUptime(3000), '50 phút');
});

test('xuất CSV lượt chạy', () => {
  const csv = L.sessionCsv({ bat_dau_ts: Date.UTC(2026, 10, 22, 7, 0, 0) },
    { '000005': { t: 5, T: 37.51, RH: 58, L: 50, F: 100, g: 'giu_nhiet', n: 12, k: 2 }, '000000': { t: 0, T: 30.1, L: 75, F: 100, g: 'lam_am' } });
  const lines = csv.replace('\ufeff', '').trim().split('\r\n');
  assert.equal(csv[0], '\ufeff');
  assert.equal(lines[0], 'thoi_gian_utc,giay_tu_dau,nhiet_c,do_am_pct,bong_pct,quat_pct,giai_doan,ngay_ap,giai_doan_ap');
  assert.equal(lines[1], '2026-11-22T07:00:00.000Z,0,30.1,,75,100,lam_am,,');
  assert.equal(lines[2], '2026-11-22T07:00:05.000Z,5,37.51,58,50,100,giu_nhiet,12,2');
  assert.equal(L.csvFileName('20261122_070000_rl'), 'hop_ap_20261122_070000_rl_mau5s.csv');
  assert.equal(L.csvFileName('a/b c'), 'hop_ap_a_b_c_mau5s.csv');
});

test('mẻ ấp chạy liên tục: trạng thái, tạo mẻ, đổi ngày', () => {
  const on = { piOnline: true, running: true }, idle = { piOnline: true, running: false };
  const lich = { co_me: true, ngay: 12, chay: true };
  assert.equal(L.batchState(null, on).has, false);
  assert.equal(L.batchState(lich, on).label, 'Đang ấp');
  assert.equal(L.batchState(lich, idle).label, 'Đang khởi động');
  const paused = L.batchState({ ...lich, chay: false, ly_do_dung: 'Dừng khẩn cấp từ a@b.c' }, idle);
  assert.equal(paused.label, 'Tạm dừng');
  assert.match(L.runHeadline(idle, null, paused).detail, /Dừng khẩn cấp từ a@b.c\. Bấm "Chạy tiếp"/);
  assert.equal(L.batchState({ ...lich, chay: false, het_lich: true }, idle).done, true);
  assert.equal(L.runHeadline(idle, null, L.batchState(lich, idle)).title, 'Đang khởi động phiên ấp…');
  assert.equal(L.canCreateBatch({ piOnline: true, chay: false, pending: false, day: 1 }).ok, true);
  assert.match(L.canCreateBatch({ piOnline: true, chay: true, pending: false, day: 1 }).reason, /kết thúc mẻ đang chạy/);
  assert.equal(L.canCreateBatch({ piOnline: true, chay: false, pending: false, day: 22 }).ok, false);
  assert.equal(L.canChangeDay({ piOnline: true, chay: true, running: true, pending: false, day: 12 }).ok, true);
  assert.equal(L.canChangeDay({ piOnline: true, chay: true, running: false, pending: false, day: 12 }).ok, false);
  assert.equal(L.canChangeDay({ piOnline: true, chay: false, running: true, pending: false, day: 12 }).ok, false);
  assert.match(L.dayCommandStatus({ ngay: 8, da_xu_ly: true, ket_qua: 'TU_CHOI: chỉ đổi ngày được khi mẻ ấp đang chạy', xu_ly_ts: 1 }).text,
    /Pi từ chối: chỉ đổi ngày/);
  assert.match(L.commandStatus({ da_xu_ly: true, ket_qua: 'DA_TAO', xu_ly_ts: 1 }).text, /bắt đầu ấp bằng RL/);
});
