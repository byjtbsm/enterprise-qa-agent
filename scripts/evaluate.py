"""Run actual cases, check observable behavior, and preserve every live run."""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from enterprise_qa.agent import run
from enterprise_qa.config import load_env
from enterprise_qa.models import LiveModel, OfflineMock
from enterprise_qa.tools import Tools

# Tuple: id, input, corpus, injected failures, history, step limit, expected status.
CASES = [
    ('01_normal', '报销期限是多少？', 'normal.json', {}, [], 10, 'answered'),
    ('02_conflict', '报销期限是多少？', 'documents.json', {}, [], 10, 'needs_clarification'),
    ('03_out_of_scope', '公司停车位如何分配？', 'documents.json', {}, [], 10, 'insufficient_evidence'),
    ('04_paraphrase', '垫付之后最迟何时能报账？', 'normal.json', {}, [], 10, 'answered'),
    ('05_follow_up', '期限是多久？', 'normal.json', {}, 'history.json', 10, 'answered'),
    ('06_search_recovery', '报销期限是多少？', 'normal.json', {'search': 1}, [], 10, 'answered'),
    ('07_read_failure', '报销期限是多少？', 'normal.json', {'read': 100}, [], 10, 'tool_error'),
    ('08_step_limit', '报销期限是多少？', 'documents.json', {}, [], 1, 'incomplete'),
    ('09_missing_context', '期限是多久？', 'documents.json', {}, [], 10, 'needs_clarification'),
]
EXTRA_CASES = [
    ('10_document_changed', '报销期限是多少？', 'changed.json', {}, [], 10, 'answered'),
    ('11_conflict_resolved', '报销期限是多少？', 'resolved.json', {}, [], 10, 'answered'),
]
ALL_CASES = CASES + EXTRA_CASES


def check_result(name, result, documents, expected):
    """Observable acceptance checks; cannot replace semantic human review."""
    checks = {'status_matches': result['status'] == expected,
              'within_step_limit': result['steps'] <= result['max_steps']}
    evidence = {e['observation']['document']['id']: e['observation']['document']
                for e in result['trace'] if e.get('observation', {}).get('ok') and
                'document' in e['observation']}
    citations = result['citations']
    checks['citations_verified'] = all(
        c.get('doc_id') in evidence and isinstance(c.get('quote'), str) and c['quote'].strip()
        and c['quote'] in evidence[c['doc_id']]['text'] for c in citations)
    if expected == 'answered':
        number = '(45|四十五)' if name == '10_document_changed' else '(30|三十)'
        checks['answer_contains_expected_deadline'] = bool(re.search(number + r'\s*(个自然日|天|日)', result['answer']))
        checks['answer_has_evidence'] = bool(citations) and 'D01' in {c['doc_id'] for c in citations}
    if name == '02_conflict':
        checks['both_conflicting_sources_read_and_cited'] = {'D01','D02'} <= {c['doc_id'] for c in citations}
        joined = result['answer'] + ' '.join(c['quote'] for c in citations)
        checks['both_deadlines_present'] = all(re.search(n + r'\s*(天|日)', joined) for n in ('30','15'))
        checks['missing_scope_reported'] = bool(result['gaps'])
    if name == '11_conflict_resolved':
        checks['both_candidate_originals_read'] = {'D01','D02'} <= set(evidence)
    if name in ('03_out_of_scope', '07_read_failure', '09_missing_context'):
        checks['no_unsupported_citations'] = not citations
        checks['gap_reported'] = bool(result['gaps'])
    if name in ('06_search_recovery', '07_read_failure'):
        failure_steps = [e for e in result['trace'] if e.get('observation', {}).get('error') == 'injected_tool_failure']
        checks['failure_actually_observed'] = bool(failure_steps)
        checks['action_after_failure'] = bool(failure_steps) and failure_steps[0]['step'] < result['steps']
    if name == '08_step_limit':
        checks['incomplete_is_explicit'] = result['status'] == 'incomplete' and bool(result['gaps'])
    return {k: bool(v) for k,v in checks.items()}


def summarize_paths(results):
    normal, conflict = results.get('01_normal'), results.get('02_conflict')
    if not normal or not conflict:
        return False
    def reads(r):
        return {e['observation']['document']['id'] for e in r['trace']
                if e.get('observation',{}).get('ok') and 'document' in e['observation']}
    return (normal['status'] == 'answered' and conflict['status'] == 'needs_clarification'
            and 'D01' in reads(normal) and {'D01','D02'} <= reads(conflict)
            and normal['trace'][-1].get('action') == 'finish'
            and conflict['trace'][-1].get('action') == 'finish')


