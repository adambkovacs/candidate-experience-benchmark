"""Offline evidence and public-output boundaries for Gemma26 second continuation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemma26_continuation_findings as first
import build_gemma26_second_continuation_findings as report


class SecondContinuationFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = first.build(ROOT)

    def clean_inputs(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        relative = {item['path'] for item in self.prior['sourceBindings']}
        relative.add('scripts/build_gemma26_second_continuation_findings.py')
        relative.add(str(report.SECOND / 'manifest.json'))
        manifest = json.loads((ROOT / report.SECOND / 'manifest.json').read_text())
        relative.update(item['path'] for item in manifest['source_bindings'].values())
        for name in relative:
            source, destination = ROOT / name, root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        return temp, root

    def test_clean_inputs_show_incomplete_without_public_final(self):
        temp, root = self.clean_inputs()
        with temp:
            result = report.build(root)
            self.assertEqual(result['originalInterruption']['failedId'], 'DEV-007')
            self.assertEqual(result['secondInterruption']['failedId'], 'DEV-002')
            self.assertEqual(result['secondInterruption']['unknownCostUpperBoundUsd'],
                             '0.01974272')
            self.assertFalse(result['publicCompositeP0Available'])
            self.assertIsNone(result['compositeP0'])
            self.assertEqual(result['stageStatus'][0]['status'], 'not_started_in_cutoff')
            self.assertIs(result['cleanMatchedThreeEligible'], False)
            rendered = json.dumps(result)
            for private in ('error_body', 'error_headers', 'user_id', 'quota',
                            'OPENROUTER_API_KEY'):
                self.assertNotIn(private, rendered)

    def test_manifest_or_bound_source_tamper_rejected(self):
        temp, root = self.clean_inputs()
        with temp:
            manifest = root / report.SECOND / 'manifest.json'
            data = json.loads(manifest.read_text())
            data['first_suffix_failed_id'] = 'DEV-003'
            manifest.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'identity or schedule'):
                report.build(root)
        temp, root = self.clean_inputs()
        with temp:
            controller = root / 'scripts/gemma26_v2_second_continuation.py'
            controller.write_bytes(controller.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.build(root)

    def test_closed_journal_without_public_attestation_stays_unscored(self):
        temp, root = self.clean_inputs()
        with temp:
            journal = root / report.SECOND / 'fresh2/P0/suffix.journal.jsonl'
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text('{"event":"phase_completed","request_count":58}\n')
            result = report.build(root)
            self.assertEqual(result['stageStatus'][0]['status'],
                             'awaiting_public_review')
            self.assertFalse(result['publicCompositeP0Available'])
            self.assertIsNone(result['compositeP0'])
            summary = journal.parent / 'suffix.public-summary.json'
            summary.write_text('{}\n')
            result = report.build(root)
            self.assertEqual(result['stageStatus'][0]['status'],
                             'awaiting_public_review')
            self.assertFalse(result['publicCompositeP0Available'])

    def test_public_projection_excludes_provider_and_account_details(self):
        source = ROOT / report.FIRST / 'fresh2/P0/development.attempts.jsonl'
        record = first.rows(source)[0]
        self.assertEqual(record['status'], 'ok')
        record['user_id'] = 'private-test-account'
        record['error_body'] = 'private-test-error'
        record['quota'] = {'remaining': 0}
        projected = report.public_row(record)
        self.assertEqual(set(projected), report.PUBLIC_KEYS)
        rendered = json.dumps(projected)
        self.assertNotIn('private-test-account', rendered)
        self.assertNotIn('private-test-error', rendered)
        self.assertNotIn('quota', rendered)
        self.assertIn('requestSha256', projected)
        record['observed_cost_usd'] = None
        with self.assertRaisesRegex(ValueError, 'cost'):
            report.public_row(record)

    def test_composite_requires_exact_58_unsent_positions(self):
        original = first.rows(ROOT / report.FIRST /
                              'fresh2/P0/development.attempts.jsonl')
        labels = {r['id']: r['proposed_labels'] for r in
                  first.rows(ROOT / first.LABELS)}
        prediction = original[0]['prediction']
        suffix = [{'id': rid, 'status': 'ok', 'prediction': prediction}
                  for rid in report.IDS[2:]]
        result = report.composite_p0(original, suffix, labels, '0.01974272')
        self.assertEqual(result['score']['denominator'], 60)
        self.assertEqual(result['score']['saved'], 60)
        self.assertEqual(result['score']['valid'], 59)
        self.assertEqual(result['score']['outcomes']['service_error'], 1)
        self.assertEqual(result['score']['outcomes']['never_sent'], 0)
        self.assertFalse(result['cleanMatchedThreeEligible'])
        with self.assertRaisesRegex(ValueError, '60-position'):
            report.composite_p0(original, suffix[:-1], labels, '0.01974272')
        with self.assertRaisesRegex(ValueError, '60-position'):
            report.composite_p0(original, suffix[1:] + suffix[:1], labels, '0.01974272')

    def test_export_requires_controller_verified_closed_stage(self):
        with patch.object(report.controller, 'verify_manifest', return_value={}), \
             patch.object(report.controller, 'verify_stage_closure',
                          side_effect=ValueError('stage evidence missing')):
            with self.assertRaisesRegex(ValueError, 'stage evidence missing'):
                report.export_closed_stage(report.controller.study.CONFIG,
                                           'fresh2', 'P0', 'suffix', '0' * 64)

    def test_public_attestation_rejects_changed_private_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {}
            for kind in ('claim', 'review', 'journal', 'attempts',
                         'responses', 'wire'):
                path = root / (kind + '.json')
                path.write_text('{}\n')
                files[kind] = path
            summary = root / 'summary.json'
            summary.write_text(json.dumps({
                'schema': report.SCHEMA + '-public-stage-v1',
                'stage': 'fresh2/P0/suffix', 'manifestSha256': '0' * 64,
                'manualPrivacyReviewRequired': True,
                'privateSourceSha256': {kind: '0' * 64 for kind in files},
                'responses': []}) + '\n')
            files['summary'] = summary
            review = root / 'public-review.json'
            review.write_text('{}\n')
            files['public_review'] = review
            spec = {'fresh_pass': 'fresh2', 'condition': 'P0',
                    'stage': 'suffix'}
            with patch.object(report, 'files_for', return_value=files):
                with self.assertRaisesRegex(ValueError, 'attestation differs'):
                    report.verify_public_stage(root, {}, '0' * 64, spec, [])

    def closed_public_archive(self):
        temp, root = self.clean_inputs()
        manifest_sha = first.digest(ROOT / report.SECOND / 'manifest.json')
        stage = report.SECOND / 'fresh2/P0'
        names = {'claim': 'suffix.claim.json',
                 'review': 'suffix.root-review.json',
                 'journal': 'suffix.journal.jsonl',
                 'attempts': 'suffix.attempts.jsonl',
                 'responses': 'suffix.responses.jsonl',
                 'wire': 'suffix.wire.jsonl'}
        for key in ('claim', 'review', 'journal'):
            target = root / stage / names[key]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / stage / names[key], target)
        source_sha = {key: first.digest(ROOT / stage / value)
                     for key, value in names.items()}
        projected = [report.public_row(row) for row in
                     first.rows(ROOT / stage / names['attempts'])]
        summary_path = root / stage / 'suffix.public-summary.json'
        summary = {'schema': report.SCHEMA + '-public-stage-v1',
                   'stage': 'fresh2/P0/suffix', 'manifestSha256': manifest_sha,
                   'manualPrivacyReviewRequired': True,
                   'privateSourceSha256': source_sha, 'responses': projected}
        summary_path.write_text(json.dumps(summary) + '\n')
        public_review = {'schema': report.SCHEMA + '-public-review-v1',
                         'approved': True, 'summarySha256': first.digest(summary_path),
                         'stage': 'fresh2/P0/suffix'}
        (root / stage / 'suffix.public-review.json').write_text(json.dumps(public_review) + '\n')
        self.assertFalse((root / stage / names['attempts']).exists())
        self.assertFalse((root / stage / names['responses']).exists())
        self.assertFalse((root / stage / names['wire']).exists())
        return temp, root, summary_path

    def test_closed_public_archive_rebuilds_without_new_private_stage_bytes(self):
        temp, root, _ = self.closed_public_archive()
        with temp:
            result = report.build(root)
            self.assertTrue(result['publicCompositeP0Available'])
            self.assertEqual(result['completedConditions'], self.prior['completedConditions'] + 1)
            score = result['compositeP0']['score']
            self.assertEqual((score['denominator'], score['saved'], score['valid']),
                             (60, 60, 59))
            self.assertEqual(score['outcomes']['service_error'], 1)
            self.assertEqual(score['outcomes']['never_sent'], 0)
            self.assertEqual(result['originalInterruption']['failedId'], 'DEV-007')
            self.assertEqual(result['secondInterruption']['failedId'], 'DEV-002')
            new_private = str(report.SECOND / 'fresh2/P0/suffix.attempts.jsonl')
            self.assertNotIn(new_private, [b['path'] for b in result['sourceBindings']])

    def test_closed_public_archive_rejects_changed_projection_even_if_reapproved(self):
        temp, root, summary_path = self.closed_public_archive()
        with temp:
            summary = json.loads(summary_path.read_text())
            summary['responses'][0]['requestSha256'] = '0' * 64
            summary_path.write_text(json.dumps(summary) + '\n')
            review_path = summary_path.with_name('suffix.public-review.json')
            review = json.loads(review_path.read_text())
            review['summarySha256'] = first.digest(summary_path)
            review_path.write_text(json.dumps(review) + '\n')
            with self.assertRaisesRegex(ValueError, 'frozen request'):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
