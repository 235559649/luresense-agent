import json
import unittest
from context_agent import ContextSession, extract_initial, respond, route, session_record
from llm import ModelError
from retriever import KnowledgeBase


class FakeClient:
    model = 'fake-test-model'

    def __init__(self, error=None, bad_ref=False, extra_question=False):
        self.messages = None
        self.error, self.bad_ref, self.extra_question = error, bad_ref, extra_question

    def complete(self, messages):
        self.messages = messages
        if self.error:
            raise ModelError(self.error)
        card = json.loads(messages[1]['content'])['evidence'][0]
        return json.dumps({'status': 'answered', 'claims': [
            {'kind': 'source_fact', 'text': card['claim'], 'evidence_ids': ['FAKE' if self.bad_ref else card['id']],
             'anchors': [{'card_id': card['id'], 'field': 'claim', 'quote': card['claim'][:180]}], 'caveat': None}],
            'followup_question': '再问一个？' if self.extra_question else None}), {'total_tokens': 20}


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_knowledge_does_not_ask_site_questions(self):
        for q in ('大口黑鲈吃什么？', '气温能直接代替水温吗？'):
            s = ContextSession(q)
            self.assertEqual(s.task, 'knowledge')
            self.assertIsNone(s.next_question())

    def test_complete_site_skips_questions(self):
        s = ContextSession('我在湖泊，看到水草和倒木，应该优先观察哪里？')
        self.assertEqual(s.task, 'site')
        self.assertIsNone(s.next_question())
        self.assertEqual(s.context()['cover']['value'], '水草和倒木')

    def test_partial_site_only_asks_missing(self):
        s = ContextSession('我在湖泊，应该先看哪里？')
        self.assertEqual(s.next_question(), 'cover')
        self.assertEqual(s.next_question(), 'cover')
        self.assertEqual(s.questions_asked, 1)
        s.choose('cover', '0')
        self.assertIsNone(s.next_question())

    def test_unknown_no_model_or_key(self):
        s = ContextSession('我在淡水边，应该先看哪里？')
        for _ in range(2):
            s.choose(s.next_question(), '0')
        def forbidden():
            self.fail('No key/config read for empty retrieval')
        r = respond(s, self.kb, 'rag', forbidden)
        self.assertFalse(r['request_attempted'])
        self.assertEqual(r['status'], 'insufficient_evidence')
        self.assertEqual(s.questions_asked, 2)

    def test_ambiguous_or_negated_initial_not_positive(self):
        for q in ('我在湖泊或河流，没看到水草，怎么钓？', '如果在湖泊有水草，怎么钓？'):
            s = ContextSession(q)
            self.assertEqual(s.facts, {})

    def test_correction_removes_original_keywords_and_reaches_model(self):
        s = ContextSession('我在湖泊，看到水草和倒木，应该先看哪里？')
        s.choose('waterbody', '4')
        s.choose('cover', '5')
        q = s.retrieval_query()
        self.assertNotIn('湖泊', q)
        self.assertNotIn('水草', q)
        self.assertIn('池塘', q)
        client = FakeClient()
        r = respond(s, self.kb, 'rag', lambda: client)
        payload = json.loads(client.messages[1]['content'])
        self.assertEqual(payload['current_context']['cover']['value'], '未观察到上述结构')
        self.assertTrue(payload['current_context']['cover']['corrected'])
        self.assertTrue(r['model_response_received'])

    def test_correct_to_unknown_does_not_restore_initial(self):
        s = ContextSession('我在湖泊，看到水草，应该先看哪里？')
        s.choose('cover', '0')
        self.assertNotIn('水草', s.retrieval_query())
        self.assertEqual(s.context()['cover']['status'], 'unknown')
        self.assertIsNone(s.next_question())

    def test_temperature_source_not_inferred_from_unlabelled_number(self):
        s = ContextSession('今天温度28度，怎么钓？')
        self.assertEqual(s.next_question(), 'temperature_source')
        s.choose('temperature_source', '1')
        s.choose(s.next_question(), '1')
        self.assertEqual(s.context()['temperature_source']['value'], '气温')
        self.assertFalse(s.context()['temperature_source']['verified'])

    def test_labelled_temperature_is_retained(self):
        self.assertEqual(extract_initial('今天气温28度，怎么钓？')['temperature_source'], '气温')

    def test_out_of_scope_never_calls(self):
        s = ContextSession('海边花鲈怎么钓？')
        self.assertEqual(s.task, 'out_of_scope')
        self.assertIsNone(s.next_question())
        r = respond(s, self.kb, 'rag', lambda: self.fail('Must not call'))
        self.assertFalse(r['model_called'])

    def test_failure_counts_toward_three_attempt_budget(self):
        s = ContextSession('大口黑鲈吃什么？')
        client = FakeClient(error='接口失败（模拟）')
        for _ in range(3):
            r = respond(s, self.kb, 'rag', lambda: client)
            self.assertEqual(r['status'], 'error')
            self.assertTrue(r['request_attempted'])
        r = respond(s, self.kb, 'rag', lambda: self.fail('Budget must prevent even client creation'))
        self.assertEqual(r['status'], 'budget_exhausted')
        self.assertEqual(s.attempts, 3)

    def test_invalid_citation_keeps_usage_but_no_claim(self):
        s = ContextSession('大口黑鲈吃什么？')
        r = respond(s, self.kb, 'rag', lambda: FakeClient(bad_ref=True))
        self.assertEqual(r['status'], 'error')
        self.assertEqual(r['claims'], [])
        self.assertEqual(r['usage']['total_tokens'], 20)
        self.assertTrue(r['model_response_received'])

    def test_model_followup_cannot_bypass_controller(self):
        s = ContextSession('大口黑鲈吃什么？')
        r = respond(s, self.kb, 'rag', lambda: FakeClient(extra_question=True))
        self.assertEqual(r['status'], 'error')

    def test_mock_does_not_masquerade_as_answer(self):
        s = ContextSession('大口黑鲈吃什么？')
        r = respond(s, self.kb)
        self.assertTrue(r['synthetic'])
        self.assertEqual(r['status'], 'evidence_only')
        self.assertEqual(r['claims'], [])

    def test_new_session_resets_budget_and_facts(self):
        old = ContextSession('我在湖泊，看到水草，怎么钓？')
        respond(old, self.kb, 'rag', lambda: FakeClient())
        new = ContextSession('我在淡水边，应该先看哪里？')
        self.assertEqual(new.attempts, 0)
        self.assertEqual(new.facts, {})

    def test_log_snapshots_survive_later_mutation(self):
        s = ContextSession('我在湖泊，看到水草，怎么钓？')
        respond(s, self.kb)
        s.choose('cover', '5')
        old_response = [e for e in s.events if e['event'] == 'response'][0]
        self.assertEqual(old_response['result']['current_context']['cover']['value'], '水草')
        record = session_record(s, self.kb)
        self.assertEqual(record['context']['cover']['value'], '未观察到上述结构')
        self.assertIn('context_agent.py', record['code_sha256'])

    def test_invalid_choice_leaves_state_untouched(self):
        s = ContextSession('我在淡水边，先看哪里？')
        slot = s.next_question()
        with self.assertRaises(ValueError):
            s.choose(slot, '9')
        self.assertEqual(s.facts, {})
        self.assertEqual(s.next_question(), slot)


if __name__ == '__main__':
    unittest.main()
