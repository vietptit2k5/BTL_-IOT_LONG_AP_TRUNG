"""Standalone plots from the two measured CSVs; no simulation or smoothing."""
from pathlib import Path
import json,sys
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing,String,Rect,Line
from reportlab.lib import colors

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'Code_HopAp_Demo'))
import phan_tich_reward as study

result=json.loads((OUT/'so_sanh.json').read_text(encoding='utf-8'))
runs=[result['baseline'],result['rl']]
sessions=[study.read_log(ROOT/r['path']) for r in runs]
palette=['#26768E','#C16B28']
d=Drawing(1100,800)
d.add(Rect(0,0,1100,800,fillColor=colors.white,strokeColor=None))

def label(x,y,value,size=12,anchor='start',color='#26354A'):
    d.add(String(x,y,value,fontName='Helvetica',fontSize=size,textAnchor=anchor,fillColor=colors.HexColor(color)))

def chart(data,y,height,minimum,maximum,step,title,show_x=False):
    p=LinePlot();p.x=65;p.y=y;p.width=980;p.height=height;p.data=data;p.joinedLines=1
    p.xValueAxis.valueMin=0;p.xValueAxis.valueMax=10;p.xValueAxis.valueStep=1
    p.yValueAxis.valueMin=minimum;p.yValueAxis.valueMax=maximum;p.yValueAxis.valueStep=step
    p.yValueAxis.visibleGrid=1;p.yValueAxis.gridStrokeColor=colors.HexColor('#E3E8EF')
    for axis in (p.xValueAxis,p.yValueAxis):
        axis.labels.fontName='Helvetica';axis.labels.fontSize=10;axis.strokeColor=colors.HexColor('#A6B2C1')
    if not show_x:p.xValueAxis.labels.visible=False
    for i,c in enumerate(palette):
        p.lines[i].strokeColor=colors.HexColor(c);p.lines[i].strokeWidth=1.7
    p.lines[0].strokeDashArray=[5,2]
    if len(data)>2:
        p.lines[2].strokeColor=colors.HexColor('#7D8996');p.lines[2].strokeDashArray=[3,3]
    d.add(p);label(65,y+height+15,title,12)

label(65,762,'THERMOSTAT VÀ Q-LEARNING: HAI LƯỢT ĐO TRÊN HỘP THẬT',19)
label(65,737,'Cùng đầu dò · mỗi lượt 600 giây · không gồm làm ấm và quạt cuối · không làm mượt số đo',12)
temperature=[]
for r,s in zip(runs,sessions):
    start,end=r['hold_start_s'],r['hold_end_s']
    temperature.append([((x['t']-start)/60,x['temperature']) for x in s['samples'] if start<=x['t']<=end])
temperature.append([(0,37.5),(10,37.5)])
d.add(Rect(65,395+(37.35-36.9)/1*260,980,.3*260,fillColor=colors.HexColor('#ECF7F0'),strokeColor=None))
chart(temperature,395,260,36.9,37.9,.2,'Nhiệt độ (°C); vùng xanh là 37,5 ± 0,15°C')

for channel,y,title in ((1,230,'Duty bóng đã áp dụng (%)'),(2,80,'Duty quạt đã áp dụng (%)')):
    series=[]
    for r,s in zip(runs,sessions):
        points=[];start,end=r['hold_start_s'],r['hold_end_s'];commands=s['commands']
        for i,c in enumerate(commands):
            left,right=max(start,c[0]),min(end,commands[i+1][0] if i+1<len(commands) else end)
            if right>left:
                points.extend([((left-start)/60,c[channel]*100),((right-start)/60,c[channel]*100)])
        series.append(points)
    chart(series,y,100,0,105,25,title,show_x=channel==2)

label(555,43,'Thời gian giữ nhiệt của từng lượt (phút)',12,anchor='middle')
for x,c,text in [(65,palette[0],'Thermostat'),(255,palette[1],'Q-learning, seed 11')]:
    d.add(Line(x,18,x+25,18,strokeColor=colors.HexColor(c),strokeWidth=2));label(x+33,14,text,11)
label(565,14,'Một cặp thử; nhiệt phòng chưa đo độc lập; chưa đo W/Wh.',11)
renderSVG.drawToFile(d,str(OUT/'SO_SANH_NHIET_THUC.svg'))
