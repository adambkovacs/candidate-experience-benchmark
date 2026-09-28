"""Synthetic offline evidence tests; no fixture represents a real model run."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_anyjev_generated_repeat_findings as report
from anyjev_generation_control import control_messages
from anyjev_raw_repeat_admission import canonical
from development_benchmark import digest


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


class SyntheticGeneratedReport(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plan = json.loads((ROOT / report.MANIFEST).read_text())
        self.inputs = [json.loads(line) for line in (ROOT / 'data/pilot/inputs.jsonl').read_text().splitlines()]
        self.labels = [json.loads(line) for line in (ROOT / 'data/pilot/proposed_labels.jsonl').read_text().splitlines()]
        self.policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
        required = list(self.plan['source_sha256']) + [
            str(report.MANIFEST), 'data/pilot/proposed_labels.jsonl',
            'results/anyjev-generated-phase2-token-preflight-2026-09-23.json',
            'results/prompt-comparison-v1-2026-09-24/anyjev-generated-exact/execution-manifest.json']
        required += [item['file'] for item in self.plan['historical']['conditions'].values()]
        for name in required:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def stage(self, phase, kind, bad=None):
        # Synthetic captures use illustrative token IDs; the portable builder cannot decode them.
        condition = phase.split('/')[1]
        count = 3 if kind == 'smoke' else 60
        folder = self.root / report.BASE / phase
        folder.mkdir(parents=True, exist_ok=True)
        receipt = {'kind': 'root-reviewed-anyjev-generated-stage-v1', 'approved': True,
                   'phase': phase, 'stage': kind, 'plan_sha256': report.MANIFEST_SHA,
                   'controller_sha256': self.plan['source_sha256']['scripts/anyjev_generated_repeat_admission.py'],
                   'artifact_sha256': self.plan['asset_sha256']['model.safetensors'],
                   'reference_labels_read': False}
        if kind == 'development':
            receipt['smoke_inspection_sha256'] = report.sha(folder / 'smoke-inspection.json')
        write_json(folder / f'{kind}.root-review.json', receipt)
        claim = {'phase': phase, 'stage': kind, 'plan_sha256': report.MANIFEST_SHA,
                 'receipt_sha256': report.sha(folder / f'{kind}.root-review.json'),
                 'policy': 'exclusive one attempt; uncertain started positions are not replayed'}
        write_json(folder / f'{kind}.claim.json', claim)
        journal = [{'event': 'phase_started', 'phase': phase, 'stage': kind}]
        captures, records = [], []
        for i, (row, request, label) in enumerate(zip(self.inputs[:count], self.plan['requests'][condition][:count], self.labels[:count])):
            messages = control_messages(row['feedback'], self.policy, condition, 'anyjev-qwen06-generated-control')
            self.assertEqual(digest(json.dumps(messages, sort_keys=True)), request['messages_sha256'])
            invalid = bad == 'invalid' and i == 0
            response = '```bad```' if invalid else json.dumps(label['proposed_labels'])
            ids = [1] if invalid else [1, 0]
            prediction = None if invalid else label['proposed_labels']
            status = 'invalid_output' if invalid else 'ok'
            attempt = f'synthetic-{phase}-{kind}-{i}'
            capture = {'id': row['id'], 'attempt_id': attempt, 'messages': messages,
                       'messages_sha256': request['messages_sha256'],
                       'rendered_prompt_sha256': request['rendered_prompt_sha256'],
                       'input_ids_sha256': request['input_ids_sha256'],
                       'input_tokens': request['input_tokens'], 'generated_token_ids': ids,
                       'raw_response': response, 'eos_token_ids': [0], 'output_tokens': len(ids),
                       'finish_reason': 'length' if invalid else 'stop',
                       'client_generation_seconds': 0.25}
            record = {'id': row['id'], 'attempt_id': attempt, 'phase': phase, 'stage': kind,
                      'status': status, 'prediction': prediction, 'raw_sha256': digest(canonical(capture)),
                      'input_sha256': request['input_sha256'], 'messages_sha256': request['messages_sha256'],
                      'reference_labels_read': False, 'model_id': self.plan['model_id'],
                      'artifact_revision': self.plan['artifact_revision'], 'device': 'mps:0',
                      'dtype': 'torch.bfloat16', 'do_sample': False, 'enable_thinking': False,
                      'client_generation_seconds': 0.25}
            captures.append(capture); records.append(record)
            journal.extend([{'event': 'request_started', 'id': row['id'], 'attempt_id': attempt,
                             'messages_sha256': request['messages_sha256']},
                            {'event': 'request_completed', 'id': row['id'], 'attempt_id': attempt,
                             'status': status}])
        journal.append({'event': 'phase_completed', 'count': count})
        write_rows(folder / f'{kind}.raw.jsonl', captures)
        write_rows(folder / f'{kind}.records.jsonl', records)
        write_rows(folder / f'{kind}.journal.jsonl', journal)
        completion = {'phase': phase, 'stage': kind, 'plan_sha256': report.MANIFEST_SHA,
                      'count': count, 'records_sha256': report.sha(folder / f'{kind}.records.jsonl'),
                      'raw_sha256': report.sha(folder / f'{kind}.raw.jsonl'),
                      'journal_sha256': report.sha(folder / f'{kind}.journal.jsonl')}
        write_json(folder / f'{kind}.completion.json', completion)
        return folder, captures, records

    def closed(self, phase, bad=None):
        folder, _, smoke = self.stage(phase, 'smoke', bad=bad)
        inspection = {'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                      'smoke_records_sha256': report.sha(folder / 'smoke.records.jsonl'),
                      'approved': True, 'records': []}
        for record in smoke:
            declaration = {key: record[key] for key in ('id', 'status', 'prediction', 'raw_sha256')}
            if record['status'] == 'invalid_output':
                declaration.update(accepted_unchanged=True, failure_class='intrinsic_schema',
                                   inspection_reason='Synthetic length finish retained.')
            inspection['records'].append(declaration)
        write_json(folder / 'smoke-inspection.json', inspection)
        return self.stage(phase, 'development', bad=bad)

    def test_baseline_nine_missing_and_history_separate(self):
        result = report.build(self.root)
        self.assertEqual(result['completedConditions'], 0)
        self.assertEqual(len(result['missingPasses']), 9)
        self.assertEqual([result['historicalObservation']['conditions'][x]['score']['valid'] for x in report.CONDITIONS], [0, 0, 30])
        self.assertEqual(result['passOrder'], ['fresh1', 'fresh2', 'fresh3'])

    def test_closed_phase_fixed_denominator_and_invalid(self):
        self.closed('fresh1/P0', bad='invalid')
        result = report.build(self.root)
        entry = result['passes']['fresh1']['P0']
        self.assertEqual((entry['score']['denominator'], entry['score']['valid'], entry['score']['allFour']), (60, 59, 59))
        self.assertEqual(entry['score']['outcomes']['invalid_output'], 1)
        self.assertEqual(entry['usage']['tokens']['output_tokens'], 119)
        field = report.FIELDS[0]
        self.assertEqual(sum(sum(row.values()) for row in entry['confusionCounts'][field].values()), 60)
        self.assertEqual(result['completedConditions'], 1)

    def test_open_partial_never_parsed(self):
        folder = self.root / report.BASE / 'fresh1/P0'
        folder.mkdir(parents=True)
        write_json(folder / 'smoke.claim.json', {'phase': 'fresh1/P0'})
        (folder / 'development.raw.jsonl').write_bytes(b'{partial')
        result = report.build(self.root)
        self.assertEqual(result['missingPasses'][0]['status'], 'claimed_in_progress_or_interrupted')
        self.assertEqual(result['completedConditions'], 0)

    def test_tampered_capture_and_rebound_hash_rejected(self):
        folder, captures, _ = self.closed('fresh1/P0')
        captures[0]['messages'][0]['content'] += ' changed'
        write_rows(folder / 'development.raw.jsonl', captures)
        completion = json.loads((folder / 'development.completion.json').read_text())
        completion['raw_sha256'] = report.sha(folder / 'development.raw.jsonl')
        write_json(folder / 'development.completion.json', completion)
        with self.assertRaisesRegex(ValueError, 'output binding'):
            report.build(self.root)

    def test_missing_inspection_or_completion_not_scored(self):
        folder, _, _ = self.closed('fresh1/P0')
        (folder / 'smoke-inspection.json').unlink()
        with self.assertRaises(FileNotFoundError):
            report.build(self.root)

    def test_later_closed_cannot_skip_predecessor(self):
        self.closed('fresh1/P1')
        with self.assertRaisesRegex(ValueError, 'open predecessor'):
            report.build(self.root)

    def test_prompt_comparison_only_closed_pairs(self):
        self.closed('fresh1/P0'); self.closed('fresh1/P1')
        result = report.build(self.root)
        self.assertEqual(len(result['withinPassPromptDeltas']), 1)
        self.assertEqual(result['withinPassPromptFlips'][0]['denominator'], 60)
        self.assertEqual(result['threePassSummary']['P2']['allFour']['completedPasses'], 0)

    def test_missing_terminal_completion_is_open(self):
        folder, _, _ = self.closed('fresh1/P0')
        (folder / 'development.completion.json').unlink()
        result = report.build(self.root)
        self.assertEqual(result['completedConditions'], 0)
        self.assertEqual(result['missingPasses'][0]['status'], 'claimed_in_progress_or_interrupted')

    def test_rehashed_projection_drift_rejected(self):
        folder, _, records = self.closed('fresh1/P0')
        records[0]['prediction'] = None
        write_rows(folder / 'development.records.jsonl', records)
        completion = json.loads((folder / 'development.completion.json').read_text())
        completion['records_sha256'] = report.sha(folder / 'development.records.jsonl')
        write_json(folder / 'development.completion.json', completion)
        with self.assertRaisesRegex(ValueError, 'output binding'):
            report.build(self.root)


if __name__ == '__main__':
    unittest.main()
