import json
import unittest
from copy import deepcopy
from context_agent import ContextSession, respond, session_record
from observation_policy import observation_answer
from retriever import KnowledgeBase
from llm import ModelError

class Client:
    model = 'offline-policy-test'
    def __init__(self, answer=None, error=False):
        self.answer,self.error=answer,error
    def complete(self,messages):
        if self.error: raise ModelError('test transport failure')
        if self.answer is not None: return json.dumps(self.answer,ensure_ascii=False),{'total_tokens':10}
        c=next(c for c in json.loads(messages[1]['content'])['evidence'] if c['id']=='K003')
        return json.dumps({'status':'answered','followup_question':None,'claims':[{'kind':'source_fact','text':c['claim'],'evidence_ids':['K003'],'anchors':[{'card_id':'K003','field':'claim','quote':c['claim']}],'caveat':None}]},ensure_ascii=False),{'total_tokens':10}

class PolicyTests(unittest.TestCase):
    def setUp(self): self.kb=KnowledgeBase()
    def session(self): return ContextSession('我在湖泊，看到水草，应该先观察哪里？')
    def test_fact_only_gets_direct_candidate(self):
        s=ContextSession('我在水库岸边，看到一片倒木，应该先观察什么？')
        r=respond(s,self.kb,'rag',Client)
        self.assertEqual(r['answer_origin'],'reviewed_observation_policy_v1')
        self.assertEqual(len(r['model_answer_before_policy']['claims']),1)
        self.assertEqual(len(r['claims']),2)
        self.assertIn('倒木作为观察候选',r['claims'][1]['text'])
        self.assertNotIn('水草',r['claims'][1]['text'])
        self.assertEqual(s.attempts,1)
        self.assertEqual(r['usage']['total_tokens'],10)
    def test_overstrong_original_preserved(self):
        c=next(c for c in self.kb.cards if c['id']=='K003')
        bad={'status':'answered','followup_question':None,'claims':[{'kind':'project_inference','text':'应重点观察水草附近倒木和岩石，这是重要利用点。','evidence_ids':['K003'],'anchors':[{'card_id':'K003','field':'application_note','quote':c['application_note']}],'caveat':'实际情况需核查。'}]}
        r=respond(self.session(),self.kb,'rag',lambda:Client(bad))
        self.assertIn('应重点观察',r['raw_response'])
        self.assertEqual(r['model_answer_before_policy'],bad)
        self.assertNotIn('倒木',r['claims'][1]['text'])
        self.assertNotIn('重点',r['claims'][1]['text'])
    def test_all_supported_covers(self):
        for choice,value in [('1','水草'),('2','倒木'),('3','岩石'),('4','水草和倒木')]:
            s=self.session();s.choose('cover',choice)
            r=respond(s,self.kb,'rag',Client)
            self.assertIn(value+'作为观察候选',r['claims'][1]['text'])
    def test_retraction_preserved(self):
        s=self.session();s.choose('cover','0')
        r=respond(s,self.kb,'rag',lambda:Client({'status':'insufficient_evidence','claims':[],'followup_question':None}))
        self.assertEqual(r['claims'],[])
        self.assertEqual(r['answer_origin'],'model')
    def test_other_tasks_untouched(self):
        s=self.session()
        for q in ['应该用什么饵？','水草是什么？','应该先观察水温吗？','应该先观察哪里才一定有鱼？']:
            self.assertIsNone(observation_answer(q,'site',s.context(),self.kb.cards,{'status':'answered'}))
        self.assertIsNone(observation_answer(s.question,'knowledge',s.context(),self.kb.cards,{'status':'answered'}))
    def test_unknown_negative_untouched(self):
        for choice in ('0','5'):
            s=self.session();s.choose('cover',choice)
            self.assertIsNone(observation_answer(s.question,'site',s.context(),self.kb.cards,{'status':'answered'}))
    def test_missing_changed_card_untouched(self):
        s=self.session()
        for cards in [[],deepcopy(self.kb.cards)]:
            for c in cards:
                if c['id']=='K003': c['claim']='changed source'
            self.assertIsNone(observation_answer(s.question,'site',s.context(),cards,{'status':'answered'}))
    def test_refusal_error_not_hidden(self):
        for client in [Client({'status':'insufficient_evidence','claims':[],'followup_question':None}),Client(error=True)]:
            r=respond(self.session(),self.kb,'rag',lambda:client)
            self.assertNotEqual(r['status'],'answered')
            self.assertNotIn('model_answer_before_policy',r)
            self.assertEqual(r['claims'],[])
    def test_invalid_model_not_replaced(self):
        r=respond(self.session(),self.kb,'rag',lambda:Client({'status':'answered','claims':[],'followup_question':None}))
        self.assertEqual(r['status'],'error')
        self.assertNotIn('model_answer_before_policy',r)
    def test_mock_and_hash(self):
        s=self.session();r=respond(s,self.kb)
        self.assertEqual(r['claims'],[])
        self.assertEqual(r['status'],'evidence_only')
        self.assertIn('observation_policy.py',session_record(s,self.kb)['code_sha256'])
