"""Plot accelerated schedule illustration, not a 21-day incubation record."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('folder',type=Path)
args=p.parse_args()
with (args.folder/'CHUYEN_GIAI_DOAN_MO_PHONG.csv').open(encoding='utf-8') as f:
    data=list(csv.DictReader(f))
t=[float(r['seconds'])/60 for r in data]
temperature=[float(r['temperature_c']) for r in data]
target=[float(r['target_c']) for r in data]
band=[float(r['band_c']) for r in data]
fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True)
axes[0].fill_between(t,[a-b for a,b in zip(target,band)],[a+b for a,b in zip(target,band)],
                     step='pre',color='#4f9e69',alpha=.15,label='Proposed engineering band')
axes[0].plot(t,temperature,color='#197c88',label='Simulated air temperature',lw=1.4)
axes[0].step(t,target,where='pre',color='#555555',ls='--',lw=1,label='Stage target')
protected=[r for r in data if float(r['guard'])]
if protected:
    axes[0].scatter([float(r['seconds'])/60 for r in protected],[float(r['temperature_c']) for r in protected],
                    color='#c34137',s=12,label='Soft guard active',zorder=4)
for ax,column,label in zip(axes[1:],('lamp_pct','fan_pct'),('Lamp duty (%)','Fan duty (%)')):
    values=[float(r[column]) for r in data]
    ax.step([a-5/60 for a in t]+[t[-1]],values+[values[-1]],where='post',color='#197c88',lw=1.2)
    ax.set_ylabel(label)
axes[0].set_ylabel('Temperature (C)')
axes[0].legend(fontsize=8,loc='best')
axes[2].set_xlabel('Simulated time (minutes)')
for ax in axes:
    ax.grid(alpha=.2);ax.set_xlim(0,30)
    ax.axvline(10,color='#888888',ls=':',lw=.8)
    ax.axvline(20,color='#888888',ls=':',lw=.8)
fig.suptitle('SIMULATION ONLY: three stages compressed to 10 minutes each\nNot validated biological limits or a real incubation trace',fontsize=12)
fig.tight_layout()
fig.savefig(args.folder/'BA_GIAI_DOAN_MO_PHONG.png',dpi=160)
fig.savefig(args.folder/'BA_GIAI_DOAN_MO_PHONG.svg')
plt.close(fig)
