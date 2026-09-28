"""Offline checks for hash-bound small-local closed-phase reporting."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_small_local_repeat_findings as report


class SmallLocalReportTests(unittest.TestCase):
    config = 'gemma4-e2b-sdk-thinking-off'

    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        manifest = json.loads((ROOT / report.MANIFEST).read_text())
        config = manifest['configurations'][self.config]
        files = {report.MANIFEST, report.LABELS,
                 Path('scripts/small_local_repeat_admission.cjs')}
        files.update(Path(name) for name in manifest['source_sha256'])
        files.update(Path(config[name]['file']) for name in ('paired_report', 'historical_manifest'))
        files.update(Path(c['source']['file']) for c in config['conditions'].values())
        phase = report.BASE / self.config / 'fresh1/P0'
        files.update(phase / name for name in (
            'smoke.root-review.json', 'smoke.claim.json', 'smoke.raw.jsonl',
            'smoke.records.jsonl', 'smoke.journal.jsonl', 'smoke.completion.json',
            'smoke-inspection.json', 'development.root-review.json',
            'development.claim.json', 'development.raw.jsonl',
            'development.records.jsonl', 'development.journal.jsonl',
            'development.completion.json'))
        review = json.loads((ROOT / phase / 'development.root-review.json').read_text())
        files.add(Path(review['route_catalog_file']))
        for relative in files:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def build_one(self, root):
        return report.build(root, (self.config,))['series'][0]

    def test_real_closed_phase_reports_reference_and_observed_usage(self):
        root = self.fixture()
        result = self.build_one(root)
        self.assertEqual(result['completedConditions'], 1)
        self.assertEqual(result['historicalStatus'],
                         'observational_not_part_of_fresh_matched_three')
        p0 = result['passes']['fresh1']['P0']
        self.assertEqual(p0['score']['denominator'], 60)
        self.assertEqual(p0['score']['valid'], 60)
        self.assertEqual(p0['score']['allFour'], 35)
        self.assertEqual(p0['usage']['tokens']['input_tokens'], 97768)
        self.assertEqual(p0['usage']['tokens']['output_tokens'], 2098)
        self.assertEqual(p0['usage']['timeBasis'], 'client_observed_wall_clock')
        self.assertIsNone(p0['usage']['actualCostUsd'])
        self.assertIsNone(p0['usage']['modelLoadSeconds'])
        self.assertIsNone(p0['usage']['loadedEngineVersion'])
        self.assertEqual(len(result['missingPasses']), 8)
        self.assertEqual(result['pairwiseFlips'], [])
        self.assertIsNone(result['threePassSummary']['P0']['allFour']['range'])
        names = {b['path'] for b in result['sourceBindings']}
        review = json.loads((root / report.BASE / self.config /
                             'fresh1/P0/development.root-review.json').read_text())
        self.assertIn(review['route_catalog_file'], names)
        for suffix in ('raw.jsonl', 'records.jsonl', 'journal.jsonl', 'completion.json'):
            self.assertIn(str(report.BASE / self.config / 'fresh1/P0' /
                              f'development.{suffix}'), names)

    def test_unclaimed_mutable_evidence_is_rejected(self):
        root = self.fixture()
        phase = root / report.BASE / self.config / 'fresh2/P0'
        phase.mkdir(parents=True)
        (phase / 'development.raw.jsonl').write_bytes(b'{interrupted')
        with self.assertRaisesRegex(ValueError, 'Unclaimed stage has mutable evidence'):
            self.build_one(root)

    def claimed_fixture(self, root, *, journal=b'', raw=b'', records=b''):
        original = root / report.BASE / self.config / 'fresh1/P0'
        phase = root / report.BASE / self.config / 'fresh2/P0'
        phase.mkdir(parents=True)
        new_phase = f'{self.config}/fresh2/P0'
        review_path = phase / 'development.root-review.json'
        review = json.loads((original / 'development.root-review.json').read_text())
        review['phase'] = new_phase
        review_path.write_text(json.dumps(review) + '\n')
        claim_path = phase / 'development.claim.json'
        claim = json.loads((original / 'development.claim.json').read_text())
        claim['phase'] = new_phase
        claim['receipt_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        claim_path.write_text(json.dumps(claim) + '\n')
        for kind, content in [('journal', journal), ('raw', raw), ('records', records)]:
            (phase / f'development.{kind}.jsonl').write_bytes(content)
        return phase

    def test_claimed_intent_without_raw_is_visible_and_unscored(self):
        root = self.fixture()
        self.claimed_fixture(root)
        result = self.build_one(root)
        pending = result['partialPasses'][0]
        self.assertEqual(pending['status'], 'claimed_in_progress_or_interrupted')
        self.assertEqual(pending['snapshotStatus'], 'stable_unsealed')
        self.assertEqual(pending['startedIds'], [])
        self.assertEqual(pending['unknownStartedIds'], [])
        self.assertEqual(result['passes']['fresh2'], {})

    def test_saved_raw_without_decision_remains_unknown_started(self):
        root = self.fixture()
        original = root / report.BASE / self.config / 'fresh1/P0'
        journal = (original / 'development.journal.jsonl').read_bytes().splitlines()[0] + b'\n'
        raw = (original / 'development.raw.jsonl').read_bytes().splitlines()[0] + b'\n'
        self.claimed_fixture(root, journal=journal, raw=raw)
        result = self.build_one(root)
        pending = result['partialPasses'][0]
        self.assertEqual(pending['startedIds'], ['DEV-001'])
        self.assertEqual(pending['rawSavedIds'], ['DEV-001'])
        self.assertEqual(pending['savedIds'], [])
        self.assertEqual(pending['unknownStartedIds'], ['DEV-001'])
        self.assertEqual(len(pending['snapshotBindings']), 3)
        self.assertEqual(result['passes']['fresh2'], {})

    def test_active_claimed_snapshot_with_decision_is_still_unscored(self):
        root = self.fixture()
        original = root / report.BASE / self.config / 'fresh1/P0'
        journal = b'\n'.join((original / 'development.journal.jsonl').read_bytes().splitlines()[:2]) + b'\n'
        raw = (original / 'development.raw.jsonl').read_bytes().splitlines()[0] + b'\n'
        records = (original / 'development.records.jsonl').read_bytes().splitlines()[0] + b'\n'
        self.claimed_fixture(root, journal=journal, raw=raw, records=records)
        result = self.build_one(root)
        pending = result['partialPasses'][0]
        self.assertEqual(pending['savedIds'], ['DEV-001'])
        self.assertEqual(pending['unknownStartedIds'], [])
        self.assertEqual(result['passes']['fresh2'], {})

    def test_incomplete_active_bytes_are_not_projected(self):
        root = self.fixture()
        self.claimed_fixture(root, journal=b'{partial')
        pending = self.build_one(root)['partialPasses'][0]
        self.assertEqual(pending['snapshotStatus'], 'unstable_partial_bytes')
        self.assertIsNone(pending['startedIds'])
        self.assertEqual(pending['snapshotBindings'], [])

    def test_cross_file_live_append_is_unstable_not_false_corruption(self):
        root = self.fixture()
        original = root / report.BASE / self.config / 'fresh1/P0'
        first_started = (original / 'development.journal.jsonl').read_bytes().splitlines()[0]
        first_raw = (original / 'development.raw.jsonl').read_bytes().splitlines()[0]
        phase = self.claimed_fixture(root, journal=first_started + b'\n',
                                     raw=first_raw + b'\n')
        second_started = (original / 'development.journal.jsonl').read_bytes().splitlines()[2]
        second_raw = (original / 'development.raw.jsonl').read_bytes().splitlines()[1]
        actual_read = report._snapshot_bytes
        injected = False

        def racing_read(local_root, relative):
            nonlocal injected
            if not injected and str(relative).endswith('development.raw.jsonl'):
                injected = True
                with (phase / 'development.journal.jsonl').open('ab') as output:
                    output.write(second_started + b'\n')
                with (phase / 'development.raw.jsonl').open('ab') as output:
                    output.write(second_raw + b'\n')
            return actual_read(local_root, relative)

        with mock.patch.object(report, '_snapshot_bytes', side_effect=racing_read):
            pending = self.build_one(root)['partialPasses'][0]
        self.assertTrue(injected)
        self.assertEqual(pending['snapshotStatus'], 'unstable_partial_bytes')
        self.assertIsNone(pending['startedIds'])
        self.assertEqual(pending['snapshotBindings'], [])

    def test_terminal_hash_and_raw_decision_tampering_are_rejected(self):
        root = self.fixture()
        folder = root / report.BASE / self.config / 'fresh1/P0'
        target = folder / 'development.records.jsonl'
        data = target.read_text().replace('"sentiment":"positive"', '"sentiment":"negative"', 1)
        target.write_text(data)
        with self.assertRaisesRegex(ValueError, 'Closed phase evidence differs'):
            self.build_one(root)
        terminal = folder / 'development.completion.json'
        saved = json.loads(terminal.read_text())
        saved['records_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        terminal.write_text(json.dumps(saved) + '\n')
        with self.assertRaisesRegex(ValueError, 'Parsed decision differs from raw'):
            self.build_one(root)

    def test_claim_or_request_source_mismatch_rejected(self):
        root = self.fixture()
        claim = root / report.BASE / self.config / 'fresh1/P0/development.claim.json'
        obj = json.loads(claim.read_text())
        obj['plan_sha256'] = '0' * 64
        claim.write_text(json.dumps(obj) + '\n')
        with self.assertRaisesRegex(ValueError, 'Closed phase evidence differs'):
            self.build_one(root)
        root = self.fixture()
        source = root / 'results/gemma4-e2b-2026-09-21/nonthinking-development.jsonl'
        with source.open('ab') as stream:
            stream.write(b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            self.build_one(root)

    def test_route_audit_hash_binding_rejects_changed_catalog(self):
        root = self.fixture()
        review = json.loads((root / report.BASE / self.config /
                             'fresh1/P0/development.root-review.json').read_text())
        catalog = root / review['route_catalog_file']
        catalog.write_bytes(catalog.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            self.build_one(root)

    def test_stopped_phase_preserves_hashes_and_is_not_scored(self):
        root = self.fixture()
        terminal = root / report.BASE / self.config / 'fresh1/P0/development.completion.json'
        saved = json.loads(terminal.read_text())
        saved['status'] = 'stopped'
        saved['reason'] = 'simulated local failure after response capture'
        terminal.write_text(json.dumps(saved) + '\n')
        result = self.build_one(root)
        self.assertEqual(result['completedConditions'], 0)
        self.assertEqual(result['passes']['fresh1'], {})
        self.assertEqual(len(result['partialPasses']), 1)
        self.assertEqual(result['partialPasses'][0]['status'], 'stopped')
        self.assertEqual(result['partialPasses'][0]['saved'], 60)
        self.assertEqual(result['partialPasses'][0]['startedIds'],
                         [f'DEV-{i:03d}' for i in range(1, 61)])
        self.assertEqual(result['partialPasses'][0]['savedIds'],
                         [f'DEV-{i:03d}' for i in range(1, 61)])
        self.assertEqual(result['partialPasses'][0]['unknownStartedIds'], [])
        self.assertEqual(result['partialPasses'][0]['failedIds'], [])
        self.assertIsNone(result['threePassSummary']['P0']['allFour']['range'])

    def test_stopped_after_started_without_decision_keeps_unknown_id(self):
        root = self.fixture()
        folder = root / report.BASE / self.config / 'fresh1/P0'
        first_started = json.loads((folder / 'development.journal.jsonl').read_text().splitlines()[0])
        stopped = {'event': 'stopped_unknown', 'attempt_id': first_started['attempt_id'],
                   'id': first_started['id'], 'at': first_started['at']}
        journal = folder / 'development.journal.jsonl'
        journal.write_text(json.dumps(first_started) + '\n' + json.dumps(stopped) + '\n')
        raw = folder / 'development.raw.jsonl'
        raw.write_bytes(raw.read_bytes().splitlines()[0] + b'\n')
        records = folder / 'development.records.jsonl'
        records.write_bytes(b'')
        terminal_path = folder / 'development.completion.json'
        terminal = json.loads(terminal_path.read_text())
        terminal.update(status='stopped', reason='simulated interrupted response',
                        attempted=1, saved=0, invalid=0,
                        raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                        records_sha256=hashlib.sha256(records.read_bytes()).hexdigest(),
                        journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest())
        terminal_path.write_text(json.dumps(terminal) + '\n')
        result = self.build_one(root)
        stopped_entry = result['partialPasses'][0]
        self.assertEqual(stopped_entry['startedIds'], ['DEV-001'])
        self.assertEqual(stopped_entry['rawSavedIds'], ['DEV-001'])
        self.assertEqual(stopped_entry['savedIds'], [])
        self.assertEqual(stopped_entry['unknownStartedIds'], ['DEV-001'])
        self.assertEqual(stopped_entry['failedIds'], ['DEV-001'])
        self.assertEqual(result['completedConditions'], 0)

    def test_three_fresh_p0_passes_enable_flips_only_after_all_closed(self):
        root = self.fixture()
        base = root / report.BASE / self.config
        source = base / 'fresh1/P0'
        old_phase = f'{self.config}/fresh1/P0'
        for name in ('fresh2', 'fresh3'):
            dest = base / name / 'P0'
            shutil.copytree(source, dest)
            new_phase = f'{self.config}/{name}/P0'
            for stage in ('smoke', 'development'):
                review_path = dest / f'{stage}.root-review.json'
                review = json.loads(review_path.read_text())
                review['phase'] = new_phase
                review_path.write_text(json.dumps(review) + '\n')
                claim_path = dest / f'{stage}.claim.json'
                claim = json.loads(claim_path.read_text())
                claim['phase'] = new_phase
                claim['receipt_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
                claim_path.write_text(json.dumps(claim) + '\n')
                terminal_path = dest / f'{stage}.completion.json'
                terminal = json.loads(terminal_path.read_text())
                terminal['phase'] = new_phase
                terminal_path.write_text(json.dumps(terminal) + '\n')
        result = self.build_one(root)
        self.assertEqual(result['threePassSummary']['P0']['allFour']['range'], [35, 35])
        self.assertEqual(len(result['pairwiseFlips']), 3)
        self.assertEqual(result['changesAcrossThreePasses']['P0']['denominator'], 60)
        self.assertEqual(result['changesAcrossThreePasses']['P0']['fourFieldVector'], [])


if __name__ == '__main__':
    unittest.main()
