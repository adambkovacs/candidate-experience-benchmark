#!/usr/bin/env python3
"""Build a compact, offline analysis of published benchmark evidence.

The output is descriptive. Each response scores the same 60 development reviews;
repeat cells are never treated as independent reviews.
"""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "public-site/analysis-refresh.json"
MISTRAL_ORIGINAL = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-development-none-v1/fresh1/P0/development.terminal-public.json"
MISTRAL_FIRST_SUFFIX = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-remaining-none-v1/fresh1/P0-suffix-049-060/suffix.terminal-public.json"
MISTRAL_SECOND_SUFFIX = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-second-suffix-none-v1/fresh1/P0/suffix.terminal-public.json"
GEMMA_TERMINAL = "results/repeatability-v1/gemma26-on-fresh-matched3-v2/third-interruption-continuation-v1/terminal-public-after-dev006.json"
SOURCES = (
    "public-site/sonnet55-fresh-matched3.json",
    "public-site/sonnet55-fresh-matched3-evidence/report.json",
    "public-site/claude-roster-repeats.json",
    "public-site/claude-repeats.json",
    "public-site/haiku-fresh-matched3.json",
    "public-site/findings.json",
    "public-site/subscription-price-estimates.json",
    "public-site/qwen27-final-descriptive-findings.json",
    "public-site/legacy-qwen-repeats.json",
    "public-site/deepseek-low-third-interruption-findings.json",
    "public-site/gemma26-second-continuation-findings.json",
    "public-site/gemma26-postabort-findings.json",
    "public-site/gemma26-p2-repeat-findings.json",
    "public-site/gemma26-fresh3-p0-checkpoint.json",
    "public-site/clef-findings.json",
    "public-site/clef-p0-repeat-findings.json",
    "public-site/clef-p0-third-checkpoint.json",
    MISTRAL_ORIGINAL,
    MISTRAL_FIRST_SUFFIX,
    MISTRAL_SECOND_SUFFIX,
    GEMMA_TERMINAL,
    "data/pilot/proposed_labels.jsonl",
)
EFFORTS = ("low", "medium", "high", "xhigh")
CONDITIONS = ("P0", "P1", "P2")
PASSES = ("pass1", "pass2", "pass3")
FIELDS = ("sentiment", "follow_up_needed", "serious_concern_reported", "testimonial_potential")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(root, name, bindings):
    path = root / name
    bindings[name] = sha(path)
    return json.loads(path.read_text())


def score_values(series, condition):
    return series["threePassSummary"][condition]["allFour"]["values"]


def _class_hits(root, public_report, labels, bindings):
    """Recheck public records, their hashes, and the reporter's cell scores."""
    result = {}
    for effort in EFFORTS:
        result[effort] = {}
        for condition in CONDITIONS:
            vals = {field: {label: [] for label in counts}
                    for field, counts in public_report["referenceClassCounts"].items()}
            for repeat in PASSES:
                cell = public_report["cells"][effort][repeat][condition]["development"]
                assert cell["state"] == "complete"
                source = cell["evidence"]["records"]
                path = source["path"]
                actual = sha(root / path)
                if actual != source["sha256"]:
                    raise ValueError(f"Public Sonnet records changed: {path}")
                bindings[path] = actual
                rows = [json.loads(line) for line in (root / path).read_text().splitlines()]
                if len(rows) != 60 or set(row["id"] for row in rows) != set(labels):
                    raise ValueError(f"Wrong Sonnet record membership: {path}")
                hits = {field: Counter() for field in FIELDS}
                all_four = 0
                for row in rows:
                    if row.get("status") != "ok":
                        raise ValueError(f"Nonvalid Sonnet result in {path}")
                    ref = labels[row["id"]]
                    prediction = row["prediction"]
                    for field in FIELDS:
                        if prediction[field] == ref[field]:
                            hits[field][ref[field]] += 1
                    all_four += all(prediction[field] == ref[field] for field in FIELDS)
                if all_four != cell["score"]["allFour"] or any(
                    sum(hits[field].values()) != cell["score"]["fields"][field] for field in FIELDS
                ):
                    raise ValueError(f"Sonnet evidence and public score differ: {path}")
                for field in FIELDS:
                    for label in vals[field]:
                        vals[field][label].append(hits[field][label])
            result[effort][condition] = vals
    return result


