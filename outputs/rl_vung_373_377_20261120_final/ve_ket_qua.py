"""Plot the PREDECLARED first simulated test case; not a hardware trace."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

folder=Path(__file__).resolve().parent
with (folder/'trace_MO_PHONG.csv').open(encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True)
for name,color,label in [('old_q','#c55b32','Previous Q-table'),('candidate','#197c88','New band Q-table')]:
    r=[p for p in rows if p['controller']==name]
    t=[float(p['seconds'])/60 for p in r]
    axes[0].plot(t,[float(p['temperature_c']) for p in r],color=color,label=label,lw=1.5)
    starts=[x-5/60 for x in t]+[t[-1]]
    for ax,column in zip(axes[1:],('lamp_pct','fan_pct')):
        values=[float(p[column]) for p in r]
        ax.step(starts,values+[values[-1]],where='post',color=color,label=label,lw=1.3)
axes[0].axhspan(37.3,37.7,color='#459b64',alpha=.12,label='Target band 37.3-37.7 C')
axes[0].axhline(37.5,color='#555555',ls='--',lw=.8)
axes[0].set_ylabel('Temperature (C)')
axes[1].set_ylabel('Lamp duty (%)')
axes[2].set_ylabel('Fan duty (%)')
axes[2].set_xlabel('Simulated time (minutes)')
axes[0].legend(loc='best',fontsize=9)
for ax in axes:
    ax.grid(alpha=.2)
    ax.set_xlim(0,10)
fig.suptitle('SIMULATION ONLY: fixed first test case, same initial state and noise',fontsize=13)
fig.tight_layout()
fig.savefig(folder/'SO_SANH_MO_PHONG.png',dpi=160)
fig.savefig(folder/'SO_SANH_MO_PHONG.svg')
plt.close(fig)
