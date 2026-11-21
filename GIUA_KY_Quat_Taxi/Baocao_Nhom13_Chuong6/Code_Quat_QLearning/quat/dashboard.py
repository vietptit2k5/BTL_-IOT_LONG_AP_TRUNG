#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web xem trực tiếp nhiệt độ + mức quạt khi agent đang chạy (đọc file log CSV).
Chạy trên Pi:   python3 dashboard.py --log log_q.csv --target 52
Mở trên laptop: http://pi:5000   (laptop và Pi cùng mạng; không cần Internet, chart.umd.js để cạnh file này)
Cài Flask nếu chưa có:  sudo apt install -y python3-flask
"""
import argparse
import csv
import os

import numpy as np
from flask import Flask, jsonify, send_file

ap = argparse.ArgumentParser()
ap.add_argument("--log", default="log_q.csv")
ap.add_argument("--q", default="q_quat.npy")
ap.add_argument("--rewards", default="q_quat_rewards.npy")
ap.add_argument("--target", type=float, default=52.0)
ap.add_argument("--port", type=int, default=5000)
args = ap.parse_args()

app = Flask(__name__)

PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quạt Q-learning</title>
<script src="/chart.js"></script>
<style>
body{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}
h1{font-size:20px;margin:0 0 4px} .sub{color:#666;font-size:13px;margin-bottom:12px}
.kpi{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.kpi div{border:1px solid #ddd;border-radius:8px;padding:8px 12px;min-width:120px}
.kpi b{display:block;font-size:22px} .kpi span{font-size:12px;color:#666}
.box{border:1px solid #ddd;border-radius:8px;padding:8px;margin-bottom:12px}
table{border-collapse:collapse;font-size:13px} td,th{border:1px solid #ddd;padding:3px 8px;text-align:center}
.tang{background:#fde2e2}.giam{background:#e2ecfd}.giu{background:#eee}
</style></head><body>
<h1>Điều khiển quạt bằng Q-learning (Raspberry Pi 4)</h1>
<div class="sub">Tự cập nhật mỗi 3 giây · file log: <code>%LOG%</code> · target %TARGET% °C</div>
<div class="kpi">
 <div><b id="k_t">-</b><span>Nhiệt độ CPU hiện tại</span></div>
 <div><b id="k_l">-</b><span>Mức quạt hiện tại</span></div>
 <div><b id="k_a">-</b><span>Hành động vừa chọn</span></div>
 <div><b id="k_p">-</b><span>Đầu dò DS18B20</span></div>
 <div><b id="k_avg">-</b><span>Nhiệt độ TB</span></div>
 <div><b id="k_in">-</b><span>% thời gian trong target ±3 °C</span></div>
</div>
<div class="box"><canvas id="c1" height="110"></canvas></div>
<div class="box"><canvas id="c2" height="60"></canvas></div>
<div class="box"><canvas id="c3" height="80"></canvas></div>
<div class="box"><b>Q-table: hành động agent chọn ở mỗi tình huống</b><div id="qt"></div></div>
<script>
const TARGET=%TARGET%;
const c1=new Chart(document.getElementById('c1'),{type:'line',data:{labels:[],datasets:[
 {label:'Nhiệt độ CPU (°C)',data:[],borderColor:'#d62728',pointRadius:0,tension:.2},
 {label:'Đầu dò DS18B20 (°C)',data:[],borderColor:'#999',borderDash:[2,2],pointRadius:0},
 {label:'Target',data:[],borderColor:'#2ca02c',borderDash:[6,4],pointRadius:0}]},
 options:{animation:false,scales:{x:{title:{display:true,text:'giây'}}}}});
const c2=new Chart(document.getElementById('c2'),{type:'line',data:{labels:[],datasets:[
 {label:'Mức quạt (0-3)',data:[],borderColor:'#1f77b4',stepped:true,pointRadius:0}]},
 options:{animation:false,scales:{y:{min:0,max:3,ticks:{stepSize:1}}}}});
const c3=new Chart(document.getElementById('c3'),{type:'line',data:{labels:[],datasets:[
 {label:'Tổng reward mỗi episode khi học trong mô phỏng',data:[],borderColor:'#ccc',pointRadius:0},
 {label:'Trung bình trượt 20 episode',data:[],borderColor:'#9467bd',borderWidth:3,pointRadius:0}]},
 options:{animation:false,scales:{x:{title:{display:true,text:'episode'}}}}});
async function tick(){
 const d=await (await fetch('/data')).json();
 if(d.sec.length){
  const n=d.sec.length-1;
  c1.data.labels=d.sec; c1.data.datasets[0].data=d.temp; c1.data.datasets[1].data=d.probe;
  c1.data.datasets[2].data=d.sec.map(()=>TARGET); c1.update();
  c2.data.labels=d.sec; c2.data.datasets[0].data=d.lvl; c2.update();
  document.getElementById('k_t').textContent=d.temp[n].toFixed(1)+' °C';
  document.getElementById('k_l').textContent=d.lvl[n];
  document.getElementById('k_a').textContent=d.act[n];
  document.getElementById('k_p').textContent=d.probe[n]==null?'-':d.probe[n].toFixed(1)+' °C';
  document.getElementById('k_avg').textContent=d.avg.toFixed(1)+' °C';
  document.getElementById('k_in').textContent=d.inband.toFixed(0)+' %';
 }
}
async function once(){
 const r=await (await fetch('/learn')).json();
 c3.data.labels=r.ep; c3.data.datasets[0].data=r.r; c3.data.datasets[1].data=r.avg; c3.update();
 let h='<table><tr><th>Nhiệt độ</th><th>quạt 0</th><th>quạt 1</th><th>quạt 2</th><th>quạt 3</th></tr>';
 for(const row of r.qt){h+='<tr><td>'+row[0]+'</td>'+row.slice(1).map(a=>'<td class="'+(a=='tăng'?'tang':a=='giảm'?'giam':'giu')+'">'+a+'</td>').join('')+'</tr>';}
 document.getElementById('qt').innerHTML=r.qt.length?h+'</table>':'(không tìm thấy Q-table)';
}
once(); tick(); setInterval(tick,3000);
</script></body></html>"""


