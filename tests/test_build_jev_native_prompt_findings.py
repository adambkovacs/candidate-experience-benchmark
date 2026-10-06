import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import build_jev_native_prompt_findings as report


class JevNativePromptFindingsTests(unittest.TestCase):
    def test_closed_and_stopped_states_preserve_denominators(self):
        value = report.build()
        passes = value['passes']
        self.assertEqual([(passes[c][s]['score']['valid'], passes[c][s]['score']['allFour'])
                          for c, s in [('P1', 'fresh1'), ('P1', 'fresh2'),
                                       ('P2', 'fresh1'), ('P2', 'fresh2')]],
                         [(60, 54), (59, 53), (60, 54), (17, 15)])
        self.assertEqual(passes['P1']['fresh2']['outcomes']['invalid_native_distribution'], 1)
        self.assertEqual(passes['P2']['fresh2']['outcomes']['unknown_cost_http_429'], 1)
        self.assertEqual(passes['P2']['fresh2']['outcomes']['never_sent'], 42)
        self.assertEqual(passes['P2']['fresh2']['unknownUpperBoundUsd'], '0.001344000')
        self.assertEqual(value['comparisons']['P1repeat']['denominator'], 59)
        self.assertEqual(value['comparisons']['P1repeat']['excludedIds'], ['DEV-056'])
        self.assertEqual(value['comparisons']['P1repeat']['fourFieldVectorChangedIds'], [])
        self.assertEqual(value['comparisons']['P1P2fresh1']['fourFieldVectorChangedIds'], ['DEV-013'])

    def test_archived_receipt_never_queries_live_budget_identity(self):
        with patch.object(report.full, 'budget_identity', side_effect=AssertionError('live budget read')):
            value = report.build()
        self.assertEqual(value['passes']['P2']['fresh2']['status'], 'stopped')

    def test_saved_report_matches_verified_evidence(self):
        self.assertEqual(report.OUTPUT.read_text(), report.render(report.build()))
        self.assertIn('not a distinct Jev model', report.OUTPUT.read_text())
        self.assertIn('unknown charge bounded at $0.001344000', report.OUTPUT.read_text())

    def test_raw_response_drift_fails_before_scoring(self):
        config = report.CONFIGS['P1']
        directory = report.BASE / config / 'fresh1'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        with tempfile.TemporaryDirectory() as temp:
            copy_dir = Path(temp)
            shutil.copy2(directory / 'attempts.jsonl', copy_dir / 'attempts.jsonl')
            events = report.rows(copy_dir / 'attempts.jsonl')
            events[2]['raw_response_sha256'] = '0' * 64
            (copy_dir / 'attempts.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in events))
            with self.assertRaisesRegex(ValueError, 'Raw response differs'):
                report.parse_attempts(manifest, copy_dir, 60)

    def test_invalid_native_distribution_cannot_be_scored(self):
        config = report.CONFIGS['P1']
        directory = report.BASE / config / 'fresh2'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        parsed = report.parse_attempts(manifest, directory, 60, invalid_id='DEV-056')
        self.assertNotIn('DEV-056', parsed['predictions'])
        with self.assertRaisesRegex(ValueError, 'Probabilities do not sum to one'):
            report.parse_attempts(manifest, directory, 60)

    def test_terminal_unknown_is_not_treated_as_unsent(self):
        config = report.CONFIGS['P2']
        directory = report.BASE / config / 'fresh2'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        parsed = report.parse_attempts(manifest, directory, 18, unknown_id='DEV-018')
        self.assertEqual(parsed['statuses']['DEV-018'], 'unknown_cost_http_429')
        self.assertEqual(len(parsed['statuses']), 18)
        with self.assertRaisesRegex(ValueError, 'Attempt event count differs'):
            report.parse_attempts(manifest, directory, 17)

    def test_child_reconciliation_drift_is_rejected(self):
        config = report.CONFIGS['P2']
        stage = 'fresh2'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        directory = report.BASE / config / stage
        parsed = report.parse_attempts(manifest, directory, 18, unknown_id='DEV-018')
        child = report.BASE / config / (stage + '.budget-' + config + '-' + stage + '-full-v1.jsonl')
        reconciliation = json.loads((directory / 'budget-reconciliation.json').read_text())
        reconciliation['unknown_upper_bound_usd'] = '0'
        archived_child = reconciliation['child_ledger']
        archived_root = report.archived_root(archived_child,
            report.BASE_RELATIVE / config / child.name, 'Budget child ledger')
        with self.assertRaisesRegex(ValueError, 'Child reconciliation differs'):
            report.check_child(child, archived_child, archived_root,
                               config + '-' + stage + '-full-v1', parsed,
                               reconciliation, directory / 'unknown-cost-evidence.jsonl')

    def test_archived_receipt_survives_relocation_and_rejects_tamper(self):
        config, stage = report.CONFIGS['P1'], 'fresh1'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        original = report.full.paths(report.BASE, config, stage)
        with tempfile.TemporaryDirectory() as temp:
            relocated = Path(temp) / 'results/route-audits/jev-native-full-v1-20261006'
            copied = report.full.paths(relocated, config, stage)
            files = ('manifest', 'estimate', 'context', 'inspection', 'receipt', 'budget')
            for name in files:
                copied[name].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original[name], copied[name])
            copied_child = copied['budget'].parent / (
                copied['budget'].stem + '-' + manifest['passes'][0]['partition_id'] + '.jsonl')
            original_child = original['budget'].parent / copied_child.name
            shutil.copy2(original_child, copied_child)
            copied_receipt = copied['stage'] / 'review-receipt.json'
            copied_receipt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original['stage'] / 'review-receipt.json', copied_receipt)
            value = report.archived_receipt(config, stage, manifest, relocated)
            self.assertEqual(value[1], copied_child)
            archived_child = json.loads(original['budget'].read_text())['partitions'][0]['child_ledger']
            self.assertEqual(value[2], archived_child)
            receipt = json.loads(copied['receipt'].read_text())
            receipt['approved'] = False
            copied['receipt'].write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'Archived root receipt differs'):
                report.archived_receipt(config, stage, manifest, relocated)

    def test_archived_unknown_evidence_path_rejects_root_drift(self):
        config, stage = report.CONFIGS['P2'], 'fresh2'
        manifest = json.loads((report.BASE / (config + '.json')).read_text())
        directory = report.BASE / config / stage
        parsed = report.parse_attempts(manifest, directory, 18, unknown_id='DEV-018')
        original_child = report.BASE / config / (
            stage + '.budget-' + config + '-' + stage + '-full-v1.jsonl')
        archived_child = json.loads((directory / 'budget-reconciliation.json').read_text())['child_ledger']
        archived_root = report.archived_root(archived_child,
            report.BASE_RELATIVE / config / original_child.name, 'Budget child ledger')
        with tempfile.TemporaryDirectory() as temp:
            child = Path(temp) / original_child.name
            events = report.rows(original_child)
            events[-2]['evidence_path'] = '/different/checkout/' + '/'.join(
                (report.BASE_RELATIVE / config / stage / 'unknown-cost-evidence.jsonl').parts)
            child.write_text(''.join(json.dumps(item) + '\n' for item in events))
            reconciliation = json.loads((directory / 'budget-reconciliation.json').read_text())
            reconciliation['child_sha256'] = report.sha(child)
            with self.assertRaisesRegex(ValueError, 'Unknown-cost raw evidence differs'):
                report.check_child(child, archived_child, archived_root,
                    config + '-' + stage + '-full-v1', parsed, reconciliation,
                    directory / 'unknown-cost-evidence.jsonl')

    def test_prompt_non_instruction_drift_is_rejected(self):
        plans = report.frozen.build_plan(report.ROOT)
        broken = copy.deepcopy(plans)
        broken[report.CONFIGS['P2']]['requests'][0]['payload']['state']['feedback'] += ' drift'
        with self.assertRaisesRegex(ValueError, 'Native prompt non-instruction controls differ'):
            report.verify_prompt_delta(broken)


if __name__ == '__main__':
    unittest.main()
