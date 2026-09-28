"""Synthetic closed and interrupted evidence for the offline fresh Codex reporter."""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import build_codex_fresh_repeat_findings as report
import codex_fresh_roster as controller


CONFIG = 'codex-gpt-6-astra-medium'
SERIES = CONFIG + '-fresh-matched3'


class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.private = Path(self.temp.name) / 'private'
        self.private.mkdir(mode=0o700)
        self.base = self.root / report.BASE / SERIES
        self.manifests = {}
        for fresh in report.PASSES:
            path = report.BASE / SERIES / fresh / 'manifest.json'
            manifest = json.loads((REPO / path).read_text())
            self.manifests[fresh] = manifest
            for source in manifest['source_bindings']:
                self.copy(source['path'])
            self.copy(path)
        self.copy(report.LABELS)
        self.copy('scripts/build_codex_fresh_repeat_findings.py')
        self.patcher = patch.object(controller, 'base_dir', return_value=self.base)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def copy(self, relative):
        target = self.root / relative
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)

    @staticmethod
    def backend(command, prompt, env, cwd):
        ids = [r['id'] for r in json.loads(prompt.splitlines()[-1])['records']]
        records = [{'id': rid, 'sentiment': 'neutral', 'follow_up_needed': 'no',
                    'serious_concern_reported': 'no', 'testimonial_potential': 'no'} for rid in ids]
        return {'returncode': 0,
                'stdout': json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 20}}),
                'stderr': '', 'response': json.dumps({'records': records})}

    def receipt(self, fresh, condition, phase):
        manifest = self.manifests[fresh]
        path = self.private / f'{fresh}-{condition}-{phase}.json'
        quota = {'source': 'Codex get_usage_limits', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                 'ordinary_usage_allowed': True, 'spend_control_reached': False,
                 'credits_available': False, 'unlimited_credits': False,
                 'paid_overage_disabled': True, 'weekly_remaining_percent': 70,
                 'five_hour_remaining_percent': 70}
        value = {'schema': controller.REVIEW_SCHEMA, 'approved': True,
                 'configuration_id': CONFIG, 'pass': fresh, 'condition': condition,
                 'phase': phase, 'manifest_sha256': controller.sha(self.base / fresh / 'manifest.json'),
                 'controller_sha256': controller.sha(controller.CONTROLLER),
                 'model': manifest['model'], 'effort': manifest['effort'],
                 'runtime': controller.RUNTIME, 'cli_path': controller.CODEX, 'quota': quota}
        if phase == 'development':
            value['smoke_inspection_sha256'] = controller.sha(self.base / fresh / condition / 'smoke-inspection.json')
        controller.write_new(path, value)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return path, controller.sha(path)

    def phase(self, fresh, condition, phase, backend=None):
        path, receipt_hash = self.receipt(fresh, condition, phase)
        controller.run_phase(self.manifests[fresh], condition, phase,
                             controller.sha(self.base / fresh / 'manifest.json'), path, receipt_hash,
                             backend=backend or self.backend, runtime=lambda _: {})

    def close(self, fresh, condition, backend=None):
        self.phase(fresh, condition, 'smoke', backend)
        controller.inspect(self.manifests[fresh], condition, 'Synthetic test fixture, three raw records inspected')
        self.phase(fresh, condition, 'development', backend)

    def test_pending_does_not_read_mutable_attempts(self):
        before = json.dumps(report.build(self.root, [CONFIG]), sort_keys=True)
        self.phase('fresh1', 'P0', 'smoke')
        (self.base / 'fresh1/P0/development.claim.json').write_text('{}')
        (self.base / 'fresh1/P0/development.attempts.jsonl').write_text('{incomplete')
        (self.base / 'fresh1/P0/development.journal.jsonl').write_text('{incomplete')
        item = report.build(self.root, [CONFIG])['series'][0]
        self.assertEqual(0, item['completedConditions'])
        self.assertEqual('not_completed', item['missingPasses'][0]['status'])
        self.assertEqual({}, item['passes']['fresh1'])
        self.assertEqual(before, json.dumps(report.build(self.root, [CONFIG]), sort_keys=True))

    def test_stopped_phase_is_unscored(self):
        self.phase('fresh1', 'P0', 'smoke')
        controller.inspect(self.manifests['fresh1'], 'P0', 'Synthetic raw three inspected')
        def failed(command, prompt, env, cwd):
            return {'returncode': 1, 'stdout': json.dumps({'type': 'turn.failed'}),
                    'stderr': 'synthetic service failure', 'response': ''}
        with self.assertRaisesRegex(RuntimeError, 'stopped on first non-ok'):
            self.phase('fresh1', 'P0', 'development', failed)
        item = report.build(self.root, [CONFIG])['series'][0]
        self.assertEqual(0, item['completedConditions'])
        self.assertEqual('not_completed', item['missingPasses'][0]['status'])
        self.assertEqual({}, item['passes']['fresh1'])

    def test_one_closed_phase_and_raw_tamper(self):
        self.close('fresh1', 'P0')
        item = report.build(self.root, [CONFIG])['series'][0]
        self.assertEqual(1, item['completedConditions'])
        self.assertEqual(60, item['passes']['fresh1']['P0']['score']['denominator'])
        self.assertEqual(60, item['passes']['fresh1']['P0']['score']['valid'])
        self.assertEqual(6, item['passes']['fresh1']['P0']['usage']['requestCount'])
        self.assertEqual(600, item['passes']['fresh1']['P0']['usage']['tokens']['input_tokens'])
        self.assertIsNone(item['passes']['fresh1']['P0']['usage']['actualCostUsd'])
        self.assertIsNone(item['servedModel'])
        for matrix in item['passes']['fresh1']['P0']['score']['confusionCounts'].values():
            self.assertEqual(60, sum(sum(row.values()) for row in matrix.values()))
        raw = self.base / 'fresh1/P0/development.raw-1.json'
        raw.write_text(raw.read_text().replace('neutral', 'positive', 1))
        with self.assertRaisesRegex(ValueError, 'Raw response sidecar differs'):
            report.build(self.root, [CONFIG])

    def test_three_passes_and_prompt_case_flips(self):
        for fresh in report.PASSES:
            for condition in report.ORDERS[fresh]:
                if fresh == 'fresh1' and condition == 'P1':
                    def changed(command, prompt, env, cwd):
                        value = self.backend(command, prompt, env, cwd)
                        payload = json.loads(value['response'])
                        for row in payload['records']:
                            if row['id'] == 'DEV-001':
                                row['sentiment'] = 'positive'
                        value['response'] = json.dumps(payload)
                        return value
                    self.close(fresh, condition, changed)
                else:
                    self.close(fresh, condition)
        item = report.build(self.root, [CONFIG])['series'][0]
        self.assertEqual(9, item['completedConditions'])
        self.assertEqual([], item['missingPasses'])
        self.assertEqual(6, len(item['withinPassPromptDeltas']))
        self.assertEqual(6, len(item['withinPassPromptFlips']))
        p1 = next(x for x in item['withinPassPromptFlips'] if x['pass'] == 'fresh1' and x['to'] == 'P1')
        self.assertEqual(['DEV-001'], p1['fourFieldVector']['caseIds'])
        self.assertEqual(9, len(item['pairwiseFlips']))
        score_range = item['threePassSummary']['P0']['allFour']['range']
        self.assertEqual(score_range[0], score_range[1])
        self.assertEqual(60, item['changesAcrossThreePasses']['P0']['denominator'])
        self.assertEqual([], item['changesAcrossThreePasses']['P0']['fourFieldVector'])

    def test_manifest_or_reference_tamper(self):
        manifest = self.base / 'fresh1/manifest.json'
        manifest.write_text(manifest.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.root, [CONFIG])
        shutil.copy2(REPO / report.BASE / SERIES / 'fresh1/manifest.json', manifest)
        labels = self.root / report.LABELS
        labels.write_text(labels.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.root, [CONFIG])

    def test_usage_mirror_tamper(self):
        self.close('fresh1', 'P0')
        path = self.base / 'fresh1/P0/development.attempts.jsonl'
        attempts = [json.loads(line) for line in path.read_text().splitlines()]
        attempts[0]['input_tokens'] = 0
        path.write_text(''.join(json.dumps(row) + '\n' for row in attempts))
        with self.assertRaisesRegex(ValueError, 'Raw response, usage or attempt projection differs'):
            report.build(self.root, [CONFIG])


if __name__ == '__main__':
    unittest.main()