@app.route("/")
def index():
    return PAGE.replace("%LOG%", args.log).replace("%TARGET%", str(args.target))


@app.route("/chart.js")
def chartjs():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart.umd.js"),
                     mimetype="application/javascript")


@app.route("/data")
def data():
    sec, temp, lvl, act, probe = [], [], [], [], []
    if os.path.exists(args.log):
        with open(args.log, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    sec.append(round(float(row["giay"])))
                    temp.append(float(row["nhiet_do"]))
                    lvl.append(int(row["muc_quat"]))
                    act.append(row["hanh_dong"])
                    p = row.get("dau_do_ds18b20") or ""
                    probe.append(float(p) if p else None)
                except (ValueError, KeyError, TypeError):
                    continue                     # dòng đang ghi dở
    T = np.array(temp) if temp else np.array([0.0])
    return jsonify(sec=sec, temp=temp, lvl=lvl, act=act, probe=probe,
                   avg=float(T.mean()), inband=float(100 * np.mean(np.abs(T - args.target) <= 3)))


@app.route("/learn")
def learn():
    out = {"ep": [], "r": [], "avg": [], "qt": []}
    if os.path.exists(args.rewards):
        r = np.load(args.rewards)
        k = 20
        avg = np.convolve(r, np.ones(k) / k, mode="same")
        out.update(ep=list(range(len(r))), r=[float(x) for x in r], avg=[float(x) for x in avg])
    if os.path.exists(args.q):
        import fan_qlearning as f
        Q = np.load(args.q)
        T = args.target
        for b in range(f.N_TEMP):
            lo = "<%d" % (T + f.TEMP_OFFSETS[0]) if b == 0 else (
                ">=%d" % (T + f.TEMP_OFFSETS[-1]) if b == f.N_TEMP - 1 else
                "%d-%d" % (T + f.TEMP_OFFSETS[b - 1], T + f.TEMP_OFFSETS[b]))
            out["qt"].append([lo] + [f.ACTION_NAME[int(np.argmax(Q[b * f.N_LEVEL + l]))]
                                     for l in range(f.N_LEVEL)])
    return jsonify(out)


if __name__ == "__main__":
    print("Mở trên laptop: http://pi:%d  (hoặc http://<IP của Pi>:%d)" % (args.port, args.port))
    app.run(host="0.0.0.0", port=args.port, debug=False)
