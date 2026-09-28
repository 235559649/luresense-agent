from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from grounding import validate_grounded
from llm import ModelError
from review_runs import prepare, summarize

CARD = {'id': 'K018', 'claim': '水温影响水生生物活动与生长，不同生物具有不同适温范围。',
        'application_note': '未收录目标鱼种阈值，不输出精确最佳温度。'}


def answer():
    return {'status': 'answered', 'claims': [{'kind': 'source_fact', 'text': '水温影响水生生物活动。',
            'evidence_ids': ['K018'], 'anchors': [{'card_id': 'K018', 'field': 'claim',
            'quote': '水温影响水生生物活动与生长'}], 'caveat': None}], 'followup_question': None}


class GroundingTests(unittest.TestCase):
    def validate(self, obj):
        return validate_grounded(json.dumps(obj, ensure_ascii=False), [CARD])

    def test_exact_anchor_accepted(self):
        self.assertEqual(self.validate(answer())['status'], 'answered')

    def test_invented_quote_rejected(self):
        obj = answer()
        obj['claims'][0]['anchors'][0]['quote'] = '必须精确测量水温才能钓鱼'
        with self.assertRaises(ModelError): self.validate(obj)

    def test_project_note_cannot_be_source_fact(self):
        obj = answer()
        obj['claims'][0]['anchors'][0].update(field='application_note', quote=CARD['application_note'])
        with self.assertRaises(ModelError): self.validate(obj)

    def test_inference_requires_caveat(self):
        obj = answer()
        obj['claims'][0]['kind'] = 'project_inference'
        with self.assertRaises(ModelError): self.validate(obj)
        obj['claims'][0]['caveat'] = '这是项目推断，需结合实际环境核对。'
        self.validate(obj)

    def test_reference_without_anchor_rejected(self):
        obj = answer()
        obj['claims'][0]['evidence_ids'].append('K999')
        with self.assertRaises(ModelError): self.validate(obj)

    def test_quote_does_not_prove_entailment(self):
        obj = answer()
        obj['claims'][0]['text'] = '任何情况下都必须使用精确水温数据。'
        # Explicit limitation: a real excerpt can accompany an unsupported conclusion.
        self.assertEqual(self.validate(obj)['status'], 'answered')

    def test_old_schema_is_rejected(self):
        obj = answer()
        del obj['claims'][0]['kind']
        with self.assertRaises(ModelError): self.validate(obj)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'run.json'
        self.data = {'app_version': '0.3-step3', 'sessions': [{'app_version': '0.3-step3',
            'question': '水温有什么作用？', 'events': [{'event': 'response', 'result': {
                **answer(), 'synthetic': False, 'mode': 'rag', 'usage': {'total_tokens': 10}}}]}]}
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.data), encoding='utf-8')

    def test_pending_is_not_correct(self):
        review = prepare([self.path])
        report = summarize(review)['groups']['0.3-step3']
        self.assertEqual(report['decided_coverage'], 0)
        self.assertIsNone(report['unsupported_rate_among_decided'])

    def test_partial_and_unsupported_are_distinct(self):
        review = prepare([self.path])
        review['items'][0]['claim_reviews'][0].update(support='partial', note='卡片支持影响活动，但条件需要核对。')
        report = summarize(review)['groups']['0.3-step3']
        self.assertEqual(report['unsupported_rate_among_decided'], 0)
        self.assertEqual(report['not_fully_supported_rate_among_decided'], 1)

    def test_tampered_evidence_rejected(self):
        review = prepare([self.path])
        review['items'][0]['result']['claims'][0]['text'] = '篡改回答'
        with self.assertRaises(ValueError): summarize(review)

    def test_changed_run_rejected(self):
        review = prepare([self.path])
        self.data['sessions'][0]['events'][0]['result']['usage']['total_tokens'] = 99
        self.save()
        with self.assertRaises(ValueError): summarize(review)

    def test_missing_grade_rows_rejected(self):
        review = prepare([self.path])
        review['items'][0]['claim_reviews'] = []
        with self.assertRaises(ValueError): summarize(review)

    def test_duplicate_runs_rejected(self):
        with self.assertRaises(ValueError): prepare([self.path, self.path])

    def test_synthetic_excluded(self):
        self.data['sessions'][0]['events'][0]['result']['synthetic'] = True
        self.save()
        report = summarize(prepare([self.path]))['groups']['0.3-step3']
        self.assertEqual(report['real_response_rows'], 0)
        self.assertEqual(report['synthetic_or_unknown_rows_excluded'], 1)

    def test_errors_and_refusals_remain_visible(self):
        result = self.data['sessions'][0]['events'][0]['result']
        result.update(status='error', claims=[], usage={})
        self.save()
        report = summarize(prepare([self.path]))['groups']['0.3-step3']
        self.assertEqual(report['real_status_counts']['error'], 1)
        self.assertIsNone(report['unsupported_rate_among_decided'])
        self.assertIsNone(report['known_total_tokens_sum'])

    def test_v02_record_supported(self):
        self.data = {**answer(), 'app_version': '0.2', 'synthetic': False, 'query': '水温？'}
        self.save()
        self.assertIn('0.2', summarize(prepare([self.path]))['groups'])

    def test_grade_requires_reason(self):
        review = prepare([self.path])
        review['items'][0]['claim_reviews'][0]['support'] = 'supported'
        with self.assertRaises(ValueError): summarize(review)


if __name__ == '__main__':
    unittest.main()
