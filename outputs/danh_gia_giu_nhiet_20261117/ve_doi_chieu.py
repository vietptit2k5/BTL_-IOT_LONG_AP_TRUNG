"""Render actual thermostat measurements and frozen-model replay separately."""
from pathlib import Path
import csv,json
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing,String,Rect,Line
from reportlab.lib import colors

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
DATA=ROOT/'Du_lieu_giu_nhiet/20261117_084602_831190/du_lieu.csv'
with DATA.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
with (OUT/'doi_chieu_du_bao.csv').open(encoding='utf-8-sig',newline='') as f:pred=list(csv.DictReader(f))
result=json.loads((OUT/'danh_gia.json').read_text(encoding='utf-8'))
start,end=result['hold_start_s'],result['hold_end_s']
measured=[((float(r['elapsed_s'])-float(r['temperature_age_s'])-start)/60,float(r['temperature_c']))
          for r in raw if r['event']=='MEASUREMENT' and start<=float(r['elapsed_s'])<=end]
open_loop=[(float(r['hold_seconds'])/60,float(r['open_loop_prediction_c'])) for r in pred]
d=Drawing(1100,650)
d.add(Rect(0,0,1100,650,fillColor=colors.white,strokeColor=None))

def label(x,y,text,size=12,color='#26354A',anchor='start'):
    d.add(String(x,y,text,fontName='Helvetica',fontSize=size,fillColor=colors.HexColor(color),textAnchor=anchor))

def plot(data,x,y,w,h,minimum,maximum,step,palette,title):
    p=LinePlot();p.x=x;p.y=y;p.width=w;p.height=h;p.data=data;p.joinedLines=1
    p.xValueAxis.valueMin=0;p.xValueAxis.valueMax=10;p.xValueAxis.valueStep=1
    p.yValueAxis.valueMin=minimum;p.yValueAxis.valueMax=maximum;p.yValueAxis.valueStep=step
    p.yValueAxis.visibleGrid=1;p.yValueAxis.gridStrokeColor=colors.HexColor('#E3E8EF')
    for a in (p.xValueAxis,p.yValueAxis):
        a.labels.fontName='Helvetica';a.labels.fontSize=10;a.strokeColor=colors.HexColor('#A6B2C1')
    for i,c in enumerate(palette):
        p.lines[i].strokeColor=colors.HexColor(c);p.lines[i].strokeWidth=1.6
    d.add(p);label(x,y+h+14,title,12)
    return p

label(65,613,'THERMOSTAT THỰC VÀ MÔ HÌNH PHÁT LẠI CÙNG LỆNH',19)
label(65,589,'10 phút giữ nhiệt · MAE thực 0,121°C · 100% trong 37–38°C · không ngắt mềm',12)
d.add(Rect(65,295+(37-36.5)/2*230,980,230/2,fillColor=colors.HexColor('#ECF7F0'),strokeColor=None))
p=plot([measured,open_loop,[(0,37.5),(10,37.5)]],65,295,980,230,36.5,38.5,.5,
       ['#18678A','#C16B28','#7B8899'],'Nhiệt độ (°C)')
p.lines[2].strokeDashArray=[5,3]
p.xValueAxis.labels.visible=False
commands=[]
for r in raw:
    if r['event'] in ('COMMAND','OUTPUT_CHANGE','END'):
        commands.append((float(r['elapsed_s']),float(r['lamp_command_pct']),float(r['fan_command_pct'])))
h,f=[],[]
for a,b in zip(commands,commands[1:]):
    left,right=max(start,a[0]),min(end,b[0])
    if left<right:
        h.extend([((left-start)/60,a[1]),((right-start)/60,a[1])])
        f.extend([((left-start)/60,a[2]),((right-start)/60,a[2])])
plot([h,f],65,115,980,120,0,105,25,['#C16B28','#158275'],'Duty lệnh đã áp dụng (%)')
label(555,77,'Thời gian giữ nhiệt (phút); không gồm làm ấm và quạt cuối',12,anchor='middle')
for x,y,color,text in [(65,44,'#18678A','Nhiệt đo'),(240,44,'#C16B28','Mô hình phát lại dài hạn'),
                       (65,20,'#C16B28','Bóng'),(240,20,'#158275','Quạt')]:
    d.add(Line(x,y+4,x+22,y+4,strokeColor=colors.HexColor(color),strokeWidth=2));label(x+30,y,text,11)
label(600,44,'Đường mô hình không đặt lại theo nhiệt đo.',11)
label(600,20,'Chưa có nhiệt đo khi RL điều khiển trong đồ thị này.',11)
renderSVG.drawToFile(d,str(OUT/'doi_chieu_thuc_do.svg'))
