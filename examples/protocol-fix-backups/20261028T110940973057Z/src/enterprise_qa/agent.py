import json
import time
from .models import SYSTEM, ModelError

STATUSES = {'answered', 'needs_clarification', 'insufficient_evidence', 'tool_error'}


def validate_finish(args, evidence):
    if not isinstance(args, dict) or set(args) != {'status', 'answer', 'citations', 'gaps'}:
        return 'invalid_finish_fields'
    if not isinstance(args['status'], str) or args['status'] not in STATUSES or not isinstance(args['answer'], str) or not args['answer'].strip():
        return 'invalid_finish_status_or_answer'
    if not isinstance(args['citations'], list) or not isinstance(args['gaps'], list):
        return 'invalid_finish_lists'
    if not all(isinstance(g, str) and g.strip() for g in args['gaps']):
        return 'invalid_gaps'
    if args['status'] == 'answered' and not args['citations']:
        return 'missing_citations'
    if args['status'] != 'answered' and not args['gaps']:
        return 'missing_gaps'
    for citation in args['citations']:
        if not isinstance(citation, dict) or set(citation) != {'doc_id', 'quote'}:
            return 'invalid_citation'
        doc_id, quote = citation['doc_id'], citation['quote']
        if not isinstance(doc_id, str) or not isinstance(quote, str):
            return 'invalid_citation_types'
        if doc_id not in evidence or not quote.strip() or quote not in evidence[doc_id]['text']:
            return 'unverified_citation'
    return None



def validate_finish_process(args, trace, evidence):
    """Evidence acquisition guardrails; never choose the model's next action or answer."""
    tool_steps = [e for e in trace if e.get('action') in ('search', 'read')]
    if not tool_steps:
        return {'ok': False, 'error': 'finish_requires_tool_observation',
                'hint': 'No tool result has been observed. Select search or read yourself before deciding whether to answer or clarify.'}
    searches = [e['observation'] for e in tool_steps
                if e.get('action') == 'search' and e.get('observation', {}).get('ok')
                and 'hits' in e['observation']]
    latest_hits = searches[-1]['hits'] if searches else []
    if args['status'] in ('answered', 'needs_clarification') and latest_hits and not evidence:
        return {'ok': False, 'error': 'read_search_candidates_before_finishing',
                'hint': 'Search returned candidate documents. Read original text before assuming missing conditions or giving an answer.'}
    if args['status'] == 'answered':
        unread = [hit['id'] for hit in latest_hits if hit['id'] not in evidence]
        if unread:
            return {'ok': False, 'error': 'unread_search_candidates', 'doc_ids': unread,
                    'hint': 'Inspect the remaining candidates before making a definitive answer; narrower search is also allowed.'}
    return None


def run(model, tools, question, history=None, max_steps=10):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('question must not be empty')
    if type(max_steps) is not int or not 1 <= max_steps <= 50:
        raise ValueError('max_steps must be between 1 and 50')
    tools.read_evidence.clear()  # Evidence must be obtained in this run.
    history = [] if history is None else history
    if not isinstance(history, list):
        raise ValueError('history must be a list')
    for item in history:
        if not isinstance(item, dict) or set(item) != {'role', 'content'} or item['role'] not in ('user', 'assistant') or not isinstance(item['content'], str):
            raise ValueError('history must contain user/assistant text messages')
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps({'question': question, 'history': history}, ensure_ascii=False)}]
    trace = []
    model_calls = []
    started = time.monotonic()
    def result(status, answer, gaps, citations=None):
        return {'mode': model.mode, 'model': model.name, 'question': question, 'history': history,
                'status': status, 'answer': answer, 'citations': citations or [], 'gaps': gaps,
                'steps': len(trace), 'max_steps': max_steps,
                'tool_calls': sum(e.get('action') in ('search', 'read') for e in trace),
                'model_calls': model_calls,
                'duration_ms': round((time.monotonic()-started)*1000, 2), 'trace': trace}
    for step in range(1, max_steps+1):
        try:
            decision = model.decide(messages)
            if getattr(model, 'last_call', None):
                model_calls.append({'step': step, **model.last_call})
        except Exception as exc:
            # Do not serialize provider response bodies, URLs, credentials or arbitrary exception strings.
            trace.append({'step': step, 'action': 'model_error', 'error_type': type(exc).__name__,
                          'error_code': exc.code if isinstance(exc, ModelError) else 'model_request_failed'})
            return result('model_error', '模型请求失败，任务未完成。', ['可用的模型响应'])
        if (not isinstance(decision, dict) or set(decision) != {'action', 'args', 'reason'}
                or not isinstance(decision.get('action'), str)
                or not isinstance(decision.get('args'), dict)
                or not isinstance(decision.get('reason'), str)):
            observation = {'ok': False, 'error': 'invalid_action_schema'}
            trace.append({'step': step, 'action': 'invalid_action', 'observation': observation})
            messages += [{'role': 'user', 'content': json.dumps(observation)}]
            continue
        name, args = decision['action'], decision['args']
        entry = {'step': step, 'action': name, 'args': args, 'reason': decision['reason']}
        if name == 'finish':
            error = validate_finish(args, tools.read_evidence)
            process_error = validate_finish_process(args, trace, tools.read_evidence) if not error else None
            if not error and not process_error:
                entry['observation'] = {'ok': True, 'accepted': True}
                trace.append(entry)
                return result(args['status'], args['answer'], args['gaps'], args['citations'])
            observation = process_error or {'ok': False, 'error': error}
        else:
            try:
                observation = tools.execute(name, args)
            except Exception:
                observation = {'ok': False, 'error': 'tool_execution_exception', 'retryable': False}
        entry['observation'] = observation
        trace.append(entry)
        messages.extend([{'role': 'assistant', 'content': json.dumps(decision, ensure_ascii=False)},
                         {'role': 'user', 'content': json.dumps(observation, ensure_ascii=False)}])
    return result('incomplete', '达到执行步数上限，任务未完成。', ['在步数限制内完成的核验结果'])
