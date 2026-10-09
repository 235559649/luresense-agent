import json
import unittest
from pathlib import Path
from context_guard import context_conflicts
from context_agent import ContextSession, respond
from retriever import KnowledgeBase

FIXTURE = Path(__file__).parent / 'fixtures/unknown_cover_presence.json'

class PresenceGuardTests(unittest.TestCase):
    def check(self, text, caveat=None):
        return context_conflicts({'claims':[{'text':text,'caveat':caveat}]},
                                 {'cover':{'value':None,'status':'unknown'}})

    def test_recorded_failure(self):
        f=json.loads(FIXTURE.read_text())
        hits=context_conflicts(f['answer'],f['context'])
        self.assertTrue(any(h['claim_index']==1 and h['rule']=='unobserved_to_present' for h in hits))

    def test_explicit_presence(self):
        for t in ['附近已知的植被可作为重点。','现场有水草。','这里存在倒木。','岸边已经确认有岩石。','已确认的水草可供观察。']:
            with self.subTest(t=t): self.assertTrue(self.check(t))

    def test_conditional_allowed(self):
        for t in ['如果现场有水草，可以再观察。','若这里存在倒木，可作为候选。','假如发现水草，请补充信息。']:
            with self.subTest(t=t): self.assertFalse(self.check(t))

    def test_uncertain_allowed(self):
        for t in ['无法确认现场有水草。','不能断定附近存在倒木。','请先确认现场是否有水草。','现场可能有水草。','尚未确认的水草不能当作现场事实。']:
            with self.subTest(t=t): self.assertFalse(self.check(t))

    def test_general_fact_allowed(self):
        self.assertFalse(self.check('大口黑鲈会利用倒木、岩石台阶、植被及人工结构等掩护。'))

    def test_later_caveat_does_not_erase(self):
        self.assertTrue(self.check('现场有水草。','现场实际存在尚需用户确认。'))

    def test_caveat_checked(self):
        self.assertTrue(self.check('资料不足。','附近已知的植被可供观察。'))

    def test_replay_preserves_original(self):
        f=json.loads(FIXTURE.read_text())
        class Client:
            model='offline-replay'
            def complete(self,messages):
                return json.dumps(f['answer'],ensure_ascii=False),{'total_tokens':1}
        s=ContextSession('我在湖泊岸边，水太浑，我看不清有没有水草，应该先观察哪里？')
        s.choose('cover','0')
        r=respond(s,KnowledgeBase(),'rag',Client)
        self.assertEqual(r['status'],'insufficient_evidence')
        self.assertEqual(r['claims'],[])
        self.assertEqual(r['model_answer_before_guard'],f['answer'])
        self.assertEqual(json.loads(r['raw_response']),f['answer'])
        self.assertEqual(s.attempts,1)
        self.assertNotIn('现有证据与已知条件不足以支持具体现场建议',r['message'])
        self.assertIn('条件已更新',r['message'])
