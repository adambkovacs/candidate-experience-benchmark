import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qwen36_on_p2_suffix_v3', ROOT / 'scripts/qwen36_on_p2_suffix_v3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Final20Tests(unittest.TestCase):
    def test_frozen_plan_exact_never_sent_ids_and_bound(self):
        result = module.verify(module.PLAN, module.smoke.sha(module.PLAN))
        self.assertEqual(result['record_ids'], [f'DEV-{i:03}' for i in range(41, 61)])
        self.assertEqual(result['prior_state']['failed_ids'], ['DEV-033', 'DEV-039', 'DEV-040'])
        self.assertEqual(result['prior_state']['attempted'], 40)
        self.assertEqual(result['call_bound_usd'], '0.5980160')
        self.assertEqual(result['proposed_partition_cap_usd'], '0.64')

    def test_changed_predecessor_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            plan = json.loads(module.PLAN.read_text())
            plan['sources']['v2_result']['sha256'] = '0' * 64
            path.write_text(json.dumps(plan))
            with patch.object(module, 'RESULT', Path(directory).resolve()):
                with self.assertRaisesRegex(ValueError, 'Changed source'):
                    module.verify(path)

    def test_v2_started_claim_and_prior_failure_are_not_replayable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = 'synthetic-attempt'
            row = {'id': 'DEV-040', 'attempt_id': attempt, 'request_sha256': 'request-hash',
                   'status': 'service_error', 'http_status': 429, 'cost_unknown': True,
                   'reserved_cost_usd': str(module.RESERVE), 'started_utc': '2026-09-24T21:30:40Z',
                   'raw_error_response': {'error': {'metadata': {'provider_name': module.NAME,
                       'limit_source': 'upstream_provider_shared_pool'}}}}
            terminal = {'event': 'terminal', 'attempted_records': 1, 'planned_records': 21,
                        'completed': False, 'terminal_status': 'service_error', 'plan_sha256': 'plan-hash'}
            data = {'v2_plan': {'contract': module.previous.CONTRACT,
                                'record_ids': module.previous.IDS,
                                'new_output': str(module.V2.relative_to(module.ROOT))},
                    'v2_result': [row],
                    'v2_journal': [{'event': 'started', 'id': 'DEV-041', 'attempt_id': attempt,
                                    'request_sha256': 'request-hash'},
                                   {'event': 'finished', 'id': 'DEV-040', 'attempt_id': attempt,
                                    'status': 'service_error'}, terminal],
                    'v2_report': {'configuration_id': module.CID, 'condition': module.VARIANT,
                                  'attempted': 40, 'valid_outputs': 37, 'never_sent_ids': module.IDS,
                                  'status_counts': {'service_error': 3},
                                  'eligible_paired_comparison': False}}
            paths = {}
            for name, value in data.items():
                path = root / (name + '.json')
                path.write_text(json.dumps(value) if name in ('v2_plan', 'v2_report') else
                                ''.join(json.dumps(item) + '\n' for item in value))
                paths[name] = path
            bindings = {name: {'file': name, 'sha256': 'plan-hash' if name == 'v2_plan' else 'hash'}
                        for name in data}
            bindings.update({name: {'file': name, 'sha256': 'hash'} for name in
                             ('original_result', 'original_journal', 'v1_result', 'v1_journal',
                              'v1_report', 'smoke_review')})
            with patch.object(module.previous, 'prior_state', return_value={
                    'attempted': 39, 'failed_ids': ['DEV-033', 'DEV-039']}), \
                 patch.object(module.smoke, 'source', side_effect=lambda binding: paths[binding['file']]):
                with self.assertRaisesRegex(ValueError, 'started claims'):
                    module.prior_state(bindings)

    def test_existing_output_and_missing_review_block(self):
        original_exists = Path.exists
        with patch.object(Path, 'exists', lambda path: True if path == module.OUTPUT else original_exists(path)):
            with self.assertRaisesRegex(FileExistsError, 'output'):
                module.verify(module.PLAN)
        budget = ROOT / 'results/hosted-recovery-budget-v2/manifest.json'
        review = ROOT / 'results/hosted-recovery-budget-v2/qwen36-final21-root-review.json'
        with self.assertRaisesRegex(ValueError, 'root review'):
            module.review_execution(module.PLAN, module.smoke.sha(module.PLAN), budget,
                                    'qwen36-on-p2-final21-v2', review)


if __name__ == '__main__':
    unittest.main()
