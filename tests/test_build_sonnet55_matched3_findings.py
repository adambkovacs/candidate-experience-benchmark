"""Offline checks for the Sonnet 5.5 closed-phase public projection."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_sonnet55_matched3_findings as report
import build_claude_repeat_findings as opus

BUNDLE = ROOT / 'public-site/sonnet55-fresh-matched3-evidence'


def public_attempt(effort, pass_name, condition, phase):
    projection = json.loads((BUNDLE / 'report.json').read_text())
    path = ROOT / projection['cells'][effort][pass_name][condition][phase]['evidence']['attempts']['path']
    return json.loads(path.read_text().splitlines()[0])


class Sonnet55ReportTests(unittest.TestCase):
    def test_terminal_service_errors_remain_visible_without_a_score(self):
        origin = ROOT / report.BASE / 'low/pass1/P1'
        required = ('smoke.claim.json', 'smoke.root-review.json', 'smoke.journal.jsonl',
                    'smoke.attempts.jsonl', 'smoke.records.jsonl', 'smoke.batch-000.raw.jsonl')
        if not all((origin / name).is_file() for name in required):
            self.skipTest('Private original smoke fixture is absent; public projection checks run separately')
        report.lane.configure('low')
        plan = report.lane.plan_data('pass1')
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            target = scratch / report.BASE / 'low/pass1/P1'
            target.parent.mkdir(parents=True)
            for missing_raw in (False, True):
                with self.subTest(missing_raw=missing_raw):
                    if target.exists():
                        shutil.rmtree(target)
                    target.mkdir()
                    for suffix in ('claim.json', 'root-review.json', 'journal.jsonl',
                                   'attempts.jsonl', 'records.jsonl', 'batch-000.raw.jsonl'):
                        filename = 'smoke.' + suffix
                        shutil.copy2(origin / filename, target / filename)
                    attempt_path = target / 'smoke.attempts.jsonl'
                    attempt = json.loads(attempt_path.read_text())
                    attempt['status'] = 'service_error'
                    attempt['error_type'] = 'OSError' if missing_raw else 'TimeoutExpired'
                    for key in ('prediction', 'usage', 'model_usage',
                                'cli_estimated_api_equivalent_usd', 'exit_code'):
                        attempt.pop(key, None)
                    raw_path = target / 'smoke.batch-000.raw.jsonl'
                    if missing_raw:
                        raw_path.unlink()
                        attempt.pop('raw_capture_file')
                        attempt.pop('raw_capture_sha256')
                    else:
                        raw = json.loads(raw_path.read_text())
                        raw.update(stdout='{', exit_code=None, timed_out=True)
                        raw_path.write_text(json.dumps(raw) + '\n')
                        attempt['raw_capture_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                    attempt_path.write_text(json.dumps(attempt) + '\n')
                    records_path = target / 'smoke.records.jsonl'
                    records = [json.loads(line) for line in records_path.read_text().splitlines()]
                    for record in records:
                        record.update(status='service_error', prediction=None)
                    records_path.write_text(''.join(json.dumps(row) + '\n' for row in records))
                    journal_path = target / 'smoke.journal.jsonl'
                    events = [json.loads(line) for line in journal_path.read_text().splitlines()]
                    events[-2]['status'] = 'service_error'
                    events[-1] = {'event': 'phase_stopped', 'reason': 'service_error', 'batch_index': 0}
                    journal_path.write_text(''.join(json.dumps(row) + '\n' for row in events))
                    bind, _ = opus._binder(scratch)
                    claim = json.loads((target / 'smoke.claim.json').read_text())
                    entry, rows = report._phase(scratch, 'low', 'pass1', 'P1', 'smoke',
                                                plan, {'sha256': claim['manifest_sha256']}, bind)
                    self.assertEqual(entry['state'], 'stopped')
                    self.assertIsNone(entry['score'])
                    self.assertIsNone(rows)
                    self.assertIsNone(entry['usage']['calculatedApiEquivalentUsd'])
                    self.assertIsNone(entry['usage']['tokensByPriceCategory']['output'])
                    self.assertEqual(len(entry['evidence']['rawCaptures']), 0 if missing_raw else 1)
                    if not missing_raw:
                        attempt.pop('raw_capture_sha256')
                        attempt_path.write_text(json.dumps(attempt) + '\n')
                        with self.assertRaises(ValueError):
                            report._phase(scratch, 'low', 'pass1', 'P1', 'smoke',
                                          plan, {'sha256': claim['manifest_sha256']}, bind)

    def test_exact_price_and_identity_validation(self):
        first = public_attempt('low', 'pass1', 'P0', 'development')
        counts, total = report._price(first)
        self.assertEqual(counts['cache1hWrite'], first['usage']['cache_creation_input_tokens'])
        self.assertEqual(str(total), '0.023556')
        changed = copy.deepcopy(first)
        changed['usage']['cache_creation']['ephemeral_1h_input_tokens'] += 1
        with self.assertRaises(ValueError):
            report._price(changed)
        changed = copy.deepcopy(first)
        changed['model_usage'][report.lane.MODEL]['canonicalModel'] = 'other-model'
        with self.assertRaises(ValueError):
            report._price(changed)

    def test_closed_snapshot_and_clean_checkout_projection(self):
        snapshot = report.check_public(BUNDLE)
        self.assertEqual(snapshot['plannedCells'], snapshot['completedCells'])
        self.assertEqual(snapshot['completedCells'], 36)
        self.assertEqual(sum(
            cell['development']['state'] == 'complete'
            for effort in snapshot['cells'].values()
            for by_condition in effort.values()
            for cell in by_condition.values()), snapshot['completedCells'])
        for effort in snapshot['cells'].values():
            for by_condition in effort.values():
                for cell in by_condition.values():
                    if cell['development']['state'] != 'complete':
                        self.assertIsNone(cell['development']['score'])
        with tempfile.TemporaryDirectory() as clean:
            clean_root = Path(clean)
            destination = clean_root / BUNDLE.relative_to(ROOT)
            destination.parent.mkdir(parents=True)
            shutil.copytree(BUNDLE, destination)
            verified = report.check_public(destination, clean_root)
            self.assertEqual(verified['completedCells'], snapshot['completedCells'])
            self.assertFalse((clean_root / report.BASE).exists())
            self.assertFalse((clean_root / 'data').exists())
            bound = destination / 'report.json'
            bound.write_bytes(bound.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                report.check_public(destination, clean_root)

    def test_missing_usage_is_unknown_not_zero(self):
        usage = report._usage([{'elapsed_seconds': 1.5, 'cli_api_duration_ms': None}])
        self.assertEqual(usage['unpricedRequests'], 1)
        self.assertIsNone(usage['calculatedApiEquivalentUsd'])
        self.assertIsNone(usage['cliListPriceEstimateUsd'])
        self.assertIsNone(usage['tokensByPriceCategory']['output'])


if __name__ == '__main__':
    unittest.main()
