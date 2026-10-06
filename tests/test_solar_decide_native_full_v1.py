import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_native_full_v1 as full


class SolarFullPlanTests(unittest.TestCase):
    def test_new_series_has_nine_independent_smokes_and_exact_requests(self):
        plan = full.build()
        self.assertEqual([p['id'] for p in plan['phases']], list(full.PHASES))
        self.assertEqual(plan['new_smoke_stage_count'], 9)
        self.assertEqual(plan['all_stage_request_count_including_smokes'], 567)
        self.assertEqual(plan['per_request_conservative_reserve_usd'], '0.10485760')
        self.assertFalse(plan['historical_smoke_reused_as_passed_three_record_gate'])
        self.assertFalse(plan['historical_dev001_retried'])
        self.assertEqual(plan['historical_failed_smoke']['attempted'], ['DEV-001'])
        self.assertEqual(plan['historical_exact_unsent_continuation']['attempted'], ['DEV-002', 'DEV-003'])
        self.assertFalse(plan['reference_labels_sent'])
        for phase in plan['phases']:
            self.assertEqual(phase['smoke_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
            self.assertEqual([r['id'] for r in phase['requests']],
                             [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertEqual(phase['development_request_count'], 60)
        for p in ('P0', 'P1', 'P2'):
            self.assertEqual(plan['phases'][('P0', 'P1', 'P2').index(p)]['requests_sha256'],
                             plan['phases'][3 + ('P0', 'P1', 'P2').index(p)]['requests_sha256'])

    def test_prior_closure_and_four_question_risk_are_required(self):
        original = full.BOUND
        with patch.object(full, 'BOUND', original / 4):
            with self.assertRaisesRegex(ValueError, 'Four-question Solar reserve'):
                full.build()
        with patch.object(full.suffix_run, 'sha', return_value='0' * 64):
            with self.assertRaises(ValueError):
                full.prior_outcomes(ROOT)

    def test_plan_verifies_without_private_raw_files_in_git_archive(self):
        if not (ROOT / '.git').exists():
            self.assertFalse((ROOT / 'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/smoke.raw.jsonl').exists())
            self.assertEqual(len(full.build()['phases']), 9)
            return
        data = subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT)
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
                archive.extractall(checkout)
            for name in ('scripts/solar_decide_native_full_v1.py',
                         'tests/test_solar_decide_native_full_v1.py',
                         'results/solar-decide-native-full-v1/plan.json',
                         'results/solar-decide-native-full-v1/root-review.json'):
                target = checkout / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            env = dict(os.environ, PYTHONPATH=str(checkout / 'scripts'))
            result = subprocess.run([sys.executable, str(checkout / 'scripts/solar_decide_native_full_v1.py'),
                                     'verify'], cwd=checkout, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            script = '''import tempfile
from pathlib import Path
from unittest.mock import patch
import solar_decide_native_full_v1 as s
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp) / 'fresh-plan'
    with (patch.object(s, 'BASE', base),
          patch.object(s, 'PLAN', base / 'plan.json'),
          patch.object(s, 'REVIEW', base / 'root-review.json')):
        assert s.prepare() == s.verify()
'''
            result = subprocess.run([sys.executable, '-c', script], cwd=checkout,
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
