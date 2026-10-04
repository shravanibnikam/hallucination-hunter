"""CSV validation checks; no database credentials needed."""
import csv
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('import_pairs', ROOT / 'research' / 'import_pairs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImportValidation(unittest.TestCase):
    def setUp(self):
        with (ROOT / 'research/data/sample_pairs.csv').open(newline='') as source:
            self.rows = list(csv.DictReader(source))
        self.row = self.rows[0].copy()

    def test_samples(self):
        self.assertEqual(len(self.rows), 8)
        for row in self.rows:
            self.assertEqual(module.validate(row)[1], [])
            self.assertTrue(row['question'].startswith('[SAMPLE]'))

    def test_required(self):
        for key in module.REQUIRED:
            with self.subTest(key=key):
                self.assertTrue(module.validate({**self.row, key: ''})[1])

    def test_exact_span(self):
        self.assertTrue(module.validate({**self.row, 'fabricated_span': 'FOUR'})[1])

    def test_urls(self):
        for url in ['javascript:alert(1)', 'https://', 'http://a b.com', 'https://user:pass@example.com', 'https://example.com:bad', 'https://exa<mple.com', 'https://example.com/\x00']:
            with self.subTest(url=url):
                self.assertTrue(module.validate({**self.row, 'source_url': url})[1])

    def test_enums_and_booleans(self):
        for key in ['hallucination_type', 'origin', 'is_active', 'is_attention_check']:
            self.assertTrue(module.validate({**self.row, key: 'invalid'})[1])

    def test_defaults_and_uuid(self):
        result, errors = module.validate({**self.row, 'is_active': '', 'is_attention_check': '', 'source_url': '', 'model_name': ''})
        self.assertEqual(errors, [])
        self.assertTrue(result['is_active'])
        self.assertFalse(result['is_attention_check'])
        self.assertIsNone(result['source_url'])
        self.assertTrue(module.validate({**self.row, 'id': 'bad'})[1])


if __name__ == '__main__':
    unittest.main()
