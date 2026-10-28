"""Execute fixtures; never manufacture model-generated traces."""
import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from enterprise_qa.agent import run
from enterprise_qa.models import LiveModel, OfflineMock
from enterprise_qa.tools import Tools

CASES = [
    ('01_normal', '报销期限是多少？', 'normal.json', {}, [], 10, 'answered'),
    ('02_conflict', '报销期限是多少？', 'documents.json', {}, [], 10, 'needs_clarification'),
    ('03_out_of_scope', '公司停车位如何分配？', 'documents.json', {}, [], 10, 'insufficient_evidence'),
    ('04_paraphrase', '垫付之后最迟何时能报账？', 'normal.json', {}, [], 10, 'answered'),
    ('05_follow_up', '期限是多久？', 'normal.json', {}, 'history.json', 10, 'answered'),
    ('06_search_recovery', '报销期限是多少？', 'normal.json', {'search': 1}, [], 10, 'answered'),
    ('07_read_failure', '报销期限是多少？', 'normal.json', {'read': 2}, [], 10, 'tool_error'),
    ('08_step_limit', '报销期限是多少？', 'documents.json', {}, [], 1, 'incomplete'),
    ('09_missing_context', '期限是多久？', 'documents.json', {}, [], 10, 'needs_clarification'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['mock', 'live'], default='mock')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    output = ROOT / (args.output_dir or ('examples/' + args.mode))
    # Never leave a success-looking partial live suite when credentials are absent.
    factory = LiveModel if args.mode == 'live' else OfflineMock
    factory()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, question, data, failures, history, max_steps, expected in CASES:
        if isinstance(history, str):
            history = json.loads((ROOT / 'data' / history).read_text(encoding='utf-8'))
        result = run(factory(), Tools.load(ROOT/'data'/data, failures), question, history, max_steps)
        result['fixture'] = {'data': 'data/'+data, 'failures': failures, 'max_steps': max_steps}
        (output/(name+'.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        rows.append({'case': name, 'expected_status': expected, 'actual_status': result['status'],
                     'status_matches': result['status'] == expected, 'trace': name+'.json'})
    summary = {'mode': args.mode, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
               'python': platform.python_version(), 'model': factory().name,
               'scope': 'status checks only; live traces require human semantic review',
               'cases': rows, 'passed': sum(r['status_matches'] for r in rows), 'total': len(rows)}
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['passed'] == summary['total'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
