import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import guard_experiments as g


class GuardExperimentTests(unittest.TestCase):
    def dataset(self):
        return dict(schema_version='guard-dataset-1', split='dev', cases=[
            dict(id='A', context={'cover': {'status': 'unknown', 'value': None}},
                 answer={'claims': [{'text': '现场有水草。'}]},
                 expected_block=True, label_reason='未知条件不能断言存在'),
            dict(id='B', context={'cover': {'status': 'unknown', 'value': None}},
                 answer={'claims': [{'text': '先确认结构。'}]},
                 expected_block=False, label_reason='请求观察不是存在断言')])

    def test_metrics_and_empty_denominator(self):
        with patch.object(g.context_guard, 'context_conflicts', return_value=[]):
            r=g.evaluate(self.dataset())
        self.assertIsNone(r['summary']['precision']['value'])
        self.assertEqual(r['summary']['recall']['value'], 0)
        self.assertEqual(r['summary']['fn'], 1)

    def test_duplicate_ids_rejected(self):
        d=self.dataset();d['cases'][1]['id']='A'
        with self.assertRaises(ValueError): g.validate(d)

    def test_non_boolean_label_rejected(self):
        d=self.dataset();d['cases'][0]['expected_block']='false'
        with self.assertRaises(ValueError): g.validate(d)

    def test_changed_dataset_rejected(self):
        a=g.evaluate(self.dataset());d=self.dataset()
        d['cases'][0]['answer']['claims'][0]['text']='附近有倒木。'
        b=g.evaluate(d)
        with self.assertRaises(ValueError): g.compare(a,b)

    def test_fixed_and_regressed_reported(self):
        with patch.object(g.context_guard,'context_conflicts', side_effect=[[], []]):
            a=g.evaluate(self.dataset())
        with patch.object(g.context_guard,'context_conflicts', side_effect=[[{}], [{}]]):
            b=g.evaluate(self.dataset())
        r=g.compare(a,b)
        self.assertEqual(r['fixed_ids'],['A'])
        self.assertEqual(r['regressed_ids'],['B'])

    def test_tampered_dataset_rejected(self):
        r=g.evaluate(self.dataset());r['dataset']['split']='holdout'
        with self.assertRaises(ValueError): g.checked_rows(r)

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.json';g.write(p,{'original':True})
            with self.assertRaises(FileExistsError): g.write(p,{})
            self.assertEqual(g.read(p),{'original':True})


if __name__=='__main__':
    unittest.main()
