import unittest
from context_agent import ContextSession, route, respond
from retriever import KnowledgeBase, has_out_of_scope, OUT_OF_SCOPE


class ScopeNegationTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_explicit_negative_clauses(self):
        for prefix in ('我不是在', '我不在', '我并不在', '这里并非', '我们并不是在'):
            with self.subTest(prefix=prefix):
                q = prefix + '海边，我在湖泊，看到水草，应该先看哪里？'
                self.assertFalse(has_out_of_scope(q))
                self.assertEqual(route(q), 'site')
                self.assertEqual(self.kb.search(q)['status'], 'ok')

    def test_all_positive_scope_terms_still_blocked(self):
        for term in OUT_OF_SCOPE:
            with self.subTest(term=term):
                q = term + '怎么钓？'
                self.assertTrue(has_out_of_scope(q))
                self.assertEqual(route(q), 'out_of_scope')
                self.assertEqual(self.kb.search(q)['status'], 'out_of_scope')

    def test_negated_species(self):
        q = '目标不是海鲈，大口黑鲈吃什么？'
        self.assertEqual(route(q), 'knowledge')
        self.assertEqual(self.kb.search(q)['status'], 'ok')

    def test_mixed_positive_mentions_not_hidden(self):
        for q in ('我不在海边，但是这里是海水，怎么钓？',
                  '我不是在海边，我后来去了海边，怎么钓？',
                  '目标不是海鲈，目标是孔雀鲈，怎么钓？'):
            with self.subTest(q=q):
                self.assertTrue(has_out_of_scope(q))
                self.assertEqual(self.kb.search(q)['status'], 'out_of_scope')

    def test_uncertain_and_complex_negatives_remain_conservative(self):
        for q in ('我不是不在海边', '我不是在海边吗？', '我不在海边？',
                  '我可能不在海边', '如果不是在海边，怎么钓？',
                  '海水和淡水有什么区别？', '我不是在海水湖，怎么钓？'):
            with self.subTest(q=q):
                self.assertTrue(has_out_of_scope(q))

    def test_s30_end_to_end_no_redundant_questions(self):
        s = ContextSession('我不是在海边，我在湖泊，看到水草，应该先看哪里？')
        self.assertEqual(s.task, 'site')
        self.assertEqual(s.context()['waterbody']['value'], '湖泊')
        self.assertEqual(s.context()['cover']['value'], '水草')
        self.assertIsNone(s.next_question())
        result = respond(s, self.kb, mode='mock')
        self.assertEqual(result['status'], 'evidence_only')
        self.assertTrue({'K003', 'K005'} <= set(result['retrieved_ids']))
        self.assertFalse(result['model_called'])

    def test_negative_alone_does_not_invent_freshwater(self):
        s = ContextSession('我不在海边，应该先看哪里？')
        self.assertEqual(s.context()['waterbody']['status'], 'unanswered')
        self.assertEqual(s.next_question(), 'waterbody')

    def test_whitespace_and_punctuation(self):
        self.assertFalse(has_out_of_scope('我 不在 海边；我在湖泊。'))
        self.assertFalse(has_out_of_scope('我不是在海边\n我在湖泊'))
