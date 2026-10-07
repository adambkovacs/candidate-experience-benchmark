import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch

from scripts import build_extended_cases_v1 as builder


ROOT = Path(__file__).resolve().parents[1]


class ExtendedCasesTests(unittest.TestCase):
    def test_real_projection_reconciles_catalog_and_source(self):
        data = builder.build(ROOT)
        self.assertEqual(data['coverage']['catalogRuns'], 637)
        self.assertEqual(data['coverage']['caseRuns'], 637)
        self.assertEqual(data['coverage']['reportOnlyRuns'], 0)
        self.assertEqual(len(data['cases']), 60)
        self.assertEqual(len({run['runId'] for run in data['runs']}), 637)
        self.assertEqual(sum(len(run['cases']) for run in data['runs']), 637 * 60)
        self.assertEqual(data['sourceSha256'][str(builder.CATALOG)], builder.digest(ROOT / builder.CATALOG))
        sonnet = next(run for run in data['runs'] if 'sonnet55' in run['sourceStage'])
        self.assertIn('/public-site/sonnet55-fresh-matched3-evidence/', sonnet['sourceRecordUrl'])
        self.assertTrue(any(row['status'] == 'invalid_output' and row['prediction'] is None
                            for run in data['runs'] for row in run['cases']))
        self.assertEqual(sum(bool(run['projectionReview']) for run in data['runs']), 4)
        self.assertTrue(all(run['sourceRecordParts'] and all(part['sha256'] for part in run['sourceRecordParts'])
                            for run in data['runs']))
        qwen = next(run for run in data['runs'] if run['runId'].endswith('qwen36-35b-a3b-on-authority-v3-hosted-v2-fresh1-p1'))
        self.assertEqual(len(qwen['sourceRecordParts']), 2)
        self.assertEqual(qwen['scores']['valid'], next(row['valid'] for row in
                         json.loads((ROOT / builder.CATALOG).read_text())['runs'] if row['id'] == qwen['runId']))
        stopped_jev = next(run for run in data['runs'] if
                           run['runId'] == 'extended-typesafe-jev113-native-prompts-fresh2-p2')
        self.assertEqual(Counter(row['status'] for row in stopped_jev['cases']),
                         {'ok': 17, 'unknown_cost_http_429': 1, 'never_sent': 42})
        self.assertIsNone(stopped_jev['cases'][17]['prediction'])
        self.assertEqual(stopped_jev['cases'][17]['id'], 'DEV-018')
        self.assertTrue(all(set(case) == {'id', 'status', 'prediction'}
                            for run in data['runs'] for case in run['cases']))
        self.assertTrue(all(set(case) == {'id', 'feedback', 'reference'}
                            for case in data['cases']))

    def fixture(self, temp):
        target = Path(temp)
        for source in (builder.INPUTS, builder.REFERENCES):
            (target / source).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target / source)
        source_catalog = json.loads((ROOT / builder.CATALOG).read_text())
        run = next(row for row in source_catalog['runs'] if row['sourceFamily'] == 'repeats')
        configuration, repeat, condition = run['sourceStage'].rsplit('/', 2)
        original_report = json.loads((ROOT / 'public-site/repeats.json').read_text())
        series = next(row for row in original_report['series'] if row['configuration'] == configuration)
        cell = series['passes'][repeat][condition]
        record_path = Path(cell['evidence']['records']['path'])
        (target / record_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / record_path, target / record_path)
        report = {'series': [{'configuration': configuration, 'passes': {repeat: {condition: cell}}}]}
        report_path = target / 'public-site/repeats.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report))
        run['sourceRecordSha256'] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        catalog = {'schema': 'extended-run-catalog-v1', 'runs': [run], 'runCount': 1}
        (target / builder.CATALOG).write_text(json.dumps(catalog))
        return target, run, record_path

    def test_record_hash_drift_rejected_even_with_python_optimized(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _, path = self.fixture(temp)
            with patch.object(subprocess, 'check_output', return_value=str(path) + '\n'):
                self.assertEqual(builder.build(root)['coverage']['caseRuns'], 1)
                (root / path).write_bytes((root / path).read_bytes() + b'\n')
                with self.assertRaisesRegex(ValueError, 'record SHA mismatch'):
                    builder.build(root)

    def test_score_drift_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, run, path = self.fixture(temp)
            catalog_path = root / builder.CATALOG
            catalog = json.loads(catalog_path.read_text())
            catalog['runs'][0]['metrics']['all_four'] -= 1
            catalog_path.write_text(json.dumps(catalog))
            with patch.object(subprocess, 'check_output', return_value=str(path) + '\n'):
                with self.assertRaisesRegex(ValueError, 'case scores do not match catalog'):
                    builder.build(root)

    def test_duplicate_case_id_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _, path = self.fixture(temp)
            rows = builder.read_jsonl(root / path)
            rows[1]['id'] = rows[0]['id']
            (root / path).write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            report_path = root / 'public-site/repeats.json'
            report = json.loads(report_path.read_text())
            cell = next(iter(next(iter(report['series'][0]['passes'].values())).values()))
            cell['evidence']['records']['sha256'] = builder.digest(root / path)
            report_path.write_text(json.dumps(report))
            catalog_path = root / builder.CATALOG
            catalog = json.loads(catalog_path.read_text())
            catalog['runs'][0]['sourceRecordSha256'] = builder.digest(report_path)
            catalog_path.write_text(json.dumps(catalog))
            with patch.object(subprocess, 'check_output', return_value=str(path) + '\n'):
                with self.assertRaisesRegex(ValueError, 'duplicate or unknown case ID'):
                    builder.build(root)


if __name__ == '__main__':
    unittest.main()
