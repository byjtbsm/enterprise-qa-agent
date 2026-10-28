"""Check deliverable presence and evidence. Does not invent missing acceptance."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from scripts.evaluate import ALL_CASES, check_result, summarize_paths

REQUIRED = ['README.md','requirements.txt','pyproject.toml','.env.example',
    'docs/01-requirements.md','docs/02-solution.md','docs/03-evaluation.md',
    'docs/04-ai-usage.md','docs/05-retrospective.md','docs/06-submission.md',
    'examples/test-results.txt','src/enterprise_qa/agent.py','tests/test_agent.py']


def source_digest():
    digest = hashlib.sha256()
    paths = sorted(p for directory in ('src','scripts','data') for p in (ROOT/directory).rglob('*')
                   if p.is_file() and p.suffix in ('.py','.json') and not p.name.startswith('personal-record'))
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b'\x00'); digest.update(path.read_bytes()); digest.update(b'\x00')
    return digest.hexdigest()


def audit_live(directory):
    errors = []
    try:
        summary = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
        if summary.get('mode') != 'live':
            errors.append('summary is not live')
        if summary.get('source_digest') != source_digest():
            errors.append('live run source digest does not match current code/data; rerun')
        rows = {r['case']:r for r in summary['cases']}
        results = {}
        for name, question, data, failures, history, limit, expected in ALL_CASES:
            row = rows.get(name)
            if not row or not row.get('trace'):
                errors.append(name + ': missing run')
                continue
            path = (directory/row['trace']).resolve()
            if directory.resolve() not in path.parents:
                errors.append(name + ': invalid trace path'); continue
            result = json.loads(path.read_text(encoding='utf-8'))
            results[name] = result
            if result.get('mode') != 'live' or not result.get('model_calls'):
                errors.append(name + ': no live API call metadata')
            if result.get('question') != question or result.get('max_steps') != limit:
                errors.append(name + ': input does not match the acceptance fixture')
            expected_history = json.loads((ROOT/'data'/history).read_text(encoding='utf-8')) if isinstance(history,str) else history
            if result.get('history') != expected_history:
                errors.append(name + ': history does not match the acceptance fixture')
            fixture = result['fixture']
            corpus_path = (directory/fixture['data']).resolve()
            if directory.resolve() not in corpus_path.parents:
                errors.append(name + ': invalid corpus path'); continue
            raw = corpus_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != fixture.get('sha256') or raw != (ROOT/'data'/data).read_bytes():
                errors.append(name + ': corpus mismatch')
            checks = check_result(name,result,json.loads(raw),expected)
            if not all(checks.values()):
                errors.append(name + ': ' + ', '.join(k for k,v in checks.items() if not v))
            if fixture.get('failures') != failures:
                errors.append(name + ': failure injection mismatch')
        if not summarize_paths(results):
            errors.append('two distinct observation-driven paths not demonstrated')
        if summary.get('passed') != len(ALL_CASES) or summary.get('total') != len(ALL_CASES):
            errors.append('summary contains unsuccessful or missing cases')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        errors.append('invalid evidence files: '+type(exc).__name__)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-live',action='store_true')
    parser.add_argument('--require-personal',action='store_true')
    parser.add_argument('--live-dir',help='Specific run directory; otherwise use newest existing run')
    args = parser.parse_args(argv)
    errors = [f'missing {name}' for name in REQUIRED if not (ROOT/name).is_file()]
    test_log = ROOT/'examples/test-results.txt'
    if test_log.exists() and not re.search(r'\nOK\s*\n\s*Exit code: 0',test_log.read_text(encoding='utf-8')):
        errors.append('test-results.txt does not record a successful suite')
    try:
        tracked = subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).splitlines()
        if '.env' in tracked or any(f.startswith('.env.') and f != '.env.example' for f in tracked):
            errors.append('a local .env file is tracked by git')
    except (OSError,subprocess.CalledProcessError):
        pass
    if args.require_live:
        if args.live_dir:
            directory = Path(args.live_dir)
        else:
            candidates = sorted((ROOT/'examples/live').glob('*/summary.json'),key=lambda p:p.parent.name)
            directory = candidates[-1].parent if candidates else None
        if directory is None:
            errors.append('no real model run found; configure a model and execute --mode live')
        else:
            errors += audit_live(directory)
    if args.require_personal:
        try:
            personal = json.loads((ROOT/'data/personal-record.json').read_text(encoding='utf-8'))
            if not isinstance(personal, dict):
                raise ValueError('personal record must be an object')
            if type(personal.get('actual_minutes')) not in (int, float) or personal['actual_minutes'] <= 0:
                errors.append('actual_minutes must be a positive number')
            for key in ('actual_minutes','personal_changes','personal_verification','learning','reviewed_live_run'):
                if not personal.get(key):
                    errors.append('personal record missing '+key)
            reviewed = personal.get('reviewed_live_run')
            if isinstance(reviewed, str) and reviewed:
                reviewed_dir = (ROOT/reviewed).resolve()
                if ROOT.resolve() not in reviewed_dir.parents or not (reviewed_dir/'summary.json').is_file():
                    errors.append('reviewed_live_run must identify an actual run directory in this project')
                elif args.require_live and directory and reviewed_dir != directory.resolve():
                    errors.append('personal semantic review must refer to the live run selected by this audit')
            if personal.get('semantic_review_completed') is not True:
                errors.append('human semantic review has not been recorded')
        except (OSError,ValueError,TypeError):
            errors.append('no valid data/personal-record.json; copy the example and fill truthfully')
    if errors:
        print('Submission check FAILED:')
        for error in errors:
            print('- '+error)
        return 1
    print('Submission structure/evidence checks passed. Human statements are not independently verified.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
