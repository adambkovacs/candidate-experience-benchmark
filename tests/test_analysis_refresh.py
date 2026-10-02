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
        self.assertEqual(len(rebuilt["sources"]), 79)
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
        cohorts = rebuilt["newerCohorts"]
        self.assertEqual(cohorts["gemma26"]["source"],
                         "public-site/gemma26-postabort-findings.json")
        self.assertEqual(cohorts["gemma26"]["completedConditionsAtSecondContinuation"], 6)
        self.assertEqual(cohorts["gemma26"]["completedConditions"], 7)
        self.assertEqual(cohorts["gemma26"]["fresh3P2"], {
            "status": "completed_composite_interrupted", "valid": 58,
            "failedIds": ["DEV-005", "DEV-006"], "allFour": 56,
            "denominator": 60})
        self.assertEqual(cohorts["gemma26"]["p2RepeatSource"],
                         "public-site/gemma26-p2-repeat-findings.json")
        self.assertEqual(cohorts["gemma26"]["p2Repeat"], {
            "fixed60AllFourByPass": {"fresh1": 57, "fresh2": 56, "fresh3": 56},
            "sharedValidDenominator": 57,
            "excludedIds": ["DEV-005", "DEV-006", "DEV-007"],
            "changedFourFieldVectorIds": ["DEV-013", "DEV-059"],
            "cleanMatchedThreeEligible": False})
        self.assertEqual(cohorts["gemma26"]["neverSentConditions"],
                         ["fresh3/P0", "fresh3/P1"])
        self.assertEqual(cohorts["clefNativeP0"]["models"], {
            "clef": {"valid": 60, "allFour": 53, "denominator": 60},
            "clef-flash": {"valid": 60, "allFour": 45, "denominator": 60}})
        self.assertEqual(cohorts["clefNativeP0"]["fullPassesPerModelCompleted"], 1)
        self.assertEqual(cohorts["clefNativeP0"]["repeatSource"],
                         "public-site/clef-p0-repeat-findings.json")
        self.assertEqual(cohorts["clefNativeP0"]["repeat"]["fullPassesPerModelCompleted"], 2)
        self.assertEqual(cohorts["clefNativeP0"]["repeat"]["sharedValidDenominator"], 60)
        self.assertEqual(cohorts["clefNativeP0"]["repeat"]["models"], {
            "clef": {"fresh1AllFour": 53, "fresh2AllFour": 53,
                     "changedFourFieldVectorIds": []},
            "clef-flash": {"fresh1AllFour": 45, "fresh2AllFour": 45,
                           "changedFourFieldVectorIds": []}})
        self.assertIsNone(cohorts["clefNativeP0"]["providerBilledUsd"])
        self.assertEqual(len(cohorts["legacyQwen"]["completedConfigurations"]), 3)
        legacy = json.loads((ROOT / "public-site/legacy-qwen-repeats.json").read_text())
        pending = {s["configuration"]: s for s in legacy["series"]}
        for name, progress in cohorts["legacyQwen"]["remainingConfigurations"].items():
            self.assertEqual(progress["completedConditions"],
                             pending[name]["completedConditions"])
        self.assertEqual(cohorts["legacyQwen"]["sdkFinalP2"]["thinkingOn"],
                         {"valid": 58, "invalid": 2, "allFour": 1, "denominator": 60})
        self.assertEqual(cohorts["legacyQwen"]["sdkFinalP2"]["thinkingOff"],
                         {"valid": 5, "invalid": 55, "allFour": 0, "denominator": 60})
        self.assertEqual(cohorts["qwen27"]["seriesCount"], 2)

    def test_check_rejects_changed_source_even_if_json_values_same(self):
        published = json.loads((ROOT / analysis.OUTPUT).read_text())
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            for item in published["sources"]:
                source = ROOT / item["path"]
                target = temp / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            clef_repeat = json.loads((ROOT / "public-site/clef-p0-repeat-findings.json").read_text())
            for name in clef_repeat["sourceSha256"]:
                target = temp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
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
            shutil.copyfile(ROOT / "public-site/findings.json", path)
            gemma = temp / "public-site/gemma26-postabort-findings.json"
            changed = json.loads(gemma.read_text())
            changed["fresh3P2"]["score"]["valid"] = 59
            gemma.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "Gemma postabort composite"):
                analysis.build(temp)


if __name__ == "__main__":
    unittest.main()
