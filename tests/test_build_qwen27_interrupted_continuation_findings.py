"""Offline public-evidence gates for the two Qwen27 P0 suffixes."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_qwen27_interrupted_continuation_findings as report


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True) + '\n' for v in values))


class PublicContinuationTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name).resolve()
        script = root / 'scripts' / Path(report.__file__).name
        script.parent.mkdir(parents=True)
        shutil.copyfile(report.__file__, script)
        labels_path = root / report.LABELS
        labels_path.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / report.LABELS, labels_path)
        labels = {x['id']: x['proposed_labels'] for x in report.rows(labels_path)}
        for kind in ('medium', 'xhigh'):
            directory = root / report.CONT / kind / 'public-evidence-v1'
            config = 'openrouter-paid-qwen3.8-27b-' + kind
            plan = json.loads((ROOT / report.BASE / config / 'fresh3/manifest.json').read_text())
            planned = plan['conditions']['P0']['development']
            requests = [{'id': x['record_id'], 'request_sha256': x['request_sha256'],
                         'input_sha256': x['input_sha256'],
                         'instruction_sha256': x['instruction_sha256']}
                        for x in planned]
            self.assertEqual(report.schedule_sha(requests), report.REQUEST_SCHEDULE_SHA[kind])
            p1_planned = plan['conditions']['P1']['development']
            p1_requests = [{'id': x['record_id'], 'request_sha256': x['request_sha256'],
                            'input_sha256': x['input_sha256'],
                            'instruction_sha256': x['instruction_sha256']}
                           for x in p1_planned]
            self.assertEqual(report.schedule_sha(p1_requests), report.P1_REQUEST_SCHEDULE_SHA[kind])
            failed, prefix_valid = report.FAILED[kind]
            positions = []
            for index, (request, rid) in enumerate(zip(requests, report.IDS)):
                row = {**request, 'id': rid, 'attempt_id': f'{kind}-{rid}',
                       'reference_labels_read': False,
                       'reserved_cost_usd': '0.047001600', 'elapsed_seconds': 1.0}
                if rid == failed:
                    row.update(status='service_error', error_type='TimeoutError',
                               prediction=None, observed_cost_usd=None,
                               cost_unknown=True, billing_ok=False)
                else:
                    row.update(status='ok', prediction=labels[rid],
                               observed_cost_usd='0.001', cost_unknown=False,
                               billing_ok=True,
                               usage={'cost': '0.001', 'prompt_tokens': 10,
                                      'completion_tokens': 5, 'total_tokens': 15})
                positions.append(row)
            prefix_path = directory / 'prefix.positions.jsonl'
            suffix_path = directory / 'suffix.positions.jsonl'
            write_rows(prefix_path, positions[:prefix_valid + 1])
            write_rows(suffix_path, positions[prefix_valid + 1:])
            p1_path = directory / 'p1.positions.jsonl'
            p1_rows = []
            if kind == 'xhigh':
                for request in p1_requests[:8]:
                    rid = request['id']
                    p1_rows.append({**request, 'id': rid,
                        'attempt_id': f'{kind}-p1-{rid}', 'reference_labels_read': False,
                        'reserved_cost_usd': '0.047001600', 'elapsed_seconds': 1.0,
                        'status': 'ok', 'prediction': labels[rid],
                        'observed_cost_usd': '0.001', 'cost_unknown': False,
                        'billing_ok': True,
                        'usage': {'cost': '0.001', 'prompt_tokens': 10,
                                  'completion_tokens': 5, 'total_tokens': 15}})
                write_rows(p1_path, p1_rows)
            projection_path = directory / 'request-projection.json'
            write_json(projection_path, {'schema': report.EXPORT_SCHEMA + '-request-projection',
                'configuration_id': config,
                'original_plan_sha256': report.PLAN_SHA[kind],
                'continuation_manifest_sha256': report.MANIFEST_SHA[kind],
                'series_id': 'qwen27-v2-interrupted-continuation-v1-' + kind,
                'clean_matched_three_eligible': False,
                'reference_labels_read': False, 'failed_id': failed,
                'reserve_usd': '0.047001600', 'requests': requests,
                'p1_requests': p1_requests})
            files = {'prefix': prefix_path, 'suffix': suffix_path, 'projection': projection_path}
            if p1_rows:
                files['p1'] = p1_path
            private = {name: {key: 'a' * 64 for key in
                       ('claim.json', 'root-review.json', 'journal.jsonl',
                        'attempts.jsonl', 'responses.jsonl')}
                       for name in ('prefix', 'suffix')}
            private['prefix'].update(report.PREFIX_PRIVATE_SHA[kind])
            if p1_rows:
                private['p1'] = {key: 'b' * 64 for key in private['prefix']}
            export_path = directory / 'export-manifest.json'
            write_json(export_path, {'schema': report.EXPORT_SCHEMA,
                'manual_privacy_review_required': True,
                'configuration_id': config,
                'original_plan_sha256': report.PLAN_SHA[kind],
                'continuation_manifest_sha256': report.MANIFEST_SHA[kind],
                'original_failed_id': failed, 'original_prefix_valid': prefix_valid,
                'suffix_terminal': 'phase_completed',
                'suffix_saved': len(positions) - prefix_valid - 1,
                'p1_terminal': 'phase_aborted' if p1_rows else 'not_dispatched',
                'p1_saved': len(p1_rows),
                'unknown_cost_upper_bound_usd': '0.047001600',
                'private_source_sha256': private,
                'public': {name: {'path': str(path.relative_to(root)),
                                  'sha256': report.sha(path)} for name, path in files.items()}})
            write_json(directory / 'privacy-review.json', {
                'schema': report.REVIEW_SCHEMA, 'approved': True,
                'export_manifest_sha256': report.sha(export_path),
                'reviewer': 'fixture reviewer'})
        return temp, root

    def test_public_projection_scores_only_all_sixty_accounted_positions(self):
        temp, root = self.fixture()
        with temp:
            value = report.build(root)
            self.assertFalse(value['cleanMatchedThreeEligible'])
            self.assertEqual(len(value['sourceBindings']), 13)
            for kind in ('medium', 'xhigh'):
                row = value['series'][kind]
                self.assertEqual(row['score']['valid'], 59)
                self.assertEqual(row['score']['allFour'], 59)
                self.assertEqual(row['score']['serviceErrors'], 1)
                self.assertEqual(row['score']['neverSent'], 0)
                self.assertIsNone(row['laterP1']['score'])
                self.assertEqual(row['knownObservedDevelopmentCostUsd'], '0.059')
            self.assertEqual(value['series']['xhigh']['laterP1']['saved'], 8)
            self.assertEqual(value['series']['xhigh']['laterP1']['neverSent'], 52)
            self.assertIsNone(value['series']['xhigh']['laterP1']['score'])
            rendered = json.dumps(value)
            for secret in ('raw_response', 'user_id', 'child_cap_usd',
                           'private_source_sha256', 'error_body', 'budget.jsonl'):
                self.assertNotIn(secret, rendered)
            for item in value['sourceBindings']:
                self.assertEqual(report.sha(root / item['path']), item['sha256'])

    def test_missing_or_tampered_suffix_never_yields_a_score(self):
        temp, root = self.fixture()
        with temp:
            file = root / report.CONT / 'medium/public-evidence-v1/suffix.positions.jsonl'
            file.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                report.build(root)
            write_rows(file, [{'id': 'DEV-023'}])
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.build(root)

    def test_aborted_suffix_retains_partial_inventory_without_score(self):
        temp, root = self.fixture()
        with temp:
            directory = root / report.CONT / 'medium/public-evidence-v1'
            suffix_path = directory / 'suffix.positions.jsonl'
            saved = report.rows(suffix_path)[:16]
            write_rows(suffix_path, saved)
            export_path = directory / 'export-manifest.json'
            export = json.loads(export_path.read_text())
            export['suffix_terminal'] = 'phase_aborted'
            export['suffix_saved'] = 16
            export['public']['suffix']['sha256'] = report.sha(suffix_path)
            write_json(export_path, export)
            write_json(directory / 'privacy-review.json', {
                'schema': report.REVIEW_SCHEMA, 'approved': True,
                'export_manifest_sha256': report.sha(export_path),
                'reviewer': 'fixture reviewer'})
            value = report.build(root)
            medium = value['series']['medium']
            self.assertEqual(medium['status'], 'aborted_suffix_unscored')
            self.assertIsNone(medium['score'])
            self.assertEqual(medium['validSaved'], 37)
            self.assertEqual(medium['suffixSaved'], 16)
            self.assertEqual(medium['neverSentAfterContinuation'], report.IDS[38:])
            self.assertEqual(value['series']['xhigh']['score']['valid'], 59)

    def test_privacy_review_and_original_prefix_hash_are_required(self):
        temp, root = self.fixture()
        with temp:
            directory = root / report.CONT / 'xhigh/public-evidence-v1'
            review = directory / 'privacy-review.json'
            review.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                report.build(root)
            export_path = directory / 'export-manifest.json'
            export = json.loads(export_path.read_text())
            export['private_source_sha256']['prefix']['attempts.jsonl'] = '0' * 64
            write_json(export_path, export)
            write_json(review, {'schema': report.REVIEW_SCHEMA, 'approved': True,
                'export_manifest_sha256': report.sha(export_path),
                'reviewer': 'fixture reviewer'})
            with self.assertRaisesRegex(ValueError, 'attestation differs'):
                report.build(root)

    def test_public_sanitizer_drops_raw_and_account_fields(self):
        private = {'id': 'DEV-001', 'request': {'secret': 'not public'},
                   'raw_response': {'user_id': 'not public'},
                   'error_body': 'not public',
                   'usage': {'cost': 0.001, 'prompt_tokens': 10,
                             'completion_tokens': 5, 'total_tokens': 15,
                             'cost_details': {'upstream_inference_cost': 0.2},
                             'user_id': 'not public',
                             'completion_tokens_details': {'reasoning_tokens': 9}}}
        public = report.public_position(private)
        self.assertEqual(set(public), {'id', 'usage'})
        self.assertEqual(public['usage'], {'cost': 0.001, 'prompt_tokens': 10,
            'completion_tokens': 5, 'total_tokens': 15,
            'provider_reported_reasoning_tokens': 9})

    def test_private_usage_key_rejected_even_if_export_and_review_rehashed(self):
        temp, root = self.fixture()
        with temp:
            directory = root / report.CONT / 'medium/public-evidence-v1'
            file = directory / 'suffix.positions.jsonl'
            saved = report.rows(file)
            saved[0]['usage']['user_id'] = 'private'
            write_rows(file, saved)
            export_path = directory / 'export-manifest.json'
            export = json.loads(export_path.read_text())
            export['public']['suffix']['sha256'] = report.sha(file)
            write_json(export_path, export)
            write_json(directory / 'privacy-review.json', {
                'schema': report.REVIEW_SCHEMA, 'approved': True,
                'export_manifest_sha256': report.sha(export_path),
                'reviewer': 'fixture reviewer'})
            with self.assertRaisesRegex(ValueError, 'Private or unexpected usage'):
                report.build(root)

    def test_aborted_p1_cannot_disappear_or_claim_a_score(self):
        temp, root = self.fixture()
        with temp:
            directory = root / report.CONT / 'xhigh/public-evidence-v1'
            p1 = directory / 'p1.positions.jsonl'
            p1.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                report.build(root)
            write_rows(p1, [{'id': 'DEV-001'}])
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.build(root)

    def test_rehashed_public_schedule_drift_still_rejected(self):
        temp, root = self.fixture()
        with temp:
            directory = root / report.CONT / 'medium/public-evidence-v1'
            projection_path = directory / 'request-projection.json'
            projection = json.loads(projection_path.read_text())
            projection['requests'][0]['request_sha256'] = '0' * 64
            write_json(projection_path, projection)
            export_path = directory / 'export-manifest.json'
            export = json.loads(export_path.read_text())
            export['public']['projection']['sha256'] = report.sha(projection_path)
            write_json(export_path, export)
            write_json(directory / 'privacy-review.json', {
                'schema': report.REVIEW_SCHEMA, 'approved': True,
                'export_manifest_sha256': report.sha(export_path),
                'reviewer': 'fixture reviewer'})
            with self.assertRaisesRegex(ValueError, 'request projection differs'):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
