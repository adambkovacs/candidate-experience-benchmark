import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from development_benchmark import ROOT
import build_solar_decide_native_full_findings as report


PRIVATE = ('development.raw.jsonl', 'development.parsed.jsonl',
           'development.attempts.jsonl', 'development.journal.jsonl',
           'smoke.raw.jsonl', 'smoke.parsed.jsonl',
           'smoke.attempts.jsonl', 'smoke.journal.jsonl')


class SolarFullReportTests(unittest.TestCase):
    def copied_public_sources(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        names = [*report.source_paths(), str(report.PROJECTION),
                 str(report.RECEIPT), str(report.OUTPUT)]
        for name in names:
            if name.endswith(PRIVATE):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        return temporary, root

    def test_published_report_keeps_unknown_and_shared_valid_denominators(self):
        self.assertEqual(report.check(), report.first.digest(ROOT / report.OUTPUT))
        value = report.build()
        self.assertEqual(value['valid_development_answers'], 539)
        self.assertEqual(value['unknown_cost_development_attempts'], 1)
        self.assertEqual(value['stages'][-1]['valid_answers'], 59)
        self.assertEqual(value['stages'][-1]['unusable_ids'], ['DEV-009'])
        self.assertEqual(value['child_all_requests']['original_unknown_upper_bound_usd'],
                         '0.10485760')
        self.assertEqual({row['paired_records'] for row in value['repeat_comparisons']
                          if report.FINAL in (row['left'], row['right'])}, {59})
        self.assertEqual({row['paired_records'] for row in value['matched_prompt_comparisons']
                          if report.FINAL in (row['left'], row['right'])}, {59})

    def test_source_bindings_only_copy_rebuilds(self):
        temporary, root = self.copied_public_sources()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(report.check(root), report.first.digest(root / report.OUTPUT))

    def test_clean_git_archive_subprocess_rebuilds_without_private_raw(self):
        if not (ROOT / '.git').exists():
            self.assertFalse((ROOT / report.BASE / 'fresh3/P2/development.raw.jsonl').exists())
            self.assertEqual(report.check(), report.first.digest(ROOT / report.OUTPUT))
            return
        data = subprocess.check_output(['git', 'archive', 'HEAD'], cwd=ROOT)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
                archive.extractall(root)
            for name in [*report.source_paths(), str(report.PROJECTION),
                         str(report.RECEIPT), str(report.OUTPUT)]:
                if name.endswith(PRIVATE):
                    continue
                source, target = ROOT / name, root / name
                if not target.is_file() or target.read_bytes() != source.read_bytes():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            env = dict(os.environ, PYTHONPATH=str(root / 'scripts'))
            result = subprocess.run([sys.executable,
                'scripts/build_solar_decide_native_full_findings.py', 'check'],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_projection_tamper_rejected_even_with_rehashed_receipt(self):
        temporary, root = self.copied_public_sources()
        self.addCleanup(temporary.cleanup)
        projection_path = root / report.PROJECTION
        projection = json.loads(projection_path.read_text())
        prediction = projection['stages'][0]['records'][0]['prediction']
        prediction['testimonial_potential'] = ('no' if prediction['testimonial_potential']
                                               == 'yes' else 'yes')
        projection_path.write_text(json.dumps(projection, sort_keys=True) + '\n')
        receipt_path = root / report.RECEIPT
        receipt = json.loads(receipt_path.read_text())
        receipt['projection_sha256'] = report.first.digest(projection_path)
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'Published Solar'):
            report.check(root)

    def test_sealed_suffix_snapshot_tamper_rejected(self):
        temporary, root = self.copied_public_sources()
        self.addCleanup(temporary.cleanup)
        path = root / report.SUFFIX_SNAPSHOT
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            report.build(root)


if __name__ == '__main__':
    unittest.main()
