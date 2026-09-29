"""Offline public Qwen continuation report tests, including a private-file-free checkout."""
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests'))
import build_qwen36_off_continuation_findings as report
import qwen36_off_v2_successors as successors
import qwen36_off_v2_continuation as suffix
from export_provider_error_public_evidence import INVENTORY as ACCOUNT_ID_SOURCES
from test_additional_hosted_fresh_repeat_findings import write_json, write_rows
from test_qwen36_off_v2_continuation import ContinuationFixture


class PublicFixture:
    def __init__(self, case):
        self.fixture = ContinuationFixture(case)
        self.root = self.fixture.root
        self.base = self.fixture.base
        self.output = self.base / 'later-phases-v1'
        self.fixture.add_suffix(54)
        projection = suffix.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        write_json(self.fixture.suffix / 'reconciliation.json', projection)
        controller = self.root / 'scripts/qwen36_off_v2_successors.py'
        shutil.copy2(REPO / 'scripts/qwen36_off_v2_successors.py', controller)
        for field, value in (('ROOT', self.root), ('BASE', self.base),
                             ('OUTPUT', self.output), ('__file__', str(controller))):
            item = patch.object(successors, field, value)
            item.start(); case.addCleanup(item.stop)
        self.manifest_path = self.output / 'manifest.json'
        successors.freeze(self.manifest_path)
        self.manifest_sha = successors.sha(self.manifest_path)
        self.manifest = json.loads(self.manifest_path.read_text())
        item = patch.object(report, 'MANIFEST_SHA', self.manifest_sha)
        item.start(); case.addCleanup(item.stop)
        # These bytes are deliberately unavailable to a public report checkout.
        for name in ('raw', 'records'):
            (self.base / f'phase-01-development.{name}.jsonl').unlink()
            (self.fixture.suffix / f'development.{name}.jsonl').unlink()

    def receipt(self, index, stage):
        relative = successors.stage_review_path(index, stage)
        value = {'schema': successors.SCHEMA + '-stage-review', 'approved': True,
                 'manifest_sha256': self.manifest_sha,
                 'controller_sha256': self.manifest['controller']['sha256'],
                 'original_manifest_sha256': self.manifest['sources']['original_manifest']['sha256'],
                 'suffix_reconciliation_sha256': self.manifest['sources']['suffix_reconciliation']['sha256'],
                 'budget_manifest_sha256': self.manifest['sources']['budget_manifest']['sha256'],
                 'partition_id': self.manifest['partition_id'], 'phase_index': index,
                 'stage': stage}
        if stage == 'development':
            smoke = successors.stage_paths(index, 'smoke')
            value['smoke_inspection'] = {'approved': True, 'statuses': ['ok'] * 3,
                **{'smoke_' + name + '_sha256': successors.sha(smoke[name])
                   for name in ('records', 'journal', 'raw')}}
        write_json(relative, value)
        return relative

    def stage(self, index, stage, changed_id=None):
        source = self.fixture.series.stage(index, stage, changed_id=changed_id)
        target = successors.stage_paths(index, stage)
        self.receipt(index, stage)
        for key in ('claim', 'journal', 'raw', 'records'):
            shutil.copy2(source[key], target[key])
        claim = json.loads(target['claim'].read_text())
        claim['manifest_sha256'] = self.manifest_sha
        claim['review_sha256'] = successors.sha(successors.stage_review_path(index, stage))
        write_json(target['claim'], claim)
        journal = [json.loads(line) for line in target['journal'].read_text().splitlines()]
        journal[0]['claim_sha256'] = successors.sha(target['claim'])
        write_rows(target['journal'], journal)
        return target