def build(root=ROOT):
    bindings = {}
    data = {name: read(root, name, bindings) for name in SOURCES if not name.endswith(".jsonl")}
    labels_path = "data/pilot/proposed_labels.jsonl"
    bindings[labels_path] = sha(root / labels_path)
    rows = [json.loads(line) for line in (root / labels_path).read_text().splitlines()]
    labels = {row["id"]: row["proposed_labels"] for row in rows}
    if len(labels) != 60 or any(row["review_version"] != "0.2" for row in rows):
        raise ValueError("Expected 60 frozen v0.2 references")

    sonnet = data["public-site/sonnet55-fresh-matched3.json"]
    public_report = data["public-site/sonnet55-fresh-matched3-evidence/report.json"]
    if (sonnet["completedCells"] != 36 or sonnet["plannedCells"] != 36 or
            public_report["completedCells"] != 36 or
            public_report["threePassSummary"] != sonnet["threePassSummary"]):
        raise ValueError("Sonnet published feed and evidence report differ")
    class_hits = _class_hits(root, public_report, labels, bindings)
    manifest_controls = None
    for effort in EFFORTS:
        for repeat in PASSES:
            path = ("public-site/sonnet55-fresh-matched3-evidence/evidence/results/"
                    f"repeatability-v1/claude-sonnet55-fresh-matched3-v2/{effort}/{repeat}/manifest.json")
            manifest = read(root, path, bindings)
            controls = {key: manifest[key] for key in ("model", "batch_size", "timeout_seconds",
                "runtime_required", "seed_policy", "prompt_source", "reference_labels_read")}
            if manifest["effort"] != effort or manifest["pass"] != repeat:
                raise ValueError(f"Sonnet manifest identity differs: {path}")
            if manifest_controls is None:
                manifest_controls = controls
            elif manifest_controls != controls:
                raise ValueError(f"Sonnet control drift across fresh passes: {path}")
    by_effort = {}
    for effort in EFFORTS:
        conditions = {}
        usage = Counter()
        estimated = Decimal(0)
        client_seconds = 0.0
        cli_api_seconds = 0.0
        for condition in CONDITIONS:
            scores = sonnet["threePassSummary"][effort][condition]["allFour"]["values"]
            if len(scores) != 3:
                raise ValueError("Sonnet missing a full matched pass")
            changed_ids = sorted({rid for flip in sonnet["pairwiseFlips"]
                                  if flip["effort"] == effort and flip["condition"] == condition
                                  for rid in flip["fourFieldVector"]["caseIds"]})
            fields = {field: sonnet["threePassSummary"][effort][condition]["fields"][field]["values"]
                      for field in FIELDS}
            conditions[condition] = {
                "scores": scores, "range": [min(scores), max(scores)],
                "mean": sum(scores) / 3, "fields": fields,
                "changedReviewIds": changed_ids, "changedReviewCount": len(changed_ids),
                "classHits": class_hits[effort][condition],
            }
            for repeat in PASSES:
                cell = sonnet["cells"][effort][repeat][condition]["development"]
                if cell["score"]["valid"] != 60:
                    raise ValueError("Sonnet full cell has invalid records")
                u = cell["usage"]
                usage.update(u["tokens"])
                estimated += Decimal(u["calculatedApiEquivalentUsd"])
                client_seconds += u["requestSecondsTotal"]
                cli_api_seconds += u["cliReportedApiSeconds"]
        deltas = {}
        for condition in ("P1", "P2"):
            values = [item["allFour"] for item in sonnet["withinPassPromptDeltas"]
                      if item["effort"] == effort and item["to"] == condition]
            if len(values) != 3:
                raise ValueError("Sonnet prompt delta triplet absent")
            expected = [conditions[condition]["scores"][i] - conditions["P0"]["scores"][i]
                        for i in range(3)]
            if values != expected:
                raise ValueError("Sonnet prompt delta differs from cells")
            deltas[condition] = {"values": values, "range": [min(values), max(values)]}
        by_effort[effort] = {
            "conditions": conditions, "promptDeltas": deltas,
            "usage": {"developmentApiEquivalentUsd": str(estimated),
                      "outputTokens": usage["output_tokens"],
                      "reportedThinkingTokens": usage["thinking_tokens"],
                      "inputTokens": usage["input_tokens"],
                      "cacheWriteTokens": usage["cache_creation_input_tokens"],
                      "cacheReadTokens": usage["cache_read_input_tokens"],
                      "clientRequestSecondsSum": round(client_seconds, 6),
                      "cliReportedApiSecondsSum": round(cli_api_seconds, 6)},
        }

    roster = data["public-site/claude-roster-repeats.json"]["series"]
    opus = data["public-site/claude-repeats.json"]
    haiku = data["public-site/haiku-fresh-matched3.json"]
    if len(roster) != 15:
        raise ValueError("Claude historical roster changed")
    historical = roster + [opus, haiku]
    pricing = data["public-site/subscription-price-estimates.json"]
    if len({item["configuration"] for item in historical}) != 17:
        raise ValueError("Claude historical cohort is not 17 distinct configurations")
    claude_rows = []
    for item in historical:
        first_pass = next(iter(item["passes"]))
        if item["completedConditions"] != 9:
            raise ValueError("Claude historical matched series incomplete")
        spread = {condition: item["pairedDeltaSpread"][condition]["allFourValues"]
                  for condition in ("P1", "P2")}
        claude_rows.append({"configuration": item["configuration"], "model": item["model"],
                            "effort": item["effort"], "seriesKind": "historical_first_plus_two_repeats"
                            if first_pass == "original" else "fresh_matched_three",
                            "scores": {condition: score_values(item, condition) for condition in CONDITIONS},
                            "promptDeltas": spread,
                            "apiEquivalentEstimate": {
                                key: pricing["repeatSeries"][item["configuration"]][key]
                                for key in ("estimatedUsdForPricedPhases", "fullSeriesEstimateUsd",
                                            "pricedPhases", "totalPhases")},
                            "allThreePassPromptGain": {condition: all(v > 0 for v in spread[condition])
                                                       for condition in ("P1", "P2")}})
    for effort in EFFORTS:
        claude_rows.append({"configuration": f"claude-sonnet-5-5-{effort}-v2",
                            "model": sonnet["model"], "effort": effort,
                            "seriesKind": "fresh_matched_three_v2_claude_cli",
                            "scores": {condition: by_effort[effort]["conditions"][condition]["scores"]
                                       for condition in CONDITIONS},
                            "promptDeltas": {condition: by_effort[effort]["promptDeltas"][condition]["values"]
                                             for condition in ("P1", "P2")},
                            "allThreePassPromptGain": {condition: all(v > 0 for v in
                                by_effort[effort]["promptDeltas"][condition]["values"])
                                for condition in ("P1", "P2")}})

    qwen = data["public-site/qwen27-final-descriptive-findings.json"]
    legacy_qwen = data["public-site/legacy-qwen-repeats.json"]
    deepseek = data["public-site/deepseek-low-third-interruption-findings.json"]
    gemma = data["public-site/gemma26-second-continuation-findings.json"]
    gemma_postabort = data["public-site/gemma26-postabort-findings.json"]
    gemma_p2_repeat = data["public-site/gemma26-p2-repeat-findings.json"]
    gemma_p0 = data["public-site/gemma26-fresh3-p0-checkpoint.json"]
    if (gemma_p0.get("schema") != "gemma26-on-v2-fresh3-checkpoint-v1" or
            gemma_p0.get("cutoff") != "P0" or gemma_p0.get("scoredSeriesConditions") != 8 or
            gemma_p0.get("denominator") != 60 or gemma_p0.get("cleanMatchedThreeEligible") is not False):
        raise ValueError("Gemma P0 checkpoint differs from reviewed sources")
    for item in gemma_p0["sourceBindings"]:
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts or sha(root / path) != item["sha256"]:
            raise ValueError("Gemma P0 checkpoint source hash differs")
        bindings[item["path"]] = item["sha256"]
    clef = data["public-site/clef-findings.json"]
    clef_repeat = data["public-site/clef-p0-repeat-findings.json"]
    clef_third = data["public-site/clef-p0-third-checkpoint.json"]
    mistral_original = data[MISTRAL_ORIGINAL]
    mistral_first = data[MISTRAL_FIRST_SUFFIX]
    mistral_second = data[MISTRAL_SECOND_SUFFIX]
    gemma_terminal = data[GEMMA_TERMINAL]
    if (mistral_original["status"] != "interrupted_unscored" or
            mistral_first["status"] != "interrupted_unscored" or
            mistral_second["status"] != "interrupted_unscored" or
            gemma_terminal["status"] != "stopped_unscored"):
        raise ValueError("Expected retained unscored interruption states")
    new_gemma = gemma_postabort.get("fresh3P2") or {}
    new_score = new_gemma.get("score") or {}
    gemma_usage = gemma_postabort.get("compositeUsage") or {}
    if (gemma_postabort.get("schema") != "gemma26-on-v2-postabort-findings-v1" or
            gemma_postabort.get("completedConditions") != 7 or
            gemma_postabort.get("priorCompletedConditions") != 6 or
            gemma_postabort.get("plannedConditions") != 9 or
            gemma_postabort.get("cleanMatchedThreeEligible") is not False or
            new_gemma.get("status") != "completed_composite_interrupted" or
            new_gemma.get("failedIds") != ["DEV-005", "DEV-006"] or
            new_score.get("denominator") != 60 or
            new_score.get("saved") != 60 or
            new_score.get("valid") != 58 or
            new_score.get("allFour") != 56 or
            new_score.get("scoreKind") != "fixed_60" or
            new_score.get("outcomes", {}).get("never_sent") != 0 or
            gemma_postabort.get("fresh3P0", {}).get("status") != "never_sent" or
            gemma_postabort.get("fresh3P1", {}).get("status") != "never_sent" or
            gemma_usage.get("requestCount") != 60 or
            gemma_usage.get("reportedCostCount") != 58 or
            gemma_usage.get("missingCostCount") != 2 or
            gemma_usage.get("providerBilledUsd") is not None or
            gemma_usage.get("pureInferenceSeconds") is not None or
            set(gemma_usage.get("tokenAvailability", {})) !=
                {"prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"} or
            any(v.get("reportedCount") != 58 or v.get("missingCount") != 2
                for v in gemma_usage["tokenAvailability"].values()) or
            gemma_usage.get("reportedReasoningExceedsCompletion") is not True or
            "categories conflict" not in gemma_usage.get("tokenCategoryCaveat", "") or
            not gemma_postabort.get("sourceBindings")):
        raise ValueError("Gemma postabort composite source or coverage differs")
    reported_gemma_cost = Decimal(str(gemma_usage.get("reportedKnownCostUsd")))
    if (not reported_gemma_cost.is_finite() or reported_gemma_cost < 0 or
            type(gemma_usage.get("clientRequestSecondsTotal")) not in (int, float) or
            not math.isfinite(gemma_usage["clientRequestSecondsTotal"]) or
            gemma_usage["clientRequestSecondsTotal"] < 0):
        raise ValueError("Gemma reported usage differs")
    gemma_repeat_shared = gemma_p2_repeat.get("allThreeSharedValid") or {}
    gemma_repeat_scores = gemma_p2_repeat.get("fixed60Scores") or {}
    gemma_repeat_bindings = gemma_p2_repeat.get("sourceBindings") or []
    if (gemma_p2_repeat.get("schema") != "gemma26-on-v2-p2-descriptive-repeat-findings-v1" or
            gemma_p2_repeat.get("configuration") != gemma_postabort.get("configuration") or
            gemma_p2_repeat.get("condition") != "P2" or
            gemma_p2_repeat.get("method") != "descriptive-interrupted-three-pass-comparison" or
            gemma_p2_repeat.get("denominator") != 60 or
            gemma_p2_repeat.get("completedP2Passes") != 3 or
            gemma_p2_repeat.get("scoredSeriesConditions") != 7 or
            gemma_p2_repeat.get("cleanMatchedThreeEligible") is not False or
            {name: gemma_repeat_scores.get(name, {}).get("allFour")
             for name in ("fresh1", "fresh2", "fresh3")} !=
                {"fresh1": 57, "fresh2": 56, "fresh3": 56} or
            gemma_repeat_scores.get("fresh3") != new_score or
            gemma_repeat_shared.get("denominator") != 57 or
            gemma_repeat_shared.get("excludedIds") != ["DEV-005", "DEV-006", "DEV-007"] or
            [row.get("id") for row in gemma_repeat_shared.get("changedRecords", [])] !=
                ["DEV-013", "DEV-059"] or
            len(gemma_repeat_bindings) != 14 or
            any(not isinstance(item, dict) or not isinstance(item.get("path"), str) or
                not isinstance(item.get("sha256"), str) or
                len(item["sha256"]) != 64 or
                item["path"].startswith("/") or ".." in Path(item["path"]).parts or
                sha(root / item["path"]) != item["sha256"]
                for item in gemma_repeat_bindings)):
        raise ValueError("Gemma P2 repeat comparison differs from closed evidence")
    for item in gemma_repeat_bindings:
        bindings[item["path"]] = item["sha256"]
    if (clef.get("schema") != "clef-native-p0-findings-v1" or
            clef.get("cohort", {}).get("records") != 60 or
            clef["cohort"].get("pass") != "fresh1" or
            clef["cohort"].get("condition") != "P0" or
            clef["cohort"].get("fullPassesPerModelCompleted") != 1 or
            set(clef.get("models", {})) != {"clef", "clef-flash"} or
            any(clef["models"][name].get("valid") != 60 for name in clef["models"]) or
            clef["models"]["clef"].get("allFourCorrect") != 53 or
            clef["models"]["clef-flash"].get("allFourCorrect") != 45 or
            clef.get("cost", {}).get("providerBilledUsd") is not None or
            not clef.get("sourceSha256")):
        raise ValueError("Clef first-pass source or coverage differs")
    if (clef_repeat.get("schema") != "clef-native-p0-repeat-findings-v1" or
            clef_repeat.get("cohort") != {"records": 60, "condition": "P0",
                "fullPassesPerModelCompleted": 2, "requiredFullPassesPerCondition": 3,
                "otherConditionsCompleted": False} or
            clef_repeat.get("referenceStatus") !=
                "Frozen provisional v0.2 key; project owner confirmed human checks of all 60 reviews on 2026-10-02" or
            set(clef_repeat.get("models", {})) != {"clef", "clef-flash"} or
            any(clef_repeat["models"][name]["fresh1"]["allFourCorrect"] !=
                clef["models"][name]["allFourCorrect"] or
                clef_repeat["models"][name]["fresh2"]["allFourCorrect"] !=
                clef["models"][name]["allFourCorrect"] or
                clef_repeat["models"][name]["paired"]["sharedValid"] != 60 or
                clef_repeat["models"][name]["paired"]["predictionVectorChangedIds"] != [] or
                clef_repeat["models"][name]["fresh2"]["providerBilledUsd"] is not None
                for name in ("clef", "clef-flash")) or
            len(clef_repeat.get("sourceSha256", {})) != 1258):
        raise ValueError("Clef P0 paired repeat source or coverage differs")
    for name, expected in clef_repeat["sourceSha256"].items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or
                sha(root / relative) != expected):
            raise ValueError("Clef P0 paired repeat source changed: " + name)
    third_models = clef_third.get("models") or {}
    third_clef = third_models.get("clef") or {}
    third_flash = third_models.get("clef-flash") or {}
    if (clef_third.get("schema") != "clef-native-p0-third-checkpoint-v1" or
            clef_third.get("referenceStatus") != clef_repeat.get("referenceStatus") or
            clef_third.get("priorTwoPassSource") != "public-site/clef-p0-repeat-findings.json" or
            clef_third.get("cohort") != {"records": 60, "condition": "P0",
                "plannedCellsPerModel": 9, "thirdPassStatus": "clef_complete_flash_stopped",
                "otherConditionsCompleted": False} or
            set(third_models) != {"clef", "clef-flash"} or
            third_clef.get("status") != "complete" or
            third_clef.get("scoredCellsOfNine") != 3 or
            third_clef.get("p0AllFourByPass") != {"fresh1": 53, "fresh2": 53, "fresh3": 53} or
            third_clef.get("fresh3P0", {}).get("attempted") != 60 or
            third_clef["fresh3P0"].get("valid") != 60 or
            third_clef["fresh3P0"].get("allFourCorrect") != 53 or
            third_clef["fresh3P0"].get("denominator") != 60 or
            third_clef["fresh3P0"].get("providerBilledUsd") is not None or
            third_clef.get("sharedValidThreePassDenominator") != 60 or
            third_clef.get("threePassPredictionChangedIds") != [] or
            third_clef.get("nativeDistributionChangedIds") != [] or
            third_clef.get("vendorConfidenceChangedIds") != [] or
            third_flash.get("status") != "stopped_unknown_outcome" or
            third_flash.get("scoredCellsOfNine") != 2 or
            third_flash.get("p0AllFourByPass") != {"fresh1": 45, "fresh2": 45, "fresh3": None} or
            third_flash.get("fresh3P0", {}).get("attempted") != 1 or
            third_flash["fresh3P0"].get("valid") != 0 or
            third_flash["fresh3P0"].get("unknownOutcomeIds") != ["DEV-001"] or
            third_flash["fresh3P0"].get("neverSentIds") !=
                [f"DEV-{i:03d}" for i in range(2, 61)] or
            third_flash["fresh3P0"].get("score") is not None or
            third_flash["fresh3P0"].get("providerEnvelopeAvailable") is not False or
            third_flash.get("sharedValidThreePassDenominator") != 0 or
            third_flash.get("threePassPredictionChangedIds") is not None or
            len(clef_third.get("sourceSha256", {})) != 1595):
        raise ValueError("Clef third P0 checkpoint source or coverage differs")
    for name, expected in clef_third["sourceSha256"].items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or
                sha(root / relative) != expected):
            raise ValueError("Clef third P0 checkpoint source changed: " + name)
    legacy_series = {s.get("configuration"): s for s in legacy_qwen.get("series", [])}
    legacy_complete = ("qwen3-0.6b-q4km-nonthinking",
                       "qwen3-0.6b-sdk-thinking-on",
                       "qwen3-0.6b-sdk-thinking-off")
    legacy_pending = ("qwen3-1.7b-sdk-thinking-on",
                      "qwen3-1.7b-sdk-thinking-off",
                      "qwen3.5-4b-sdk-thinking-on")
    if (legacy_qwen.get("schema") != "legacy-qwen-closed-phase-report-v1" or
            set(legacy_series) != set(legacy_complete + legacy_pending) or
            any(legacy_series[name].get("completedConditions") != 9 or
                legacy_series[name].get("plannedConditions") != 9 or
                legacy_series[name].get("missingPasses") or
                not legacy_series[name].get("sourceBindings")
                for name in legacy_complete) or
            any(not isinstance(legacy_series[name].get("completedConditions"), int) or
                not 0 <= legacy_series[name]["completedConditions"] < 9 or
                legacy_series[name].get("plannedConditions") != 9
                for name in legacy_pending)):
        raise ValueError("Legacy Qwen SDK and HTTP cohort coverage differs")
    sdk_on = legacy_series["qwen3-0.6b-sdk-thinking-on"]["passes"]["fresh3"]["P2"]["score"]
    sdk_off = legacy_series["qwen3-0.6b-sdk-thinking-off"]["passes"]["fresh3"]["P2"]["score"]
    if (sdk_on.get("denominator") != 60 or sdk_on.get("valid") != 58 or
            sdk_on.get("allFour") != 1 or
            sdk_on.get("outcomes", {}).get("invalid_output") != 2 or
            sdk_off.get("denominator") != 60 or sdk_off.get("valid") != 5 or
            sdk_off.get("allFour") != 0 or
            sdk_off.get("outcomes", {}).get("invalid_output") != 55):
        raise ValueError("Qwen SDK final P2 validity or score differs")
    mistral_valid = mistral_original["valid_count"] + len(mistral_first["valid_ids"]) + len(mistral_second["valid_ids"])
    mistral_failed = mistral_original["unknown_outcome_count"] + 2
    if (mistral_original["unknown_id"] != "DEV-048" or
            mistral_first["valid_ids"] != ["DEV-049"] or
            mistral_first["failed_id"] != "DEV-050" or
            mistral_first["unsent_ids"] != [f"DEV-{i:03d}" for i in range(51, 61)] or
            mistral_second["valid_ids"] != ["DEV-051", "DEV-052"] or
            mistral_second["failed_id"] != "DEV-053" or
            mistral_second["unsent_ids"] != [f"DEV-{i:03d}" for i in range(54, 61)] or
            mistral_second["earlier_failed_ids_preserved"] != ["DEV-048", "DEV-050"] or
            mistral_second["http_status"] != 429 or
            mistral_second["limit_source"] != "upstream_provider_shared_pool" or
            mistral_second["reference_labels_sent"] is not False or
            mistral_second["composite_valid_count"] != mistral_valid or
            mistral_second["composite_failed_count"] != mistral_failed or
            mistral_second["composite_never_sent_count"] != len(mistral_second["unsent_ids"]) or
            mistral_second["composite_score"] is not None or
            mistral_valid + mistral_failed + len(mistral_second["unsent_ids"]) != 60):
        raise ValueError("Mistral saved suffix and composite outcomes differ")
    estimated_total = sum((Decimal(by_effort[e]["usage"]["developmentApiEquivalentUsd"])
                           for e in EFFORTS), Decimal(0))
    return {
        "schema": "analysis-refresh-v1", "generatedAt": "2026-10-02",
        "method": "Offline descriptive synthesis of published feeds and sanitized Sonnet record evidence",
        "reference": {"version": "0.2", "reviews": 60,
                      "status": sonnet["referenceStatus"],
                      "classCounts": sonnet["referenceClassCounts"],
                      "majorityBaselines": {field: max(counts.values()) for field, counts in
                                            sonnet["referenceClassCounts"].items()}},
        "sonnet55": {"completedCells": 36, "validClassifications": 2160,
                     "byEffort": by_effort,
                     "executionControls": {**manifest_controls,
                           "route": "Claude Code CLI subscription auth, claude.ai",
                           "requestUnit": "One ordinary CLI request contains ten reviews",
                           "controlStatus": "visible manifest settings held constant; serving revision and hidden defaults unknown"},
                     "developmentApiEquivalentUsd": str(estimated_total),
                     "costKind": "CLI API-equivalent list-price estimate; not a subscription charge",
                     "timingKind": "client and CLI API durations; neither is pure inference time",
                     "originalGuardFailure": sonnet["originalGuardFailure"]},
        "claude": {"historicalCount": 17, "newSonnetCount": 4, "totalConfigurations": 21,
                   "series": claude_rows,
                   "allThreePassPromptGainCount": {condition: sum(row["allThreePassPromptGain"][condition]
                       for row in claude_rows) for condition in ("P1", "P2")},
                   "comparability": "Within each saved series only. Historical first passes and later repeats can use different CLI versions; fresh Sonnet 5.5 v2 is a separate route and model. Do not pool reviews or score differences across series."},
        "newerCohorts": {
            "qwen27": {"source": "public-site/qwen27-final-descriptive-findings.json",
                        "seriesCount": len(qwen["series"]),
                        "cleanMatchedThreeEligible": qwen["cleanMatchedThreeEligible"]},
            "legacyQwen": {"source": "public-site/legacy-qwen-repeats.json",
                           "completedConfigurations": list(legacy_complete),
                           "remainingConfigurations": {name:
                               {"completedConditions": legacy_series[name]["completedConditions"],
                                "plannedConditions": 9} for name in legacy_pending},
                           "sdkFinalP2": {"thinkingOn": {"valid": sdk_on["valid"],
                                   "invalid": sdk_on["outcomes"]["invalid_output"],
                                   "allFour": sdk_on["allFour"], "denominator": 60},
                               "thinkingOff": {"valid": sdk_off["valid"],
                                   "invalid": sdk_off["outcomes"]["invalid_output"],
                                   "allFour": sdk_off["allFour"], "denominator": 60}}},
            "clefNativeP0": {"source": "public-site/clef-findings.json",
                             "pass": "fresh1", "condition": "P0",
                             "fullPassesPerModelCompleted": 1,
                             "models": {name: {"valid": clef["models"][name]["valid"],
                                "allFour": clef["models"][name]["allFourCorrect"],
                                "denominator": 60}
                                for name in ("clef", "clef-flash")},
                             "providerBilledUsd": None,
                             "costKind": "input-price estimate and conservative hold, not an observed bill",
                             "repeatSource": "public-site/clef-p0-repeat-findings.json",
                             "repeat": {"fullPassesPerModelCompleted": 2,
                                 "requiredFullPassesPerCondition": 3,
                                 "sharedValidDenominator": 60,
                                 "models": {name: {
                                     "fresh1AllFour": clef_repeat["models"][name]["fresh1"]["allFourCorrect"],
                                     "fresh2AllFour": clef_repeat["models"][name]["fresh2"]["allFourCorrect"],
                                     "changedFourFieldVectorIds": clef_repeat["models"][name]["paired"]["predictionVectorChangedIds"]}
                                     for name in ("clef", "clef-flash")}},
                             "thirdCheckpointSource": "public-site/clef-p0-third-checkpoint.json",
                             "thirdCheckpoint": {"clef": {"scoredCellsOfNine": 3,
                                 "fresh3AllFour": third_clef["fresh3P0"]["allFourCorrect"],
                                 "valid": third_clef["fresh3P0"]["valid"],
                                 "sharedValidThreePassDenominator": 60,
                                 "changedPredictionIds": third_clef["threePassPredictionChangedIds"],
                                 "nativeDistributionChangedIds": third_clef["nativeDistributionChangedIds"],
                                 "vendorConfidenceChangedIds": third_clef["vendorConfidenceChangedIds"]},
                               "clefFlash": {"scoredCellsOfNine": 2,
                                 "fresh3Status": "stopped_unknown_outcome",
                                 "unknownOutcomeIds": third_flash["fresh3P0"]["unknownOutcomeIds"],
                                 "neverSentCount": len(third_flash["fresh3P0"]["neverSentIds"]),
                                 "fresh3Score": None}}},
            "deepseekLow": {"source": "public-site/deepseek-low-third-interruption-findings.json",
                            "seriesCount": len(deepseek["series"]),
                            "completedConditions": [item["completedConditions"] for item in deepseek["series"]],
                            "plannedConditions": [item["plannedConditions"] for item in deepseek["series"]],
                            "latestInterruptedPhase": deepseek["series"][0]["thirdInterruptionCheckpoint"]["phase"],
                            "latestInterruptedOutcomes": deepseek["series"][0]["thirdInterruptionCheckpoint"]["outcomes"],
                            "latestInterruptedScore": deepseek["series"][0]["thirdInterruptionCheckpoint"]["score"]},
            "gemma26": {"source": "public-site/gemma26-fresh3-p0-checkpoint.json",
                        "p0Checkpoint": gemma_p0["conditions"]["P0"],
                        "p2RepeatSource": "public-site/gemma26-p2-repeat-findings.json",
                        "p2Repeat": {"fixed60AllFourByPass": {name: gemma_repeat_scores[name]["allFour"]
                            for name in ("fresh1", "fresh2", "fresh3")},
                            "sharedValidDenominator": gemma_repeat_shared["denominator"],
                            "excludedIds": gemma_repeat_shared["excludedIds"],
                            "changedFourFieldVectorIds": [row["id"] for row in
                                gemma_repeat_shared["changedRecords"]],
                            "cleanMatchedThreeEligible": False},
                        "priorCutoffSource": "public-site/gemma26-second-continuation-findings.json",
                        "completedConditionsAtSecondContinuation": gemma["completedConditions"],
                        "completedConditions": gemma_p0["scoredSeriesConditions"],
                        "plannedConditions": gemma_postabort["plannedConditions"],
                        "cleanMatchedThreeEligible": False,
                        "fresh3P2": {"status": new_gemma["status"],
                            "valid": new_score["valid"],
                            "failedIds": new_gemma["failedIds"],
                            "allFour": new_score["allFour"],
                            "denominator": 60},
                        "usage": {"reportedKnownCostUsd": gemma_usage["reportedKnownCostUsd"],
                            "reportedCostCount": gemma_usage["reportedCostCount"],
                            "missingCostCount": gemma_usage["missingCostCount"],
                            "clientRequestSecondsTotal": gemma_usage["clientRequestSecondsTotal"],
                            "pureInferenceSeconds": None,
                            "tokenAvailability": gemma_usage["tokenAvailability"],
                            "reportedReasoningExceedsCompletion": True,
                            "tokenCategoryCaveat": gemma_usage["tokenCategoryCaveat"]},
                        "unscoredConditionsAtCutoff": ["fresh3/P1"],
                        "priorThirdContinuation": {"status": gemma_terminal["status"],
                            "failedId": gemma_terminal["new_failed_id"],
                            "neverSentCount": len(gemma_terminal["new_stage_never_sent_ids"]),
                            "score": gemma_terminal["score"]}},
            "mistral119": {"source": MISTRAL_SECOND_SUFFIX,
                           "priorSuffixSource": MISTRAL_FIRST_SUFFIX,
                           "status": mistral_second["status"],
                           "originalValidCount": mistral_original["valid_count"],
                           "combinedSavedValidCount": mistral_valid,
                           "validCount": mistral_valid,
                           "failedOrUnknownCount": mistral_failed,
                           "originalUnknownId": mistral_original["unknown_id"],
                           "validIdsInSuffix": mistral_first["valid_ids"] + mistral_second["valid_ids"],
                           "validIdsInFirstSuffix": mistral_first["valid_ids"],
                           "validIdsInSecondSuffix": mistral_second["valid_ids"],
                           "priorFailedId": mistral_first["failed_id"],
                           "failedId": mistral_second["failed_id"],
                           "failedIds": [mistral_original["unknown_id"], mistral_first["failed_id"], mistral_second["failed_id"]],
                           "neverSentCount": len(mistral_second["unsent_ids"]),
                           "originalDev048UnknownPreserved": mistral_first["original_DEV048_unknown_preserved"],
                           "score": mistral_second["composite_score"]},
        },
        "coverage": {
            "observed": ["frozen reference class counts", "all-four and per-field scores",
                         "within-series matched prompt deltas", "per-record repeat flips",
                         "provider-reported token categories", "Sonnet cache-aware API-equivalent estimates",
                         "client request and CLI API duration", "saved failure and never-sent states"],
            "notObserved": ["true subscription per-request charges or quota use",
                            "pure model inference time", "effective provider seed or serving revision",
                            "independence of repeated responses", "population hiring accuracy"],
        },
        "sources": [{"path": path, "sha256": digest} for path, digest in sorted(bindings.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.root)
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output = args.root / OUTPUT
    if args.check:
        if not output.exists() or output.read_text() != rendered:
            raise SystemExit("Analysis refresh is stale; rerun scripts/build_analysis_refresh.py")
        print(f"Verified {OUTPUT} against {len(result['sources'])} source hashes")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"Wrote {OUTPUT} from {len(result['sources'])} source hashes")


if __name__ == "__main__":
    main()
