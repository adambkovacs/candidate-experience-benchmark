import unittest
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qwen27_fresh_repeat_study as study


class Qwen27FreshRepeatStudyTests(unittest.TestCase):
    def test_each_config_has_three_counterbalanced_input_only_plans(self):
        for config_id, spec in study.CONFIGS.items():
            plans = [study.plan_data(config_id, fresh) for fresh in study.ORDERS]
            self.assertEqual([p['condition_order'] for p in plans], list(study.ORDERS.values()))
            self.assertEqual([p['configuration_id'] for p in plans], [config_id] * 3)
            first = plans[0]['conditions']
            self.assertEqual(set(first), {'P0', 'P1', 'P2'})
            for condition, phase in first.items():
                self.assertEqual([r['record_id'] for r in phase['development']], [f'DEV-{i:03}' for i in range(1, 61)])
                self.assertEqual(phase['smoke'], phase['development'][:3])
                failures = [r['historical_outcome_excluded'] for r in phase['development']
                            if r['historical_outcome_excluded'] != 'ok']
                expected = {
                    'openrouter-paid-qwen3.8-27b-medium': {'P0': ['service_error'], 'P1': ['service_error'], 'P2': []},
                    'openrouter-paid-qwen3.8-27b-xhigh': {'P0': ['invalid_output'], 'P1': [], 'P2': ['service_error']},
                }[config_id][condition]
                self.assertEqual(sorted(failures), sorted(expected))
                for request in phase['development']:
                    self.assertEqual(set(request['payload']), {'model', 'temperature', 'max_tokens', 'stream', 'provider', 'response_format', 'reasoning', 'messages'})
                    self.assertEqual(request['payload']['messages'][1]['content'], json.dumps({'feedback': study.input_feedback()[request['record_id']]}))
            for later in plans[1:]:
                for condition in ('P0','P1','P2'):
                    self.assertEqual(first[condition]['development'], later['conditions'][condition]['development'])

    def test_cost_proxy_unknown_bounds_and_reserve_are_distinct(self):
        medium = study.estimate('openrouter-paid-qwen3.8-27b-medium')
        xhigh = study.estimate('openrouter-paid-qwen3.8-27b-xhigh')
        self.assertEqual(medium['historical_one_pass_known_cost_usd'], '0.198897225')
        self.assertEqual(medium['historical_one_pass_unknown_bound_usd'], '0.094003200')
        self.assertEqual(medium['three_pass_known_plus_unknown_sensitivity_usd'], '0.878701275')
        self.assertEqual(xhigh['historical_one_pass_known_cost_usd'], '0.184197225')
        self.assertEqual(xhigh['historical_one_pass_unknown_bound_usd'], '0.047001600')
        self.assertEqual(xhigh['three_pass_known_plus_unknown_sensitivity_usd'], '0.693596475')
        self.assertEqual(medium['per_request_maximum_reserve_usd'], '0.047001600')
        self.assertEqual(medium['all_requests_max_reserve_stress_usd'], '26.649907200')
        self.assertEqual(medium['proposed_child_budget_usd'], '1.00')
        self.assertEqual(xhigh['proposed_child_budget_usd'], '0.80')

    def test_missing_request_body_proof_fails_closed(self):
        row = {'id':'DEV-001','request':None,'reference_labels_read':False}
        with self.assertRaisesRegex(ValueError, 'request body'):
            study.validate_historical_request(row, {}, 'P0', 'DEV-001')

    def test_manifest_verification_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / 'openrouter-paid-qwen3.8-27b-medium' / 'fresh1' / 'manifest.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{}\n')
            with patch.object(study, 'BASE', Path(temporary)):
                with self.assertRaisesRegex(ValueError, 'Manifest hash mismatch'):
                    study.verify('openrouter-paid-qwen3.8-27b-medium', 'fresh1', '0' * 64)


if __name__ == '__main__':
    unittest.main()
