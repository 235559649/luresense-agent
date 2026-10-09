import json
import unittest
from context_guard import context_conflicts
from context_agent import ContextSession, respond, session_record
from retriever import KnowledgeBase

class ContextGuardTests(unittest.TestCase):
    def ctx(self, value='未观察到上述结构', status='user_reported'):
        return {'cover': {'value':value, 'status':status}}
    def conflicts(self,text,ctx=None,caveat=None):
        return context_conflicts({'claims':[{'text':text,'caveat':caveat}]},ctx or self.ctx())
    def test_saved_failure(self):
        self.assertTrue(self.conflicts('没有水草、倒木、岩石覆盖时，现场缺乏常见的鱼类藏匿结构，深水不一定更适宜。'))
    def test_absence_paraphrases(self):
        for t in ['现场没有水草。','这里缺少掩护结构。','倒木均不存在。','水域无任何植被。']:
            with self.subTest(t=t): self.assertTrue(self.conflicts(t))
    def test_unknown_and_unanswered(self):
        for status in ['unknown','unanswered']:
            self.assertTrue(self.conflicts('现场缺乏结构。',self.ctx(None,status)))
    def test_unobserved_wording_allowed(self):
        for t in ['未观察到水草，不能判断是否存在。','目前没有观察到倒木。','我不知道结构是否存在。']:
            self.assertFalse(self.conflicts(t))
    def test_disclaimer_allowed(self):
        for t in ['未观察到不代表没有水草。','无法断定现场缺乏结构。','不能说倒木不存在。']:
            self.assertFalse(self.conflicts(t))
    def test_hypothesis_allowed(self):
        self.assertFalse(self.conflicts('如果现场没有水草，则需要其他信息。'))
    def test_later_caveat_does_not_erase_premise(self):
        self.assertTrue(self.conflicts('现场没有水草。',caveat='不能确认现场是否没有水草。'))
    def test_caveat_checked_too(self):
        self.assertTrue(self.conflicts('资料不足。',caveat='现场没有掩护结构。'))
    def test_confirmed_structure_not_targeted(self):
        self.assertFalse(self.conflicts('如果没有倒木，可以再观察。',self.ctx('水草')))
    def test_actual_answer_retained_and_blocked(self):
        kb=KnowledgeBase()
        s=ContextSession('我在湖泊岸边，没有观察到水草、倒木或岩石，应该先看什么？')
        c=next(c for c in kb.cards if c['id']=='K019')
        answer={'status':'answered','followup_question':None,'claims':[{'kind':'project_inference',
            'text':'现场缺乏常见的鱼类藏匿结构，深水不一定更适宜。','evidence_ids':['K019'],
            'anchors':[{'card_id':'K019','field':'claim','quote':c['claim']}], 'caveat':'实际情况需核查。'}]}
        class Client:
            model='offline-test'
            def complete(self,messages): return json.dumps(answer,ensure_ascii=False),{'total_tokens':12}
        r=respond(s,kb,'rag',Client)
        self.assertEqual(r['status'],'insufficient_evidence')
        self.assertEqual(r['claims'],[])
        self.assertEqual(r['evidence'],[])
        self.assertEqual(r['answer_origin'],'context_guard_v1')
        self.assertEqual(r['model_answer_before_guard'],answer)
        self.assertTrue(r['context_guard_conflicts'])
        self.assertEqual(json.loads(r['raw_response']),answer)
        self.assertEqual(s.attempts,1)
        self.assertEqual(r['usage']['total_tokens'],12)
        self.assertIn('context_guard.py',session_record(s,kb)['code_sha256'])

if __name__=='__main__':unittest.main()
