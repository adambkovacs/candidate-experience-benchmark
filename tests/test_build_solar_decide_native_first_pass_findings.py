import json
from pathlib import Path
import shutil
import tempfile
import unittest

from development_benchmark import ROOT
import build_solar_decide_native_first_pass_findings as report


class SolarFirstPassReportTests(unittest.TestCase):
    def copied_public_sources(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        names = [*report.source_paths(), str(report.PROJECTION),
                 str(report.RECEIPT), str(report.OUTPUT)]
        for name in names:
            if name.endswith(report.PRIVATE_SUFFIXES):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        return temporary, root

    def test_published_first_pass_is_exact(self):
        self.assertEqual(report.check(), report.digest(ROOT / report.OUTPUT))

    def test_private_absent_projection_tamper_rejected_even_with_updated_receipt_hash(self):
        temporary, root = self.copied_public_sources()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(report.build(root), json.loads((root / report.OUTPUT).read_text()))
        projection_path = root / report.PROJECTION
        projection = json.loads(projection_path.read_text())
        prediction = projection['stages'][0]['records'][0]['prediction']
        prediction['testimonial_potential'] = 'no' if prediction['testimonial_potential'] == 'yes' else 'yes'
        projection_path.write_text(json.dumps(projection, sort_keys=True) + '\n')
        receipt_path = root / report.RECEIPT
        receipt = json.loads(receipt_path.read_text())
        receipt['projection_sha256'] = report.digest(projection_path)
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'score|closure'):
            report.build(root)

    def test_public_source_hash_change_rejected(self):
        temporary, root = self.copied_public_sources()
        self.addCleanup(temporary.cleanup)
        path = root / report.BASE / 'fresh1/P1/development.public-score.json'
        public = json.loads(path.read_text())
        public['all_four_correct'] += 1
        path.write_text(json.dumps(public) + '\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            report.build(root)


if __name__ == '__main__':
    unittest.main()
