import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluate_legacy_local_prompt_pairs_v1 as module

REPO = Path(__file__).resolve().parents[1]


class LegacyLocalPromptPairsTests(unittest.TestCase):
    def fixture(self, config='qwen3-1.7b-sdk-thinking-on'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        manifest = json.loads((REPO / module.LOCAL).read_text())
        cfg = manifest['configs'][config]
        paths = [module.LOCAL, Path(cfg['baseline_file']), Path(cfg['baseline_manifest_file']),
                 Path(manifest['schedule_file']), Path('data/pilot/inputs.jsonl'),
                 Path('data/pilot/proposed_labels.jsonl'), Path('data/pilot/pairs.json'),
                 Path('docs/LABELING_GUIDE.md'), Path('schemas/judgments.schema.json'),
                 Path('prompts/variants-v1/manifest.json'),
                 Path('prompts/variants-v1/P1-classifier.txt'),
                 Path('prompts/variants-v1/P2-classifier-sop.txt')]
        for condition in ('P1', 'P2'):
            directory = Path(module.SPECS[config][2]) / condition
            paths.extend(directory / filename for filename in (
                'development.jsonl', 'development.attempts.jsonl', 'development.terminal.json'))
        for name in paths:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, target)
        return root, config

    def test_exact_five_real_saved_triples_are_descriptive(self):
        expected = {
            'qwen3-0.6b-q4km-nonthinking': (60, 60, 60),
            'qwen3-0.6b-sdk-thinking-on': (31, 50, 58),
            'qwen3-0.6b-sdk-thinking-off': (0, 4, 2),
            'qwen3-1.7b-sdk-thinking-on': (60, 60, 59),
            'qwen3-1.7b-sdk-thinking-off': (60, 59, 53),
        }
        self.assertEqual(set(module.SPECS), set(expected))
        for config, counts in expected.items():
            with self.subTest(config=config):
                report = module.evaluate(REPO, config)
                self.assertEqual(report['eligibility_status'], 'descriptive_legacy_baseline')
                self.assertFalse(report['eligible_paired_comparison'])
                self.assertEqual(report['denominator'], 60)
                self.assertFalse(report['historical_p0_attempt_journal_available'])
                self.assertTrue(all(isinstance(report['conditions'][name]['all_four_correct'], int)
                                    for name in ('P0', 'P1', 'P2')))
                self.assertEqual(tuple(report['conditions'][name]['evaluation']['valid_outputs']
                                       for name in ('P0', 'P1', 'P2')), counts)
                self.assertTrue(all(report['comparisons'][name]['denominator'] == 60 for name in
                                    ('P0_to_P1', 'P0_to_P2', 'P1_to_P2')))

    def test_relocated_root_checks_its_own_p0_journal_and_policy(self):
        root, config = self.fixture()
        manifest = json.loads((root / module.LOCAL).read_text())
        journal = root / (manifest['configs'][config]['baseline_file'] + '.attempts.jsonl')
        journal.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'Unexpected historical P0 journal'):
            module.evaluate(root, config)
        root, config = self.fixture('qwen3-0.6b-q4km-nonthinking')
        root = root.resolve()
        guide = root / 'docs/LABELING_GUIDE.md'
        guide.write_text(guide.read_text().replace('# Labeling guide', '# Changed labeling guide', 1))
        manifest = json.loads((root / module.LOCAL).read_text())
        inputs = module.rows(root / 'data/pilot/inputs.jsonl')
        with self.assertRaisesRegex(ValueError, 'P0 HTTP source-derived request/control drift'):
            module.baseline(root, config, module.SPECS[config], manifest, inputs)

    def test_frozen_p0_drift_rejected(self):
        root, config = self.fixture()
        baseline = root / json.loads((root / module.LOCAL).read_text())['configs'][config]['baseline_file']
        baseline.write_bytes(baseline.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            module.evaluate(root, config)

    def test_variant_request_or_journal_drift_rejected(self):
        root, config = self.fixture()
        directory = root / module.SPECS[config][2] / 'P1'
        output = directory / 'development.jsonl'
        lines = output.read_text().splitlines()
        first = json.loads(lines[0])
        first['request']['messages'][1]['content'] = '{"feedback":"different"}'
        lines[0] = json.dumps(first, ensure_ascii=False)
        output.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'terminal/coverage binding'):
            module.evaluate(root, config)
        shutil.copy2(REPO / module.SPECS[config][2] / 'P1/development.jsonl', output)
        journal = directory / 'development.attempts.jsonl'
        events = journal.read_text().splitlines()
        events[0] = events[0].replace('DEV-001', 'DEV-999')
        journal.write_text('\n'.join(events) + '\n')
        with self.assertRaisesRegex(ValueError, 'terminal/coverage binding'):
            module.evaluate(root, config)

    def test_row_runtime_attestation_mismatch_rejected(self):
        root, config = self.fixture()
        directory = root / module.SPECS[config][2] / 'P1'
        output = directory / 'development.jsonl'
        lines = output.read_text().splitlines()
        first = json.loads(lines[0])
        first['runtime_attestation']['cli_commit'] = 'different'
        lines[0] = json.dumps(first, ensure_ascii=False)
        output.write_text('\n'.join(lines) + '\n')
        terminal_file = directory / 'development.terminal.json'
        terminal = json.loads(terminal_file.read_text())
        terminal['output_sha256'] = module.sha(output)
        terminal_file.write_text(json.dumps(terminal) + '\n')
        with self.assertRaisesRegex(ValueError, 'Variant request, feedback, or journal linkage differs'):
            module.evaluate(root, config)

    def test_invalid_raw_claim_rejected(self):
        row = {'raw_response': '<think>done</think>{"bad":true}',
               'reasoning_content': 'done', 'non_reasoning_content': '{"bad":true}',
               'request': {'config': {'reasoningParsing': {'enabled': True,
                           'startString': '<think>', 'endString': '</think>'}}},
               'stats': {'stopReason': 'eosFound'}}
        with self.assertRaisesRegex(ValueError, 'unsupported by raw'):
            module.sdk_status(row, 'ok', {'sentiment': 'positive'})

    def test_unknown_configuration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported legacy'):
            module.evaluate(REPO, 'unapproved-model')


if __name__ == '__main__':
    unittest.main()
