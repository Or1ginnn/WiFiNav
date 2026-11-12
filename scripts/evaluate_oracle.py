"""Evaluate a completed full Oracle batch against its frozen development gate."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from connectivity_vln.evaluation.oracle import assess, complete, metric, success


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch-dir',type=Path,required=True)
    args=parser.parse_args();b=args.batch_dir
    meta=json.loads((b/'batch_metadata.json').read_text());spec=meta['spec']
    assert hashlib.sha256((b/'manifest.json').read_bytes()).hexdigest()==meta['manifest_sha256']
    manifest=json.loads((b/'manifest.json').read_text())
    expected={(e['episode_id'],l['layout_id']) for e in manifest['episodes'] for l in e['layouts']}
    rows=json.loads((b/'oracle_report.json').read_text())['rows']
    result=assess(rows,spec,expected)
    result.update({'execution_commit':meta['execution_commit'],'manifest_sha256':meta['manifest_sha256'],'spec_sha256':meta['spec_sha256']})
    with (b/'acceptance.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    with (b/'case_metrics.csv').open('x') as f:
        writer=csv.writer(f);writer.writerow(['episode','layout','lambda','complete','success','spl','ndtw','path_m','actions','collisions','outage_s','outage_ratio','longest_s','weak_s','motion_s','requests','wall_s','exit','error','run_dir'])
        for r in rows:
            c=r.get('communication') or {};s=r.get('summary') or {}
            writer.writerow([r['episode_id'],r['layout_id'],r['lambda'],complete(r),success(r),metric(r,'spl'),metric(r,'ndtw_exact_euclidean'),metric(r,'path_length_m'),metric(r,'primitive_actions_including_stop'),metric(r,'collision_actions'),c.get('outage_seconds'),c.get('outage_ratio'),c.get('longest_outage_seconds'),c.get('weak_seconds'),c.get('motion_time_seconds'),s.get('model_request_attempts'),r['status']['wall_seconds'],s.get('exit_reason'),s.get('error'),r['run_dir']])
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
