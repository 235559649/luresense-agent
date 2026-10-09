import unittest
from context_agent import ContextSession
from context_guard import context_conflicts

class ContextVariantsTests(unittest.TestCase):
    def cover(self, text):
        return ContextSession('我在湖泊岸边，' + text + '，应该先观察哪里？').context()['cover']['value']

    def test_uncertain_cover(self):
        for text in ['水太浑，我看不清有没有水草', '不确定有没有倒木', '可能有水草', '如果有水草']:
            with self.subTest(text=text): self.assertIsNone(self.cover(text))

    def test_partial_confirmation(self):
        for text in ['我看到倒木，但不知道有没有水草', '我看到倒木但不知道有没有水草', '水草不确定，但是看到了倒木']:
            with self.subTest(text=text): self.assertEqual(self.cover(text), '倒木')

    def test_same_structure_contradiction(self):
        self.assertIsNone(self.cover('看到水草，但不确定是不是水草'))

    def test_negated_other_structure(self):
        self.assertEqual(self.cover('看到倒木，没看到水草'), '倒木')

    def test_retraction(self):
        s=ContextSession('我在湖泊岸边，看到水草，应该先观察哪里？')
        s.choose('cover','0')
        self.assertIsNone(s.context()['cover']['value'])
        self.assertNotIn('水草',s.retrieval_query())
        self.assertNotIn('水草',s.effective_question())

    def test_guard_disclaimer_and_failure(self):
        ctx={'cover':{'status':'unknown','value':None}}
        for text, blocked in [
            ('没看到水草，不代表这里没有水草。',False),
            ('这里缺少掩护，鱼不会停留。',True),
            ('无法观察水底所以这里没有水草。',True),
            ('不能确定这里有没有水草。',False),
            ('不能断定这里没有水草。',False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(bool(context_conflicts({'claims':[{'text':text}]},ctx)),blocked)
