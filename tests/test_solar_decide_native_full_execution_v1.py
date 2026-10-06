import io
import json
import os
from decimal import Decimal
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
from development_benchmark import KEYS, VALUES
import openrouter_budget_v4 as budget_v4
import openrouter_decision_smoke as native
import paid_budget_partitions_v4 as partitions
import solar_decide_native_full_execution_v1 as run


class SolarFullExecutionTests(unittest.TestCase):
    def test_manifest_is_new_series_with_nine_new_smokes(self):
        value = run.manifest_value()
        self.assertEqual(value['phase_order'], list(run.PHASES))
        self.assertEqual(value['new_smoke_stage_count'], 9)
        self.assertFalse(value['historical_failed_smoke_reused'])
        self.assertFalse(value['historical_exact_unsent_continuation_reused'])
        self.assertEqual(value['per_request_conservative_reserve_usd'], '0.10485760')
        self.assertEqual(value['proposed_child_cap_usd'], '1.00')
        self.assertFalse(value['inference_authorized'])
        self.assertFalse(value['allocation_authorized'])
        self.assertEqual([r['id'] for r in run.stage_rows('fresh1/P0', 'smoke')],
                         ['DEV-001', 'DEV-002', 'DEV-003'])

    def test_no_stage_without_full_review_budget_and_inspected_smoke(self):
        with self.assertRaises((FileNotFoundError, ValueError)):
            run.stage_template('fresh1/P0', 'smoke')
        with self.assertRaises((FileNotFoundError, ValueError)):
            run.require_order('fresh1/P0', 'development')
        with self.assertRaises((FileNotFoundError, ValueError)):
            run.verify_phase_closure('fresh1/P0', 'smoke')

    def test_transitive_money_and_key_reader_drift_rejects_manifest(self):
        original = run.sha
        for name in ('openrouter_budget_amendment_v3.py',
                     'openrouter_benchmark.py', 'development_benchmark.py'):
            with self.subTest(name=name):
                def changed(path):
                    return '0' * 64 if Path(path).name == name else original(path)
                with patch.object(run, 'sha', side_effect=changed):
                    with self.assertRaisesRegex(ValueError, 'manifest'):
                        run.verify()

    def test_real_temporary_child_mock_http_success_unknown_and_no_replay(self):
        item = run.phase('fresh1/P0')['requests'][0]
        catalog = json.loads((ROOT / 'results/route-audits/solar-openrouter-endpoint-20260930.json').read_text())
        catalog_raw = native.canonical(catalog)
        answers = {}
        for key in KEYS:
            options = list(VALUES[key]); first = options[0]
            answers[key] = {'type': 'choice', 'choice': first,
                            'probabilities': {option: 1 if option == first else 0 for option in options},
                            'confidence': 1}
        good_wire = native.canonical({'model': run.solar.VERSION, 'provider': run.solar.PROVIDER,
            'answers': answers, 'usage': {'input_tokens': 100, 'output_tokens': 8, 'cost': 0.000005}})
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as temp:
                base = Path(temp).resolve(); master = base / 'master.jsonl'
                master.write_text(json.dumps({'event': 'budget', 'cap_usd': '1'}) + '\n')
                budget = base / 'budget.json'
                child = base / ('budget-' + run.PARTITION_ID + '.jsonl')
                manifest = base / 'manifest.json'; manifest.write_text('{}\n')
                folder = base / 'fresh1/P0'; folder.mkdir(parents=True)
                review = folder / 'development.root-review.json'
                pending = {'schema': 'synthetic-stage', 'approved': False,
                           'independent_review': False, 'authorized_by_root': False,
                           'reviewer': None}
                accepted = dict(pending, approved=True, independent_review=True,
                                authorized_by_root=True, reviewer='root')
                review.write_text(json.dumps(accepted) + '\n')
                with patch.object(budget_v4, 'CAP', Decimal('1')):
                    partitions.allocate(master, budget, [{'id': run.PARTITION_ID,
                        'cap_usd': '1.00', 'model': run.solar.MODEL,
                        'provider': run.solar.PROVIDER, 'reasoning': run.REASONING}])
                    with patch.object(run, 'BASE', base), patch.object(run, 'MANIFEST', manifest), \
                            patch.object(run, 'BUDGET', budget), patch.object(run, 'CHILD', child), \
                            patch.object(run.risk, 'MASTER', master), \
                            patch.object(run, 'phase', return_value={'requests_sha256': 'synthetic-set'}), \
                            patch.object(run, 'stage_rows', return_value=[item]), \
                            patch.object(run, 'stage_template', return_value=pending), \
                            patch.object(run, 'verify', return_value='synthetic-manifest-sha'), \
                            patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-token'}):
                        calls = []
                        def send(payload, token):
                            self.assertEqual(token, 'test-token')
                            calls.append(payload)
                            return (429, b'{"error":"rate limit"}') if unknown else (200, good_wire)
                        fetch = lambda: (catalog_raw, catalog)
                        if unknown:
                            with self.assertRaisesRegex(ValueError, 'cost unknown'):
                                run.execute('fresh1/P0', 'development', review, fetch=fetch, send=send)
                        else:
                            closure = run.execute('fresh1/P0', 'development', review, fetch=fetch, send=send)
                            self.assertEqual((closure['request_count'], closure['known_valid_count']), (1, 1))
                        self.assertEqual(len(calls), 1)
                        events = [json.loads(line) for line in child.read_text().splitlines()]
                        self.assertEqual(sum(event['event'] == 'reserve' for event in events), 1)
                        self.assertEqual(sum(event['event'] == 'settle' for event in events), 0 if unknown else 1)
                        self.assertEqual(len(run.jsonl(folder / 'development.raw.jsonl')), 1)
                        with self.assertRaises(FileExistsError):
                            run.execute('fresh1/P0', 'development', review, fetch=fetch,
                                        send=lambda *_: self.fail('Claimed Solar stage replayed'))

    def test_archive_can_prepare_and_verify_without_private_raw(self):
        if not (ROOT / '.git').exists():
            self.assertFalse((ROOT / 'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/smoke.raw.jsonl').exists())
            self.assertEqual(run.verify(), run.sha(run.MANIFEST))
            return
        data = subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT)
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
                archive.extractall(checkout)
            copies = ('scripts/solar_decide_native_full_v1.py',
                      'tests/test_solar_decide_native_full_v1.py',
                      'scripts/solar_decide_native_full_execution_v1.py',
                      'tests/test_solar_decide_native_full_execution_v1.py',
                      'results/solar-decide-native-full-v1/plan.json',
                      'results/solar-decide-native-full-v1/root-review.json',
                      'results/solar-decide-native-full-v1/execution-adapter-v1/manifest.json',
                      'results/solar-decide-native-full-v1/execution-adapter-v1/root-review.json')
            for name in copies:
                target = checkout / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            env = dict(os.environ, PYTHONPATH=str(checkout / 'scripts'))
            command = [sys.executable, str(checkout / 'scripts/solar_decide_native_full_execution_v1.py')]
            result = subprocess.run(command + ['verify'], cwd=checkout, env=env,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            script = '''import tempfile
from pathlib import Path
from unittest.mock import patch
import solar_decide_native_full_execution_v1 as s
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp) / 'fresh-adapter'
    with (patch.object(s, 'BASE', base),
          patch.object(s, 'MANIFEST', base / 'manifest.json'),
          patch.object(s, 'REVIEW', base / 'root-review.json')):
        assert s.prepare() == s.verify()
'''
            result = subprocess.run([sys.executable, '-c', script], cwd=checkout,
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
