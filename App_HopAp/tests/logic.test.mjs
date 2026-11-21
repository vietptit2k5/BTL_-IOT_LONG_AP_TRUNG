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
  assert.match(L.commandStatus({ da_xu_ly: true, ket_qua: 'DA_TAO', xu_ly_ts: 1 }).text, /tạo mẻ mới/);
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
