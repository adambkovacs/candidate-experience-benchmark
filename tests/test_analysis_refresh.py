import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_analysis_refresh", ROOT / "scripts/build_analysis_refresh.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class AnalysisRefreshTest(unittest.TestCase):
    def test_published_feed_rebuilds_from_bound_sources(self):
        expected = json.loads((ROOT / analysis.OUTPUT).read_text())
        rebuilt = analysis.build(ROOT)
        self.assertEqual(rebuilt, expected)
        self.assertEqual(len(rebuilt["sources"]), 63)
        self.assertEqual(rebuilt["claude"]["totalConfigurations"], 21)
        self.assertEqual(rebuilt["claude"]["allThreePassPromptGainCount"], {"P1": 0, "P2": 0})
        self.assertEqual(rebuilt["sonnet55"]["developmentApiEquivalentUsd"], "3.5429424")
        self.assertEqual(rebuilt["sonnet55"]["byEffort"]["xhigh"]["conditions"]["P1"]["scores"],
                         [58, 58, 58])
        self.assertEqual(rebuilt["sonnet55"]["byEffort"]["xhigh"]["conditions"]["P1"]["changedReviewCount"], 1)
        mistral = rebuilt["newerCohorts"]["mistral119"]
        self.assertEqual(mistral["source"], analysis.MISTRAL_SECOND_SUFFIX)
        self.assertEqual(mistral["priorSuffixSource"], analysis.MISTRAL_FIRST_SUFFIX)
        self.assertEqual(mistral["combinedSavedValidCount"], 50)
        self.assertEqual(mistral["failedOrUnknownCount"], 3)
        self.assertEqual(mistral["neverSentCount"], 7)
        self.assertEqual(mistral["validIdsInFirstSuffix"], ["DEV-049"])
        self.assertEqual(mistral["validIdsInSecondSuffix"], ["DEV-051", "DEV-052"])
        self.assertEqual(mistral["failedIds"], ["DEV-048", "DEV-050", "DEV-053"])
        self.assertIsNone(mistral["score"])
        self.assertIn(analysis.MISTRAL_SECOND_SUFFIX,
                      {item["path"] for item in rebuilt["sources"]})

    def test_check_rejects_changed_source_even_if_json_values_same(self):
        published = json.loads((ROOT / analysis.OUTPUT).read_text())
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            for item in published["sources"]:
                source = ROOT / item["path"]
                target = temp / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            output = temp / analysis.OUTPUT
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / analysis.OUTPUT, output)
            check = subprocess.run([sys.executable, str(ROOT / "scripts/build_analysis_refresh.py"),
                                    "--root", str(temp), "--check"], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            path = temp / "public-site/findings.json"
            path.write_text(path.read_text() + " ")
            stale = subprocess.run([sys.executable, str(ROOT / "scripts/build_analysis_refresh.py"),
                                    "--root", str(temp), "--check"], capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("stale", stale.stderr)


if __name__ == "__main__":
    unittest.main()
