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
        self.assertEqual(len(rebuilt["sources"]), 127)
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
        latest = cohorts["latestFlashP0Interruption"]
        self.assertEqual(latest["unknownOutcomeIds"], ["DEV-001", "DEV-002"])
        self.assertEqual(latest["neverSentIds"], [f"DEV-{i:03d}" for i in range(3, 61)])
        self.assertEqual(latest["valid"], 0)
        self.assertEqual(latest["reviewCount"], 60)
        self.assertIsNone(latest["score"])
        p1 = cohorts["clefP1FirstPass"]
        self.assertEqual((p1["valid"], p1["allFour"], p1["completedP1Passes"]), (60, 52, 1))
        self.assertEqual(p1["matchedP0"], {"allFour": 53,
            "changedIds": ["DEV-013", "DEV-014", "DEV-053", "DEV-056"],
            "gainedIds": ["DEV-056"], "lostIds": ["DEV-013", "DEV-014"]})
        self.assertEqual(p1["inputPriceEstimateUsd"], "0.03472656")
        self.assertFalse(p1["repeatabilityClaim"])
        self.assertIsNone(p1["providerBilledUsd"])

        self.assertEqual(cohorts["gemma26"]["source"],
                         "public-site/gemma26-fresh3-p1-interrupted-checkpoint.json")
        self.assertEqual(cohorts["gemma26"]["priorP0Source"],
                         "public-site/gemma26-fresh3-p0-checkpoint.json")
        self.assertEqual(cohorts["gemma26"]["completedConditionsAtSecondContinuation"], 6)
        self.assertEqual(cohorts["gemma26"]["completedConditions"], 9)
        self.assertEqual(cohorts["gemma26"]["p1Checkpoint"], {
            "fixed60AllFourByPass": {"fresh1": 58, "fresh2": 58, "fresh3": 57},
            "validByPass": {"fresh1": 60, "fresh2": 60, "fresh3": 59},
            "failedIds": ["DEV-059"], "sharedValidDenominator": 59,
            "sharedValidAllFourByPass": {"fresh1": 57, "fresh2": 57, "fresh3": 57},
            "thirdPassKnownCostUsd": "0.01941923",
            "thirdPassMissingCostCount": 1,
            "cleanMatchedThreeEligible": False})
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
        self.assertEqual(cohorts["gemma26"]["unscoredConditionsAtCutoff"],
                         [])
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
        self.assertEqual(cohorts["clefNativeP0"]["thirdCheckpointSource"],
                         "public-site/clef-p0-third-checkpoint.json")
        self.assertEqual(cohorts["clefNativeP0"]["thirdCheckpoint"], {
            "clef": {"scoredCellsOfNine": 3, "fresh3AllFour": 53, "valid": 60,
                     "sharedValidThreePassDenominator": 60, "changedPredictionIds": [],
                     "nativeDistributionChangedIds": [], "vendorConfidenceChangedIds": []},
            "clefFlash": {"scoredCellsOfNine": 2,
                          "fresh3Status": "stopped_unknown_outcome",
                          "unknownOutcomeIds": ["DEV-001"], "neverSentCount": 59,
                          "fresh3Score": None}})
        self.assertIsNone(cohorts["clefNativeP0"]["providerBilledUsd"])
        flash_p1 = cohorts["clefFlashP1"]
        self.assertEqual(flash_p1["source"], "public-site/clef-flash-p1-findings.json")
        self.assertEqual([flash_p1["passes"][p]["allFour"] for p in ("fresh1", "fresh2", "fresh3")],
                         [47, 47, 47])
        self.assertTrue(flash_p1["predictionVectorsStable"])
        self.assertTrue(flash_p1["nativeDistributionsStable"])
        self.assertTrue(flash_p1["vendorConfidenceStable"])
        self.assertEqual(flash_p1["matchedFresh1P0"], {
            "sharedValid": 60, "p0AllFour": 45, "p1AllFour": 47, "allFourDelta": 2,
            "becameCorrectIds": ["DEV-027", "DEV-044"], "becameIncorrectIds": []})
        self.assertEqual(flash_p1["inputTokensPerPass"],
                         {"fresh1": 144694, "fresh2": 144694, "fresh3": 144694})
        self.assertIsNone(flash_p1["providerBilledUsd"])
        p2 = cohorts["clefFlashP2"]
        self.assertEqual([p2["passes"][p]["allFour"] for p in ("fresh1", "fresh2", "fresh3")], [46, 46, 46])
        self.assertEqual(p2["matchedFresh1P1"]["allFourBecameCorrectIds"], ["DEV-058"])
        self.assertEqual(p2["matchedFresh1P1"]["allFourBecameIncorrectIds"], ["DEV-027", "DEV-032"])
        self.assertIsNone(p2["providerBilledUsd"])
        mistral_partial = cohorts["mistral119Fresh1P0"]
        self.assertEqual(mistral_partial["source"], "public-site/mistral119-fresh1-p0-findings.json")
        self.assertEqual((mistral_partial["valid"], mistral_partial["failed"],
                          mistral_partial["allFourMatches"], mistral_partial["fixed60Denominator"]),
                         (55, 5, 40, 60))
        self.assertFalse(mistral_partial["cleanRepeatabilityClaim"])
        q17 = cohorts["legacyQwen"]["qwen17FirstPass"]
        self.assertEqual([q17["scores"][p]["allFour"] for p in ("P0", "P1", "P2")], [24, 12, 8])
        self.assertEqual([q17["scores"][p]["valid"] for p in ("P0", "P1", "P2")], [60, 60, 59])
        self.assertFalse(q17["repeatabilityEstablished"])
        q17p2 = cohorts["legacyQwen"]["qwen17P2Repeat"]
        self.assertEqual([s["allFour"] for s in q17p2["scores"]], [8, 9])
        self.assertEqual(q17p2["comparison"]["denominator"], 58)
        self.assertEqual(q17p2["comparison"]["fourFieldVector"]["changed"], 30)
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
            clef_third = json.loads((ROOT / "public-site/clef-p0-third-checkpoint.json").read_text())
            for name in clef_third["sourceSha256"]:
                target = temp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            output = temp / analysis.OUTPUT
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / analysis.OUTPUT, output)
            check = subprocess.run([sys.executable, str(ROOT / "scripts/build_analysis_refresh.py"),
                                    "--root", str(temp), "--check"], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            suffix_path = temp / analysis.CLEF_FLASH_P0_SUFFIX / "records.jsonl"
            original_suffix = suffix_path.read_text()
            suffix_path.write_text(original_suffix + " ")
            with self.assertRaisesRegex(ValueError, "interruption source hash differs"):
                analysis.build(temp)
            suffix_path.write_text(original_suffix)
            record_path = temp / "results/clef-native-v1/clef/fresh1/P1/development/records.jsonl"
            original_records = record_path.read_text()
            record_path.write_text(original_records + " ")
            with self.assertRaisesRegex(ValueError, "Clef first-pass evidence hash changed"):
                analysis.build(temp)
            record_path.write_text(original_records)
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
            with self.assertRaisesRegex(ValueError, "Gemma (postabort composite|P0 checkpoint source hash)"):
                analysis.build(temp)


if __name__ == "__main__":
    unittest.main()
