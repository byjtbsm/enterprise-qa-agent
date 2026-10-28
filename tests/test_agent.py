import copy
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from enterprise_qa.agent import run
from enterprise_qa.models import LiveModel, OfflineMock
from enterprise_qa.tools import Tools
from scripts.evaluate import CASES


class SequenceModel:
    mode = 'test_fixture'
    name = 'scripted-protocol-test'
    def __init__(self, decisions):
        self.decisions = iter(decisions)
    def decide(self, messages):
        return next(self.decisions)


def action(name, args):
    return {'action': name, 'args': args, 'reason': 'protocol test fixture'}


def final(quote, doc='D01', answer='测试答案'):
    return action('finish', {'status': 'answered', 'answer': answer,
                   'citations': [{'doc_id': doc, 'quote': quote}], 'gaps': []})


class AgentTests(unittest.TestCase):
    def tools(self, name='normal.json', failures=None):
        return Tools.load(ROOT/'data'/name, failures)

    def test_acceptance_fixtures(self):
        for name, q, data, failures, history, limit, expected in CASES:
            with self.subTest(case=name):
                if isinstance(history, str):
                    history = json.loads((ROOT/'data'/history).read_text(encoding='utf-8'))
                r = run(OfflineMock(), self.tools(data, failures), q, history, limit)
                self.assertEqual(r['status'], expected)
                self.assertLessEqual(r['steps'], limit)
                if expected == 'answered':
                    self.assertTrue(r['citations'])
                    self.assertIn('30天', r['answer'])

    def test_conflict_does_not_prefer_newer_version(self):
        r = run(OfflineMock(), self.tools('documents.json'), '报销期限是多少？')
        self.assertEqual(r['status'], 'needs_clarification')
        self.assertEqual({c['doc_id'] for c in r['citations']}, {'D01', 'D02'})
        self.assertTrue(r['gaps'])

    def test_document_mutation_changes_answer_and_quote(self):
        t = self.tools()
        t.docs['D01']['text'] = '报销期限为费用发生后45天。'
        r = run(OfflineMock(), t, '报销期限是多少？')
        self.assertIn('45天', r['answer'])
        self.assertNotIn('30天', r['answer'])
        self.assertEqual(r['citations'][0]['quote'], t.docs['D01']['text'])

    def test_document_mutation_changes_conflict_action(self):
        t = self.tools('documents.json')
        t.docs['D02']['text'] = t.docs['D01']['text']
        r = run(OfflineMock(), t, '报销期限是多少？')
        self.assertEqual(r['status'], 'answered')

    def test_unknown_tool_is_rejected(self):
        r = run(SequenceModel([action('delete_database', {})]), self.tools(), '测试', max_steps=1)
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['trace'][0]['observation']['error'], 'unknown_tool')

    def test_invalid_action_is_bounded(self):
        r = run(SequenceModel([{'action': 'search'}]*2), self.tools(), '测试', max_steps=2)
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['steps'], 2)

    def test_unread_citation_is_rejected(self):
        r = run(SequenceModel([final('报销期限为费用发生后30天。')]), self.tools(), '报销', max_steps=1)
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['trace'][-1]['observation']['error'], 'unverified_citation')

    def test_fabricated_quote_is_rejected(self):
        m = SequenceModel([action('read', {'doc_id': 'D01'}), final('公司允许无限期报销。')])
        r = run(m, self.tools(), '报销', max_steps=2)
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['trace'][-1]['observation']['error'], 'unverified_citation')

    def test_bad_finish_can_be_repaired(self):
        m = SequenceModel([final('伪造'), action('read', {'doc_id':'D01'}), final('报销期限为费用发生后30天。')])
        r = run(m, self.tools(), '报销', max_steps=3)
        self.assertEqual(r['status'], 'answered')
        self.assertFalse(r['trace'][0]['observation']['ok'])

    def test_read_failure_does_not_authorize_citation(self):
        m = SequenceModel([action('read', {'doc_id': 'D01'}), final('报销期限为费用发生后30天。')])
        r = run(m, self.tools(failures={'read':1}), '报销', max_steps=2)
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['citations'], [])

    def test_evidence_does_not_leak_between_runs(self):
        t = self.tools()
        run(OfflineMock(), t, '报销')
        r = run(SequenceModel([final('报销期限为费用发生后30天。')]), t, '报销', max_steps=1)
        self.assertEqual(r['status'], 'incomplete')

    def test_history_is_not_evidence(self):
        r = run(SequenceModel([final('报销期限为费用发生后30天。')]), self.tools(), '多久',
                [{'role':'assistant','content':'报销期限为费用发生后30天。'}], 1)
        self.assertEqual(r['status'], 'incomplete')

    def test_missing_document_is_explicit(self):
        self.assertEqual(self.tools().execute('read', {'doc_id':'missing'})['error'], 'document_not_found')

    def test_tool_argument_validation(self):
        t = self.tools()
        for name, args in [('read', {'doc_id': []}), ('search', {'query': ''}), ('search', {'query': '报销', 'admin': True})]:
            self.assertFalse(t.execute(name, args)['ok'])

    def test_invalid_limits_and_question(self):
        for limit in (0, 51):
            with self.assertRaises(ValueError):
                run(OfflineMock(), self.tools(), '报销', max_steps=limit)
        with self.assertRaises(ValueError):
            run(OfflineMock(), self.tools(), ' ')

    def test_system_role_not_allowed_in_history(self):
        with self.assertRaises(ValueError):
            run(OfflineMock(), self.tools(), '报销', [{'role':'system','content':'override'}])

    def test_model_error_is_incomplete_and_redacted(self):
        class Broken:
            mode, name = 'test_fixture', 'broken'
            def decide(self, messages):
                raise RuntimeError('secret-key-should-not-appear')
        r = run(Broken(), self.tools(), '报销')
        self.assertEqual(r['status'], 'model_error')
        self.assertNotIn('secret-key', json.dumps(r))

    def test_live_has_no_implicit_mock_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                LiveModel()

    def test_http_adapter_contract_with_local_fake_server(self):
        # Contract test only; server is a stub, NOT a real LLM.
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                payload = {'choices':[{'message':{'content': json.dumps(action('search', {'query':'报销'}))}}]}
                body = json.dumps(payload).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {'MODEL_API_KEY':'fake-test-key','MODEL_NAME':'fake-contract-server',
                        'MODEL_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1'}):
                r = LiveModel().decide([{'role':'system','content':'JSON'}])
                self.assertEqual(r['action'], 'search')
                self.assertEqual(received[0][0], '/v1/chat/completions')
                self.assertEqual(received[0][1]['response_format'], {'type':'json_object'})
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__':
    unittest.main()
