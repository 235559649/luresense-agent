import http.client
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from web_app import DemoService, make_handler
from review_runs import prepare


class WebServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = DemoService()

    def test_knowledge_offline(self):
        view = self.service.start('大口黑鲈吃什么？')
        self.assertIsNone(view['followup'])
        self.assertEqual(view['result']['status'], 'evidence_only')
        self.assertFalse(view['result']['model_called'])
        self.assertTrue(view['result']['evidence'])

    def test_clarify_then_correct(self):
        first = self.service.start('我在淡水边，应该先看哪里？')
        sid = first['session_id']
        self.assertEqual(first['followup']['slot'], 'waterbody')
        second = self.service.choose(sid, 'waterbody', '1')
        self.assertIsNone(second['result'])
        third = self.service.choose(sid, 'cover', '4')
        self.assertIsNone(third['followup'])
        self.assertIn('水草', third['result']['retrieval_query'])
        corrected = self.service.choose(sid, 'cover', '5')
        self.assertNotIn('水草', corrected['result']['retrieval_query'])
        self.assertTrue(corrected['context']['cover']['corrected'])
        self.assertEqual(len(first['events']), 2)  # immutable response snapshot

    def test_unknown_does_not_call_factory(self):
        def forbidden():
            self.fail('unknown context must not call model')
        service = DemoService('rag', forbidden)
        v = service.start('我在淡水边，应该先看哪里？')
        for _ in range(2):
            v = service.choose(v['session_id'], v['followup']['slot'], '0')
        self.assertEqual(v['result']['status'], 'insufficient_evidence')
        self.assertEqual(v['model_requests'], 0)

    def test_invalid_choice_preserves_state(self):
        v = self.service.start('我在淡水边，应该先看哪里？')
        before = self.service.export(v['session_id'])
        with self.assertRaises(ValueError):
            self.service.choose(v['session_id'], 'cover', '100')
        after = self.service.export(v['session_id'])
        for key in ('events', 'context'):
            self.assertEqual(before['sessions'][0][key], after['sessions'][0][key])

    def test_invalid_start_and_missing_session(self):
        for question in (None, '', 'a' * 1001):
            with self.assertRaises(ValueError):
                self.service.start(question)
        with self.assertRaises(ValueError):
            self.service.export('missing')

    def test_export_can_prepare_review(self):
        v = self.service.start('大口黑鲈吃什么？')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'run.json'
            path.write_text(json.dumps(self.service.export(v['session_id'])), encoding='utf-8')
            review = prepare([path])
            self.assertTrue(review['items'])

    def test_capacity(self):
        for _ in range(20):
            self.service.start('我在淡水边，应该先看哪里？')
        with self.assertRaises(ValueError):
            self.service.start('大口黑鲈吃什么？')


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        cls.server.RequestHandlerClass = make_handler(DemoService(), 'test-token', cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def call(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, json.dumps(data) if data is not None else None, headers or {})
        response = conn.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        conn.close()
        return result

    def test_static_and_config(self):
        self.assertEqual(self.call('GET', '/')[0], 200)
        status, body, headers = self.call('GET', '/api/config')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'mode': 'mock', 'csrf_token': 'test-token'})
        self.assertIn('Content-Security-Policy', headers)
        self.assertEqual(self.call('GET', '/../llm.py')[0], 404)

    def test_host_token_origin_guards(self):
        self.assertEqual(self.call('GET', '/', headers={'Host': 'attacker.example'})[0], 403)
        self.assertEqual(self.call('POST', '/api/start', {'question': 'hi'})[0], 403)
        headers = {'Content-Type': 'application/json', 'X-LureSense-Token': 'test-token', 'Origin': 'https://attacker.example'}
        self.assertEqual(self.call('POST', '/api/start', {'question': 'hi'}, headers)[0], 403)

    def test_start_and_export(self):
        headers = {'Content-Type': 'application/json', 'X-LureSense-Token': 'test-token'}
        status, body, _ = self.call('POST', '/api/start', {'question': '大口黑鲈吃什么？'}, headers)
        self.assertEqual(status, 200)
        sid = json.loads(body)['session_id']
        status, body, _ = self.call('POST', '/api/export', {'session_id': sid}, headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['app_version'], 'web-0.4')
        self.assertEqual(self.call('POST', '/api/start', [], headers)[0], 400)


if __name__ == '__main__':
    unittest.main()
