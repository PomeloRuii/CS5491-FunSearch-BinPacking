"""Check and plot receipt-derived public measurements. No candidate execution."""

import argparse
from collections import Counter
import csv
import json
from math import isclose
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'results/main_study'
METHODS = ('standard','exact','s2_n16')
NAMES = ('Standard','Exact','S2-N16')
COLORS = ('#57768d','#8466a0','#13766f')


def rows(name):
    with (DATA/(name+'.csv')).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def summarize():
    runs, steps, audit, held = (rows(name) for name in ('matched_runs','trajectories','audit_events','heldout'))
    provenance = json.loads((DATA/'provenance.json').read_text(encoding='utf-8'))
    assert len(runs)==9 and len(steps)==549 and len(audit)==18 and len(held)==9
    by_run = {(int(r['pair']),r['method']):r for r in runs}
    assert len(by_run)==9
    for (pair,method), r in by_run.items():
        trace = [s for s in steps if int(s['pair'])==pair and s['method']==method]
        assert [int(s['ordinal']) for s in trace]==list(range(61))
        assert int(trace[-1]['cumulative_full'])==int(r['full'])
        assert float(trace[-1]['best_fitness'])==float(r['final_fitness'])
        assert int(r['requests'])==sum(int(r[k]) for k in ('full','exact_skips','behavioral_skips','c1_skips'))==60
        assert isclose(float(r['active_seconds']),float(r['generation_active_seconds'])+float(r['evaluation_active_seconds']))
        assert isclose(float(r['final_fitness']),-(float(r['or3_mean_bins'])+float(r['weibull_mean_bins']))/2)
    totals={m:sum(int(by_run[p,m]['full']) for p in range(3)) for m in METHODS}
    assert list(totals.values())==[180,83,48]
    assert sum(int(r['requests']) for r in runs)==provenance['normal_usage']['generation']==540
    assert sum(int(r['containers']) for r in runs)==provenance['normal_usage']['containers']==362
    assert sum(int(r['fingerprints']) for r in runs)==provenance['normal_usage']['fingerprint']==99
    assert sum(totals.values())==provenance['normal_usage']['full']==311
    margins=[float(r['island_margin']) for r in audit]
    assert Counter(int(r['pair']) for r in audit)=={0:6,1:6,2:6}
    for r in audit:
        assert isclose(float(r['fitness_delta']),float(r['candidate_fitness'])-float(r['representative_fitness']),abs_tol=1e-9)
        assert len(r['validation_positions'].split(';') if r['validation_positions'] else [])==int(r['validation_disagreements'])
    assert sum(m>1e-9 for m in margins)==7
    assert sum(abs(float(r['fitness_delta']))>1e-9 for r in audit)==2
    assert sum(float(r['global_margin'])>1e-9 for r in audit)==0
    assert sum(int(r['validation_disagreements']) for r in audit)==2
    assert len({r['source_sha256'] for r in held})==len({r['task'] for r in held})==8
    for r in held:
        assert float(r['or3_total_bins'])==4*float(r['or3_mean_bins'])
        assert float(r['fitness'])==-(float(r['or3_mean_bins'])+float(r['weibull_bins']))/2
    assert {(int(r['pair']),r['method']) for r in held}==set(by_run)
    assert provenance['heldout_usage']==dict(generation=0,containers=8,full=8,fingerprint=0)
    assert provenance['heldout_cumulative_usage']==dict(generation=0,containers=9,full=9,fingerprint=0)
    active=[float(by_run[p,'s2_n16']['active_seconds'])-float(by_run[p,'exact']['active_seconds']) for p in range(3)]
    assert list(map(lambda s:round(s,3),active))==[-90.801,-13.049,28.131]
    print(json.dumps(dict(requests=540,full_evaluations=totals,
        reduction_vs_exact_pct=100*(83-48)/83, s2_minus_exact_seconds=active,
        audit_events=len(audit),fitness_mismatches=2,potential_island_gains=7,above_global_best=0,
        heldout_incumbents=len(held),heldout_measurements=8),indent=2))
    return totals,active,steps


