import importlib.util
import copy
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
    def _qwen35_p0_only_series(self):
        report = json.loads((ROOT / "public-site/legacy-qwen-repeats.json").read_text())
        series = copy.deepcopy(next(s for s in report["series"]
                               if s["configuration"] == "qwen3.5-4b-sdk-thinking-on"))
        series["passes"] = {name: {} for name in ("fresh1", "fresh2", "fresh3")}
        series["completedConditions"] = 0
        present = {(row["pass"], row["condition"]) for row in series["missingPasses"]}
        series["missingPasses"].extend(
            {"pass": repeat, "condition": condition, "status": "not_in_closed_snapshot"}
            for repeat in series["passes"] for condition in analysis.CONDITIONS
            if (repeat, condition) not in present)
        series["pairwiseFlips"] = []
        series["changesAcrossThreePasses"] = {}
        return series

    def test_qwen35_projection_waits_for_closed_phases_and_matching_repeats(self):
        report = json.loads((ROOT / "public-site/legacy-qwen-repeats.json").read_text())
        empty = copy.deepcopy(next(s for s in report["series"]
                               if s["configuration"] == "qwen3.5-4b-sdk-thinking-on"))
        empty["passes"] = {name: {} for name in ("fresh1", "fresh2", "fresh3")}
        empty["completedConditions"] = 0
        empty["missingPasses"] = [{"pass": name, "condition": condition,
                                    "status": "not_in_closed_snapshot"}
                                   for name in empty["passes"] for condition in analysis.CONDITIONS]
        empty["partialPasses"] = []
        empty.pop("descriptiveComposites", None)
        empty["pairwiseFlips"] = []
        empty["changesAcrossThreePasses"] = {}
        result = analysis.qwen35_repeat_summary(empty)
        self.assertEqual(result["completedConditions"], 0)
        self.assertEqual(result["matchedP0AllFourDeltas"], {})
        self.assertEqual(result["conditions"]["P0"]["passes"], [])

        closed = copy.deepcopy(next(s for s in report["series"]
                                if s["configuration"] == "qwen3-1.7b-sdk-thinking-on"))
        phase = closed["passes"]["fresh1"]["P0"]
        empty["passes"]["fresh1"]["P0"] = phase
        empty["completedConditions"] = 1
        empty["missingPasses"] = [row for row in empty["missingPasses"]
                                  if (row["pass"], row["condition"]) != ("fresh1", "P0")]
        result = analysis.qwen35_repeat_summary(empty)
        self.assertEqual(result["conditions"]["P0"]["passes"][0]["score"], phase["score"])
        self.assertEqual(result["conditions"]["P0"]["passes"][0]["usage"], phase["usage"])
        self.assertEqual(result["matchedP0AllFourDeltas"], {"fresh1": {}})

        empty["passes"]["fresh1"]["P1"] = closed["passes"]["fresh1"]["P1"]
        empty["completedConditions"] = 2
        empty["missingPasses"] = [row for row in empty["missingPasses"]
                                  if (row["pass"], row["condition"]) != ("fresh1", "P1")]
        result = analysis.qwen35_repeat_summary(empty)
        self.assertEqual(result["matchedP0AllFourDeltas"]["fresh1"]["P1"],
                         closed["passes"]["fresh1"]["P1"]["score"]["allFour"] -
                         phase["score"]["allFour"])

        # Assemble two and then three P0 repeats from a saved closed schema fixture.
        empty["passes"]["fresh2"]["P0"] = closed["passes"]["fresh2"]["P0"]
        empty["completedConditions"] = 3
        empty["missingPasses"] = [row for row in empty["missingPasses"]
                                  if (row["pass"], row["condition"]) != ("fresh2", "P0")]
        with self.assertRaisesRegex(ValueError, "pairwise coverage differs"):
            analysis.qwen35_repeat_summary(empty)
        empty["pairwiseFlips"] = [pair for pair in closed["pairwiseFlips"]
                                  if pair["condition"] == "P0" and
                                  pair["from"] == "fresh1" and pair["to"] == "fresh2"]
        result = analysis.qwen35_repeat_summary(empty)
        self.assertEqual(result["conditions"]["P0"]["completedPasses"], 2)
        self.assertEqual(len(result["conditions"]["P0"]["pairwiseFlips"]), 1)
        self.assertIsNone(result["conditions"]["P0"]["changesAcrossThreePasses"])

        empty["passes"]["fresh3"]["P0"] = closed["passes"]["fresh3"]["P0"]
        empty["completedConditions"] = 4
        empty["missingPasses"] = [row for row in empty["missingPasses"]
                                  if (row["pass"], row["condition"]) != ("fresh3", "P0")]
        empty["pairwiseFlips"] = [pair for pair in closed["pairwiseFlips"]
                                  if pair["condition"] == "P0"]
        with self.assertRaisesRegex(ValueError, "three-pass coverage differs"):
            analysis.qwen35_repeat_summary(empty)
        empty["changesAcrossThreePasses"] = {
            "P0": closed["changesAcrossThreePasses"]["P0"]}
        result = analysis.qwen35_repeat_summary(empty)
        self.assertEqual(result["conditions"]["P0"]["completedPasses"], 3)
        self.assertEqual(len(result["conditions"]["P0"]["pairwiseFlips"]), 3)
        self.assertEqual(result["conditions"]["P0"]["changesAcrossThreePasses"],
                         closed["changesAcrossThreePasses"]["P0"])

    def test_qwen35_partial_projection_rejects_overlap_and_count_drift(self):
        series = self._qwen35_p0_only_series()
        projected = analysis.qwen35_repeat_summary(series)
        self.assertEqual(projected["completedConditions"], 0)
        self.assertEqual(projected["partialPasses"][0]["unknownStartedIds"], ["DEV-052"])
        self.assertEqual(len(projected["partialPasses"][0]["neverSentIds"]), 8)
        self.assertNotIn("score", projected["partialPasses"][0])

        overlap = copy.deepcopy(series)
        overlap["passes"]["fresh1"]["P0"] = {"completionStatus": "complete"}
        overlap["completedConditions"] = 1
        overlap["missingPasses"] = [item for item in overlap["missingPasses"]
                                     if (item["pass"], item["condition"]) != ("fresh1", "P0")]
        with self.assertRaisesRegex(ValueError, "partial source or counts differ"):
            analysis.qwen35_repeat_summary(overlap)

        drift = copy.deepcopy(series)
        drift["partialPasses"][0]["valid"] = 45
        with self.assertRaisesRegex(ValueError, "partial source or counts differ"):
            analysis.qwen35_repeat_summary(drift)

        unsent = copy.deepcopy(series)
        unsent["partialPasses"][0]["neverSentIds"][0] = "DEV-052"
        with self.assertRaisesRegex(ValueError, "partial source or counts differ"):
            analysis.qwen35_repeat_summary(unsent)

    def test_qwen35_descriptive_projection_keeps_clean_coverage_zero(self):
        series = self._qwen35_p0_only_series()
        partial = series["partialPasses"][0]
        exemplar = partial["evidence"]["completion"]
        keys = ("claim", "journal", "raw", "records", "completion", "review",
                "manifest", "controller", "compositeReview")
        composite = {"pass": "fresh1", "condition": "P0",
                     "status": "completed_interrupted_composite",
                     "completionStatus": "descriptive_interrupted",
                     "cleanRepeatEligible": False,
                     "score": {"denominator": 60, "valid": 51, "allFour": 20,
                               "outcomes": {"valid": 51, "invalid_output": 8,
                                            "unknown_started": 1, "never_sent": 0}},
                     "originalInterruption": partial,
                     "evidence": {key: exemplar for key in keys}}
        series["descriptiveComposites"] = [composite]
        series["missingPasses"] = [composite if (item["pass"], item["condition"]) ==
                                   ("fresh1", "P0") else item for item in series["missingPasses"]]
        projection = analysis.qwen35_repeat_summary(series)
        self.assertEqual(projection["completedConditions"], 0)
        self.assertEqual(projection["conditions"]["P0"]["passes"], [])
        self.assertEqual(projection["descriptiveComposites"][0]["score"]["allFour"], 20)

        overlap = copy.deepcopy(series)
        overlap["passes"]["fresh1"]["P0"] = {"completionStatus": "complete"}
        overlap["completedConditions"] = 1
        overlap["missingPasses"] = [item for item in overlap["missingPasses"]
                                     if (item["pass"], item["condition"]) != ("fresh1", "P0")]
        with self.assertRaisesRegex(ValueError, "partial source or counts differ"):
            analysis.qwen35_repeat_summary(overlap)

    def test_published_feed_rebuilds_from_bound_sources(self):
        expected = json.loads((ROOT / analysis.OUTPUT).read_text())
        rebuilt = analysis.build(ROOT)
        self.assertEqual(rebuilt, expected)
        self.assertEqual(len(rebuilt["sources"]), 130)
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
        self.assertTrue(q17["firstPassOnly"])
        self.assertTrue(cohorts["legacyQwen"]["qwen17RepeatStudyComplete"])
        off = cohorts["legacyQwen"]["qwen17OffFirstP0"]
        self.assertTrue(off["firstPassOnly"])
        self.assertEqual((off["score"]["valid"], off["score"]["allFour"]), (60, 28))
        self.assertEqual(off["usage"]["tokens"]["total_tokens"], 95628)
        self.assertIsNone(off["usage"]["inferenceSeconds"])
        off_prompts = cohorts["legacyQwen"]["qwen17OffFirstPass"]
        self.assertEqual([off_prompts["scores"][c]["allFour"] for c in ("P0", "P1", "P2")], [28, 25, 32])
        self.assertEqual([off_prompts["scores"][c]["valid"] for c in ("P0", "P1", "P2")], [60, 59, 57])
        pairs = off_prompts["matchedP0"]
        self.assertEqual((pairs["P1"]["sharedValid"], len(pairs["P1"]["gainedMatchIds"]), len(pairs["P1"]["lostMatchIds"])), (59, 4, 7))
        self.assertEqual((pairs["P2"]["sharedValid"], len(pairs["P2"]["gainedMatchIds"]), len(pairs["P2"]["lostMatchIds"])), (57, 9, 5))
        self.assertEqual(pairs["P2"]["validToInvalidIds"], ["DEV-002", "DEV-005", "DEV-018"])
        self.assertEqual(pairs["P2"]["previouslyCorrectNowInvalidIds"], [])
        off_repeat = cohorts["legacyQwen"]["qwen17OffRepeat"]
        self.assertEqual((off_repeat["completedConditions"], off_repeat["plannedConditions"]), (9, 9))
        self.assertEqual([off_repeat["conditions"][c]["completedPasses"] for c in ("P0", "P1", "P2")],
                         [3, 3, 3])
        self.assertEqual([[p["score"]["allFour"] for p in off_repeat["conditions"][c]["passes"]]
                          for c in ("P0", "P1", "P2")],
                         [[28, 26, 26], [25, 26, 25], [32, 30, 30]])
        self.assertEqual([[p["score"]["valid"] for p in off_repeat["conditions"][c]["passes"]]
                          for c in ("P0", "P1", "P2")],
                         [[60, 60, 60], [59, 60, 60], [57, 56, 55]])
        self.assertEqual([off_repeat["conditions"][c]["allFourRange"] for c in ("P0", "P1", "P2")],
                         [[26, 28], [25, 26], [30, 32]])
        self.assertEqual(len(off_repeat["conditions"]["P0"]["changesAcrossThreePasses"]["fourFieldVector"]), 10)
        self.assertEqual(len(off_repeat["conditions"]["P1"]["changesAcrossThreePasses"]["fourFieldVector"]), 12)
        self.assertEqual(off_repeat["conditions"]["P2"]["changesAcrossThreePasses"]["denominator"], 48)
        self.assertEqual(len(off_repeat["conditions"]["P2"]["changesAcrossThreePasses"]["fourFieldVector"]), 7)
        self.assertEqual(off_repeat["conditions"]["P2"]["pairwiseFlips"][0]["fourFieldVector"]["changed"], 5)
        self.assertEqual(off_repeat["missingPasses"], [])
        q35 = cohorts["legacyQwen"]["qwen35Repeat"]
        q35_source = next(s for s in json.loads((ROOT / "public-site/legacy-qwen-repeats.json").read_text())["series"]
                          if s["configuration"] == "qwen3.5-4b-sdk-thinking-on")
        self.assertEqual(q35["completedConditions"], q35_source["completedConditions"])
        self.assertEqual(len(q35["missingPasses"]), 9-q35["completedConditions"])
        self.assertEqual(sum(len(q35["conditions"][condition]["passes"])
                             for condition in ("P0", "P1", "P2")), q35["completedConditions"])
        q17p2 = cohorts["legacyQwen"]["qwen17P2Repeat"]
        self.assertEqual([s["allFour"] for s in q17p2["scores"]], [8, 9, 8])
        self.assertEqual(q17p2["comparison"]["denominator"], 58)
        self.assertEqual(q17p2["comparison"]["fourFieldVector"]["changed"], 30)
        self.assertEqual(q17p2["completedPasses"], 3)
        self.assertEqual(q17p2["matchedP0AllFourDeltas"], [-16, -14, -16])
        self.assertEqual(q17p2["changesAcrossThreePasses"]["denominator"], 58)
        self.assertEqual(len(q17p2["changesAcrossThreePasses"]["fourFieldVector"]), 40)
        q17p1 = cohorts["legacyQwen"]["qwen17P1Repeat"]
        self.assertEqual([s["allFour"] for s in q17p1["scores"]], [12, 11, 16])
        self.assertEqual(q17p1["comparison"]["denominator"], 60)
        self.assertEqual(q17p1["comparison"]["fourFieldVector"]["changed"], 23)
        self.assertEqual(q17p1["completedPasses"], 3)
        self.assertEqual(q17p1["matchedP0AllFourDeltas"], [-12, -12, -8])
        self.assertEqual(len(q17p1["changesAcrossThreePasses"]["fourFieldVector"]), 30)
        q17p0 = cohorts["legacyQwen"]["qwen17P0Repeat"]
        self.assertEqual([s["allFour"] for s in q17p0["scores"]], [24, 23, 24])
        self.assertEqual(q17p0["comparison"]["denominator"], 60)
        self.assertEqual(q17p0["comparison"]["fourFieldVector"]["changed"], 11)
        self.assertEqual(q17p0["completedPasses"], 3)
        self.assertEqual(len(q17p0["changesAcrossThreePasses"]["fourFieldVector"]), 19)
        self.assertEqual(len(cohorts["legacyQwen"]["completedConfigurations"]), 5)
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

    def test_qwen17_off_summary_distinguishes_stopped_smoke_from_full_phase(self):
        report = json.loads((ROOT / "public-site/legacy-qwen-repeats.json").read_text())
        series = copy.deepcopy(next(s for s in report["series"]
                                    if s["configuration"] == "qwen3-1.7b-sdk-thinking-off"))
        ninth = series["passes"]["fresh3"].pop("P2")
        full_pairs = series["pairwiseFlips"]
        series["pairwiseFlips"] = [pair for pair in full_pairs
                                   if pair["condition"] != "P2" or pair["to"] != "fresh3"]
        three_pass = series["changesAcrossThreePasses"].pop("P2")
        series["completedConditions"] = 8
        series["missingPasses"] = [{"pass": "fresh3", "condition": "P2",
                                    "status": "smoke_blocked", "stage": "smoke",
                                    "attempted": 3, "saved": 3, "valid": 2, "invalid": 1,
                                    "evidence": {"completion": "smoke.completion.json"}}]
        partial = analysis.qwen17_off_repeat_summary(series)
        self.assertEqual(partial["completedConditions"], 8)
        self.assertEqual(partial["conditions"]["P2"]["completedPasses"], 2)
        self.assertEqual(partial["missingPasses"][0]["status"], "smoke_blocked")
        series["passes"]["fresh3"]["P2"] = ninth
        series["pairwiseFlips"] = full_pairs
        series["changesAcrossThreePasses"]["P2"] = three_pass
        series["completedConditions"] = 9
        series["missingPasses"] = []
        complete = analysis.qwen17_off_repeat_summary(series)
        self.assertEqual(complete["completedConditions"], 9)
        self.assertEqual(complete["missingPasses"], [])
        self.assertEqual(complete["conditions"]["P2"]["completedPasses"], 3)
        self.assertEqual([p["score"]["allFour"] for p in complete["conditions"]["P2"]["passes"]],
                         [32, 30, 30])

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
            qwen_records = temp / "results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3-1.7b-sdk-thinking-off/fresh1/P2/development.records.jsonl"
            original_qwen = qwen_records.read_text()
            qwen_records.write_text(original_qwen + " ")
            with self.assertRaisesRegex(ValueError, "Qwen prompt-pair record hash differs"):
                analysis.build(temp)
            qwen_records.write_text(original_qwen)
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
