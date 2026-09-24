import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from reconcile_local_prompt_conditions import Condition, IDS, V3_MANIFEST, reconcile_saved_condition


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in rows))


class LocalPromptReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = 'synthetic-local-sdk'
        self.prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                           'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        self.refs = [{'id': rid, 'proposed_labels': self.prediction} for rid in IDS]
        self.runtime = {'cli_commit': 'abc', 'selected_engine': 'engine',
                        'lm_studio_version': '0.4', 'hardware': {'model_identifier': 'test'},
                        'artifact_sha256': 'artifact', 'surface': 'lmstudio_sdk',
                        'loaded_model_line': 'synthetic-id   8192   1'}
        self.parent = {'sdk_rendered_file': 'results/rendered.jsonl',
                       'runtime': {'cli_commit': 'abc', 'selected_engine': 'engine',
                       'lm_studio_version': '0.4'}, 'hardware': {'model_identifier': 'test'},
                       'configs': {self.config: {'identifier': 'synthetic-id', 'artifact_path': 'model.gguf',
                       'artifact_sha256': 'artifact', 'artifact_bytes': 100, 'timeout_ms': 600000,
                       'counts_file': 'results/counts.jsonl', 'baseline_file': 'results/baseline.jsonl',
                       'baseline_manifest_file': 'results/baseline-manifest.json'}}}
        self.condition = Condition(self.config, 'P1', Path('results/run'),
                                   Path('results/manifest.json'), Path('scripts/controller.cjs'),
                                   'manifest-hash', 'controller-hash', self.parent)
        review_path = self.root / self.condition.directory / 'execution-review-root.json'
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps({'approved_for_execution': True,
                                'manifest_sha256': 'manifest-hash',
                                'controller_sha256': 'controller-hash',
                                'approved_phases': ['smoke', 'development']}) + '\n')
        self.frozen = []
        for i, rid in enumerate(IDS):
            request = {'messages': [{'role': 'system', 'content': 'policy'},
                         {'role': 'user', 'content': json.dumps({'feedback': rid})}],
                       'config': {'temperature': 0}}
            self.frozen.append({'id': rid, 'request': request, 'request_sha256': f'request-{i}',
                                'rendered_sha256': f'render-{i}', 'expected_prompt_tokens': 10,
                                'prediction_config': {'fields': []}, 'load_config': {'fields': []}})
        for name in ('results/manifest.json', 'scripts/controller.cjs',
                     'results/local-prompt-exact-v1/manifest.json',
                     'scripts/local_prompt_execution_v1.cjs',
                     'data/pilot/inputs.jsonl', 'results/rendered.jsonl',
                     'results/counts.jsonl', 'results/baseline.jsonl',
                     'results/baseline-manifest.json',
                     'prompts/variants-v1/P1-classifier.txt',
                     'prompts/variants-v1/P2-classifier-sop.txt',
                     'scripts/frozen_prompt_variants.cjs',
                     'data/pilot/proposed_labels.jsonl', 'data/pilot/pairs.json',
                     'scripts/development_benchmark.py',
                     'scripts/reconcile_local_prompt_conditions.py'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('fixture\n')

    def phase(self, phase, count, status='completed', pending=False, failure=False):
        base = self.root / self.condition.directory
        frozen = self.frozen[:3] if phase == 'smoke' else self.frozen
        rows, events = [], []
        for i in range(count):
            source = frozen[i]
            outcome = 'service_failure' if failure and i == count - 1 else 'ok'
            row = {'id': source['id'], 'configuration': self.config, 'variant': 'P1',
                   'phase': phase, 'attempt_id': f'{phase}-{i}',
                   'manifest_sha256': 'manifest-hash', 'controller_sha256': 'controller-hash',
                   **({'predecessor_terminal_sha256': self.predecessor_hashes['terminal']}
                      if hasattr(self, 'predecessor_hashes') else {}),
                   'runtime_attestation': self.runtime, 'model_identifier': 'synthetic-id',
                   'model_path': 'model.gguf', 'timeout_ms': 600000,
                   'rendered_sha256': source['rendered_sha256'], 'expected_prompt_tokens': 10,
                   'reference_labels_read': False, 'request': source['request'],
                   'request_sha256': source['request_sha256'],
                   'non_reasoning_content': json.dumps(self.prediction),
                   'model_info': {'identifier': 'synthetic-id', 'path': 'model.gguf',
                                  'sizeBytes': 100, 'contextLength': 8192,
                                  'quantization': {'name': 'Q4_K_M'}},
                   'prediction_config': {'fields': []}, 'load_config': {'fields': []},
                   'stats': {'promptTokensCount': 10, 'predictedTokensCount': 8,
                             'stopReason': 'eosFound'}, 'elapsed_seconds': 0.5,
                   'decision': {'status': outcome, **({'prediction': self.prediction} if outcome == 'ok' else
                                                    {'reason': 'HTTP failed'})}}
            rows.append(row)
            events.append({'event': 'started', 'id': row['id'], 'attempt_id': row['attempt_id'],
                           'request_sha256': source['request_sha256'],
                           'manifest_sha256': 'manifest-hash'})
            line = json.dumps(row, separators=(',', ':')).encode()
            events.append({'event': 'finished', 'id': row['id'], 'attempt_id': row['attempt_id'],
                           'status': outcome, 'output_sha256': hashlib.sha256(line).hexdigest()})
        if pending:
            events.append({'event': 'started', 'id': frozen[count]['id'],
                           'attempt_id': f'{phase}-pending',
                           'request_sha256': frozen[count]['request_sha256'],
                           'manifest_sha256': 'manifest-hash'})
        output = base / f'{phase}.jsonl'
        journal = base / f'{phase}.attempts.jsonl'
        terminal_path = base / f'{phase}.terminal.json'
        write_jsonl(output, rows)
        write_jsonl(journal, events)
        terminal = {'configuration': self.config, 'variant': 'P1', 'phase': phase,
                    'status': status, 'manifest_sha256': 'manifest-hash',
                    'controller_sha256': 'controller-hash',
                    **({'predecessor_terminal_sha256': self.predecessor_hashes['terminal']}
                       if hasattr(self, 'predecessor_hashes') else {}),
                    'requested_records': len(frozen), 'claimed_attempts': count + int(pending),
                    'finished_attempts': count, 'saved_rows': count,
                    'ok_rows': count - int(failure), 'invalid_output_rows': 0,
                    'ambiguous_timeout': False, 'stopped_reason': None if status == 'completed' else 'Stopped',
                    'runtime_attestation': self.runtime, 'timeout_ms': 600000,
                    'output_sha256': sha(output), 'journal_sha256': sha(journal)}
        terminal_path.write_text(json.dumps(terminal) + '\n')
        return output, journal, terminal_path

    def tail(self):
        base = self.root / 'results/predecessor'
        base.mkdir(parents=True)
        rows = [{'id': rid, 'attempt_id': f'prior-{i}', 'manifest_sha256': 'prior-manifest',
                 'controller_sha256': 'prior-controller', 'request_sha256': f'prior-request-{i}',
                 'decision': {'status': 'ok'}} for i, rid in enumerate(IDS)]
        output = base / 'development.jsonl'
        journal = base / 'development.attempts.jsonl'
        terminal = base / 'development.terminal.json'
        write_jsonl(output, rows)
        events = []
        for i, row in enumerate(rows):
            events.extend([{'event': 'started', 'id': row['id'], 'attempt_id': row['attempt_id'],
                            'request_sha256': row['request_sha256']},
                           {'event': 'finished', 'id': row['id'], 'attempt_id': row['attempt_id'],
                            'status': 'ok', 'output_sha256': hashlib.sha256(
                                json.dumps(row, separators=(',', ':')).encode()).hexdigest()}])
        write_jsonl(journal, events)
        terminal.write_text(json.dumps({'configuration': 'prior-config', 'variant': 'P1',
            'phase': 'development', 'status': 'completed', 'manifest_sha256': 'prior-manifest',
            'controller_sha256': 'prior-controller', 'output_sha256': sha(output),
            'journal_sha256': sha(journal), 'requested_records': 60, 'saved_rows': 60,
            'claimed_attempts': 60, 'finished_attempts': 60, 'ambiguous_timeout': False}) + '\n')
        self.predecessor_hashes = {'terminal': sha(terminal), 'output': sha(output), 'journal': sha(journal)}
        manifest = self.root / V3_MANIFEST
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({'predecessor': {'configuration': 'prior-config',
            'variant': 'P1', 'output_dir': 'results/predecessor',
            'manifest_sha256': 'prior-manifest', 'controller_sha256': 'prior-controller'},
            'conditions': [{'configuration': self.config, 'variant': 'P1'}]}) + '\n')
        self.condition = Condition(self.config, 'P1', Path('results/run'), V3_MANIFEST,
                                   Path('scripts/controller.cjs'), sha(manifest),
                                   'controller-hash', self.parent)
        review = self.root / self.condition.directory / 'execution-review-root.json'
        receipt = json.loads(review.read_text())
        receipt.update({'configuration': self.config, 'variant': 'P1',
                        'manifest_sha256': sha(manifest),
                        **{'predecessor_' + name + '_sha256': value
                           for name, value in self.predecessor_hashes.items()}})
        review.write_text(json.dumps(receipt) + '\n')
        return terminal

    def smoke(self):
        output, journal, terminal = self.phase('smoke', 3)
        inspection = {'configuration': self.config, 'variant': 'P1',
                      'accepted_for_development': True, 'smoke_ids_inspected': 3,
                      'smoke_output_sha256': sha(output), 'smoke_journal_sha256': sha(journal),
                      'smoke_terminal_sha256': sha(terminal)}
        (self.root / self.condition.directory / 'smoke-inspection.json').write_text(
            json.dumps(inspection) + '\n')

    def test_completed_60_scores_and_separates_smoke_usage(self):
        self.smoke()
        self.phase('development', 60)
        report = reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])
        self.assertEqual(report['terminal_status'], 'completed')
        self.assertEqual(report['valid_outputs'], 60)
        self.assertEqual(report['all_four_correct'], 60)
        self.assertEqual(report['resource']['development']['prompt_tokens_observed_sum'], 600)
        self.assertEqual(report['resource']['smoke']['prompt_tokens_observed_sum'], 30)
        self.assertEqual(report['never_sent_ids'], [])
        self.assertIsNone(report['resource']['cost_usd'])

    def test_partial_terminal_preserves_unknown_and_never_sent(self):
        self.smoke()
        self.phase('development', 5, status='stopped', pending=True, failure=True)
        report = reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])
        self.assertEqual(report['terminal_status'], 'stopped')
        self.assertEqual(report['unknown_outcome_ids'], ['DEV-006'])
        self.assertEqual(report['never_sent_ids'][0], 'DEV-007')
        self.assertEqual(report['valid_outputs'], 4)
        self.assertFalse(report['coverage_complete'])

    def test_source_drift_is_rejected(self):
        self.smoke()
        output, _, _ = self.phase('development', 60)
        output.write_bytes(output.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])

    def test_frozen_request_drift_is_rejected(self):
        self.smoke()
        self.phase('development', 60)
        self.frozen[4]['request_sha256'] = 'changed-source-hash'
        with self.assertRaisesRegex(ValueError, 'Request or output journal hash mismatch'):
            reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])

    def test_zero_finished_rows_with_started_claim_is_unknown(self):
        self.smoke()
        self.phase('development', 0, status='stopped', pending=True)
        report = reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])
        self.assertEqual(report['unknown_outcome_ids'], ['DEV-001'])
        self.assertEqual(report['never_sent_ids'][0], 'DEV-002')
        self.assertEqual(report['valid_outputs'], 0)

    def test_tail_predecessor_drift_rejected(self):
        terminal = self.tail()
        self.smoke()
        self.phase('development', 60)
        # Tail fixtures bind the current manifest hash rather than the v2 fixture marker.
        for phase in ('smoke', 'development'):
            base = self.root / self.condition.directory
            output = base / f'{phase}.jsonl'
            journal = base / f'{phase}.attempts.jsonl'
            terminal_path = base / f'{phase}.terminal.json'
            rows, events = [json.loads(x) for x in output.read_text().splitlines()], [
                json.loads(x) for x in journal.read_text().splitlines()]
            for row in rows:
                row['manifest_sha256'] = self.condition.manifest_sha256
            for event in events:
                if event['event'] == 'started':
                    event['manifest_sha256'] = self.condition.manifest_sha256
            write_jsonl(output, rows)
            for i, row in enumerate(rows):
                events[2 * i + 1]['output_sha256'] = hashlib.sha256(
                    json.dumps(row, separators=(',', ':')).encode()).hexdigest()
            write_jsonl(journal, events)
            sealed = json.loads(terminal_path.read_text())
            sealed.update({'manifest_sha256': self.condition.manifest_sha256,
                           'output_sha256': sha(output), 'journal_sha256': sha(journal)})
            terminal_path.write_text(json.dumps(sealed) + '\n')
        smoke_base = self.root / self.condition.directory
        inspection = smoke_base / 'smoke-inspection.json'
        receipt = json.loads(inspection.read_text())
        receipt.update({'smoke_output_sha256': sha(smoke_base / 'smoke.jsonl'),
                        'smoke_journal_sha256': sha(smoke_base / 'smoke.attempts.jsonl'),
                        'smoke_terminal_sha256': sha(smoke_base / 'smoke.terminal.json')})
        inspection.write_text(json.dumps(receipt) + '\n')
        report = reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])
        self.assertEqual(report['sources']['predecessor']['terminal']['sha256'], sha(terminal))
        journal = terminal.parent / 'development.attempts.jsonl'
        journal.write_text(journal.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Predecessor terminal or source hash mismatch'):
            reconcile_saved_condition(self.root, self.condition, self.frozen, self.refs, [])


if __name__ == '__main__':
    unittest.main()
