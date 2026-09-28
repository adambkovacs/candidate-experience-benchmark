import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_private_evidence_removal as audit


class PrivateEvidenceInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.backup = Path(self.temp.name) / 'backup'
        self.root.mkdir()
        self.backup.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.entries = []

    def add_file(self, name, value, *, back_up=False):
        relative = Path('results') / name
        original = self.root / relative
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text(json.dumps(value) + '\n')
        subprocess.run(['git', 'add', '--', str(relative)], cwd=self.root, check=True)
        if back_up:
            copy = self.backup / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(original.read_bytes())
            self.entries.append({'path': str(relative),
                                 'sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                                 'bytes': original.stat().st_size})
        return original

    def write_manifest(self):
        (self.backup / 'backup-manifest.json').write_text(json.dumps({
            'schema': 'private-original-evidence-backup-v1',
            'originals_changed': False,
            'skipped_changed_since_inventory': [],
            'entries': self.entries,
        }))

    def test_nested_stdout_quota_is_candidate_and_path_only_is_retained(self):
        self.add_file('quota.json', {'stdout': json.dumps({
            'type': 'rate_limit_event',
            'rate_limit_info': {'five_hour': {'utilization': 0.5}},
        })}, back_up=True)
        self.add_file('path.json', {'source': '/Users/example/private/evidence'}, back_up=True)
        self.add_file('public.json', {'rate_limit_info': {'isUsingOverage': False}})
        self.write_manifest()
        report = audit.inventory(self.root, self.backup)
        self.assertEqual(report['counts']['verified_removal_candidates'], 1)
        self.assertEqual(report['counts']['supplementary_backed_provenance'], 1)
        self.assertEqual(report['backup_gaps'], [])
        self.assertEqual(report['removal_candidates'][0]['path'], 'results/quota.json')

    def test_changed_backup_or_original_blocks_quota_removal(self):
        path = self.add_file('quota.json', {'utilization': 0.4}, back_up=True)
        self.write_manifest()
        path.write_text(json.dumps({'utilization': 0.6}) + '\n')
        report = audit.inventory(self.root, self.backup)
        self.assertEqual(report['removal_candidates'], [])
        self.assertEqual(report['backup_gaps'], ['results/quota.json'])

    def test_unbacked_quota_gap_and_unbacked_path_lead_are_distinct(self):
        self.add_file('quota.json', {'stdout': json.dumps({'resetsAt': 123})})
        self.add_file('path.json', {'source': '/Users/example/reference'})
        self.write_manifest()
        report = audit.inventory(self.root, self.backup)
        self.assertEqual(report['backup_gaps'], ['results/quota.json'])
        self.assertEqual(report['counts']['unbacked_review_leads'], 2)

    def test_masked_read_probe_detects_original_and_allows_independent_check(self):
        self.add_file('quota.json', {'utilization': 0.4}, back_up=True)
        (self.root / 'needs.py').write_text("from pathlib import Path\nPath('results/quota.json').read_text()\n")
        (self.root / 'free.py').write_text("print('passed')\n")
        with patch.dict(audit.PROBES, {'needs': ['needs.py'], 'free': ['free.py']}, clear=True):
            result = audit.dependency_audit(self.root, ['results/quota.json'])
        self.assertEqual(result['needs']['status'], 'blocked_on_private_original')
        self.assertEqual(result['needs']['original_required'], 'results/quota.json')
        self.assertEqual(result['free']['status'], 'passed_without_private_original')


if __name__ == '__main__':
    unittest.main()
