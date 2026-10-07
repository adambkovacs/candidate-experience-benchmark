import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from collections import Counter

from scripts import build_additional_cases_v1 as builder


ROOT = Path(__file__).resolve().parents[1]


class AdditionalCasesTests(unittest.TestCase):
    def test_complete_separate_case_coverage(self):
        feed = builder.build()
        original = json.loads((ROOT / 'public-site/extended-cases-v1.json').read_text())
        base = json.loads((ROOT / 'public-site/data-provider-errors-v1.json').read_text())
        self.assertEqual(feed['coverage']['caseRuns'], 77)
        self.assertEqual(len(feed['runs']), 77)
        self.assertEqual(len({run['runId'] for run in feed['runs']}), 77)
        self.assertEqual(len({run['runId'] for run in original['runs']}), 637)
        self.assertEqual(len({run['id'] for run in base['runs']}), 290)
        base_positions = Counter(case['configuration'] for case in base['cases'])
        self.assertEqual(set(base_positions), {run['id'] for run in base['runs']})
        self.assertEqual(set(base_positions.values()), {60})
        self.assertTrue(all(len(run['cases']) == 60 for run in original['runs']))
        all_ids = ({run['runId'] for run in feed['runs']} |
                   {run['runId'] for run in original['runs']} |
                   {run['id'] for run in base['runs']})
        self.assertEqual(len(all_ids), 1004)
        for run in feed['runs']:
            self.assertEqual([case['id'] for case in run['cases']],
                             [f'DEV-{index:03d}' for index in range(1, 61)])
            self.assertEqual(builder.score(run['cases'], {
                case['id']: {'proposed_labels': case['reference']}
                for case in feed['cases']}), run['scores'])

    def test_missing_positions_keep_source_status_and_no_answer(self):
        feed = builder.build()
        solar = next(run for run in feed['runs'] if run['runId'] ==
                     'solar-decide-native-fresh3-p2')
        flash = next(run for run in feed['runs'] if run['runId'] ==
                     'clef-flash-openrouter-native-fresh3-p2')
        self.assertEqual([case for case in solar['cases'] if case['prediction'] is None],
                         [{'id': 'DEV-009', 'status': 'unknown_cost_no_response',
                           'prediction': None}])
        self.assertEqual([case for case in flash['cases'] if case['prediction'] is None],
                         [{'id': 'DEV-039', 'status': 'provider_failure_unknown_cost',
                           'prediction': None}])

    def test_source_hash_drift_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (builder.SUPPLEMENTAL, builder.SONNET, builder.CLEF,
                             builder.INPUTS, builder.REFERENCES):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            run = json.loads((root / builder.SUPPLEMENTAL).read_text())['runs'][0]
            record = Path(run['sourceRecordsUrl'].removeprefix(builder.BASE))
            target = root / record
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / record).read_bytes() + b'\n')
            report = Path(run['evidenceUrl'].removeprefix(builder.BASE))
            target_report = root / report
            target_report.parent.mkdir(parents=True, exist_ok=True)
            target_report.write_bytes((ROOT / report).read_bytes())
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            with self.assertRaisesRegex(ValueError, 'source SHA-256 changed'):
                builder.build(root)


if __name__ == '__main__':
    unittest.main()
