"""Regression cases from manual review, plus alternative and negative controls.
Fake clients exercise payload plumbing, never count as real model validation.
"""
import json
import unittest

from context_agent import ContextSession, extract_initial, respond, route
from retriever import KnowledgeBase


class CaptureClient:
    model = 'offline-test-double'

    def complete(self, messages):
        self.payload = json.loads(messages[1]['content'])
        return json.dumps({'status': 'insufficient_evidence', 'claims': [],
                           'followup_question': None}), {'total_tokens': 1}


class Phase1Repairs(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_observation_paraphrases_route_and_retain_conditions(self):
        for ending in ('应该先观察什么？', '应该先观察哪里？', '先留意什么？'):
            with self.subTest(ending=ending):
                s = ContextSession('我在水库岸边，看到一片倒木，' + ending)
                self.assertEqual(s.task, 'site')
                self.assertEqual(s.context()['waterbody']['value'], '水库')
                self.assertEqual(s.context()['cover']['value'], '倒木')
                self.assertIsNone(s.next_question())

    def test_cover_retraction_changes_retrieval_and_payload(self):
        s = ContextSession('我在湖泊岸边，看到水草，应该先观察哪里？')
        before = respond(s, self.kb)
        s.choose('cover', '0')
        client = CaptureClient()
        after = respond(s, self.kb, 'rag', lambda: client)
        self.assertNotIn('水草', after['retrieval_query'])
        self.assertNotIn('水草', client.payload['effective_question'])
        self.assertNotIn('original_question', client.payload)
        self.assertEqual(client.payload['current_context']['cover']['status'], 'unknown')
        self.assertEqual(before['current_context']['cover']['value'], '水草')
        self.assertIn('条件已更新', after['message'])

    def test_knowledge_corrections_also_remove_old_conditions(self):
        s = ContextSession('我在湖泊，看到水草，大口黑鲈吃什么？')
        self.assertEqual(s.task, 'knowledge')
        s.choose('waterbody', '3')
        s.choose('cover', '0')
        query = s.retrieval_query()
        self.assertNotIn('湖泊', query)
        self.assertNotIn('水草', query)
        self.assertIn('河流', query)
        self.assertIn('吃什么', query)
        client = CaptureClient()
        respond(s, self.kb, 'rag', lambda: client)
        self.assertNotIn('水草', client.payload['effective_question'])

    def test_temperature_correction_removes_old_measurement_from_payload(self):
        s = ContextSession('今天气温28度，应该先观察哪里？')
        s.choose('temperature_source', '0')
        s.choose('waterbody', '1')
        self.assertNotIn('28', s.effective_question())
        self.assertEqual(s.context()['temperature_source']['status'], 'unknown')

    def test_explicit_all_structure_negation(self):
        s = ContextSession('我在湖泊岸边，没有观察到水草、倒木或岩石，应该先看什么？')
        self.assertEqual(s.context()['cover']['value'], '未观察到上述结构')
        self.assertEqual(s.context()['cover']['source'], 'rule_extraction')
        self.assertIsNone(s.next_question())
        self.assertNotIn('水草', s.retrieval_query())

    def test_uncertain_and_mixed_negation_not_promoted(self):
        for q in ('可能没有观察到水草、倒木或岩石',
                  '不是没有观察到水草、倒木或岩石',
                  '没有观察到水草、倒木或岩石，但看到水草',
                  '如果看到水草，应该先观察哪里？'):
            with self.subTest(q=q):
                self.assertNotIn('cover', extract_initial(q))

    def test_diet_paraphrases_retrieve_adult_card(self):
        for q in ('大口黑鲈幼鱼和成鱼吃的东西一样吗？',
                  '成鱼一般吃些什么？', '大口黑鲈以什么为食？'):
            self.assertIn('K004', [r['card']['id'] for r in self.kb.search(q)['results']])

    def test_depth_paraphrase_retrieves_conditional_card(self):
        rows = self.kb.search('大口黑鲈是不是待在越深的水里越好？')['results']
        self.assertIn('K016', [r['card']['id'] for r in rows])

    def test_concept_questions_do_not_create_site_observations(self):
        for q in ('水草是什么？', '湖泊与水库有什么区别？', '气温能直接代替水温吗？'):
            s = ContextSession(q)
            self.assertEqual(s.facts, {})
            self.assertIsNone(s.next_question())

    def test_live_temperature_abstention_has_reason_and_retains_pond(self):
        s = ContextSession('我在一个没有名字的池塘边，你能告诉我此刻水下两米处的准确水温吗？')
        self.assertEqual(s.context()['waterbody']['value'], '池塘')
        r = respond(s, self.kb, 'rag', CaptureClient)
        self.assertEqual(r['status'], 'insufficient_evidence')
        self.assertEqual(r['claims'], [])
        self.assertIn('测量数据', r['message'])
        self.assertIn('单位', r['message'])

    def test_diet_positive_retrieval_reaches_client(self):
        s = ContextSession('大口黑鲈幼鱼和成鱼吃的东西一样吗？')
        r = respond(s, self.kb, 'rag', CaptureClient)
        self.assertTrue(r['request_attempted'])
        self.assertIn('K004', r['retrieved_ids'])

    def test_scope_gate_still_blocks_before_client(self):
        s = ContextSession('海边花鲈吃的东西是什么？')
        r = respond(s, self.kb, 'rag', lambda: self.fail('scope gate bypassed'))
        self.assertFalse(r['request_attempted'])


if __name__ == '__main__':
    unittest.main()
