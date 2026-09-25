import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_jev_native_prompt_report_v1 as report
import jev_native_prompt_variants_v1 as native


def response():
    answers = {}
    for key, question in native.payload('x', 'y', 'P0')['questions'].items():
        labels = list(question['criteria'])
        answers[key] = {'type': 'choice', 'choice': labels[0],
                        'probabilities': {label: float(i == 0) for i, label in enumerate(labels)},
                        'confidence': 1.0}
    return {'model': native.PRICE_MODEL, 'answers': answers,
            'usage': {'input_tokens': 100, 'output_tokens': 20}}


class NativeJevReport(unittest.TestCase):
    def closed_directory(self, directory):
        root = Path(directory)
        root.joinpath('input-only-manifest.json').write_text(
            json.dumps(native.planned_manifest(verify_baseline=True), indent=2, ensure_ascii=False) + '\n')
        manifest_sha = native.sha_bytes(root.joinpath('input-only-manifest.json').read_bytes())
        ledger = root / 'budget.jsonl'
        ledger.write_text(json.dumps({'event': 'budget', 'cap_usd': '1'}) + '\n')
        for variant in ('P1', 'P2'):
            review = root / f'{variant}-plan-review.json'
            review.write_text(json.dumps({'kind': 'jev-native-plan-review-v1',
                                          'manifest_sha256': manifest_sha, 'variant': variant,
                                          'reviewed': True}))
            for phase in ('smoke', 'development'):
                args = SimpleNamespace(authorize_hosted_inference=True,
                    manifest=str(root/'input-only-manifest.json'), variant=variant,
                    phase=phase, review_receipt=str(review),
                    smoke_attempts=str(root/f'{variant}-smoke.jsonl') if phase == 'development' else None,
                    smoke_inspection=str(root/f'{variant}-smoke-inspection.json') if phase == 'development' else None,
                    output=str(root/f'{variant}-{phase}.jsonl'),
                    journal=str(root/f'{variant}-{phase}.attempts.jsonl'),
                    budget_ledger=str(ledger), max_usd=Decimal('1'), env_file=None, timeout=1)
                with mock.patch.object(native, 'LEDGER', ledger), \
                     mock.patch.object(native, 'load_key', return_value='secret'), \
                     mock.patch.object(native, 'fetch', return_value=response()):
                    native.execute(args)
                if phase == 'smoke':
                    inspection = root / f'{variant}-smoke-inspection.json'
                    inspection.write_text(json.dumps({'kind': 'jev-native-smoke-inspection-v1',
                        'manifest_sha256': manifest_sha, 'variant': variant, 'reviewed': True,
                        'smoke_attempts_sha256': native.sha_bytes(Path(args.output).read_bytes())}))

    def test_invalid_output_is_retained_in_comparison(self):
        truth = {key: next(iter(q['criteria'])) for key,q in native.payload('x','y','P0')['questions'].items()}
        before = [{'id':'DEV-001','status':'ok','prediction':truth}]
        after = [{'id':'DEV-001','status':'invalid_output','prediction':None}]
        result = report.comparison(before, after, [{'id':'DEV-001','proposed_labels':truth}], [{'id':'DEV-001','feedback':'Example'}])
        self.assertEqual(result['bothValid'],0)
        self.assertEqual(result['changedRecordCount'],1)
        self.assertEqual(result['allFourCorrectToWrong'],['DEV-001'])
        self.assertEqual(result['cases'][0]['to_state'],'invalid_output')

    def test_closed_report_and_terminal_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            self.closed_directory(directory)
            value = report.build(directory)
            self.assertEqual(len(value['public_runs']), 3)
            self.assertEqual(len(value['public_cases']), 180)
            self.assertEqual(set(value['summary']), {'P0', 'P1', 'P2'})
            self.assertEqual(value['public_runs'][0]['timing']['requests'], 61)
            self.assertIsNone(value['public_runs'][1]['timing']['providerInferenceSeconds'])
            self.assertEqual(value['public_pair']['comparisons']['P0_to_P1']['bothValid'], 60)
            self.assertFalse(value['causal_claim_supported'])
            journal = Path(directory) / 'P2-development.attempts.jsonl'
            journal.write_text('\n'.join(journal.read_text().splitlines()[:-1]) + '\n')
            with self.assertRaisesRegex(ValueError, 'closed requests'):
                report.build(directory)


if __name__ == '__main__':
    unittest.main()
