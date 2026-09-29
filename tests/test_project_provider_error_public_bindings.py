import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import project_provider_error_public_bindings as subject
from scripts import build_findings

ROOT = Path(__file__).resolve().parents[1]


class ProviderBindingProjectionTest(unittest.TestCase):
    def test_mapping_keeps_private_attestation_separate_from_public_hash(self):
        old = 'results/example/raw.jsonl'
        public = 'public-evidence/provider-errors-v1/results/example/raw.jsonl'
        mapping = {'schema': 'provider-error-public-evidence-v1', 'sources': [{
            'originalPath': old, 'privateOriginalSha256': 'a' * 64,
            'publicPath': public, 'publicSha256': 'b' * 64,
        }]}
        original = {'runs': [{'evidenceSources': [subject.GITHUB + old],
                              'metrics': {'all_four': 4}, 'cost': {'actual': None}}]}
        result = subject.project_data(original, mapping, 'c' * 64)
        self.assertEqual(result['runs'][0]['evidenceSources'], [subject.GITHUB + public])
        self.assertEqual(result['runs'][0]['metrics'], original['runs'][0]['metrics'])
        self.assertEqual(result['runs'][0]['cost'], original['runs'][0]['cost'])
        self.assertEqual(result['publicEvidenceProjection']['mapping'][0], mapping['sources'][0])
        self.assertNotEqual(result['publicEvidenceProjection']['mapping'][0]['privateOriginalSha256'],
                            result['publicEvidenceProjection']['mapping'][0]['publicSha256'])
        self.assertEqual(original['runs'][0]['evidenceSources'], [subject.GITHUB + old])

    def test_unsupported_path_context_fails_closed(self):
        old = 'results/example/raw.jsonl'
        mapping = {'schema': 'provider-error-public-evidence-v1', 'sources': [{
            'originalPath': old, 'privateOriginalSha256': 'a' * 64,
            'publicPath': 'public-evidence/provider-errors-v1/' + old,
            'publicSha256': 'b' * 64,
        }]}
        with self.assertRaisesRegex(ValueError, 'Unsupported private evidence path context'):
            subject.project_data({'runs': [{'note': 'compare ' + old}]}, mapping, 'c' * 64)
        with self.assertRaisesRegex(ValueError, 'unprojected'):
            subject.project_data({'publicEvidenceProjection': {}}, mapping, 'c' * 64)

    def test_real_projection_and_findings_without_private_raw_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'public-site').mkdir()
            shutil.copy2(ROOT / subject.SOURCE, root / subject.SOURCE)
            bundle = root / subject.PUBLIC_DIR
            for source in (ROOT / subject.PUBLIC_DIR).rglob('*'):
                if source.is_file():
                    target = root / source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            self.assertFalse((root / 'results').exists())
            data, _ = subject.run(root)
            subject.run(root, check=True)
            subprocess.run([sys.executable, str(ROOT / 'scripts/build_public_explorer.py'),
                            '--provider-error-projection', '--root', str(root), '--check'],
                           check=True, capture_output=True, text=True)
            self.assertEqual(data, (ROOT / subject.OUTPUT).read_bytes())
            findings_path = root / 'public-site/findings-provider-errors-v1.json'
            command = [sys.executable, str(ROOT / 'scripts/build_findings.py'),
                       '--source', str(root / subject.OUTPUT), '--output', str(findings_path)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command + ['--check'], check=True, capture_output=True, text=True)
            output = build_findings.build(source=root / subject.OUTPUT,
                                          labels_path=ROOT / 'data/pilot/proposed_labels.jsonl')
            published = json.loads((ROOT / 'public-site/findings.json').read_text())
            self.assertEqual(output['charts'], published['charts'])
            self.assertEqual(output['meta']['runCount'], published['meta']['runCount'])
            self.assertEqual(output['meta']['caseCount'], published['meta']['caseCount'])

    def test_real_mapping_exactly_uses_audited_urls(self):
        original = json.loads((ROOT / subject.SOURCE).read_text())
        manifest = json.loads((ROOT / subject.PUBLIC_DIR / 'manifest.json').read_text())
        mapped = subject.project_data(original, manifest,
                                      subject.sha((ROOT / subject.SOURCE).read_bytes()))
        used = mapped['publicEvidenceProjection']['mapping']
        self.assertEqual(len(used), 10)
        reverse = {subject.GITHUB + x['publicPath']: subject.GITHUB + x['originalPath']
                   for x in used}
        restored = copy.deepcopy(mapped)
        del restored['publicEvidenceProjection']
        def visit(v):
            if isinstance(v, dict): return {k: visit(x) for k, x in v.items()}
            if isinstance(v, list): return [visit(x) for x in v]
            return reverse.get(v, v) if isinstance(v, str) else v
        self.assertEqual(visit(restored), original)


if __name__ == '__main__':
    unittest.main()
