"""Render the saved development metrics; no training or hardware access."""
from pathlib import Path
import json
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing,String,Rect,Line
from reportlab.lib import colors

folder=Path(__file__).resolve().parent
result=json.loads((folder/'ket_qua.json').read_text(encoding='utf-8'))
d=Drawing(1100,580)
d.add(Rect(0,0,1100,580,fillColor=colors.white,strokeColor=None))

def text(x,y,value,size=12,anchor='start',color='#26354A'):
    d.add(String(x,y,value,fontName='Helvetica',fontSize=size,textAnchor=anchor,fillColor=colors.HexColor(color)))

text(65,545,'ĐƯỜNG HỌC TRÊN VALIDATION MÔ PHỎNG',20)
text(65,520,'Trung bình 3 seed · 32 tình huống × 600 giây · cùng ngắt mềm 38→37°C',12)
palette=['#267C80','#425C9A','#9A58A0','#C16B28']
for panel,algorithm,title in ((0,'q-learning','Q-learning'),(1,'expected-sarsa','Expected SARSA')):
    x,y,w,h=65+panel*540,140,440,285
    text(x,460,title,16)
    text(x,440,'Thời gian trong vùng 37–38°C (%)',11)
    p=LinePlot();p.x=x;p.y=y;p.width=w;p.height=h;p.joinedLines=1
    data=[]
    for weights in result['protocol']['grid']:
        rows=sorted((r for r in result['trials'] if r['algorithm']==algorithm and r['weights']==weights),key=lambda r:r['episodes'])
        data.append([(r['episodes']/1000,r['validation']['in_band_pct']) for r in rows])
    data.extend([[(.5,90),(4,90)],[(.5,result['baseline']['validation']['in_band_pct']),(4,result['baseline']['validation']['in_band_pct'])]])
    p.data=data
    p.xValueAxis.valueMin=.5;p.xValueAxis.valueMax=4;p.xValueAxis.valueStep=.5
    p.yValueAxis.valueMin=60;p.yValueAxis.valueMax=100;p.yValueAxis.valueStep=10
    p.yValueAxis.visibleGrid=1;p.yValueAxis.gridStrokeColor=colors.HexColor('#E3E8EF')
    for axis in (p.xValueAxis,p.yValueAxis):
        axis.labels.fontName='Helvetica';axis.labels.fontSize=10;axis.strokeColor=colors.HexColor('#A6B2C1')
    for i,color in enumerate(palette):
        p.lines[i].strokeColor=colors.HexColor(color);p.lines[i].strokeWidth=1.8
    for i in (4,5):
        p.lines[i].strokeColor=colors.HexColor('#A6B2C1');p.lines[i].strokeWidth=.9;p.lines[i].strokeDashArray=[4,3]
    d.add(p)
    text(x+w/2,103,'Số episode (nghìn)',11,anchor='middle')
for i,(weights,color) in enumerate(zip(result['protocol']['grid'],palette)):
    x=65+(i%2)*290;y=67-(i//2)*24
    d.add(Line(x,y+4,x+22,y+4,strokeColor=colors.HexColor(color),strokeWidth=2))
    text(x+30,y,f'hot={weights["hot"]:g}, duty={weights["duty"]:g}',11)
text(690,67,'Nét xám: mốc 90% và đối chứng validation.',11)
text(690,43,'Kết quả này chưa phải lượt đo giữ nhiệt thật.',11)
renderSVG.drawToFile(d,str(folder/'duong_hoc.svg'))
