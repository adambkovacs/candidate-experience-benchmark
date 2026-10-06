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
        self.assertEqual(passes['P1']['fresh3']['score']['valid'], 60)
        self.assertEqual(passes['P1']['fresh3']['score']['allFour'], 54)
        self.assertEqual(passes['P1']['fresh3']['knownCostUsd'], '0.006405000')
        self.assertEqual([(passes['P0'][s]['score']['valid'],
                           passes['P0'][s]['score']['allFour'])
                          for s in ('fresh1', 'fresh2', 'fresh3')],
                         [(60, 54), (60, 53), (59, 52)])
        self.assertEqual([passes['P0'][s]['knownCostUsd']
                          for s in ('fresh1', 'fresh2', 'fresh3')],
                         ['0.005890920'] * 3)
        self.assertEqual(passes['P0']['fresh3']['outcomes']['invalid_native_distribution'], 1)
        self.assertEqual(value['comparisons']['P0fresh1fresh2']['fourFieldVectorChangedIds'],
                         ['DEV-013', 'DEV-030', 'DEV-056'])
        self.assertEqual(value['comparisons']['P0fresh2fresh3']['denominator'], 59)
        self.assertEqual(value['comparisons']['P0fresh2fresh3']['fourFieldVectorChangedIds'],
                         ['DEV-030'])
        self.assertEqual(value['comparisons']['P1fresh2fresh3']['denominator'], 59)
        self.assertEqual(value['comparisons']['P1fresh2fresh3']['fourFieldVectorChangedIds'],
                         ['DEV-013'])
        tail = value['continuations']['P2fresh2tail']
        self.assertEqual((tail['score']['denominator'], tail['score']['valid'],
                          tail['score']['allFour']), (42, 40, 35))
        self.assertEqual(tail['outcomes']['invalid_native_distribution'], 1)
        self.assertEqual(tail['outcomes']['unknown_cost_transport_timeout'], 1)
        combined = value['composites']['P2fresh2']
        self.assertEqual((combined['score']['denominator'], combined['score']['valid'],
                          combined['score']['allFour']), (60, 57, 50))
        self.assertEqual(combined['outcomes']['unknown_cost_http_429'], 1)
        self.assertEqual(combined['outcomes']['unknown_cost_transport_timeout'], 1)
        self.assertEqual(combined['outcomes']['invalid_native_distribution'], 1)
        self.assertEqual(combined['neverSent'], 0)
        self.assertFalse(combined['cleanRepeatCredit'])
        self.assertEqual(combined['parentOriginal'], passes['P2']['fresh2'])
        self.assertEqual(combined['knownCostUsd'], '0.006622434')
        self.assertEqual(combined['unknownUpperBoundUsd'], '0.002688000')
        self.assertEqual(value['comparisons']['P1P2fresh2CompositeShared']['denominator'], 56)

    def test_archived_receipt_never_queries_live_budget_identity(self):
        with patch.object(report.full, 'budget_identity', side_effect=AssertionError('live budget read')):
            value = report.build()
        self.assertEqual(value['passes']['P2']['fresh2']['status'], 'stopped')

    def test_saved_report_matches_verified_evidence(self):
        self.assertEqual(report.OUTPUT.read_text(), report.render(report.build()))
        self.assertIn('not a distinct Jev model', report.OUTPUT.read_text())
        self.assertIn('unknown charge bounded at $0.001344000', report.OUTPUT.read_text())
        self.assertIn('57 valid, one invalid, two unknown-cost attempts',
                      report.OUTPUT.read_text())
        self.assertIn('P1 fresh3 is the third attempted full pass',
                      report.OUTPUT.read_text())
        self.assertIn('P0 fresh3:', report.OUTPUT.read_text())

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

    def test_tail_raw_timeout_and_invalid_are_kept_out_of_scoring(self):
        manifest = report.bridge.verify_tail()
        stage = report.full.paths(report.TAIL_BASE, report.CONFIGS['P2'],
                                  report.bridge.TAIL_STAGE)['stage']
        requests = report.frozen.build_plan(report.ROOT)[report.CONFIGS['P2']]['requests'][18:]
        parsed = report.parse_attempts(manifest, stage, 42, invalid_id='DEV-040',
                                       unknown_id='DEV-060', unknown_kind='transport_timeout',
                                       expected_requests=requests)
        self.assertEqual(parsed['statuses']['DEV-040'], 'invalid_native_distribution')
        self.assertEqual(parsed['statuses']['DEV-060'], 'unknown_cost_transport_timeout')
        self.assertNotIn('DEV-040', parsed['predictions'])
        self.assertNotIn('DEV-060', parsed['predictions'])
        self.assertEqual(len(parsed['predictions']), 40)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'attempts.jsonl'
            events = report.rows(stage / 'attempts.jsonl')
            events[-1]['error_type'] = 'OtherError'
            path.write_text(''.join(json.dumps(event) + '\n' for event in events))
            with self.assertRaisesRegex(ValueError, 'Stopped transport outcome differs'):
                report.parse_attempts(manifest, Path(temp), 42, invalid_id='DEV-040',
                                      unknown_id='DEV-060', unknown_kind='transport_timeout',
                                      expected_requests=requests)

    def test_tail_v2_receipt_tamper_is_rejected(self):
        manifest = report.bridge.verify_tail()
        original = report.full.paths(report.TAIL_BASE, report.CONFIGS['P2'],
                                     report.bridge.TAIL_STAGE)
        with tempfile.TemporaryDirectory() as temp:
            relocated = Path(temp) / 'tail'
            copied = report.full.paths(relocated, report.CONFIGS['P2'],
                                       report.bridge.TAIL_STAGE)
            for key in ('manifest', 'budget', 'receipt'):
                copied[key].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original[key], copied[key])
            child_name = original['budget'].stem + '-' + report.bridge.TAIL_PARTITION + '.jsonl'
            shutil.copy2(original['budget'].parent / child_name, copied['budget'].parent / child_name)
            copied['stage'].mkdir(parents=True, exist_ok=True)
            shutil.copy2(original['stage'] / 'review-receipt.json',
                         copied['stage'] / 'review-receipt.json')
            with patch.object(report, 'TAIL_BASE', relocated):
                report.tail_receipt(manifest)
                receipt = json.loads(copied['receipt'].read_text())
                receipt['bridge_sha256'] = '0' * 64
                copied['receipt'].write_text(json.dumps(receipt) + '\n')
                with self.assertRaisesRegex(ValueError, 'Tail root receipt differs'):
                    report.tail_receipt(manifest)

    def test_p1_fresh3_v2_evidence_tamper_is_rejected(self):
        config = report.CONFIGS['P1']
        manifest, _ = report.bridge._source_bound(config)
        stage = report.full.paths(report.bridge.BASE, config, 'fresh3')['stage']
        with tempfile.TemporaryDirectory() as temp:
            shutil.copy2(stage / 'attempts.jsonl', Path(temp) / 'attempts.jsonl')
            events = report.rows(Path(temp) / 'attempts.jsonl')
            events[2]['raw_response_sha256'] = '0' * 64
            (Path(temp) / 'attempts.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in events))
            with self.assertRaisesRegex(ValueError, 'Raw response differs'):
                report.parse_attempts(manifest, Path(temp), 60,
                    expected_requests=report.frozen.build_plan(report.ROOT)[config]['requests'])

    def test_p0_fresh3_invalid_and_exact_requests_are_verified(self):
        config = report.bridge.p0.CONFIG
        manifest, _ = report.bridge._source_bound(config)
        stage = report.full.paths(report.bridge.BASE, config, 'fresh3')['stage']
        requests = report.bridge.p0.build_plan(report.ROOT)[config]['requests']
        parsed = report.parse_attempts(manifest, stage, 60, invalid_id='DEV-040',
                                       expected_requests=requests)
        self.assertEqual(len(parsed['predictions']), 59)
        self.assertEqual(parsed['statuses']['DEV-040'], 'invalid_native_distribution')
        with self.assertRaisesRegex(ValueError, 'Probabilities do not sum to one'):
            report.parse_attempts(manifest, stage, 60, expected_requests=requests)
        changed = copy.deepcopy(requests)
        changed[0]['payload']['state']['feedback'] += ' drift'
        with self.assertRaisesRegex(ValueError, 'Saved request bytes differ'):
            report.parse_attempts(manifest, stage, 60, invalid_id='DEV-040',
                                  expected_requests=changed)


if __name__ == '__main__':
    unittest.main()
