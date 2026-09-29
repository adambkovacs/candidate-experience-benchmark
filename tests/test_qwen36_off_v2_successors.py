"""Offline successor admission tests; never dispatch a hosted request."""
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests'))
import qwen36_off_v2_successors as successor
import qwen36_off_v2_continuation as suffix
from test_additional_hosted_fresh_repeat_findings import write_json, write_rows
from test_qwen36_off_v2_continuation import ContinuationFixture


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ContinuationFixture(self)
        self.output = self.fixture.base / 'later-phases-v1'
        controller = self.fixture.root / 'scripts/qwen36_off_v2_successors.py'
        shutil.copy2(REPO / 'scripts/qwen36_off_v2_successors.py', controller)
        for field, value in (('ROOT', self.fixture.root), ('BASE', self.fixture.base),
                             ('OUTPUT', self.output), ('__file__', str(controller))):
            p = patch.object(successor, field, value)
            p.start(); self.addCleanup(p.stop)

    def close_suffix(self):
        self.fixture.add_suffix(54)
        result = suffix.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        write_json(self.fixture.suffix / 'reconciliation.json', result)

    def freeze(self):
        self.close_suffix()
        path = self.output / 'manifest.json'
        successor.freeze(path)
        return path, successor.sha(path)

    def review(self, manifest, manifest_sha, index, stage):
        path = successor.stage_review_path(index, stage)
        receipt = {'schema': successor.SCHEMA + '-stage-review', 'approved': True,
                   'manifest_sha256': manifest_sha,
                   'controller_sha256': manifest['controller']['sha256'],
                   'original_manifest_sha256': manifest['sources']['original_manifest']['sha256'],
                   'suffix_reconciliation_sha256': manifest['sources']['suffix_reconciliation']['sha256'],
                   'budget_manifest_sha256': manifest['sources']['budget_manifest']['sha256'],
                   'partition_id': manifest['partition_id'], 'phase_index': index,
                   'stage': stage}
        if stage == 'development':
            smoke = successor.stage_paths(index, 'smoke')
            receipt['smoke_inspection'] = {'approved': True, 'statuses': ['ok'] * 3,
                **{'smoke_' + name + '_sha256': successor.sha(smoke[name])
                   for name in ('records', 'journal', 'raw')}}
        write_json(path, receipt)
        return path

    def copy_closed_stage(self, manifest_sha, index, stage):
        source = self.fixture.series.stage(index, stage)
        destination = successor.stage_paths(index, stage)
        for name in ('claim', 'journal', 'raw', 'records'):
            shutil.copy2(source[name], destination[name])
        claim = json.loads(destination['claim'].read_text())
        claim['manifest_sha256'] = manifest_sha
        claim['review_sha256'] = successor.sha(successor.stage_review_path(index, stage))
        write_json(destination['claim'], claim)
        journal = [json.loads(line) for line in destination['journal'].read_text().splitlines()]
        journal[0]['claim_sha256'] = successor.sha(destination['claim'])
        write_rows(destination['journal'], journal)
        return destination

    def test_requires_exact_closed_composite_and_persisted_hashes(self):
        with self.assertRaisesRegex(ValueError, 'closed 59/60'):
            successor.expected_manifest()
        path, digest = self.freeze()
        manifest = successor.validate_manifest(path, digest)
        self.assertEqual(list(range(1, 9)), manifest['successor_phase_indices'])
        self.assertEqual('P1', manifest['phases'][1]['condition'])
        self.assertEqual('P0', manifest['phases'][8]['condition'])
        self.assertEqual(60, len(manifest['requests_by_condition']['P1']))
        with self.assertRaises(FileExistsError):
            successor.freeze(path)
        reconciliation = self.fixture.suffix / 'reconciliation.json'
        reconciliation.write_text(reconciliation.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'closed 59/60|source changed|manifest differs'):
            successor.validate_manifest(path, digest)

    def test_review_predecessor_and_no_duplicate_claim(self):
        path, digest = self.freeze()
        manifest = successor.validate_manifest(path, digest)
        budget = self.fixture.base / 'budget.json'
        r1 = self.review(manifest, digest, 1, 'smoke')
        successor.prepare(path, digest, budget, 1, 'smoke', r1)
        r2 = self.review(manifest, digest, 2, 'smoke')
        with self.assertRaisesRegex(ValueError, 'Previous successor'):
            successor.prepare(path, digest, budget, 2, 'smoke', r2)
        successor.stage_paths(1, 'smoke')['claim'].write_text('{}')
        with patch.object(successor.paid, 'load_key', side_effect=AssertionError('key read')):
            with self.assertRaises(FileExistsError):
                successor.execute(path, digest, budget, 1, 'smoke', r1)

    def test_strict_finished_predecessor_and_smoke_inspection(self):
        path, digest = self.freeze()
        manifest = successor.validate_manifest(path, digest)
        budget = self.fixture.base / 'budget.json'
        self.review(manifest, digest, 1, 'smoke')
        smoke = self.copy_closed_stage(digest, 1, 'smoke')
        self.assertTrue(successor.finished(manifest, digest, 1, 'smoke'))
        development_review = self.review(manifest, digest, 1, 'development')
        successor.prepare(path, digest, budget, 1, 'development', development_review)
        development = self.copy_closed_stage(digest, 1, 'development')
        self.assertTrue(successor.finished(manifest, digest, 1, 'development'))
        next_review = self.review(manifest, digest, 2, 'smoke')
        successor.prepare(path, digest, budget, 2, 'smoke', next_review)
        raw = development['raw']
        raw.write_text(raw.read_text().replace('neutral', 'positive', 1))
        self.assertFalse(successor.finished(manifest, digest, 1, 'development'))
        with self.assertRaisesRegex(ValueError, 'Previous successor'):
            successor.prepare(path, digest, budget, 2, 'smoke', next_review)
        smoke['raw'].write_text(smoke['raw'].read_text().replace('neutral', 'positive', 1))
        with self.assertRaisesRegex(ValueError, 'inspected successor smoke'):
            successor.prepare(path, digest, budget, 1, 'development', development_review)

    def test_all_sixty_requests_and_budget_binding_reject_drift(self):
        path, digest = self.freeze()
        manifest = successor.validate_manifest(path, digest)
        budget = self.fixture.base / 'budget.json'
        review = self.review(manifest, digest, 1, 'smoke')
        successor.prepare(path, digest, budget, 1, 'smoke', review)
        changed = self.fixture.root / 'wrong-budget.json'
        shutil.copy2(budget, changed)
        with self.assertRaisesRegex(ValueError, 'Exact original child'):
            successor.prepare(path, digest, changed, 1, 'smoke', review)
        inputs = successor.admission.INPUTS
        lines = inputs.read_text().splitlines()
        item = json.loads(lines[-1]); item['feedback'] += ' changed'
        lines[-1] = json.dumps(item); inputs.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'Source drift|source changed'):
            successor.validate_manifest(path, digest)

    def test_route_and_cap_stop_before_any_http_call(self):
        path, digest = self.freeze()
        manifest = successor.validate_manifest(path, digest)
        budget = self.fixture.base / 'budget.json'
        review = self.review(manifest, digest, 1, 'smoke')
        with (patch.object(successor.suffix, 'live_controls', side_effect=ValueError('route changed')),
              patch.object(successor.paid, 'load_key', side_effect=AssertionError('key read'))):
            with self.assertRaisesRegex(ValueError, 'route changed'):
                successor.execute(path, digest, budget, 1, 'smoke', review)
        self.assertFalse(any(p.exists() for p in successor.stage_paths(1, 'smoke').values()))

        class CappedLedger:
            closed = False
            def state(self):
                return None, {}, False
            def reserve(self, *_):
                raise ValueError('cap reached')
            def close(self):
                pass

        with patch.object(successor.suffix, 'live_controls', return_value=(
                self.fixture.series.model, self.fixture.series.endpoint)), \
             patch.object(successor.partitions, 'open_partition', return_value=CappedLedger()), \
             patch.object(successor.paid, 'load_key', return_value='dummy'), \
             patch.object(successor.paid, 'fetch', side_effect=AssertionError('HTTP sent')):
            outcome = successor.execute(path, digest, budget, 1, 'smoke', review)
        self.assertEqual({'completed': False, 'status': 'child_cap',
                          'next_unsent_id': 'DEV-001'}, outcome)
        events = [json.loads(line) for line in successor.stage_paths(1, 'smoke')['journal'].read_text().splitlines()]
        self.assertEqual('admission_stopped', events[-1]['event'])
        self.assertFalse(successor.finished(manifest, digest, 1, 'smoke'))


if __name__ == '__main__':
    unittest.main()
