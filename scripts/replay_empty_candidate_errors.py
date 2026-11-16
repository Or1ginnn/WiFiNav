"""CPU replay of original invalid outputs, not a new model or VLN run."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from connectivity_vln.navigation.pixel_policy import PixelPolicy, ToolParseError
read = lambda p: json.loads(Path(p).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to((PROJECT/'runtime').resolve()):
        raise ValueError('Output must stay under runtime')
    output.mkdir(parents=True,exist_ok=False)
    source = PROJECT/'runtime/batches/oracle_full_action_guard_v1'
    rows = []
    for weight in (1,4):
        directory = source/f'episode_743_near_lambda{weight}'/'decision_003'
        candidates = read(directory/'candidates.json')
        if candidates != []: raise ValueError('Expected original empty candidates')
        responses = [read(directory/f'response_{i}.json') for i in range(2)]
        for enabled in (False,True):
            case = output/f'lambda{weight}_recovery{int(enabled)}'
            case.mkdir()
            policy = PixelPolicy(read(PROJECT/'configs/model/qwen35b.json'),{
                'interface_version':'v1','stop_review_enabled':False,
                'max_history_images':2,'max_parse_attempts':2,'empty_candidate_recovery':enabled})
            policy._chat = Mock(side_effect=responses)
            error = None; choice = record = None
            try:
                choice,record = policy.decide('Offline output replay, no inference',
                    directory/'policy_view.png',candidates,case)
            except ToolParseError as caught: error = str(caught)
            rows.append({'lambda':weight,'enabled':enabled,'error':error,'choice':choice,
                'record':record,'attempts':policy._chat.call_count,
                'source_sha256':{str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in directory.iterdir() if p.is_file()}})
            if policy._chat.call_count != 2 or bool(error) == enabled:
                raise AssertionError('Unexpected recovery replay result')
    (output/'report.json').write_text(json.dumps({
        'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
        'model_config':read(PROJECT/'configs/model/qwen35b.json'),
        'scope':'original response replay only; no API, GPU rendering, or closed-loop success claim',
        'rows':rows},indent=2)+'\n')
    print('replayed four conditions; original off errors preserved, on legal LOOK',flush=True)


if __name__ == '__main__': main()