def current_commit():
    try:
        return subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_report(output, summary):
    lines = ['# 实际执行报告', '', f"- 模式：`{summary['mode']}`；模型：`{summary['model']}`",
             f"- 时间：{summary['generated_at_utc']}；运行前 HEAD：`{summary['source_commit']}`",
             f"- 实际源码/资料 SHA-256：`{summary['source_digest']}`（以此对应本次代码和资料）。",
             f"- 自动检查：{summary['passed']}/{summary['total']} 场景通过。",
             f"- 两条不同工具观察路径：{'通过' if summary['distinct_observation_paths'] else '未通过'}。",
             '- 人工语义核验：尚未完成，自动通过不等于最终验收完成。', '',
             '| 场景 | 预期 | 实际 | 自动检查 | Trace |', '|---|---|---|---|---|']
    for row in summary['cases']:
        link = f"[查看]({row['trace']})" if row.get('trace') else '未执行'
        lines.append(f"| {row['case']} | {row['expected_status']} | {row['actual_status']} | {'通过' if row['passed'] else '失败'} | {link} |")
    lines += ['', '## 失败检查', '']
    for row in summary['cases']:
        failed = [k for k,v in row.get('checks',{}).items() if not v]
        if failed or not row['passed']:
            lines.append(f"- {row['case']}：{', '.join(failed) or '未执行'}")
    lines += ['', '## 人工必须核验', '',
              '- 答案是否被引用逐条支持，有没有添加原文没有的事实？',
              '- 冲突是否说明差异并请求适用范围/优先级，是否擅自按日期选择？',
              '- 下一步动作是否回应真实工具结果，失败后有没有假定成功？',
              '- 替换资料后的回答与动作是否变化？',
              '- 核查后填写 docs/08-personal-record.md，并记录真实个人投入。', '']
    (output/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['mock','live'], default='mock')
    parser.add_argument('--output-dir', help='New live directory only; refuses to overwrite an earlier live run')
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / (args.output_dir or ('examples/mock' if args.mode == 'mock' else f'examples/live/{stamp}'))
    try:
        if args.mode == 'live':
            load_env()
        factory = LiveModel if args.mode == 'live' else OfflineMock
        factory()
        if args.mode == 'live' and output.exists() and any(output.iterdir()):
            raise ValueError('refusing to overwrite an earlier live run; choose a new --output-dir')
    except (ValueError, OSError) as exc:
        print(json.dumps({'status':'configuration_error','error':str(exc)},ensure_ascii=False), file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    (output/'corpus').mkdir(exist_ok=True)
    rows, results = [], {}
    fatal = False
    for name, question, data, failures, history, max_steps, expected in ALL_CASES:
        if fatal:
            rows.append({'case':name,'expected_status':expected,'actual_status':'not_executed',
                         'passed':False,'trace':None,'checks':{'model_available':False}})
            continue
        if isinstance(history,str):
            history = json.loads((ROOT/'data'/history).read_text(encoding='utf-8'))
        raw = (ROOT/'data'/data).read_bytes()
        documents = json.loads(raw)
        (output/'corpus'/data).write_bytes(raw)
        result = run(factory(), Tools(documents,failures), question, history, max_steps)
        result['fixture'] = {'data':'corpus/'+data,'sha256':hashlib.sha256(raw).hexdigest(),
                             'failures':failures,'max_steps':max_steps}
        (output/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        results[name] = result
        checks = check_result(name,result,documents,expected)
        rows.append({'case':name,'expected_status':expected,'actual_status':result['status'],
                     'checks':checks,'passed':all(checks.values()),'trace':name+'.json'})
        print(f"{name}: {result['status']} / {'PASS' if all(checks.values()) else 'FAIL'}",flush=True)
        # Authentication/format/connection failure: stop issuing further paid model calls.
        fatal = result['status'] == 'model_error'
    from scripts.audit import source_digest
    summary = {'source_digest':source_digest(), 'mode':args.mode,'model':factory().name,'generated_at_utc':datetime.now(timezone.utc).isoformat(),
               'python':platform.python_version(),'source_commit':current_commit(),
               'scope':'observable checks; human semantic review is still required',
               'distinct_observation_paths':summarize_paths(results),
               'human_semantic_review':'not_recorded','cases':rows,
               'passed':sum(r['passed'] for r in rows),'total':len(rows)}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_report(output,summary)
    if args.mode == 'live':
        index = ROOT/'examples/live/LATEST.md'
        index.parent.mkdir(parents=True,exist_ok=True)
        rel = Path(__import__('os').path.relpath(output,index.parent)).as_posix()
        index.write_text(f'# 最新真实模型运行\n\n[实际运行报告]({rel}/REPORT.md)\n\n自动检查 {summary["passed"]}/{summary["total"]}；仍须人工核验。\n',encoding='utf-8')
    print(f"Report: {output/'REPORT.md'}")
    return 0 if summary['passed']==summary['total'] and summary['distinct_observation_paths'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
