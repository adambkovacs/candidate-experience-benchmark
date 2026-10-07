import importlib.util
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_analysis_refresh", ROOT / "scripts/build_analysis_refresh.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)
sys.path.insert(0, str(ROOT / "scripts"))
import build_legacy_qwen_repeat_findings as legacy_qwen_findings
import build_clef_openrouter_findings as openrouter_decisions


class AnalysisRefreshTest(unittest.TestCase):
    def test_hosted_fresh_projection_keeps_interrupted_p1_out_of_comparisons(self):
        published = json.loads((ROOT / analysis.HOSTED_FRESH_PUBLIC).read_text())
        bindings = {}
        result = analysis.hosted_fresh_summary(ROOT, published, bindings)
        qwen, deepseek = result["qwen36On"], result["deepseekHigh"]
        self.assertEqual((qwen["scores"]["P0"]["allFour"],
                          qwen["scores"]["P2"]["allFour"],
                          qwen["matchedP0P2AllFourDelta"]), (54, 56, 2))
        self.assertFalse(qwen["interruptedP1"]["cleanComparisonEligible"])
        self.assertFalse(qwen["cleanMatchedThreeEligible"])
        repeats = qwen["repeatability"]
        self.assertEqual(repeats['P1']['passes'], ['fresh2', 'fresh3'])
        self.assertEqual(repeats['P0']['allFourScores'], [54, 53, 51])
        self.assertEqual(repeats['P2']['allFourScores'], [56, 56, 54])
        self.assertEqual({condition: len(row['changedReviewIds'])
                          for condition, row in repeats.items()}, {'P0': 5, 'P1': 6, 'P2': 7})
        self.assertTrue(all(row['denominator'] == 60 for row in repeats.values()))
        self.assertTrue(all(not row['changedByField']['follow_up_needed']
                            for row in repeats.values()))
        self.assertEqual(len(qwen["closedCells"]), qwen["completedCleanConditions"])
        class_audit = qwen["fieldClassAudit"]
        self.assertEqual(len(class_audit), 9)
        self.assertEqual(sum(row["cleanComparisonEligible"] for row in class_audit), 8)
        first_p0 = next(row for row in class_audit if
                        (row["pass"], row["condition"]) == ("fresh1", "P0"))
        testimonial_yes = next(row for row in first_p0["fields"]["testimonial_potential"]["classes"]
                               if row["reference"] == "yes")
        self.assertEqual(testimonial_yes, {"reference": "yes", "total": 9,
            "correct": 7, "wrong": 2, "unavailable": 0,
            "wrongPredictions": {"no": 2}})
        first_p1 = next(row for row in class_audit if
                        (row["pass"], row["condition"]) == ("fresh1", "P1"))
        self.assertEqual((first_p1["valid"], first_p1["unusable"],
                          first_p1["unusableIds"]), (59, 1, ["DEV-049"]))
        follow_up_yes = next(row for row in first_p1["fields"]["follow_up_needed"]["classes"]
                             if row["reference"] == "yes")
        self.assertEqual((follow_up_yes["total"], follow_up_yes["unavailable"]), (35, 1))
        self.assertEqual(qwen["interruptedP1"]["unusableIds"], ["DEV-049"])
        self.assertTrue({"fresh1/P0", "fresh1/P2", "fresh2/P0", "fresh2/P1", "fresh2/P2", "fresh3/P2"}.issubset(qwen["closedCells"]))
        self.assertEqual(next(row["allFour"] for row in qwen["closedPhases"]
                              if row["pass"] == "fresh2" and row["condition"] == "P2"), 56)
        self.assertTrue({("fresh1", "P2", 2), ("fresh2", "P1", 1),
                         ("fresh2", "P2", 3)}.issubset({
            (row["pass"], row["to"], row["allFourDelta"])
            for row in qwen["matchedPromptComparisons"]}))
        self.assertEqual((deepseek["allFour"], deepseek["valid"],
                          deepseek["invalidIds"]), (57, 59, ["DEV-030"]))
        self.assertFalse(deepseek["firstP0AloneSupportsPromptComparison"])
        self.assertEqual(deepseek["closedCells"], ["fresh1/P0", "fresh1/P1"])
        self.assertEqual(deepseek["matchedPromptComparisons"], [{
            "pass": "fresh1", "from": "P0", "to": "P1", "allFourDelta": 0,
            "allFour": {"P0": 57, "P1": 57},
            "invalidIds": {"P0": ["DEV-030"], "P1": ["DEV-006"]},
            "denominator": 60}])
        revised = result["deepseekHighRevisedPrice"]
        self.assertIn("fresh1/P2", revised["closedCells"])
        self.assertEqual((revised["closedPhases"][0]["valid"],
                          revised["closedPhases"][0]["allFour"]), (60, 58))
        self.assertFalse(revised["comparisonWithOriginalConfigurationEligible"])
        self.assertIn("results/repeatability-v1/deepseek-high-authority-v3/"
                      "fresh1/P0/closure.root-review.json", bindings)
        self.assertTrue(any("closure-ledger-snapshot.jsonl" in path or
                            "budget-at-fresh1-p2-closure.jsonl" in path
                            for path in bindings))

    def test_hosted_fresh_projection_rejects_changed_scores_and_coverage(self):
        published = json.loads((ROOT / analysis.HOSTED_FRESH_PUBLIC).read_text())
        changed = copy.deepcopy(published)
        qwen = next(item for item in changed["series"] if "qwen36" in item["configuration"])
        qwen["passes"]["fresh1"]["P2"]["score"]["allFour"] += 1
        with self.assertRaisesRegex(ValueError, "differs from closed evidence"):
            analysis.hosted_fresh_summary(ROOT, changed, {})
        changed = copy.deepcopy(published)
        qwen = next(item for item in changed["series"] if "qwen36" in item["configuration"])
        qwen["completedConditions"] += 1
        with self.assertRaisesRegex(ValueError, "differs from closed evidence"):
            analysis.hosted_fresh_summary(ROOT, changed, {})

    def test_hosted_qwen_class_audit_rejects_inconsistent_confusion(self):
        import build_deepseek_high_remaining7_price_findings as hosted_builder
        changed = json.loads((ROOT / analysis.HOSTED_FRESH_PUBLIC).read_text())
        qwen = next(item for item in changed["series"] if "qwen36" in item["configuration"])
        qwen["passes"]["fresh1"]["P0"]["score"]["confusionCounts"][
            "testimonial_potential"]["yes"]["no"] += 1
        with patch.object(hosted_builder, "build", return_value=changed):
            with self.assertRaisesRegex(ValueError, "reference class denominator differs|field confusion differs"):
                analysis.hosted_fresh_summary(ROOT, changed, {})

    def test_hosted_fresh_projection_accepts_additional_rebuilt_closed_cells(self):
        import build_deepseek_high_remaining7_price_findings as hosted_builder
        future = copy.deepcopy(json.loads((ROOT / analysis.HOSTED_FRESH_PUBLIC).read_text()))
        qwen = next(item for item in future["series"] if "qwen36" in item["configuration"])
        deepseek = next(item for item in future["series"] if "high-authority-v3" in item["configuration"])
        added_pass, added_condition = "synthetic-future", "P0"
        qwen["passes"][added_pass] = {}
        qwen["plannedConditions"] += 1
        previous_qwen_count = qwen["completedConditions"]
        qwen["passes"][added_pass][added_condition] = copy.deepcopy(qwen["passes"]["fresh1"]["P0"])
        qwen["completedConditions"] += 1
        deepseek["passes"]["fresh1"]["P2"] = copy.deepcopy(deepseek["passes"]["fresh1"]["P0"])
        deepseek["passes"]["fresh1"]["P2"]["status"] = "completed"
        deepseek["completedConditions"] += 1
        with patch.object(hosted_builder, "build", return_value=future):
            result = analysis.hosted_fresh_summary(ROOT, future, {})
        self.assertEqual(result["qwen36On"]["completedCleanConditions"], previous_qwen_count + 1)
        self.assertIn(f"{added_pass}/{added_condition}", result["qwen36On"]["closedCells"])
        self.assertEqual(len(result["qwen36On"]["fieldClassAudit"]),
                         len(result["qwen36On"]["closedPhases"]) + 1)
        self.assertTrue({("fresh2", "P1", 1), ("fresh2", "P2", 3)}.issubset({
            (row["pass"], row["to"], row["allFourDelta"])
            for row in result["qwen36On"]["matchedPromptComparisons"]}))
        self.assertEqual(result["deepseekHigh"]["completedConditions"], 3)
        self.assertIn("fresh1/P2", result["deepseekHigh"]["closedCells"])

    def test_gemini_authority_projection_rebuilds_nine_closed_conditions(self):
        published = json.loads((ROOT / analysis.GEMINI_AUTHORITY_PUBLIC).read_text())
        bindings = {}
        result = analysis.gemini_authority_summary(ROOT, published, bindings)
        self.assertEqual(result["completedConditions"], 9)
        self.assertEqual(result["conditions"]["P0"]["allFourScores"], [55, 56, 56])
        self.assertEqual(result["conditions"]["P1"]["allFourScores"], [56, 56, 56])
        self.assertEqual(result["conditions"]["P2"]["allFourScores"], [55, 56, 56])
        self.assertEqual(result["conditions"]["P1"]["changedReviewIds"], ["DEV-030"])
        self.assertEqual([result["matchedP0"][name]["P1"]["allFourDelta"]
                          for name in ("original", "repeat2", "repeat3")], [1, 0, 0])
        self.assertIn("results/repeatability-v1/gemini31-high-authority-v2/"
                      "gemini31-pro-preview-high-p0-openrouter-v3/repeat3/P1/closure.review.json",
                      bindings)

    def test_gemini_authority_rejects_changed_feed_and_incomplete_coverage(self):
        published = json.loads((ROOT / analysis.GEMINI_AUTHORITY_PUBLIC).read_text())
        changed = copy.deepcopy(published)
        series = next(item for item in changed["series"] if item.get("configuration") ==
                      "gemini31-pro-preview-high-p0-openrouter-v3")
        series["passes"]["repeat3"]["P1"]["score"]["allFour"] += 1
        with self.assertRaisesRegex(ValueError, "differs from closed evidence"):
            analysis.gemini_authority_summary(ROOT, changed, {})
        incomplete = copy.deepcopy(published)
        series = next(item for item in incomplete["series"] if item.get("configuration") ==
                      "gemini31-pro-preview-high-p0-openrouter-v3")
        series["completedConditions"] = 8
        with self.assertRaisesRegex(ValueError, "differs from closed evidence"):
            analysis.gemini_authority_summary(ROOT, incomplete, {})

    def test_qwen35_new_missing_smokes_remain_bound_and_unscored(self):
        report = legacy_qwen_findings.build()
        series = next(row for row in report["series"]
                      if row["configuration"] == "qwen3.5-4b-sdk-thinking-on")
        projected = analysis.qwen35_repeat_summary(series)
        self.assertEqual(projected["completedConditions"], 3)
        self.assertEqual(sum(len(row["passes"]) for row in projected["conditions"].values()), 3)
        missing = {(row["pass"], row["condition"]): row for row in projected["missingPasses"]}
        p1, p2 = missing["fresh2", "P1"], missing["fresh2", "P2"]
        self.assertEqual((p1["status"], p1["saved"], p1["unknownStartedIds"]),
                         ("stopped_unknown", 2, ["DEV-003"]))
        self.assertFalse(p1["intrinsicModelFailure"])
        self.assertEqual((p2["status"], p2["valid"], p2["invalid"]),
                         ("smoke_blocked", 2, 1))
        self.assertTrue(p2["intrinsicModelFailure"])
        for item in (p1, p2):
            self.assertFalse(item["developmentAdmitted"])
            self.assertFalse(item["cleanRepeatEligible"])
            self.assertNotIn("score", item)

        for slot, change in ((("fresh2", "P1"), ("saved", 3)),
                             (("fresh2", "P1"), ("unknownStartedIds", [])),
                             (("fresh2", "P2"), ("intrinsicModelFailure", False)),
                             (("fresh2", "P2"), ("score", {"allFour": 2}))):
            with self.subTest(slot=slot, change=change):
                altered = copy.deepcopy(series)
                item = next(row for row in altered["missingPasses"]
                            if (row["pass"], row["condition"]) == slot)
                item[change[0]] = change[1]
                with self.assertRaises(ValueError):
                    analysis.qwen35_repeat_summary(altered)

        altered = copy.deepcopy(series)
        item = next(row for row in altered["missingPasses"]
                    if (row["pass"], row["condition"]) == ("fresh2", "P1"))
        item["evidence"]["smoke"]["completion"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "interrupted continuation smoke differs"):
            analysis.qwen35_repeat_summary(altered)

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

    def test_kev_projection_rejects_missing_pass_and_unbound_phase_source(self):
        report = json.loads((ROOT / analysis.KEV_NATIVE_PROMPT_PUBLIC).read_text())
        missing = copy.deepcopy(report)
        missing["conditions"]["P2"]["passes"].pop("fresh3")
        with self.assertRaisesRegex(ValueError, "Kev P2 repeat coverage differs"):
            analysis.kev_native_prompt_summary(ROOT, missing, {})

        unbound = copy.deepcopy(report)
        phase_source = unbound["conditions"]["P1"]["passes"]["fresh1"]["sourceBindings"][0]
        unbound["sourceBindings"] = [item for item in unbound["sourceBindings"]
                                     if item["path"] != phase_source["path"]]
        with self.assertRaisesRegex(ValueError, "Kev P1 fresh1 source subset differs"):
            analysis.kev_native_prompt_summary(ROOT, unbound, {})

    def test_jev_projection_keeps_invalid_and_stopped_states(self):
        report = json.loads((ROOT / analysis.JEV_NATIVE_PROMPT_PUBLIC).read_text())
        projected = analysis.jev_native_prompt_summary(ROOT, report, {})
        self.assertEqual(projected["denominator"], 60)
        self.assertEqual(projected["conditions"]["P1"]["completePasses"], 3)
        self.assertEqual(projected["conditions"]["P0"]["completePasses"], 3)
        self.assertEqual([p["score"]["allFour"] for p in projected["conditions"]["P0"]["passes"].values()], [54, 53, 52])
        composite = projected["composites"]["P2fresh2"]
        self.assertEqual(composite["score"]["valid"], 57)
        self.assertEqual(composite["score"]["allFour"], 50)
        self.assertFalse(composite["cleanRepeatCredit"])
        self.assertEqual(composite["neverSent"], 0)
        self.assertEqual(composite["unknownUpperBoundUsd"], "0.002688000")
        self.assertEqual(projected["conditions"]["P2"]["completePasses"], 2)
        p1 = projected["conditions"]["P1"]["passes"]["fresh2"]
        self.assertEqual((p1["score"]["valid"], p1["score"]["allFour"]), (59, 53))
        self.assertEqual(p1["outcomes"]["invalid_native_distribution"], 1)
        self.assertFalse(p1["cleanRepeatEligible"])
        p2 = projected["conditions"]["P2"]["passes"]["fresh2"]
        self.assertEqual(p2["status"], "stopped")
        self.assertEqual(p2["outcomes"], {"valid": 17, "unknown_cost_http_429": 1,
                                           "never_sent": 42})
        self.assertIsNone(projected["partialBoundary"]["P2fresh2"]["fullPassScore"])
        self.assertEqual(projected["comparisons"]["P1repeat"]["denominator"], 59)
        self.assertEqual(projected["comparisons"]["P1P2fresh1"]["fourFieldVectorChangedIds"],
                         ["DEV-013"])

    def test_jev_projection_rejects_laundered_invalid_and_partial_completion(self):
        report = json.loads((ROOT / analysis.JEV_NATIVE_PROMPT_PUBLIC).read_text())
        invalid = copy.deepcopy(report)
        invalid["passes"]["P1"]["fresh2"]["score"]["valid"] = 60
        with self.assertRaisesRegex(ValueError, "Jev P1 fresh2 outcome differs"):
            analysis.jev_native_prompt_summary(ROOT, invalid, {})
        partial = copy.deepcopy(report)
        partial["passes"]["P2"]["fresh2"]["status"] = "complete"
        with self.assertRaisesRegex(ValueError, "Jev P2 fresh2 outcome differs"):
            analysis.jev_native_prompt_summary(ROOT, partial, {})
        missing = copy.deepcopy(report)
        missing["sourceBindings"] = [item for item in missing["sourceBindings"]
                                     if not item["path"].endswith("fresh2/terminal-public.json")]
        with self.assertRaisesRegex(ValueError, "Jev native prompt source closure differs"):
            analysis.jev_native_prompt_summary(ROOT, missing, {})
        missing_child = copy.deepcopy(report)
        missing_child["sourceBindings"] = [item for item in missing_child["sourceBindings"]
            if not item["path"].endswith(
                "fresh2.budget-jev-openrouter-native-p2-choice-v1-fresh2-full-v1.jsonl")]
        with self.assertRaisesRegex(ValueError, "Jev native prompt source closure differs"):
            analysis.jev_native_prompt_summary(ROOT, missing_child, {})
        drift = copy.deepcopy(report)
        drift["sourceBindings"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Jev native prompt report source hash differs"):
            analysis.jev_native_prompt_summary(ROOT, drift, {})

    def test_nested_report_source_binding_rejects_byte_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "evidence/attempts.jsonl"
            source.parent.mkdir(parents=True)
            source.write_text('{"id":"DEV-001"}\n')
            report = {"sourceBindings": [{"path": "evidence/attempts.jsonl",
                                           "sha256": analysis.sha(source)}]}
            bindings = {}
            analysis.bind_report_sources(root, report, bindings, "fixture")
            self.assertEqual(bindings["evidence/attempts.jsonl"], analysis.sha(source))
            source.write_text(source.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "fixture source hash differs"):
                analysis.bind_report_sources(root, report, {}, "fixture")

    def test_published_feed_rebuilds_from_bound_sources(self):
        expected = json.loads((ROOT / analysis.OUTPUT).read_text())
        rebuilt = analysis.build(ROOT)
        self.assertEqual(rebuilt, expected)
        self.assertGreaterEqual(len(rebuilt["sources"]), 507)
        self.assertIn(analysis.GEMINI_AUTHORITY_PUBLIC,
                      {item["path"] for item in rebuilt["sources"]})
        solar = rebuilt["newerCohorts"]["solarFullSeries"]
        solar_sources = [item["path"] for item in rebuilt["sources"]
                         if "solar-decide" in item["path"]]
        self.assertFalse(any(path.endswith(("smoke.raw.jsonl", "smoke.parsed.jsonl",
                                           "smoke.attempts.jsonl", "smoke.journal.jsonl"))
                             for path in solar_sources))
        self.assertEqual(len(solar["stages"]), 9)
        self.assertEqual(sum(stage["valid_answers"] for stage in solar["stages"]), 539)
        self.assertEqual(sum(stage["valid_answers"] == 60 for stage in solar["stages"]), 8)
        final = next(stage for stage in solar["stages"] if stage["stage"] == "fresh3/P2")
        self.assertEqual(final["unusable_ids"], ["DEV-009"])
        for pair in solar["repeat_comparisons"] + solar["matched_prompt_comparisons"]:
            self.assertEqual(pair["paired_records"],
                             59 if "fresh3/P2" in (pair["left"], pair["right"]) else 60)
        self.assertEqual(solar["child_all_requests"]["original_unknown_upper_bound_usd"], "0.10485760")
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
        clef_closed = cohorts["clefClosedRepeats"]
        self.assertEqual((clef_closed["declaredCells"], clef_closed["completeCleanCells"],
                          clef_closed["interruptedCells"]), (9, 7, 2))
        self.assertEqual(clef_closed["p0Scores"], [53, 53, 53])
        self.assertEqual(clef_closed["p0RepeatChanged"], [0, 0, 0])
        self.assertEqual(clef_closed["p1Scores"], [52, 51, 51])
        self.assertEqual([pair["changed"] for pair in clef_closed["p1RepeatFlips"]], [1, 1, 0])
        self.assertEqual(clef_closed["cleanP2"], {"repeat": "fresh2", "valid": 60, "allFour": 49})
        self.assertEqual([(row["valid"], row["unknownOutcome"], row["neverSent"], row["cleanScore"])
                          for row in clef_closed["interruptedP2"]],
                         [(59, 1, 0, None), (0, 1, 59, None)])
        self.assertTrue({analysis.CLEF_CLOSED, analysis.CLEF_CLOSED_PUBLIC}.issubset(
            {item["path"] for item in rebuilt["sources"]}))
        e4b = cohorts["e4bInterrupted"]
        self.assertEqual(e4b["score"]["allFour"], 48)
        self.assertEqual(e4b["score"]["valid"], 58)
        self.assertEqual(e4b["unknownIds"], ["DEV-039", "DEV-052"])
        self.assertEqual(e4b["neverSentIds"], [])
        self.assertFalse(e4b["cleanRepeatEligible"])
        self.assertEqual(e4b["usage"]["tokens"]["total"], 184124)
        kev = cohorts["kevNativePrompts"]
        jev = cohorts["jevNativePrompts"]
        self.assertEqual(jev["source"], analysis.JEV_NATIVE_PROMPT_PUBLIC)
        self.assertEqual(jev["conditions"]["P1"]["passes"]["fresh2"]["score"]["allFour"], 53)
        self.assertEqual(jev["conditions"]["P2"]["passes"]["fresh2"]["status"], "stopped")
        self.assertEqual(kev["source"], analysis.KEV_NATIVE_PROMPT_PUBLIC)
        self.assertTrue(kev["nativePromptEquivalence"]["verified"])
        self.assertEqual(kev["conditions"]["P1"]["scores"], [49, 49, 49])
        self.assertEqual(kev["conditions"]["P2"]["scores"], [46, 46, 46])
        self.assertEqual(kev["conditions"]["P1"]["fields"]["follow_up_needed"],
                         [58, 58, 58])
        self.assertEqual(kev["conditions"]["P2"]["fields"]["follow_up_needed"],
                         [53, 53, 53])
        self.assertEqual(kev["conditions"]["P1"]["changedFourFieldVectorIdsAcrossRepeats"], [])
        self.assertEqual(kev["conditions"]["P2"]["changedFourFieldVectorIdsAcrossRepeats"], [])
        self.assertEqual(kev["matchedP1P2"]["changedFourFieldVectorIds"],
                         ["DEV-001", "DEV-005", "DEV-022", "DEV-030",
                          "DEV-035", "DEV-041", "DEV-059"])
        self.assertEqual(kev["matchedP1P2"]["scoreDeltaP2MinusP1"], {
            "allFour": -3, "fields": {"sentiment": 1, "follow_up_needed": -5,
                "serious_concern_reported": 0, "testimonial_potential": 1}})
        self.assertEqual(kev["historicalP0"], {
            "scope": "separate descriptive baseline", "cleanPasses": ["fresh1", "fresh2"],
            "scores": [48, 48], "interruptedThirdExcluded": True})
        self.assertEqual(kev["conditions"]["P1"]["usage"]["actualProviderCostUsd"],
                         "0.015622236")
        self.assertEqual(kev["conditions"]["P2"]["usage"]["actualProviderCostUsd"],
                         "0.016914996")
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
        published = analysis.build(ROOT)
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
            decision_receipt = json.loads((ROOT / openrouter_decisions.RECEIPT).read_text())
            for name in openrouter_decisions.flash_composite_public_sources():
                self.assertIn(name, decision_receipt["source_sha256"])
                target = temp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            output = temp / analysis.OUTPUT
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(published, indent=2, sort_keys=True,
                                         ensure_ascii=False) + "\n")
            check = subprocess.run([sys.executable, str(ROOT / "scripts/build_analysis_refresh.py"),
                                    "--root", str(temp), "--check"], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            clef_public = temp / analysis.CLEF_CLOSED_PUBLIC
            original_clef_public = clef_public.read_bytes()
            clef_public.write_bytes(original_clef_public + b" ")
            with self.assertRaisesRegex(ValueError, "Clef closed repeat public copy differs"):
                analysis.build(temp)
            clef_public.write_bytes(original_clef_public)
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
            kev_attempts = temp / ("results/route-audits/native-variants-full-v1-20261006/"
                                   "kev-openrouter-native-p1-choice-v1/fresh1/attempts.jsonl")
            original_kev = kev_attempts.read_text()
            kev_attempts.write_text(original_kev + " ")
            with self.assertRaisesRegex(ValueError, "Kev native prompt report source hash differs"):
                analysis.build(temp)
            kev_attempts.write_text(original_kev)
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