def make_figures(target, totals, active, steps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    plt.rcParams.update({'font.size':9,'axes.titlesize':11,'axes.labelcolor':'#263747',
                         'text.color':'#162a3a','axes.edgecolor':'#728796','savefig.dpi':240})
    target.mkdir(parents=True,exist_ok=True)
    fig,(left,right)=plt.subplots(1,2,figsize=(7.35,2.32),layout='constrained')
    bars=left.bar(NAMES,list(totals.values()),color=COLORS,width=.62)
    left.bar_label(bars,padding=3,fontsize=9)
    left.set(title='(a) Full Development evaluations',ylabel='Evaluations',ylim=(0,205))
    left.yaxis.set_major_locator(MaxNLocator(5,integer=True))
    bars=right.barh(['Pair 0','Pair 1','Pair 2'],active,color=[COLORS[2] if v<0 else '#ad6245' for v in active],height=.56)
    right.invert_yaxis()
    right.axvline(0,color='#647685',lw=.9)
    right.bar_label(bars,labels=[f'{v:+.1f}' for v in active],padding=3,fontsize=9)
    right.set(title='(b) S2-N16 minus Exact',xlabel='Method-active difference (s)',xlim=(-121,52))
    for ax in (left,right):
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y' if ax is left else 'x',alpha=.17)
        ax.set_axisbelow(True)
    fig.savefig(target/'efficiency.png',metadata={'Software':'CS5491 analysis'})
    plt.close(fig)

    fig, axes = plt.subplots(1,3,figsize=(7.35,2.43),sharey=True,layout='constrained')
    handles=[]
    for pair,ax in enumerate(axes):
        for m,name,color,style in zip(METHODS,NAMES,COLORS,('-', '--', ':'),strict=True):
            trace=[s for s in steps if int(s['pair'])==pair and s['method']==m]
            line,=ax.step([int(r['ordinal']) for r in trace],[float(r['best_fitness']) for r in trace],
                          where='post',lw=1.85,color=color,linestyle=style,label=name)
            if pair==0: handles.append(line)
        ax.set(title=f'Pair {pair}',xlim=(-1,61),ylim=(-2130,-1030),xticks=(0,20,40,60),xlabel='Requests')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(alpha=.17)
    axes[0].set_ylabel('Best-so-far fitness')
    fig.legend(handles,NAMES,loc='outside lower center',ncol=3,frameon=False)
    fig.savefig(target/'fitness.png',metadata={'Software':'CS5491 analysis'})
    plt.close(fig)

    pair2 = {m: [float(r['best_fitness']) for r in steps if r['pair']=='2' and r['method']==m] for m in METHODS}
    assert all(len(series)==61 for series in pair2.values())
    assert pair2['standard']==pair2['exact']
    delta=pair2['s2_n16'][-1]-pair2['exact'][-1]
    first_gain=next(i for i,(s,e) in enumerate(zip(pair2['s2_n16'],pair2['exact'],strict=True)) if s>e+1e-9)
    fig,(full,zoom)=plt.subplots(1,2,figsize=(7.35,2.43),layout='constrained')
    controls,=full.step(range(61),pair2['exact'],where='post',color=COLORS[0],lw=2.1,label='Standard and Exact')
    s2,=full.step(range(61),pair2['s2_n16'],where='post',color=COLORS[2],lw=2.0,linestyle='--',label='S2-N16')
    zoom.step(range(4,61),pair2['exact'][4:],where='post',color=COLORS[0],lw=2.1)
    zoom.step(range(4,61),pair2['s2_n16'][4:],where='post',color=COLORS[2],lw=2.0,linestyle='--')
    full.set(title='(a) Pair 2, full scale',ylabel='Best-so-far fitness',xlim=(-1,61),xticks=(0,20,40,60),ylim=(-2130,-1050))
    zoom.set(title='(b) Pair 2, zoom from wave 4',xlim=(4,61),xticks=(4,20,42,60),ylim=(-1148,-1113))
    zoom.annotate(f'+{delta:.3f} points',xy=(first_gain,pair2['s2_n16'][first_gain]),xytext=(14,-1122.5),
                  color=COLORS[2],fontsize=9,arrowprops={'arrowstyle':'->','color':COLORS[2],'lw':1})
    for ax in (full,zoom):
        ax.set_xlabel('Requests')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(alpha=.17)
    fig.legend([controls,s2],['Standard and Exact','S2-N16'],loc='outside lower center',ncol=2,frameon=False)
    fig.savefig(target/'fitness_pair2.png',metadata={'Software':'CS5491 analysis'})
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures',type=Path,help='Optional directory for PNG figures; requires Matplotlib 3.8+')
    args=parser.parse_args()
    measurements=summarize()
    if args.figures:
        make_figures(args.figures,*measurements)


if __name__=='__main__':
    main()
