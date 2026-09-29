from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark_v05 import ROOT, load_cases, replay, score, summarize, run_case, run_benchmark
from retriever import KnowledgeBase


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()
        self.path = ROOT/'data/scenarios_v05.json'
        self.data = load_cases(self.path,self.kb)

    def invalid(self,data):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):
                load_cases(path,self.kb)

    def test_duplicate_ids_rejected(self):
        data=deepcopy(self.data)
        data['cases'].append(deepcopy(data['cases'][0]))
        self.invalid(data)

    def test_bad_card_and_unsafe_id_rejected(self):
        for key,value in [('relevant_ids',['K999']),('id','../escape')]:
            data=deepcopy(self.data)
            data['cases'][0][key]=value
            self.invalid(data)

    def test_contradictory_labels_rejected(self):
        data=deepcopy(self.data)
        data['cases'][0]['expect_no_evidence']=True
        self.invalid(data)

    def test_missing_script_answer_not_silently_unknown(self):
        case=deepcopy(self.data['cases'][5])
        case['answers']={}
        with self.assertRaises(ValueError):
            replay(case)

    def test_metrics_use_relevant_rank_and_denominator(self):
        case=deepcopy(self.data['cases'][0])
        case['relevant_ids']=['K004','K003']
        m=score(case,['K001','K004'],'test')
        self.assertEqual(m['recall_at_4'],.5)
        self.assertEqual(m['reciprocal_rank_at_4'],.5)
        self.assertTrue(m['hit_at_4'])
        self.assertIsNone(m['empty_on_negative'])

    def test_no_denominator_is_null(self):
        result=summarize([])
        self.assertEqual(result['direct']['context_exact'],{'n':0,'mean':None})

    def test_correction_is_compared_with_stale_baseline(self):
        rows,_=run_case(self.data['cases'][11],self.kb)
        self.assertFalse(rows[0]['metrics']['stale_query_clean'])
        self.assertFalse(rows[1]['metrics']['stale_query_clean'])
        self.assertTrue(rows[2]['metrics']['stale_query_clean'])
        self.assertTrue(rows[2]['metrics']['context_exact'])

    def test_unknown_state_is_not_unanswered(self):
        case=self.data['cases'][9]
        session=replay(case)
        self.assertTrue(score(case,[],session.retrieval_query(),session.context())['context_exact'])
        context=session.context()
        context['waterbody']['status']='unanswered'
        self.assertFalse(score(case,[],'',context)['context_exact'])

    def test_offline_run_exports_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch('llm.ChatClient.complete',side_effect=AssertionError('must not call model')):
            out=Path(tmp)/'experiment'
            result=run_benchmark(self.path,'dev',out)
            self.assertFalse(result['model_called'])
            self.assertEqual(len(result['rows']),60)
            self.assertEqual(len(list((out/'agent_runs').glob('*.json'))),20)
            self.assertIn('失败与部分召回',(out/'REPORT.md').read_text())
            old=(out/'results.json').read_bytes()
            with self.assertRaises(FileExistsError):
                run_benchmark(self.path,'dev',out)
            self.assertEqual(old,(out/'results.json').read_bytes())

    def test_failures_are_not_dropped(self):
        with patch.object(self.kb, 'search', return_value={'status':'empty','results':[],'message':'test miss'}):
            rows,_=run_case(self.data['cases'][0],self.kb)
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r['metrics']['hit_at_4'] is False for r in rows))
        self.assertEqual(summarize(rows)['agent_state']['hit_at_4'],{'n':1,'mean':0})


if __name__ == '__main__':
    unittest.main()
