import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('clef_native_preparation',
    ROOT / 'scripts/clef_native_preparation.py')
clef = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clef)


class ClefNativePreparationTests(unittest.TestCase):
    def test_plan_has_exact_60_input_only_cases_and_3_smoke_then_60_for_each_phase(self):
        plan = clef.build_plan()
        self.assertEqual(plan['status'], 'offline_prepared_unapproved')
        self.assertFalse(plan['inference_performed'])
        self.assertFalse(plan['reference_labels_read'])
        self.assertEqual(plan['records'], 60)
        self.assertEqual(plan['future_credential_env_names'],
                         ['CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN'])
        self.assertEqual(plan['initial_smoke_for_review']['ids'], list(clef.SMOKE_IDS))
        self.assertEqual(plan['initial_smoke_for_review']['request_count'], 6)
        self.assertEqual(plan['initial_smoke_for_review']['full_context_planning_reservation_usd'],
                         '0.064884')
        self.assertEqual(plan['initial_smoke_for_review']['proposed_cloudflare_cap_usd'], '0.10')
        self.assertNotIn('data/pilot/proposed_labels.jsonl', plan['source_sha256'])
        self.assertEqual(set(plan['models']), {'clef', 'clef-flash'})
        for model, item in plan['models'].items():
            with self.subTest(model=model):
                self.assertEqual(len(item['stages']), 9)
                self.assertEqual(item['request_count_if_all_stages_run'], 567)
                self.assertEqual({(stage['pass'], stage['condition']) for stage in item['stages']},
                                 {(repeat, condition) for repeat in clef.PASSES
                                  for condition in clef.CONDITIONS})
                for stage in item['stages']:
                    self.assertEqual(stage['smoke_ids'], list(clef.SMOKE_IDS))
                    self.assertEqual(stage['development_ids'], list(clef.IDS))
                for condition in clef.CONDITIONS:
                    self.assertEqual([row['id'] for row in item['requests'][condition]], list(clef.IDS))
                self.assertEqual(Decimal(item['full_context_planning_reservation_usd']),
                                 clef.reservation_usd(model, 567))
        self.assertEqual(clef.reservation_usd('clef', 567), Decimal('8.918343'))
        self.assertEqual(clef.reservation_usd('clef-flash', 567), Decimal('3.344733'))

    def test_native_variants_only_append_to_question_instructions(self):
        feedback = 'A fictional interview was helpful.'
        policy = 'Apply the four labels.'
        for model in clef.MODELS:
            p0 = clef.request_payload(feedback, policy, model, 'P0')
            p1 = clef.request_payload(feedback, policy, model, 'P1')
            p2 = clef.request_payload(feedback, policy, model, 'P2')
            self.assertEqual(set(p0), {'model', 'state', 'questions'})
            self.assertEqual(p0['model'], model)
            for field in clef.KEYS:
                self.assertEqual(list(p0['questions'][field]['criteria']), list(clef.VALUES[field]))
                self.assertEqual(p1['questions'][field]['instructions'],
                                 p0['questions'][field]['instructions'] + clef.P1)
                self.assertEqual(p2['questions'][field]['instructions'],
                                 p0['questions'][field]['instructions'] + clef.P1 + clef.P2[field])
                for variant in (p1, p2):
                    self.assertEqual(variant['state'], p0['state'])
                    self.assertEqual(variant['questions'][field]['criteria'],
                                     p0['questions'][field]['criteria'])
                    self.assertEqual(variant['questions'][field]['type'], 'choice')

    def test_saved_rest_choice_envelope_is_strict_and_preserves_probabilities(self):
        answers = {}
        for field in clef.KEYS:
            labels = clef.VALUES[field]
            scores = {label: 0.0 for label in labels}
            scores[labels[0]] = 1.0
            answers[field] = {'type': 'choice', 'choice': labels[0],
                              'probabilities': scores, 'confidence': 0.97}
        envelope = {'success': True, 'errors': [], 'result':
                    {'model': 'clef', 'answers': answers, 'usage': {'input_tokens': 81}}}
        parsed = clef.parse_rest_response(envelope, 'clef')
        self.assertEqual(parsed['prediction'], {field: clef.VALUES[field][0] for field in clef.KEYS})
        self.assertEqual(parsed['usage']['input_tokens'], 81)
        self.assertIsNone(parsed['actual_charge_usd'])
        self.assertEqual(set(parsed['probabilities']), set(clef.KEYS))

        mutated = copy.deepcopy(envelope)
        mutated['success'] = False
        with self.assertRaises(ValueError):
            clef.parse_rest_response(mutated, 'clef')
        mutated = copy.deepcopy(envelope)
        mutated['result']['model'] = 'clef-flash'
        with self.assertRaises(ValueError):
            clef.parse_rest_response(mutated, 'clef')
        mutated = copy.deepcopy(envelope)
        mutated['result']['answers']['sentiment']['choice'] = 'invented'
        with self.assertRaises(ValueError):
            clef.parse_rest_response(mutated, 'clef')
        mutated = copy.deepcopy(envelope)
        del mutated['result']['answers']['follow_up_needed']
        with self.assertRaises(ValueError):
            clef.parse_rest_response(mutated, 'clef')


if __name__ == '__main__':
    unittest.main()
