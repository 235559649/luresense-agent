import unittest
from context_agent import ContextSession, respond
from retriever import KnowledgeBase


class RetrievalExplanationTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_river_expressions_retrieve_documented_habitat(self):
        for term in ('河流', '河边', '河岸', '溪流', '大河', '回湾'):
            with self.subTest(term=term):
                self.assertIn('K005', [r['card']['id'] for r in self.kb.search(term)['results']])

    def test_river_does_not_expand_to_every_lake_card(self):
        self.assertEqual([r['card']['id'] for r in self.kb.search('河流')['results']], ['K005'])
        row = self.kb.search('河流')['results'][0]
        self.assertIn('静水回湾', row['card']['claim'])

    def test_rock_alone_does_not_invent_river_context(self):
        self.assertNotIn('K005', [r['card']['id'] for r in self.kb.search('岩石')['results']])
        self.assertEqual(self.kb.search('大口黑鲈')['status'], 'empty')

    def test_explicit_id_still_dominates(self):
        row = self.kb.search('K018 河流 岩石', limit=1)['results'][0]
        self.assertEqual(row['card']['id'], 'K018')
        self.assertIn('exact_id', [c['kind'] for c in row['score_components']])

    def test_scores_are_additive_and_traceable(self):
        for q in ('河流 岩石', '水草', 'K018 水温'):
            for row in self.kb.search(q)['results']:
                self.assertEqual(row['retrieval_score'], sum(c['points'] for c in row['score_components']))
                for component in row['score_components']:
                    self.assertTrue(component['query_terms'])
                    self.assertTrue(component['card_terms'])
        row = self.kb.search('河流')['results'][0]
        concept = next(c for c in row['score_components'] if c.get('concept') == 'river_habitat')
        self.assertEqual(concept['query_terms'], ['河流'])
        self.assertIn('溪流', concept['card_terms'])

    def test_repeat_words_do_not_inflate_scores(self):
        self.assertEqual(self.kb.search('河流 岩石')['results'],
                         self.kb.search('河流 河流 岩石 岩石')['results'])

    def test_corrected_session_uses_new_habitat_without_stale_terms(self):
        s = ContextSession('我在湖泊，看到水草，怎么选钓位？')
        s.choose('waterbody', '3')
        s.choose('cover', '3')
        result = respond(s, self.kb)
        self.assertTrue({'K003', 'K005'} <= set(result['retrieved_ids']))
        self.assertNotIn('湖泊', result['retrieval_query'])
        self.assertNotIn('水草', result['retrieval_query'])
        self.assertIn('score_components', result['retrieved_evidence'][0])
        self.assertFalse(result['model_called'])

    def test_scope_and_unknown_gates_preserved(self):
        self.assertEqual(self.kb.search('海水 河流 岩石')['status'], 'out_of_scope')
        s = ContextSession('我在淡水边，应该先看哪里？')
        s.choose('waterbody', '0')
        s.choose('cover', '0')
        result = respond(s, self.kb)
        self.assertEqual(result['retrieved_ids'], [])
        self.assertFalse(result['model_called'])
