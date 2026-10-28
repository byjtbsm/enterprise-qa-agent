import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from enterprise_qa.agent import run
from enterprise_qa.config import load_env
from enterprise_qa.models import LiveModel, ModelError, OfflineMock
from enterprise_qa.tools import Tools
from scripts.evaluate import ALL_CASES, check_result, summarize_paths
from scripts.audit import audit_live
from test_agent import SequenceModel, action


class DeliveryTests(unittest.TestCase):
    def tools(self):
        return Tools.load(ROOT/'data/normal.json')

    def test_all_eleven_cases_pass_behavior_checks(self):
        results = {}
        for name,q,data,failures,history,limit,expected in ALL_CASES:
            with self.subTest(case=name):
                docs = json.loads((ROOT/'data'/data).read_text(encoding='utf-8'))
                if isinstance(history,str):
                    history = json.loads((ROOT/'data'/history).read_text(encoding='utf-8'))
                result = run(OfflineMock(),Tools(docs,failures),q,history,limit)
                self.assertTrue(all(check_result(name,result,docs,expected).values()))
                results[name] = result
        self.assertTrue(summarize_paths(results))

    def test_env_loader_does_not_execute_or_expand_values(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{},clear=True):
            path = Path(tmp)/'.env'
            path.write_text('MODEL_NAME="$(echo must-not-execute)"\nMODEL_API_KEY="local-secret"\n')
            load_env(path)
            self.assertEqual(os.environ['MODEL_NAME'],'$(echo must-not-execute)')
            self.assertEqual(os.environ['MODEL_API_KEY'],'local-secret')

    def test_environment_overrides_local_env(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'MODEL_NAME':'shell-model'},clear=True):
            path=Path(tmp)/'.env'; path.write_text('MODEL_NAME=file-model\n')
            load_env(path)
            self.assertEqual(os.environ['MODEL_NAME'],'shell-model')

    def test_bad_env_does_not_expose_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.env'; path.write_text('MODEL_API_KEY="unclosed-super-secret\n')
            with self.assertRaises(ValueError) as error:
                load_env(path)
            self.assertNotIn('super-secret',str(error.exception))

    def test_document_schema_is_validated(self):
        for docs in ({},[{}],[{'id': []}]):
            with self.assertRaises(ValueError):
                Tools(docs)

    def test_bad_history_shapes_are_configuration_errors(self):
        for history in ('bad',[None],[{'role':'user','content':3}]):
            with self.assertRaises(ValueError):
                run(OfflineMock(),self.tools(),'报销',history)

    def test_tool_exception_is_an_observation_and_model_can_stop(self):
        class BrokenTools(Tools):
            def execute(self,*args):
                raise RuntimeError('private-database-error')
        model=SequenceModel([action('search',{'query':'报销'}),action('finish',{
            'status':'tool_error','answer':'工具不可用，未完成。','citations':[],'gaps':['可用的检索工具']})])
        r=run(model,BrokenTools([]),'报销')
        self.assertEqual(r['status'],'tool_error')
        self.assertEqual(r['trace'][0]['observation']['error'],'tool_execution_exception')
        self.assertNotIn('private-database-error',json.dumps(r))

    def test_malformed_status_is_rejected_without_crash(self):
        r=run(SequenceModel([action('finish',{'status':[],'answer':'bad','citations':[],'gaps':[]})]),
              self.tools(),'报销',max_steps=1)
        self.assertEqual(r['status'],'incomplete')

    def test_model_configuration_rejects_unsafe_or_invalid_fields(self):
        base={'MODEL_API_KEY':'fake-test-key','MODEL_NAME':'fake-model'}
        for addition in ({'MODEL_TIMEOUT':'nan'},{'MODEL_TIMEOUT':'0'},
                         {'MODEL_BASE_URL':'https://user:password@example.org/v1'},
                         {'MODEL_BASE_URL':'file:///etc/passwd'}):
            with patch.dict(os.environ,{**base,**addition},clear=True):
                with self.assertRaises(ValueError):
                    LiveModel()

    def test_http_401_is_classified_without_echoing_body(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(401);self.end_headers();self.wfile.write(b'private-provider-message')
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with patch.dict(os.environ,{'MODEL_API_KEY':'fake-test-key','MODEL_NAME':'fake-model',
                     'MODEL_BASE_URL':f'http://127.0.0.1:{server.server_port}'},clear=True):
                result=run(LiveModel(),self.tools(),'报销')
                self.assertEqual(result['status'],'model_error')
                self.assertEqual(result['trace'][0]['error_code'],'model_http_error_401')
                self.assertNotIn('private-provider-message',json.dumps(result))
        finally:
            server.shutdown();server.server_close();worker.join()

    def test_full_http_stub_loop_receives_actual_observations(self):
        # Local deterministic HTTP stub. No live acceptance files are written.
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                decision=OfflineMock().decide(body['messages'])
                payload={'id':'local-http-stub','choices':[{'finish_reason':'stop',
                          'message':{'content':json.dumps(decision,ensure_ascii=False)}}],
                         'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}}
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps(payload,ensure_ascii=False).encode())
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with patch.dict(os.environ,{'MODEL_API_KEY':'fake-test-key','MODEL_NAME':'local-http-stub',
                    'MODEL_BASE_URL':f'http://127.0.0.1:{server.server_port}'},clear=True):
                r=run(LiveModel(),self.tools(),'报销期限是多少？')
            self.assertEqual(r['status'],'answered')
            self.assertEqual(len(requests),3)
            observations=[json.loads(m['content']) for m in requests[-1]['messages'][2:] if m['role']=='user']
            self.assertTrue(any('document' in o for o in observations))
            self.assertEqual(len(r['model_calls']),3)
            self.assertEqual(r['model_calls'][-1]['usage']['total_tokens'],30)
        finally:
            server.shutdown();server.server_close();worker.join()

    def test_submission_refuses_uncommitted_files(self):
        from scripts import submission
        with patch.object(submission,'audit_main',return_value=0), \
             patch.object(submission,'git',return_value=' M README.md'), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(submission.main(),1)

    def test_submission_refuses_mismatched_remote_commit(self):
        from scripts import submission
        with patch.object(submission,'audit_main',return_value=0), \
             patch.object(submission,'git',side_effect=['','local-sha','https://github.com/test/qa.git','other-sha\trefs/heads/main']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(submission.main(),1)

    def test_submission_formats_verified_repository_metadata(self):
        from scripts import submission
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(submission,'ROOT',Path(tmp)), \
             patch.object(submission,'audit_main',return_value=0), \
             patch.object(submission,'git',side_effect=['','verified-sha','https://github.com/test/qa.git','verified-sha\trefs/heads/main']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(submission.main(),0)
            record=json.loads((Path(tmp)/'submission.txt').read_text(encoding='utf-8'))
            self.assertEqual(record['GitHub URL'],'https://github.com/test/qa')
            self.assertEqual(record['最终 commit SHA'],'verified-sha')

    def test_live_audit_rejects_mock_evidence(self):
        errors=audit_live(ROOT/'examples/mock')
        self.assertTrue(any('not live' in e for e in errors))
        self.assertTrue(any('no live API call metadata' in e for e in errors))

if __name__=='__main__':
    unittest.main()
