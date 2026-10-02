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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "public-site/analysis-refresh.json"
SOURCES = (
    "public-site/sonnet55-fresh-matched3.json",
    "public-site/sonnet55-fresh-matched3-evidence/report.json",
    "public-site/claude-roster-repeats.json",
    "public-site/claude-repeats.json",
    "public-site/haiku-fresh-matched3.json",
    "public-site/findings.json",
    "public-site/subscription-price-estimates.json",
    "public-site/qwen27-final-descriptive-findings.json",
    "public-site/deepseek-low-third-interruption-findings.json",
    "public-site/gemma26-second-continuation-findings.json",
    "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-development-none-v1/fresh1/P0/development.terminal-public.json",
    "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-remaining-none-v1/fresh1/P0-suffix-049-060/suffix.terminal-public.json",
    "results/repeatability-v1/gemma26-on-fresh-matched3-v2/third-interruption-continuation-v1/terminal-public-after-dev006.json",
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
    deepseek = data["public-site/deepseek-low-third-interruption-findings.json"]
    gemma = data["public-site/gemma26-second-continuation-findings.json"]
    mistral_original = data[SOURCES[-4]]
    mistral = data[SOURCES[-3]]
    gemma_terminal = data[SOURCES[-2]]
    if (mistral_original["status"] != "interrupted_unscored" or
            mistral["status"] != "interrupted_unscored" or
            gemma_terminal["status"] != "stopped_unscored"):
        raise ValueError("Expected retained unscored interruption states")
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
            "deepseekLow": {"source": "public-site/deepseek-low-third-interruption-findings.json",
                            "seriesCount": len(deepseek["series"]),
                            "completedConditions": [item["completedConditions"] for item in deepseek["series"]],
                            "plannedConditions": [item["plannedConditions"] for item in deepseek["series"]],
                            "latestInterruptedPhase": deepseek["series"][0]["thirdInterruptionCheckpoint"]["phase"],
                            "latestInterruptedOutcomes": deepseek["series"][0]["thirdInterruptionCheckpoint"]["outcomes"],
                            "latestInterruptedScore": deepseek["series"][0]["thirdInterruptionCheckpoint"]["score"]},
            "gemma26": {"source": "public-site/gemma26-second-continuation-findings.json",
                        "completedConditionsAtSecondContinuation": gemma["completedConditions"],
                        "plannedConditions": gemma["plannedConditions"],
                        "latestThirdContinuation": {"status": gemma_terminal["status"],
                            "failedId": gemma_terminal["new_failed_id"],
                            "neverSentCount": len(gemma_terminal["new_stage_never_sent_ids"]),
                            "score": gemma_terminal["score"]}},
            "mistral119": {"source": SOURCES[-3], "status": mistral["status"],
                           "originalValidCount": mistral_original["valid_count"],
                           "combinedSavedValidCount": mistral_original["valid_count"] + len(mistral["valid_ids"]),
                           "validCount": mistral_original["valid_count"] + len(mistral["valid_ids"]),
                           "failedOrUnknownCount": mistral_original["unknown_outcome_count"] + 1,
                           "originalUnknownId": mistral_original["unknown_id"],
                           "validIdsInSuffix": mistral["valid_ids"],
                           "failedId": mistral["failed_id"],
                           "neverSentCount": len(mistral["unsent_ids"]),
                           "originalDev048UnknownPreserved": mistral["original_DEV048_unknown_preserved"],
                           "score": mistral["score"]},
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
