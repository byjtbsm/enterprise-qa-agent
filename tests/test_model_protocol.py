import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from enterprise_qa.models import LiveModel,ModelError,OfflineMock
from enterprise_qa.agent import run
from enterprise_qa.tools import Tools
from test_agent import SequenceModel,action


def envelope(content, **kw):
    value={'id':'stub-id','choices':[{'finish_reason':'stop','message':{'content':content}}],
           'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}}
    value.update(kw)
    return json.dumps(value).encode()


class ModelProtocolTests(unittest.TestCase):
    def model(self,base='https://api.deepseek.com'):
        with patch.dict(os.environ,{'MODEL_API_KEY':'fake-test-secret','MODEL_NAME':'deepseek-flash','MODEL_BASE_URL':base},clear=True):
            return LiveModel()

    def test_deepseek_profile_disables_thinking_and_sets_output_budget(self):
        body=self.model().request_body([])
        self.assertEqual(body['thinking'],{'type':'disabled'})
        self.assertEqual(body['max_tokens'],4096)

    def test_provider_specific_fields_are_not_sent_to_other_hosts(self):
        body=self.model('https://example.org/v1').request_body([])
        self.assertNotIn('thinking',body)
        self.assertNotIn('max_tokens',body)

    def test_valid_action_decodes_and_records_metadata(self):
        m=self.model();r=m.decode_response(envelope(json.dumps(action('search',{'query':'报销'}))),200)
        self.assertEqual(r['action'],'search')
        self.assertEqual(m.last_call['response_id'],'stub-id')
        self.assertEqual(m.last_call['usage']['total_tokens'],30)

    def test_one_fenced_json_object_is_accepted(self):
        r=self.model().decode_response(envelope('```json\n'+json.dumps(action('read',{'doc_id':'D01'}))+'\n```'),200)
        self.assertEqual(r['action'],'read')

    def test_empty_content_has_specific_diagnostics_without_reasoning_text(self):
        body={'id':'empty-id','choices':[{'finish_reason':'stop','message':{'content':'',
              'reasoning_content':'private-reasoning-do-not-log'}}]}
        m=self.model()
        with self.assertRaises(ModelError) as ctx:
            m.decode_response(json.dumps(body).encode(),200)
        self.assertEqual(ctx.exception.code,'model_empty_content')
        self.assertTrue(ctx.exception.retryable)
        self.assertTrue(ctx.exception.diagnostics['has_reasoning_content'])
        self.assertEqual(m.last_call['response_id'],'empty-id')
        self.assertNotIn('private-reasoning',json.dumps(ctx.exception.diagnostics))

    def test_malformed_json_reports_position_without_echoing_content(self):
        with self.assertRaises(ModelError) as ctx:
            self.model().decode_response(envelope('{private-secret'),200)
        self.assertEqual(ctx.exception.code,'model_action_invalid_json')
        self.assertIn('json_error_line',ctx.exception.diagnostics)
        self.assertNotIn('private-secret',json.dumps(ctx.exception.diagnostics))

    def test_response_failure_types_are_distinct(self):
        for raw,code in [(b'','model_empty_http_body'),(b'<html>private</html>','model_http_body_not_json'),
                         (b'[]','model_unexpected_response_shape'),(b'{}','model_missing_choices'),
                         (b'{"choices":[{}]}','model_missing_message'),
                         (b'{"choices":[{"message":{}}]}','model_missing_content'),
                         (envelope(None),'model_content_not_text'),(envelope('[]'),'model_action_not_object')]:
            with self.subTest(code=code):
                with self.assertRaises(ModelError) as ctx:self.model().decode_response(raw,200)
                self.assertEqual(ctx.exception.code,code)

    def test_malformed_envelope_usage_does_not_crash(self):
        r=self.model().decode_response(envelope(json.dumps(action('search',{'query':'报销'})),usage=['unexpected']),200)
        self.assertEqual(r['action'],'search')

    def test_truncation_and_filtering_have_separate_policy(self):
        for reason,code,retry in [('length','model_output_truncated',True),('content_filter','model_response_filtered',False)]:
            value={'choices':[{'finish_reason':reason,'message':{'content':'partial'}}]}
            with self.assertRaises(ModelError) as ctx:self.model().decode_response(json.dumps(value).encode(),200)
            self.assertEqual(ctx.exception.code,code);self.assertEqual(ctx.exception.retryable,retry)

    def test_prose_is_not_silently_substring_extracted(self):
        with self.assertRaises(ModelError):
            self.model().decode_response(envelope('Explanation '+json.dumps(action('search',{'query':'报销'}))),200)

    def test_protocol_repair_budget_stops_at_three_failed_calls(self):
        class Broken:
            mode,name='test_fixture','broken'
            def decide(self,messages):raise ModelError('model_empty_content',{'content_length':0},retryable=True)
        r=run(Broken(),Tools([]),'报销')
        self.assertEqual(r['status'],'model_error')
        self.assertEqual(r['steps'],3)
        self.assertEqual(r['trace'][-1]['recovery'],'protocol_repair_budget_exhausted')

    def test_protocol_failures_count_toward_step_limit(self):
        class Broken:
            mode,name='test_fixture','broken'
            def decide(self,messages):raise ModelError('model_empty_content',retryable=True)
        r=run(Broken(),Tools([]),'报销',max_steps=1)
        self.assertEqual(r['status'],'incomplete')
        self.assertEqual(r['steps'],1)

    def test_full_http_loop_recovers_at_second_response_without_repeating_tool(self):
        # Local HTTP stub, not an external model. No live acceptance files are saved.
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                if len(requests)==2:
                    payload=envelope('')
                else:
                    # Fixture policy receives the real observations. Remove the corrective
                    # message only for this deterministic stub, which is not a language model.
                    messages=[m for m in body['messages'] if not (m['role']=='user' and '上一轮未得到' in m['content'])]
                    decision=OfflineMock().decide(messages)
                    payload=envelope(json.dumps(decision,ensure_ascii=False))
                self.send_response(200);self.end_headers();self.wfile.write(payload)
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            r=run(self.model(f'http://127.0.0.1:{server.server_port}'),Tools.load(ROOT/'data/normal.json'),'报销期限是多少？')
            self.assertEqual(r['status'],'answered')
            self.assertEqual(r['tool_calls'],2)
            self.assertEqual(r['steps'],4)
            self.assertEqual(r['trace'][1]['error_code'],'model_empty_content')
            self.assertEqual(len(r['model_calls']),4)
            self.assertIn('上一轮未得到',requests[2]['messages'][-1]['content'])
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
