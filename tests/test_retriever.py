import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from retriever import DATA_DIR, KnowledgeBase, format_result


class RetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def ids(self, q):
        return {r['card']['id'] for r in self.kb.search(q)['results']}

    def test_vegetation_returns_cover_and_rig(self):
        self.assertTrue({'K003', 'K010'} <= self.ids('水草附近可以先了解什么'))

    def test_synonym(self):
        self.assertIn('K010', self.ids('草丛边有软饵可以试吗'))

    def test_diet_intent_without_literal_tag(self):
        self.assertIn('K004', self.ids('大口黑鲈吃啥'))

    def test_no_match_and_generic_species_do_not_hallucinate(self):
        for q in ('火星钓鱼', '大口黑鲈股价预测'):
            self.assertEqual(self.kb.search(q)['status'], 'empty')

    def test_species_boundary(self):
        self.assertEqual(self.kb.search('海鲈水草策略')['status'], 'out_of_scope')

    def test_input_validation(self):
        for q in ('', '   ', 'a'*2001):
            with self.assertRaises(ValueError): self.kb.search(q)
        for limit in (0, 5, True):
            with self.assertRaises(ValueError): self.kb.search('水草', limit)

    def test_provenance_and_limit_survive_rendering(self):
        result = self.kb.search('K010', limit=1)
        text = format_result(result)
        self.assertIn('佛州', text)
        self.assertIn('https://myfwc.com/', text)
        self.assertIn('项目推断', text)
        self.assertEqual(len(result['results']), 1)

    def test_missing_source_fails_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'knowledge_cards.json').write_text((DATA_DIR/'knowledge_cards.json').read_text(), encoding='utf-8')
            (p/'sources.json').write_text('[]', encoding='utf-8')
            with self.assertRaises(ValueError): KnowledgeBase(p)

    def test_duplicate_query_terms_do_not_change_ranking(self):
        a = self.kb.search('水草')
        b = self.kb.search('水草水草水草')
        self.assertEqual(a['results'], b['results'])

    def test_cli_works_from_other_directory(self):
        script = Path(__file__).resolve().parents[1]/'app.py'
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, str(script), '--query', '水草', '--json'],
                               cwd=tmp, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(p.stdout)['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
