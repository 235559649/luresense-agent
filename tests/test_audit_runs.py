import json
import tempfile
import unittest
from pathlib import Path
from audit_runs import build_audit
from review_runs import write_new

class AuditTests(unittest.TestCase):
    def audit(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run.json'
            p.write_text(json.dumps({'events':[{'event':'response','result':r} for r in rows]}))
            before=p.read_bytes()
            result=build_audit([p])
            self.assertEqual(before,p.read_bytes())
            return result
    def row(self, **kw):
        return dict({'synthetic':False,'claims':[],'status':'answered'},**kw)
    def test_guard_keeps_original_separate(self):
        r=self.row(answer_origin='context_guard_v1',request_attempted=True,model_response_received=True,
                   model_answer_before_guard={'status':'answered','claims':[{}]},
                   context_guard_conflicts=[{'rule':'unobserved_to_present'}])
        r['status']='insufficient_evidence'
        a=self.audit([r]);self.assertEqual(a['rows'][0]['original_claim_count'],1)
        self.assertEqual(a['rows'][0]['final_claim_count'],0)
        self.assertEqual(a['summary']['guard_interceptions'],1)
    def test_policy_is_not_guard(self):
        a=self.audit([self.row(answer_origin='reviewed_observation_policy_v1',model_answer_before_policy={'status':'answered','claims':[]})])
        self.assertEqual(a['summary']['policy_rewrites'],1)
        self.assertEqual(a['summary']['guard_interceptions'],0)
    def test_http_error_not_refusal(self):
        r=self.row(request_attempted=True,model_response_received=False);r['status']='error'
        a=self.audit([r])['summary'];self.assertEqual(a['final_status_counts'],{'error':1})
        self.assertIsNone(a['interception_rate_on_received'])
    def test_mock_excluded(self):
        r=self.row(request_attempted=False);r['synthetic']=True
        a=self.audit([r])['summary'];self.assertEqual(a['real_rows'],0)
    def test_missing_usage_is_not_measured_zero(self):
        a=self.audit([self.row(usage={}),self.row(usage={'total_tokens':0})])['summary']
        self.assertEqual(a['rows_without_known_tokens'],1)
        self.assertEqual(a['rows_with_known_tokens'],1)
    def test_invalid_raw_visible(self):
        a=self.audit([self.row(raw_response='not-json',model_response_received=True)])
        self.assertEqual(a['rows'][0]['original_source'],'unparseable_raw')
    def test_duplicate_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text('{"events":[]}')
            with self.assertRaises(ValueError):build_audit([p,p])
    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text('original')
            with self.assertRaises(FileExistsError):write_new(p,{})
            self.assertEqual(p.read_text(),'original')
