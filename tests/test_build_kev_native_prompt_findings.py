import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import build_kev_native_prompt_findings as report


class KevNativePromptFindingsTests(unittest.TestCase):
    def test_real_report_admits_only_closed_reconciled_passes(self):
        value = report.build()
        self.assertEqual(value['schema'], 'kev-native-prompt-findings-v1')
        self.assertEqual(value['conditionOrder'], ['P1', 'P2'])
        self.assertEqual(value['denominator'], 60)
        for condition in ('P1', 'P2'):
            self.assertGreaterEqual(value['conditions'][condition]['completedPasses'], 2)
            for phase in value['conditions'][condition]['passes'].values():
                self.assertEqual(phase['completionStatus'], 'complete')
                self.assertEqual(phase['score']['valid'], 60)
                self.assertEqual(phase['score']['denominator'], 60)
        self.assertTrue(value['nativePromptEquivalence']['verified'])
        self.assertNotIn('fresh3', value['historicalP0']['cleanComparisons'])

    def test_phase_state_excludes_partial_or_unreconciled_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertEqual(report.phase_state(directory), 'not_started')
            (directory / 'attempts.jsonl').write_text('{}\n')
            self.assertEqual(report.phase_state(directory), 'running_unscored')
            (directory / 'completion.json').write_text('{}\n')
            self.assertEqual(report.phase_state(directory), 'terminal_unreconciled')
            (directory / 'budget-reconciliation.json').write_text('{}\n')
            self.assertEqual(report.phase_state(directory), 'closed_candidate')

    def test_attempt_source_drift_is_rejected(self):
        source = report.BASE / report.CONFIGS['P1'] / 'fresh1'
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ('attempts.jsonl', 'completion.json', 'endpoint-catalog.json',
                         'review-receipt.json', 'budget-reconciliation.json'):
                shutil.copy2(source / name, directory / name)
            rows = report.read_jsonl(directory / 'attempts.jsonl')
            rows[2]['client_request_elapsed_ns'] += 1
            (directory / 'attempts.jsonl').write_text(
                ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
            manifest = json.loads((report.BASE / (report.CONFIGS['P1'] + '.json')).read_text())
            with self.assertRaisesRegex(ValueError, 'attempts SHA'):
                report.validate_phase_attempts(manifest, directory)

    def test_missing_outcome_is_rejected_even_with_matching_attempt_hash(self):
        source = report.BASE / report.CONFIGS['P1'] / 'fresh1'
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ('attempts.jsonl', 'completion.json', 'endpoint-catalog.json',
                         'review-receipt.json', 'budget-reconciliation.json'):
                shutil.copy2(source / name, directory / name)
            rows = report.read_jsonl(directory / 'attempts.jsonl')[:-4]
            attempts = directory / 'attempts.jsonl'
            attempts.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            completion = json.loads((directory / 'completion.json').read_text())
            completion['attempts_sha256'] = report.file_sha(attempts)
            (directory / 'completion.json').write_text(json.dumps(completion))
            manifest = json.loads((report.BASE / (report.CONFIGS['P1'] + '.json')).read_text())
            with self.assertRaisesRegex(ValueError, 'exactly 60 four-event outcomes'):
                report.validate_phase_attempts(manifest, directory)

    def test_probability_maps_and_vendor_confidence_remain_separate(self):
        value = report.build()
        comparison = value['pairedP1P2'][0]
        self.assertIn('nativeProbabilityDictionaryChanges', comparison)
        self.assertIn('vendorConfidenceChanges', comparison)
        source = report.BASE / report.CONFIGS['P1'] / 'fresh1'
        manifest = json.loads((report.BASE / (report.CONFIGS['P1'] + '.json')).read_text())
        parsed = report.validate_phase_attempts(manifest, source)
        self.assertTrue(any(
            item['confidence'] != item['probabilities'][item['choice']]
            for record in parsed['native'].values() for item in record.values()))
        self.assertIn('nativeChoiceProbabilities', value['interpretation'])
        self.assertIn('vendorConfidence', value['interpretation'])

    def test_native_prompt_equivalence_rejects_non_instruction_drift(self):
        p1, p2 = report.load_frozen_native_plans()
        broken = copy.deepcopy(p2)
        broken[0]['payload']['state']['feedback'] += ' drift'
        with self.assertRaisesRegex(ValueError, 'non-instruction controls differ'):
            report.verify_native_prompt_equivalence(p1, broken)

    def test_closed_report_verifies_after_checkout_relocation_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'relocated-checkout'
            base = root / report.BASE_RELATIVE
            refs = root / 'data/pilot/proposed_labels.jsonl'
            shutil.copytree(report.BASE, base)
            refs.parent.mkdir(parents=True)
            shutil.copy2(report.REFERENCES, refs)
            with mock.patch.object(report, 'ROOT', root):
                value = report.build(base=base, refs_path=refs)
                self.assertEqual(value['conditions']['P1']['completedPasses'], 3)
                self.assertEqual(value['conditions']['P2']['completedPasses'], 3)

                receipt_path = (base / report.CONFIGS['P1'] / 'fresh1.root-review.json')
                original_receipt = receipt_path.read_text()
                receipt = json.loads(original_receipt)
                receipt['global_hold_source_sha256'] = '0' * 64
                receipt_path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'Independent full-pass receipt differs'):
                    report.build(base=base, refs_path=refs)
                receipt_path.write_text(original_receipt)

                budget = json.loads((base / report.CONFIGS['P1'] / 'fresh1.budget.json').read_text())
                child = base / report.CONFIGS['P1'] / Path(
                    budget['partitions'][0]['child_ledger']).name
                original_child = child.read_text()
                child.write_text(original_child + ' ')
                with self.assertRaisesRegex(ValueError, 'budget reconciliation differs'):
                    report.build(base=base, refs_path=refs)


if __name__ == '__main__':
    unittest.main()
