"""Plot the frozen gate without hiding lost baseline successes or error prefixes."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

PROJECT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();b=args.batch_dir
    data=json.loads((b/'acceptance.json').read_text())
    policy=json.loads((b/'batch_metadata.json').read_text())['spec']['acceptance']
    max_path=100*(1+policy['maximum_paired_total_path_increase'])
    max_outage=100*(1-policy['minimum_paired_total_outage_reduction'])
    target=(args.output or b/'oracle_tradeoffs.png').resolve()
    if not target.is_relative_to((PROJECT/'runtime').resolve()) or target.exists():
        raise ValueError('Use a new output file under project runtime')
    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    xs=[100.];ys=[100.]
    ax=axes[0];ax.scatter([100],[100],color='#334155',s=55)
    ax.annotate('lambda=0',(100,100),xytext=(5,8),textcoords='offset points')
    for index,(key,decision) in enumerate(data['decisions'].items()):
        p=decision['paired'];x=100*(1+p['path_increase']);y=100*(1-p['outage_reduction'])
        xs.append(x);ys.append(y)
        color='#15803d' if decision['passed'] else '#b91c1c'
        ax.scatter([x],[y],marker='o' if decision['passed'] else 'x',color=color,s=80,linewidths=2)
        ax.annotate(f"lambda={float(key):g}; lost {len(decision['lost_success_cases'])}/{len(data['baseline_success_subset'])}",
                    (x,y),xytext=(5,10 if index==0 else -18),textcoords='offset points',fontsize=9,color=color)
    ax.axhline(max_outage,color='#64748b',linestyle='--',linewidth=1)
    ax.axvline(max_path,color='#64748b',linestyle=':',linewidth=1)
    ax.set_xlim(min(xs)*.90,max(max_path,max(xs))*1.05);ax.set_ylim(min(ys)*.80,max(110,max(ys))*1.05)
    ax.set_xlabel('Path length / baseline (%)');ax.set_ylabel('Outage seconds / baseline (%)')
    ax.set_title('Fixed baseline-success subset\nAll frozen gates are required')
    ax.grid(alpha=.15)
    groups=list(data['aggregate']);positions=np.arange(3);width=.23
    for i,key in enumerate(groups):
        a=data['aggregate'][key];values=[a['sr_all_selected'],a['spl_all_selected'],a['ndtw_all_selected']]
        bars=axes[1].bar(positions+(i-1)*width,values,width,label=f'lambda={float(key):g}')
        for bar,v in zip(bars,values):axes[1].text(bar.get_x()+bar.get_width()/2,v+.015,f'{v:.3f}',ha='center',fontsize=8)
    axes[1].set_xticks(positions);axes[1].set_xticklabels(['SR','SPL','nDTW']);axes[1].set_ylim(0,1)
    axes[1].set_title('All selected cases per weight\nFailures and error prefixes retained');axes[1].legend(fontsize=8)
    verdict='no signal weight passes' if data['selected_lambda'] is None else f"selected lambda={data['selected_lambda']:g}"
    fig.suptitle('B3 development validation: '+verdict,fontsize=13)
    fig.text(.5,.02,f"{data['independent_language_tasks']} instructions; AP layouts are correlated. Red = failed gate, not a valid communication improvement. No significance claim.",ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.05,1,.93));fig.savefig(target,dpi=160);plt.close(fig)
    print(target)


if __name__=='__main__':main()
