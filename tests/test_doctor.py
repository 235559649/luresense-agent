import tempfile
import unittest
from pathlib import Path
from doctor import checks, ROOT

class DoctorTests(unittest.TestCase):
    def test_mock_needs_no_credentials(self):
        self.assertTrue(all(r['ok'] for r in checks(env={})))
    def test_rag_missing_credentials(self):
        rows={r['check']:r for r in checks(mode='rag',env={})}
        self.assertFalse(rows['model']['ok'])
        self.assertFalse(rows['credential']['ok'])
    def test_prompt_does_not_require_existing_key(self):
        self.assertTrue(all(r['ok'] for r in checks(mode='rag',env={},model='example-model',prompt=True)))
    def test_sensitive_configuration_not_returned(self):
        rows=checks(mode='rag',env={'MODEL_API_KEY':'secret-token'},model='example-model',base_url='https://user:secret-password@example.org/v1')
        self.assertFalse(next(r['ok'] for r in rows if r['check']=='endpoint'))
        self.assertNotIn('secret-token',str(rows))
        self.assertNotIn('secret-password',str(rows))
    def test_missing_project_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(all(r['ok'] for r in checks(root=Path(directory),env={})))
