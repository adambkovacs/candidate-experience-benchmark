import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from development_benchmark import KEYS, VALUES
import jev_cloudflare_native_preparation_v1 as prep
from jev_native_prompt_variants_v1 import payload as typesafe_payload


class JevCloudflareNativePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.policy = prep.inputs_and_policy()

    def test_offline_plan_has_nine_stages_and_no_reference_binding(self):
        plan = prep.build_plan()
        self.assertEqual(plan['route'], 'typesafe/jev')
        self.assertEqual(plan['expected_returned_version'], 'jev-1.13.0')
        self.assertEqual(plan['returned_version_status'],
                         'documentation_example_only_live_smoke_required')
        self.assertEqual(len(plan['stages']), 9)
        self.assertEqual(plan['request_count_if_all_stages_run'], 567)
        self.assertEqual(plan['full_context_planning_reservation_usd'], '0.762048')
        self.assertEqual(plan['shared_authority']['cap_usd'], '10.00')
        self.assertFalse(plan['inference_performed'])
        self.assertFalse(plan['reference_labels_read_or_sent'])
        self.assertNotIn('proposed_labels', json.dumps(plan))
        for stage in plan['stages']:
            self.assertEqual(stage['smoke_ids'], list(prep.SMOKE_IDS))
            self.assertEqual(stage['development_ids'], list(prep.IDS))
            self.assertEqual(stage['order'], 'review_three_smoke_before_sixty_development')
        for condition in prep.CONDITIONS:
            self.assertEqual([r['id'] for r in plan['requests'][condition]], list(prep.IDS))
        first_hashes = [plan['requests'][condition][0]['rest_body_sha256']
                        for condition in prep.CONDITIONS]
        self.assertEqual(len(set(first_hashes)), 3)

    def test_payload_is_exact_native_choice_rest_shape(self):
        feedback = self.rows[0]['feedback']
        payloads = {name: prep.request_payload(feedback, self.policy, name)
                    for name in prep.CONDITIONS}
        for payload in payloads.values():
            self.assertEqual(set(payload), {'model', 'input'})
            self.assertEqual(payload['model'], 'typesafe/jev')
            self.assertEqual(set(payload['input']), {'state', 'questions'})
            self.assertEqual(payload['input']['state'],
                             {'feedback': feedback, 'policy': self.policy})
            self.assertEqual(list(payload['input']['questions']), list(KEYS))
            for field in KEYS:
                question = payload['input']['questions'][field]
                self.assertEqual(question['type'], 'choice')
                self.assertEqual(list(question['criteria']), list(VALUES[field]))
        for field in KEYS:
            p0 = payloads['P0']['input']['questions'][field]
            p1 = payloads['P1']['input']['questions'][field]
            p2 = payloads['P2']['input']['questions'][field]
            self.assertEqual(p1['instructions'], p0['instructions'] + prep.P1)
            self.assertEqual(p2['instructions'], p1['instructions'] + prep.P2[field])
            self.assertEqual(p0['criteria'], p1['criteria'])
            self.assertEqual(p1['criteria'], p2['criteria'])
        self.assertNotIn('proposed_labels', json.dumps(payloads))
        typesafe_p0 = typesafe_payload(feedback, self.policy, 'P0')
        self.assertEqual(payloads['P0']['input'],
                         {key: value for key, value in typesafe_p0.items() if key != 'model'})
        with self.assertRaises(ValueError):
            prep.request_payload(feedback, self.policy, 'P3')

    def test_checked_plan_rejects_tampering(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.json'
            path.write_text(json.dumps(prep.build_plan(), indent=2, ensure_ascii=False) + '\n')
            plan, plan_hash = prep.checked_plan(path)
            self.assertEqual(plan['records'], 60)
            self.assertEqual(len(plan_hash), 64)
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                prep.checked_plan(path)

    def test_saved_response_parser_preserves_probabilities_and_fails_closed(self):
        answers = {}
        for field in KEYS:
            labels = VALUES[field]
            answers[field] = {'type': 'choice', 'choice': labels[0],
                              'confidence': 0.8,
                              'probabilities': {label: int(label == labels[0])
                                                for label in labels}}
        envelope = {'success': True, 'errors': [],
                    'result': {'model': 'jev-1.13.0', 'answers': answers,
                               'usage': {'input_tokens': 500, 'output_tokens': 50}}}
        parsed = prep.parse_rest_response(envelope)
        self.assertEqual(parsed['prediction'], {field: VALUES[field][0] for field in KEYS})
        self.assertEqual(parsed['returned_model'], 'jev-1.13.0')
        self.assertIsNone(parsed['actual_charge_usd'])
        self.assertEqual(parsed['confidence'], {field: 0.8 for field in KEYS})
        for mutation in (
            lambda item: item['result'].__setitem__('model', 'jev-1.14.0'),
            lambda item: item.__setitem__('success', False),
            lambda item: item['result']['answers'].pop(KEYS[0]),
            lambda item: item['result']['usage'].__setitem__('input_tokens', -1),
        ):
            invalid = copy.deepcopy(envelope)
            mutation(invalid)
            with self.assertRaises(ValueError):
                prep.parse_rest_response(invalid)

    def test_full_context_hold_math_rejects_bad_count(self):
        self.assertEqual(str(prep.reservation_usd(3)), '0.004032')
        self.assertEqual(prep.reservation_usd(60), Decimal('0.080640'))
        for bad in (-1, 1.0, True):
            with self.assertRaises(ValueError):
                prep.reservation_usd(bad)


if __name__ == '__main__':
    unittest.main()