class PublicContinuationTests(unittest.TestCase):
    def setUp(self):
        self.fx = PublicFixture(self)

    def test_relocated_public_checkout_reports_first_failed_pass_without_private_bytes(self):
        for relative, _, _ in ACCOUNT_ID_SOURCES:
            (self.fx.root / relative).unlink(missing_ok=True)
        result = report.build(self.fx.root)
        series = result['series'][0]
        self.assertEqual(report.SERIES, series['seriesId'])
        self.assertEqual('descriptive-continuation-after-service-error', series['method'])
        self.assertFalse(series['cleanMatchedThreeEligible'])
        self.assertEqual(1, series['completedConditions'])
        first = series['passes']['fresh1']['P0']
        self.assertEqual({'ok': 59, 'service_error': 1}, first['score']['outcomes'])
        self.assertEqual(60, first['score']['denominator'])
        self.assertEqual(59, first['score']['valid'])
        self.assertEqual(['DEV-006'], first['score']['invalidIds'])
        self.assertEqual('0.0299008', first['usage']['unknownChargeUpperBoundUsd'])
        self.assertEqual(8, len(series['missingPasses']))
        self.assertNotIn(self.fx.fixture.secret, json.dumps(result))
        self.assertNotIn('raw_error_response', json.dumps(result))

    def test_closed_later_phase_budget_prefix_and_shared_valid_flip(self):
        self.fx.stage(1, 'smoke')
        self.fx.stage(1, 'development', changed_id='DEV-001')
        before = report.build(self.fx.root)['series'][0]
        self.assertEqual(1, before['completedConditions'])
        self.assertEqual('budget_prefix_absent_or_prior_unreported',
                         before['missingPasses'][0]['status'])
        prefix = report.capture_prefix(self.fx.root, 1)
        self.assertTrue(prefix.exists())
        self.assertNotIn(self.fx.fixture.secret, prefix.read_text())
        self.assertNotIn('evidence_path', prefix.read_text())
        for relative, _, _ in ACCOUNT_ID_SOURCES:
            (self.fx.root / relative).unlink(missing_ok=True)
        series = report.build(self.fx.root)['series'][0]
        self.assertEqual(2, series['completedConditions'])
        self.assertEqual(60, series['passes']['fresh1']['P1']['score']['valid'])
        flip = series['withinPassPromptFlips'][0]
        self.assertEqual(59, flip['denominator'])
        self.assertEqual(['DEV-006'], flip['excludedIds'])
        self.assertEqual(8, len(series['missingPasses']) + 1)
        prefix.write_text(prefix.read_text().replace('0.0001', '0.9', 1))
        with self.assertRaises(FileExistsError):
            report.capture_prefix(self.fx.root, 1)

    def test_tampered_reconciliation_and_manifest_hash_rejected(self):
        projection = self.fx.fixture.suffix / 'reconciliation.json'
        original = projection.read_bytes()
        projection.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.fx.root)
        projection.write_bytes(original)
        self.fx.manifest_path.write_bytes(self.fx.manifest_path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.fx.root)

    def test_invalid_or_missing_closed_stage_is_unscored(self):
        self.fx.stage(1, 'smoke')
        development = self.fx.stage(1, 'development')
        report.capture_prefix(self.fx.root, 1)
        raw = development['raw']
        original = raw.read_text()
        raw.write_text(raw.read_text().replace('neutral', 'positive', 1))
        with self.assertRaisesRegex(ValueError, 'strict runner verification'):
            report.build(self.fx.root)
        raw.write_text(original)
        journal = development['journal']
        journal.write_text('\n'.join(journal.read_text().splitlines()[:-1]) + '\n')
        series = report.build(self.fx.root)['series'][0]
        self.assertEqual(1, series['completedConditions'])

    def test_budget_prefix_tamper_rejected(self):
        self.fx.stage(1, 'smoke')
        self.fx.stage(1, 'development')
        prefix = report.capture_prefix(self.fx.root, 1)
        data = json.loads(prefix.read_text())
        data['events'][-1]['usd'] = '0.9'
        write_json(prefix, data)
        with self.assertRaisesRegex(ValueError, 'budget settlement differs'):
            report.build(self.fx.root)


if __name__ == '__main__':
    unittest.main()
