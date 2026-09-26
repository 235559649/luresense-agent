import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from llm import ChatClient, ModelError
from rag import generate, validate_answer, save_run, format_answer
from retriever import KnowledgeBase


def response(ref='K004', text='有依据的说明'):
    return json.dumps({'status':'answered', 'claims':[{'text':text, 'evidence_ids':[ref]}], 'followup_question':None})


class RagTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_mock_is_explicit_and_offline(self):
        with patch('llm.build_opener', side_effect=AssertionError('network')):
            result = generate(self.kb, '吃什么', 'mock')
        self.assertTrue(result['synthetic'])
        self.assertFalse(result['model_called'])
        self.assertIn('模拟', format_answer(result))

    def test_unknown_reference_rejected(self):
        with self.assertRaises(ModelError): validate_answer(response('K999'), ['K004'])

    def test_known_but_unretrieved_reference_rejected(self):
        with self.assertRaises(ModelError): validate_answer(response('K003'), ['K004'])

    def test_empty_retrieval_does_not_call_model(self):
        client = MagicMock()
        result = generate(self.kb, '火星钓鱼', 'rag', client)
        self.assertEqual(result['status'], 'empty')
        client.complete.assert_not_called()

    def test_bad_json_and_schema(self):
        for raw in ('not json', '[]', '{}', '{"status":"answered","claims":[],"followup_question":null}'):
            with self.subTest(raw=raw), self.assertRaises(ModelError): validate_answer(raw, ['K004'])

    def test_uncited_claim_rejected(self):
        raw = json.dumps({'status':'answered','claims':[{'text':'一条断言','evidence_ids':[]}],'followup_question':None})
        with self.assertRaises(ModelError): validate_answer(raw, ['K004'])

    def test_honest_abstention(self):
        raw = json.dumps({'status':'insufficient_evidence','claims':[],'followup_question':'你知道水温吗？'})
        self.assertEqual(validate_answer(raw, [])['status'], 'insufficient_evidence')

    def test_mock_model_integration_uses_retrieved_cards(self):
        client = MagicMock(model='test-only')
        client.complete.return_value = (response(), {'total_tokens':10})
        result = generate(self.kb, '成年大口黑鲈吃什么', 'rag', client)
        self.assertTrue(result['model_called'])
        self.assertFalse(result['synthetic'])
        self.assertEqual(result['evidence'][0]['card']['id'], 'K004')
        self.assertIn('K004', client.complete.call_args.args[0][1]['content'])

    def test_transport_with_fake_response(self):
        envelope = {'choices':[{'finish_reason':'stop','message':{'content':response()}}], 'usage':{'total_tokens':10}}
        context = MagicMock()
        context.__enter__.return_value.read.return_value = json.dumps(envelope).encode()
        with patch('llm.build_opener') as op:
            op.return_value.open.return_value = context
            raw, usage = ChatClient('fake-model','test-key').complete([])
        self.assertEqual(usage['total_tokens'],10)
        self.assertEqual(json.loads(raw)['status'],'answered')

    def test_http_error_does_not_echo_credentials(self):
        with patch('llm.build_opener') as op:
            op.return_value.open.side_effect = HTTPError('https://example.com',401,'test-key',{},None)
            with self.assertRaises(ModelError) as exc:
                ChatClient('fake','test-key').complete([])
        self.assertNotIn('test-key',str(exc.exception))

    def test_truncated_model_response_rejected(self):
        context = MagicMock()
        context.__enter__.return_value.read.return_value = json.dumps({'choices':[{'finish_reason':'length'}]}).encode()
        with patch('llm.build_opener') as op:
            op.return_value.open.return_value = context
            with self.assertRaises(ModelError): ChatClient('fake','test-key').complete([])

    def test_unsafe_endpoint_and_missing_config(self):
        for url in ('http://example.com/v1','https://user:secret@example.com','https://example.com/?key=secret'):
            with self.assertRaises(ValueError): ChatClient('fake','test-key',url)
        with self.assertRaises(ValueError): ChatClient('', '')

    def test_experiment_record_does_not_overwrite(self):
        result = generate(self.kb,'吃什么')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run.json'
            save_run(result,p,self.kb)
            record=json.loads(p.read_text())
            self.assertTrue(record['synthetic'])
            self.assertEqual(len(record['knowledge_sha256']),64)
            with self.assertRaises(FileExistsError): save_run(result,p,self.kb)

    def test_id_validation_is_not_entailment(self):
        # 明确记录语义盲区，不能把这个检查声称为事实核验。
        bad_semantics=response('K004','这片水域百分之百有鱼。')
        self.assertEqual(validate_answer(bad_semantics,['K004'])['status'],'answered')


if __name__ == '__main__':
    unittest.main()
