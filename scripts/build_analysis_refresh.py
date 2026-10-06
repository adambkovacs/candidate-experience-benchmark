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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "public-site/analysis-refresh.json"
MISTRAL_ORIGINAL = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-development-none-v1/fresh1/P0/development.terminal-public.json"
MISTRAL_FIRST_SUFFIX = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-remaining-none-v1/fresh1/P0-suffix-049-060/suffix.terminal-public.json"
MISTRAL_SECOND_SUFFIX = "results/repeatability-v1/mistral119-fresh-matched3-v1/v3-second-suffix-none-v1/fresh1/P0/suffix.terminal-public.json"
GEMMA_TERMINAL = "results/repeatability-v1/gemma26-on-fresh-matched3-v2/third-interruption-continuation-v1/terminal-public-after-dev006.json"
CLEF_FLASH_P1 = "results/clef-native-v1/clef-flash-p1-findings-public.json"
CLEF_FLASH_P1_PUBLIC = "public-site/clef-flash-p1-findings.json"
CLEF_FLASH_P2 = "results/clef-native-v1/clef-flash-p2-findings-public.json"
CLEF_FLASH_P2_PUBLIC = "public-site/clef-flash-p2-findings.json"
CLEF_FLASH_P0_PARENT = "results/clef-native-v1/clef-flash/fresh3/P0/development"
CLEF_FLASH_P0_SUFFIX = "results/clef-native-v1/clef-flash/fresh3/P0/development-suffix-v1"
MISTRAL_P0_PUBLIC = "public-site/mistral119-fresh1-p0-findings.json"
KEV_NATIVE_PROMPT_PUBLIC = "public-site/kev-native-prompt-findings.json"
JEV_NATIVE_PROMPT_PUBLIC = "public-site/jev-native-prompt-findings.json"
GEMINI_AUTHORITY_PUBLIC = "public-site/gemini-repeats.json"
HOSTED_FRESH_PUBLIC = "public-site/additional-hosted-fresh-repeats.json"
HIGH_SUCCESSOR_PUBLIC = "public-site/deepseek-high-remaining6-successor-findings.json"
LIQUID_PUBLIC = "public-site/liquid-d1-native-full-findings.json"
LOW_P1_SUCCESSOR_PUBLIC = "public-site/deepseek-low-p1-successor-findings.json"
LOW_REVISED_PUBLIC = "public-site/deepseek-low-remaining6-price-v2-findings.json"
SOURCES = (
    "public-site/e4b-interruption-findings.json",
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
    "public-site/deepseek-low-final-suffix-findings.json",
    "public-site/gemma26-second-continuation-findings.json",
    "public-site/gemma26-postabort-findings.json",
    "public-site/gemma26-p2-repeat-findings.json",
    "public-site/gemma26-fresh3-p0-checkpoint.json",
    "public-site/gemma26-fresh3-p1-interrupted-checkpoint.json",
    "public-site/clef-findings.json",
    "public-site/clef-p0-repeat-findings.json",
    "public-site/clef-p0-third-checkpoint.json",
    MISTRAL_ORIGINAL,
    MISTRAL_FIRST_SUFFIX,
    MISTRAL_SECOND_SUFFIX,
    GEMMA_TERMINAL,
    CLEF_FLASH_P1,
    CLEF_FLASH_P2,
    MISTRAL_P0_PUBLIC,
    KEV_NATIVE_PROMPT_PUBLIC,
    JEV_NATIVE_PROMPT_PUBLIC,
    GEMINI_AUTHORITY_PUBLIC,
    HOSTED_FRESH_PUBLIC,
    LOW_REVISED_PUBLIC,
    LOW_P1_SUCCESSOR_PUBLIC,
    LIQUID_PUBLIC,
    HIGH_SUCCESSOR_PUBLIC,
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


def bind_report_sources(root, report, bindings, label):
    """Verify and retain every source named by a source-bound public report."""
    items = report.get("sourceBindings") or []
    if not items:
        raise ValueError(f"{label} has no source bindings")
    seen = {}
    for item in items:
        path = item.get("path") if isinstance(item, dict) else None
        digest = item.get("sha256") if isinstance(item, dict) else None
        if (not isinstance(path, str) or not path or path.startswith("/") or
                ".." in Path(path).parts or not isinstance(digest, str) or
                len(digest) != 64):
            raise ValueError(f"{label} source binding is malformed")
        if path in seen and seen[path] != digest:
            raise ValueError(f"{label} repeats a source with conflicting hashes: {path}")
        if sha(root / path) != digest:
            raise ValueError(f"{label} source hash differs: {path}")
        seen[path] = digest
        bindings[path] = digest
    return seen


def hosted_fresh_summary(root, published, bindings):
    """Project only independently closed hosted cells from the rebuilt report."""
    import build_deepseek_high_remaining7_price_findings as hosted_builder

    if published != hosted_builder.build(root):
        raise ValueError("Hosted fresh report differs from closed evidence")
    bind_report_sources(root, published, bindings, "Hosted fresh report")
    series = {item["configuration"]: item for item in published["series"]}
    qwen = series["openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2"]
    deepseek = series["openrouter-paid-deepseek-v41-flash-high-authority-v3-current-price"]
    priced = series.get(hosted_builder.CONFIG)
    qpasses = qwen["passes"]["fresh1"]
    base, rules, interrupted = (qpasses[name] for name in ("P0", "P2", "P1"))
    delta = qwen["withinPassPromptDeltas"]
    first_delta = [item for item in delta if item.get("pass") == "fresh1" and
                   item.get("from") == "P0" and item.get("to") == "P2"]
    qwen_closed = [(name, condition) for name, phases in qwen["passes"].items()
                   for condition, phase in phases.items() if phase["status"] == "completed"]
    deepseek_closed = [(name, condition) for name, phases in deepseek["passes"].items()
                       for condition, phase in phases.items()
                       if phase["status"].startswith("completed")]

    def closed_phase_summaries(item, cells):
        return [{"pass": name, "condition": condition,
                 "status": item["passes"][name][condition]["status"],
                 "allFour": item["passes"][name][condition]["score"]["allFour"],
                 "valid": item["passes"][name][condition]["score"]["valid"],
                 "invalidIds": item["passes"][name][condition]["score"]["invalidIds"],
                 "denominator": item["passes"][name][condition]["score"]["denominator"]}
                for name, condition in cells]

    def matched_comparisons(item, allowed_statuses):
        compared = []
        for name, phases in item["passes"].items():
            base = phases.get("P0")
            if not base or base["status"] not in allowed_statuses:
                continue
            for condition in ("P1", "P2"):
                added = phases.get(condition)
                if not added or added["status"] not in allowed_statuses:
                    continue
                if (base["score"]["denominator"] != 60 or
                        added["score"]["denominator"] != 60):
                    raise ValueError("Hosted matched comparison denominator differs")
                compared.append({"pass": name, "from": "P0", "to": condition,
                    "allFourDelta": added["score"]["allFour"] - base["score"]["allFour"],
                    "allFour": {"P0": base["score"]["allFour"],
                                condition: added["score"]["allFour"]},
                    "invalidIds": {"P0": base["score"]["invalidIds"],
                                   condition: added["score"]["invalidIds"]},
                    "denominator": 60})
        return compared

    qwen_pairs = matched_comparisons(qwen, {"completed"})
    deepseek_pairs = matched_comparisons(
        deepseek, {"completed", "completed_with_intrinsic_invalid"})
    if (qwen["denominator"] != 60 or
            qwen["completedConditions"] != len(qwen_closed) or
            not 2 <= len(qwen_closed) <= qwen["plannedConditions"] or
            base["status"] != "completed" or rules["status"] != "completed" or
            interrupted["status"] != "completed_interrupted_composite" or
            (base["score"]["valid"], rules["score"]["valid"]) != (60, 60) or
            first_delta != [{"pass": "fresh1", "from": "P0", "to": "P2",
                       "denominator": 60,
                       "allFour": rules["score"]["allFour"] - base["score"]["allFour"],
                       "fields": {field: rules["score"]["fields"][field] -
                                  base["score"]["fields"][field] for field in FIELDS},
                       "scope": "descriptive matched first pass; interrupted P1 excluded"}] or
            not any(item["pass"] == "fresh1" and item["condition"] == "P1" and
                    item["status"] == "interrupted_descriptive"
                    for item in qwen["missingPasses"])):
        raise ValueError("Hosted Qwen clean comparison differs")
    dpass = deepseek["passes"]["fresh1"]["P0"]
    dscore = dpass["score"]
    if (deepseek["denominator"] != 60 or
            deepseek["completedConditions"] != len(deepseek_closed) or
            not 1 <= len(deepseek_closed) <= deepseek["plannedConditions"] or
            dpass["status"] != "completed_with_intrinsic_invalid" or
            dscore["valid"] != 59 or dscore["outcomes"] !=
                {"ok": 59, "invalid_output": 1} or
            dscore["invalidIds"] != ["DEV-030"]):
        raise ValueError("Hosted DeepSeek high first pass differs")
    priced_summary = None
    if priced is not None:
        priced_closed = [(name, condition) for name, phases in priced["passes"].items()
                         for condition, phase in phases.items()
                         if phase["status"].startswith("completed")]
        if (priced["configuration"] != hosted_builder.CONFIG or
                priced["originalConfiguration"] != deepseek["configuration"] or
                priced["method"] != "separate-price-control-continuation" or
                priced["denominator"] != 60 or
                priced["completedConditions"] != len(priced_closed) or
                priced["cleanMatchedThreeEligible"] is not False or
                not priced_closed or priced_closed[0] != ("fresh1", "P2")):
            raise ValueError("Hosted DeepSeek revised-price series differs")
        priced_summary = {
            "configuration": hosted_builder.CONFIG,
            "originalConfiguration": deepseek["configuration"],
            "completedConditions": len(priced_closed),
            "plannedConditions": priced["plannedConditions"],
            "closedCells": [f"{name}/{condition}" for name, condition in priced_closed],
            "closedPhases": closed_phase_summaries(priced, priced_closed),
            "cleanMatchedThreeEligible": False,
            "comparisonWithOriginalConfigurationEligible": False,
        }
    # Compare only complete passes of the same prompt. The interrupted P1
    # remains visible elsewhere but contributes no repeat-stability credit.
    qwen_repeats = {}
    qbase = Path('results/repeatability-v1/qwen36-on-hosted-authority-v3-v2')
    for condition in ('P0', 'P1', 'P2'):
        passes = [name for name in ('fresh1', 'fresh2', 'fresh3')
                  if (name, condition) in qwen_closed]
        predictions = []
        for name in passes:
            folder = (qbase / name / condition if (name, condition) == ('fresh1', 'P0')
                      else qbase / 'remaining-hosted-v1' / qwen['configuration'] / name / condition)
            source = str(folder / 'development.attempts.jsonl')
            if source not in bindings:
                raise ValueError('Qwen repeat input lacks verified source binding')
            records = [json.loads(line) for line in (root / source).read_text().splitlines()]
            predictions.append({row['id']: row['prediction'] for row in records})
        if len(passes) < 2:
            continue
        ids = [f'DEV-{i:03d}' for i in range(1, 61)]
        if any(set(prediction) != set(ids) for prediction in predictions):
            raise ValueError('Qwen repeat membership differs')
        qwen_repeats[condition] = {
            'passes': passes, 'passCount': len(passes), 'denominator': 60,
            'allFourScores': [qwen['passes'][name][condition]['score']['allFour'] for name in passes],
            'changedReviewIds': [rid for rid in ids if any(
                prediction[rid] != predictions[0][rid] for prediction in predictions[1:])],
            'changedByField': {field: [rid for rid in ids if len({
                prediction[rid][field] for prediction in predictions}) > 1] for field in FIELDS},
        }
    return {
        "source": HOSTED_FRESH_PUBLIC,
        "qwen36On": {"completedCleanConditions": qwen["completedConditions"],
            "plannedConditions": qwen["plannedConditions"],
            "closedCells": [f"{name}/{condition}" for name, condition in qwen_closed],
            "closedPhases": closed_phase_summaries(qwen, qwen_closed),
            "matchedPromptComparisons": qwen_pairs,
            "repeatability": qwen_repeats,
            "pass": "fresh1", "scores": {name: {"allFour": qpasses[name]["score"]["allFour"],
                "valid": qpasses[name]["score"]["valid"], "denominator": 60}
                for name in ("P0", "P2")},
            "matchedP0P2AllFourDelta": first_delta[0]["allFour"],
            "interruptedP1": {"status": interrupted["status"],
                "valid": interrupted["score"]["valid"],
                "allFour": interrupted["score"]["allFour"],
                "cleanComparisonEligible": False},
            "cleanMatchedThreeEligible": qwen["cleanMatchedThreeEligible"]},
        "deepseekHigh": {"completedConditions": deepseek["completedConditions"],
            "plannedConditions": deepseek["plannedConditions"],
            "closedCells": [f"{name}/{condition}" for name, condition in deepseek_closed],
            "closedPhases": closed_phase_summaries(deepseek, deepseek_closed),
            "matchedPromptComparisons": deepseek_pairs,
            "pass": "fresh1",
            "condition": "P0", "allFour": dscore["allFour"], "valid": dscore["valid"],
            "denominator": 60, "invalidIds": dscore["invalidIds"],
            "intrinsicInvalidCount": dscore["outcomes"]["invalid_output"],
            "firstP0AloneSupportsPromptComparison": False},
        "deepseekHighRevisedPrice": priced_summary,
    }


def gemini_authority_summary(root, published, bindings):
    """Rebuild the closed series before projecting its matched comparisons."""
    import build_gemini31_high_authority_v2_findings as gemini_report

    if published.get("schema") != "gemini-repeat-series-v1":
        raise ValueError("Published Gemini authority report differs from closed evidence")
    closures = {}
    for repeat in gemini_report.REPEATS:
        for condition in gemini_report.CONDITIONS:
            found = gemini_report._closure(root, repeat, condition)
            if found is None:
                raise ValueError("Gemini authority closure is missing")
            closures[repeat, condition] = found
        plan_path = gemini_report.BASE / gemini_report.CONFIG / repeat / "manifest.json"
        plan = json.loads((root / plan_path).read_text())
        for condition in gemini_report.CONDITIONS:
            for name in ("catalog", "endpoints"):
                source = plan["conditions"][condition][name]
                if sha(root / source["path"]) != source["sha256"]:
                    raise ValueError("Gemini authority endpoint source differs")
                bindings[source["path"]] = source["sha256"]

    ordinary_terminal = gemini_report.report._terminal

    def admitted_terminal(report_root, relative):
        relative = Path(relative)
        if (relative.name in ("smoke.journal.jsonl", "development.journal.jsonl") and
                relative.parts[:len(gemini_report.BASE.parts) + 1] ==
                (*gemini_report.BASE.parts, gemini_report.CONFIG)):
            repeat, condition = relative.parts[len(gemini_report.BASE.parts) + 1:
                                               len(gemini_report.BASE.parts) + 3]
            if (repeat, condition) not in closures:
                return None
        return ordinary_terminal(report_root, relative)

    def authority_controller(config):
        if config != gemini_report.CONFIG:
            raise ValueError("Unexpected Gemini authority configuration")
        return gemini_report.authority.runner

    with (patch.object(gemini_report.report, "BASE", gemini_report.BASE),
          patch.object(gemini_report.report, "_controller", authority_controller),
          patch.object(gemini_report.report, "_terminal", admitted_terminal)):
        rebuilt = gemini_report.report.build_series(gemini_report.CONFIG, root)
    for (repeat, condition), (binding, metrics) in closures.items():
        phase = rebuilt["passes"][repeat][condition]
        if (phase["completionStatus"] != "complete" or
                phase["score"]["allFour"] != metrics["all_four_matches"] or
                phase["score"]["valid"] != metrics["valid_records"] or
                phase["score"]["outcomes"]["invalid_output"] != metrics["invalid_records"] or
                phase["usage"]["knownCostUsd"] != metrics["development_observed_cost_usd"]):
            raise ValueError("Gemini authority closure metrics differ from report")
        rebuilt["sourceBindings"].append(binding)
    matches = [item for item in published.get("series", [])
               if item.get("configuration") == gemini_report.CONFIG]
    if len(matches) != 1 or matches[0] != rebuilt:
        raise ValueError("Published Gemini authority report differs from closed evidence")
    series = matches[0]
    passes = ("original", "repeat2", "repeat3")
    if (series.get("completedConditions") != 9 or series.get("plannedConditions") != 9 or
            series.get("denominator") != 60 or series.get("missingPasses") or
            series.get("partialPasses") or set(series.get("passes", {})) != set(passes)):
        raise ValueError("Gemini authority nine-condition coverage differs")
    source_map = bind_report_sources(root, series, bindings, "Gemini authority report")
    ids = [f"DEV-{n:03}" for n in range(1, 61)]
    records = {}
    conditions = {}
    for condition in CONDITIONS:
        phases = [series["passes"][name][condition] for name in passes]
        if any(phase["completionStatus"] != "complete" or
               phase["score"]["valid"] != 60 or
               phase["score"]["outcomes"]["invalid_output"] != 0
               for phase in phases):
            raise ValueError("Gemini authority phase is incomplete or invalid")
        for name, phase in zip(passes, phases):
            evidence = phase["evidence"]
            binding = evidence["development_records" if name == "original" else "records"]
            if source_map.get(binding["path"]) != binding["sha256"]:
                raise ValueError("Gemini authority record binding differs")
            rows = [json.loads(line) for line in (root / binding["path"]).read_text().splitlines()]
            if ([row.get("id") for row in rows] != ids or
                    any(row.get("status") != "ok" or not isinstance(row.get("prediction"), dict)
                        for row in rows)):
                raise ValueError("Gemini authority ordered records differ")
            records[name, condition] = {row["id"]: row["prediction"] for row in rows}
        summary = series["threePassSummary"][condition]
        scores = [phase["score"]["allFour"] for phase in phases]
        changes = series["changesAcrossThreePasses"][condition]
        if (summary["allFour"]["values"] != scores or
                summary["allFour"]["range"] != [min(scores), max(scores)] or
                changes["denominator"] != 60 or changes["excludedIds"]):
            raise ValueError("Gemini authority repeat summary differs")
        conditions[condition] = {
            "allFourScores": scores,
            "allFourRange": summary["allFour"]["range"],
            "changedReviewIds": changes["fourFieldVector"],
            "pairwiseFlips": [{"from": pair["from"], "to": pair["to"],
                               "changedReviewIds": pair["fourFieldVector"]["caseIds"]}
                              for pair in series["pairwiseFlips"] if pair["condition"] == condition],
        }
    prompt_pairs = {}
    for name in passes:
        prompt_pairs[name] = {}
        for target in ("P1", "P2"):
            changed = [rid for rid in ids if records[name, "P0"][rid] != records[name, target][rid]]
            delta = next(item["allFour"] for item in series["withinPassPromptDeltas"]
                         if item["pass"] == name and item["from"] == "P0" and item["to"] == target)
            expected_delta = (series["passes"][name][target]["score"]["allFour"] -
                              series["passes"][name]["P0"]["score"]["allFour"])
            if delta != expected_delta:
                raise ValueError("Gemini authority paired prompt delta differs")
            prompt_pairs[name][target] = {"allFourDelta": delta,
                                          "changedReviewIds": changed}
    return {"source": GEMINI_AUTHORITY_PUBLIC, "configuration": series["configuration"],
            "completedConditions": 9, "plannedConditions": 9, "denominator": 60,
            "conditions": conditions, "matchedP0": prompt_pairs,
            "referenceStatus": series["referenceStatus"]}


def kev_native_prompt_summary(root, report, bindings):
    """Validate the closed native P1/P2 study and return its compact projection."""
    expected_ids = ["DEV-001", "DEV-005", "DEV-022", "DEV-030",
                    "DEV-035", "DEV-041", "DEV-059"]
    expected = {
        "P1": {"allFour": 49, "fields": {"sentiment": 53,
            "follow_up_needed": 58, "serious_concern_reported": 55,
            "testimonial_potential": 58}},
        "P2": {"allFour": 46, "fields": {"sentiment": 54,
            "follow_up_needed": 53, "serious_concern_reported": 55,
            "testimonial_potential": 59}},
    }
    if (report.get("schema") != "kev-native-prompt-findings-v1" or
            report.get("denominator") != 60 or
            report.get("conditionOrder") != ["P1", "P2"] or
            report.get("excludedPasses") != [] or
            set(report.get("conditions", {})) != {"P1", "P2"} or
            report.get("nativePromptEquivalence", {}).get("verified") is not True or
            report["nativePromptEquivalence"].get("denominator") != 60):
        raise ValueError("Kev native prompt report identity or coverage differs")
    source_map = bind_report_sources(root, report, bindings, "Kev native prompt report")
    reference = report.get("referenceBinding") or {}
    if source_map.get(reference.get("path")) != reference.get("sha256"):
        raise ValueError("Kev native prompt reference binding differs")

    projected_conditions = {}
    for condition in ("P1", "P2"):
        item = report["conditions"][condition]
        if (item.get("completedPasses") != 3 or item.get("plannedPasses") != 3 or
                item.get("passOrder") != ["fresh1", "fresh2", "fresh3"] or
                set(item.get("passes", {})) != {"fresh1", "fresh2", "fresh3"} or
                len(item.get("repeatComparisons", [])) != 3 or
                item.get("repeatVariation", {}).get("allFourRange") !=
                    [expected[condition]["allFour"]] * 2):
            raise ValueError(f"Kev {condition} repeat coverage differs")
        scores = []
        fields = {field: [] for field in FIELDS}
        usage = {"inputTokens": 0, "outputTokens": 0,
                 "actualProviderCostUsd": Decimal(0), "clientRequestSeconds": 0.0}
        for name in ("fresh1", "fresh2", "fresh3"):
            phase = item["passes"][name]
            score = phase.get("score") or {}
            if (phase.get("completionStatus") != "complete" or
                    score.get("denominator") != 60 or score.get("valid") != 60 or
                    score.get("allFour") != expected[condition]["allFour"] or
                    score.get("fields") != expected[condition]["fields"] or
                    score.get("outcomes", {}).get("valid") != 60 or
                    any(value for key, value in score.get("outcomes", {}).items()
                        if key != "valid") or score.get("invalidIds") != []):
                raise ValueError(f"Kev {condition} {name} score or outcomes differ")
            for source in phase.get("sourceBindings") or []:
                if source_map.get(source.get("path")) != source.get("sha256"):
                    raise ValueError(f"Kev {condition} {name} source subset differs")
            scores.append(score["allFour"])
            for field in FIELDS:
                fields[field].append(score["fields"][field])
            phase_usage = phase.get("usage") or {}
            try:
                cost = Decimal(str(phase_usage["actualProviderCostUsd"]))
                client_seconds = phase_usage["clientRequestSeconds"]["total"]
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"Kev {condition} {name} usage differs") from None
            if (not cost.is_finite() or cost < 0 or
                    type(client_seconds) not in (int, float) or
                    not math.isfinite(client_seconds) or client_seconds < 0 or
                    phase_usage["clientRequestSeconds"].get("kind") !=
                        "client_observed_request"):
                raise ValueError(f"Kev {condition} {name} usage differs")
            usage["inputTokens"] += phase_usage["inputTokens"]
            usage["outputTokens"] += phase_usage["outputTokens"]
            usage["actualProviderCostUsd"] += cost
            usage["clientRequestSeconds"] += client_seconds
        for comparison in item["repeatComparisons"]:
            if (comparison.get("denominator") != 60 or
                    comparison.get("fourFieldVectorChanges") != 0 or
                    comparison.get("fourFieldVectorChangedIds") != [] or
                    comparison.get("nativeProbabilityDictionaryChanges") != 0 or
                    comparison.get("vendorConfidenceChanges") != 0):
                raise ValueError(f"Kev {condition} repeat stability differs")
        projected_conditions[condition] = {
            "completedPasses": 3, "scores": scores, "fields": fields,
            "changedFourFieldVectorIdsAcrossRepeats": [],
            "usage": {"inputTokens": usage["inputTokens"],
                "outputTokens": usage["outputTokens"],
                "actualProviderCostUsd": str(usage["actualProviderCostUsd"]),
                "clientRequestSeconds": usage["clientRequestSeconds"],
                "timingKind": "client-observed request time; not pure inference time"},
        }

    paired = report.get("pairedP1P2") or []
    expected_delta = {"allFour": -3, "fields": {"sentiment": 1,
        "follow_up_needed": -5, "serious_concern_reported": 0,
        "testimonial_potential": 1}}
    if (len(paired) != 3 or [row.get("stage") for row in paired] !=
            ["fresh1", "fresh2", "fresh3"] or
            any(row.get("denominator") != 60 or row.get("fourFieldVectorChanges") != 7 or
                row.get("fourFieldVectorChangedIds") != expected_ids or
                row.get("scoreDeltaP2MinusP1") != expected_delta
                for row in paired)):
        raise ValueError("Kev matched P1/P2 comparison differs")
    historical = report.get("historicalP0") or {}
    clean = historical.get("cleanComparisons") or {}
    if (historical.get("controlsVerified") is not True or
            historical.get("interruptedThirdExcluded") is not True or
            set(clean) != {"fresh1", "fresh2"} or
            any(clean[name].get("score") != {"denominator": 60, "valid": 60,
                "allFour": 48, "fields": {"sentiment": 52,
                    "follow_up_needed": 58, "serious_concern_reported": 55,
                    "testimonial_potential": 59}} for name in clean)):
        raise ValueError("Kev historical P0 boundary differs")
    for name, phase in clean.items():
        bind_report_sources(root, phase, bindings, f"Kev historical P0 {name}")
    return {"source": KEV_NATIVE_PROMPT_PUBLIC,
        "findings": "docs/KEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md",
        "nativePromptEquivalence": report["nativePromptEquivalence"],
        "conditions": projected_conditions,
        "matchedP1P2": {"passes": 3, "changedFourFieldVectorIds": expected_ids,
            "changedReviewsPerPass": 7, "scoreDeltaP2MinusP1": expected_delta},
        "historicalP0": {"scope": "separate descriptive baseline",
            "cleanPasses": ["fresh1", "fresh2"], "scores": [48, 48],
            "interruptedThirdExcluded": True}}


def jev_native_prompt_summary(root, report, bindings):
    """Recompute the native report from raw evidence before projecting it."""
    import build_jev_native_prompt_findings as jev
    source_map = bind_report_sources(root, report, bindings, "Jev native prompt report")
    # The canonical verifier uses its checkout-relative archive. The hash map
    # above verifies every equivalent source under --root before projection.
    verified = jev.build()
    if source_map != {item["path"]: item["sha256"] for item in verified["sourceBindings"]}:
        raise ValueError("Jev native prompt source closure differs")
    for condition, passes in verified["passes"].items():
        for stage, item in passes.items():
            if report.get("passes", {}).get(condition, {}).get(stage) != item:
                raise ValueError(f"Jev {condition} {stage} outcome differs")
    if report != verified:
        raise ValueError("Jev native prompt coverage or comparisons differ")
    projected = {}
    for condition, passes in report["passes"].items():
        projected[condition] = {"plannedPasses": 3,
            "completePasses": sum(item["status"] == "complete" for item in passes.values()),
            "passes": {stage: {
                "status": item["status"], "score": item["score"],
                "outcomes": item["outcomes"],
                "knownProviderCostUsd": item["knownCostUsd"],
                "unknownChargeUpperBoundUsd": item["unknownUpperBoundUsd"],
                "inputTokens": item["inputTokens"], "outputTokens": item["outputTokens"],
                "clientSeconds": item["clientSeconds"],
                "cleanRepeatEligible": item["status"] == "complete" and item["score"]["valid"] == 60,
            } for stage, item in passes.items()}}
    compact = {name: {"denominator": item["denominator"],
        "excludedIds": item["excludedIds"],
        "fourFieldVectorChangedIds": item["fourFieldVectorChangedIds"],
        "fields": {field: {kind: len(ids) for kind, ids in changes.items()}
                   for field, changes in item["fields"].items()}}
        for name, item in report["comparisons"].items()}
    return {"source": JEV_NATIVE_PROMPT_PUBLIC,
            "findings": "docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md",
            "routeScope": "standalone OpenRouter native Choice route; same Jev model",
            "denominator": 60, "conditions": projected, "comparisons": compact,
            "continuations": report["continuations"], "composites": report["composites"],
            "partialBoundary": {"P2fresh2": {"attempted": 60, "valid": 57,
                "unknownCostIds": ["DEV-018", "DEV-060"], "neverSentIds": [],
                "fullPassScore": None, "descriptiveAllFour": 50,
                "cleanRepeatEligible": False},
                "P1fresh2Invalid": {"id": "DEV-056",
                    "reason": "native probability distribution validation failure; categorical labels not adjudicated",
                    "strictAllFour": 53}}}


def score_values(series, condition):
    return series["threePassSummary"][condition]["allFour"]["values"]


def qwen17_off_repeat_summary(series):
    """Carry closed scores and unscored phase status from the bound repeat feed."""
    passes = series.get("passes", {})
    names = ("fresh1", "fresh2", "fresh3")
    if (series.get("plannedConditions") != 9 or
            set(passes) != set(names) or
            any(set(passes[name]) - set(CONDITIONS) for name in names)):
        raise ValueError("Qwen1.7B thinking-off repeat coverage differs")
    completed = sum(len(passes[name]) for name in names)
    missing = series.get("missingPasses", [])
    expected_missing = {(name, condition) for name in names for condition in CONDITIONS
                        if condition not in passes[name]}
    if (series.get("completedConditions") != completed or
            len(missing) != len(expected_missing) or
            {(item.get("pass"), item.get("condition")) for item in missing} != expected_missing):
        raise ValueError("Qwen1.7B thinking-off missing phases differ")
    conditions = {}
    for condition in CONDITIONS:
        closed = []
        for name in names:
            phase = passes[name].get(condition)
            if phase is None:
                continue
            score = phase.get("score", {})
            if (phase.get("completionStatus") != "complete" or
                    score.get("denominator") != 60 or
                    not 0 <= score.get("allFour", -1) <= score.get("valid", -1) <= 60):
                raise ValueError("Qwen1.7B thinking-off closed score differs")
            closed.append({"pass": name, "score": score})
        pairs = [item for item in series.get("pairwiseFlips", [])
                 if item.get("condition") == condition]
        if len(pairs) != len(closed) * (len(closed) - 1) // 2:
            raise ValueError("Qwen1.7B thinking-off pairwise coverage differs")
        three_pass = series.get("changesAcrossThreePasses", {}).get(condition)
        if (len(closed) == 3) != (three_pass is not None):
            raise ValueError("Qwen1.7B thinking-off three-pass coverage differs")
        conditions[condition] = {"completedPasses": len(closed), "passes": closed,
                                 "allFourRange": ([min(x["score"]["allFour"] for x in closed),
                                                    max(x["score"]["allFour"] for x in closed)]
                                                   if closed else None),
                                 "pairwiseFlips": pairs,
                                 "changesAcrossThreePasses": three_pass}
    remaining = []
    for item in missing:
        if item.get("status") == "smoke_blocked":
            if (item.get("stage") != "smoke" or item.get("attempted") != 3 or
                    item.get("saved") != 3 or
                    item.get("valid", -1) + item.get("invalid", -1) != 3 or
                    "score" in item or not item.get("evidence", {}).get("completion")):
                raise ValueError("Qwen1.7B thinking-off stopped smoke differs")
        remaining.append(item)
    return {"completedConditions": completed, "plannedConditions": 9,
            "conditions": conditions, "missingPasses": remaining}


def qwen35_repeat_summary(series):
    """Project closed scores and source-bound unscored Qwen3.5 interruptions."""
    names = ("fresh1", "fresh2", "fresh3")
    passes = series.get("passes", {})
    if (series.get("plannedConditions") != 9 or set(passes) != set(names) or
            any(set(passes[name]) - set(CONDITIONS) for name in names)):
        raise ValueError("Qwen3.5 repeat coverage differs")
    completed = sum(len(passes[name]) for name in names)
    missing = series.get("missingPasses", [])
    expected_missing = {(name, condition) for name in names for condition in CONDITIONS
                        if condition not in passes[name]}
    if (series.get("completedConditions") != completed or
            len(missing) != len(expected_missing) or
            {(item.get("pass"), item.get("condition")) for item in missing} != expected_missing):
        raise ValueError("Qwen3.5 missing phases differ")
    partial = series.get("partialPasses", [])
    descriptive = series.get("descriptiveComposites", [])
    if not isinstance(partial, list) or len(partial) > 1:
        raise ValueError("Qwen3.5 partial coverage differs")
    if not isinstance(descriptive, list) or len(descriptive) > 1:
        raise ValueError("Qwen3.5 descriptive coverage differs")
    bound = {item.get("path"): item.get("sha256") for item in series.get("sourceBindings", [])}

    def bound_source(source):
        return (isinstance(source, dict) and set(source) == {"path", "sha256"} and
                isinstance(source["path"], str) and
                isinstance(source["sha256"], str) and
                bound.get(source["path"]) == source["sha256"])

    def bound_group(group, keys):
        return (isinstance(group, dict) and set(group) == set(keys) and
                all(bound_source(source) for source in group.values()))

    continuation = "results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-after-smoke-failure-v1"
    blocked_folder = "results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh2/P2"
    blocked_keys = {"review", "claim", "journal", "raw", "records", "completion",
                    "hostAudit", "candidate", "hostBaseline", "runtimePreflight",
                    "routeAudit", "routeRaw"}
    continuation_authority_keys = {"proposal", "designReview", "controller", "blockedSmoke"}
    continuation_smoke_keys = {"review", "claim", "raw", "records", "journal",
                               "completion", "hostAudit", "candidate"}
    for item in missing:
        slot = (item.get("pass"), item.get("condition"))
        status = item.get("status")
        if slot == ("fresh2", "P2") and status == "smoke_blocked":
            evidence = item.get("evidence")
            if (item.get("stage") != "smoke" or
                    (item.get("attempted"), item.get("saved"), item.get("valid"),
                     item.get("invalid")) != (3, 3, 2, 1) or
                    item.get("invalidReasonIds") != {"non_json": ["DEV-001"]} or
                    item.get("cleanRepeatEligible") is not False or
                    item.get("intrinsicModelFailure") is not True or
                    item.get("developmentAdmitted") is not False or
                    item.get("source") != "qwen35_after_smoke_failure_v1" or
                    item.get("sourcePath") != blocked_folder or "score" in item or
                    not isinstance(evidence, dict) or
                    set(evidence) != {"proposal", "designReview", "controller", "smoke"} or
                    not all(bound_source(evidence[key]) for key in
                            ("proposal", "designReview", "controller")) or
                    not bound_group(evidence["smoke"], blocked_keys)):
                raise ValueError("Qwen3.5 blocked continuation smoke differs")
        elif slot == ("fresh2", "P1") and status == "stopped_unknown":
            evidence = item.get("evidence")
            if (item.get("stage") != "smoke" or
                    (item.get("attempted"), item.get("saved"), item.get("valid"),
                     item.get("invalid")) != (3, 2, 2, 0) or
                    item.get("unknownStartedIds") != ["DEV-003"] or
                    item.get("neverSentIds") != [] or
                    item.get("cleanRepeatEligible") is not False or
                    item.get("failureClass") != "host_sleep_during_timeout" or
                    item.get("intrinsicModelFailure") is not False or
                    item.get("developmentAdmitted") is not False or
                    item.get("source") != "qwen35_after_smoke_failure_v1" or
                    item.get("sourcePath") != continuation + "/fresh2/P1" or
                    "score" in item or not isinstance(evidence, dict) or
                    set(evidence) != {"authority", "smoke"} or
                    not isinstance(evidence["authority"], dict) or
                    set(evidence["authority"]) != continuation_authority_keys or
                    not all(bound_source(evidence["authority"][key]) for key in
                            ("proposal", "designReview", "controller")) or
                    not bound_group(evidence["authority"]["blockedSmoke"], blocked_keys) or
                    not bound_group(evidence["smoke"], continuation_smoke_keys)):
                raise ValueError("Qwen3.5 interrupted continuation smoke differs")
        elif status == "smoke_blocked" and slot != ("fresh2", "P2"):
            raise ValueError("Qwen3.5 unexpected blocked smoke")
    for item in partial:
        slot = (item.get("pass"), item.get("condition"))
        unknown = item.get("unknownStartedIds")
        unsent = item.get("neverSentIds")
        evidence = item.get("evidence")
        if (slot != ("fresh1", "P0") or slot not in expected_missing or
                (item not in missing and not any(c.get("originalInterruption") == item
                                                 for c in descriptive)) or
                item.get("status") != "stopped_unknown" or
                item.get("attempted") != 52 or item.get("saved") != 51 or
                item.get("valid") != 44 or item.get("invalid") != 7 or
                unknown != ["DEV-052"] or
                unsent != [f"DEV-{i:03d}" for i in range(53, 61)] or
                item.get("cleanRepeatEligible") is not False or
                "score" in item or
                item["saved"] != item["valid"] + item["invalid"] or
                item["attempted"] != item["saved"] + len(unknown) or
                item["attempted"] + len(unsent) != 60 or
                not isinstance(evidence, dict) or
                set(evidence) != {"admission", "claim", "completion", "raw",
                                  "records", "journal", "hostAudit", "rootReview"} or
                any(not isinstance(source, dict) or bound.get(source.get("path")) != source.get("sha256")
                    for source in evidence.values())):
            raise ValueError("Qwen3.5 partial source or counts differ")
    if any(item.get("status") == "stopped_unknown" and item not in partial and
           (item.get("pass"), item.get("condition")) != ("fresh2", "P1")
           for item in missing):
        raise ValueError("Qwen3.5 stopped phase is not projected")
    for item in descriptive:
        score = item.get("score", {})
        outcomes = score.get("outcomes", {})
        evidence = item.get("evidence")
        if (len(partial) != 1 or item.get("originalInterruption") != partial[0] or
                (item.get("pass"), item.get("condition")) != ("fresh1", "P0") or
                item not in missing or ("fresh1", "P0") not in expected_missing or
                item.get("status") != "completed_interrupted_composite" or
                item.get("completionStatus") != "descriptive_interrupted" or
                item.get("cleanRepeatEligible") is not False or
                score.get("denominator") != 60 or
                not 0 <= score.get("allFour", -1) <= score.get("valid", -1) <= 59 or
                outcomes.get("valid") != score.get("valid") or
                outcomes.get("unknown_started") != 1 or
                outcomes.get("never_sent") != 0 or
                outcomes.get("invalid_output") != 59 - score.get("valid", -1) or
                sum(outcomes.values()) != 60 or
                not isinstance(evidence, dict) or
                set(evidence) != {"claim", "journal", "raw", "records", "completion",
                                  "review", "manifest", "controller", "compositeReview"} or
                any(not isinstance(source, dict) or bound.get(source.get("path")) != source.get("sha256")
                    for source in evidence.values())):
            raise ValueError("Qwen3.5 descriptive composite differs")
    if any(item.get("status") == "completed_interrupted_composite" and item not in descriptive
           for item in missing):
        raise ValueError("Qwen3.5 composite is not projected")
    conditions = {}
    for condition in CONDITIONS:
        closed = []
        for name in names:
            phase = passes[name].get(condition)
            if phase is None:
                continue
            score = phase.get("score", {})
            usage = phase.get("usage", {})
            outcomes = score.get("outcomes", {})
            if (phase.get("completionStatus") != "complete" or
                    score.get("denominator") != 60 or
                    not 0 <= score.get("allFour", -1) <= score.get("valid", -1) <= 60 or
                    outcomes.get("valid") != score["valid"] or
                    sum(outcomes.values()) != 60 or
                    usage.get("requestCount") != 60 or
                    usage.get("timeBasis") != "client_observed_wall_clock" or
                    not isinstance(usage.get("clientRequestSecondsTotal"), (int, float)) or
                    usage["clientRequestSecondsTotal"] < 0 or
                    usage.get("inferenceSeconds") is not None or
                    usage.get("actualCostUsd") is not None):
                raise ValueError("Qwen3.5 closed phase score or usage differs")
            closed.append({"pass": name, "score": score, "usage": usage})
        pairs = [item for item in series.get("pairwiseFlips", [])
                 if item.get("condition") == condition]
        expected_pairs = {(left, right) for i, left in enumerate(
            [item["pass"] for item in closed]) for right in
            [item["pass"] for item in closed][i + 1:]}
        if {(item.get("from"), item.get("to")) for item in pairs} != expected_pairs or len(pairs) != len(expected_pairs):
            raise ValueError("Qwen3.5 pairwise coverage differs")
        three_pass = series.get("changesAcrossThreePasses", {}).get(condition)
        if (len(closed) == 3) != (three_pass is not None):
            raise ValueError("Qwen3.5 three-pass coverage differs")
        conditions[condition] = {"completedPasses": len(closed), "passes": closed,
                                 "pairwiseFlips": pairs,
                                 "changesAcrossThreePasses": three_pass}
    matched = {}
    for name in names:
        first = passes[name]
        if "P0" in first:
            matched[name] = {condition: first[condition]["score"]["allFour"] -
                             first["P0"]["score"]["allFour"]
                             for condition in ("P1", "P2") if condition in first}
    result = {"completedConditions": completed, "plannedConditions": 9,
              "conditions": conditions, "matchedP0AllFourDeltas": matched,
              "missingPasses": missing, "partialPasses": partial}
    if descriptive:
        result["descriptiveComposites"] = descriptive
    return result


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


def clef_p1_first_pass(root, labels, bindings):
    """Score two closed native passes offline; do not imply repeat coverage."""
    phases = {}
    for condition in ("P0", "P1"):
        base = f"results/clef-native-v1/clef/fresh1/{condition}/development"
        completion = read(root, base + "/completion.json", bindings)
        if (completion.get("status") != "complete" or completion.get("attempted") != 60
                or completion.get("counts", {}).get("valid") != 60
                or completion.get("never_sent") != []):
            raise ValueError("Clef first-pass completion is not 60 valid records")
        for kind in ("claim", "journal", "raw", "records"):
            name = base + "/" + kind + (".json" if kind == "claim" else ".jsonl")
            digest = sha(root / name)
            if digest != completion.get(kind + "_sha256"):
                raise ValueError("Clef first-pass evidence hash changed: " + name)
            bindings[name] = digest
        records = [json.loads(line) for line in (root / (base + "/records.jsonl")).read_text().splitlines()]
        if [r.get("id") for r in records] != [f"DEV-{i:03d}" for i in range(1, 61)]:
            raise ValueError("Clef first-pass record order differs")
        for row in records:
            parsed = row.get("parsed") or {}
            if (row.get("status") != "valid" or row.get("reference_labels_read") is not False
                    or parsed.get("returned_model") != "clef"
                    or set(parsed.get("prediction", {})) != set(FIELDS)):
                raise ValueError("Clef first-pass record identity or isolation differs")
        phases[condition] = records
    predictions = {c: {r["id"]: r["parsed"]["prediction"] for r in rows}
                   for c, rows in phases.items()}
    hit = lambda c, i: all(predictions[c][i][f] == labels[i][f] for f in FIELDS)
    ids = list(predictions["P1"])
    usage = [r["parsed"]["usage"] for r in phases["P1"]]
    if any(type(u.get(k)) is not int or u[k] < 0 for u in usage
           for k in ("input_tokens", "output_tokens")):
        raise ValueError("Clef P1 usage unavailable")
    inputs = sum(u["input_tokens"] for u in usage)
    return {"source": "results/clef-native-v1/clef/fresh1/P1/development/records.jsonl",
            "findings": "docs/CLEF_P1_FIRST_PASS_2026-10-05.md",
            "condition": "P1", "pass": "fresh1", "valid": 60, "denominator": 60,
            "completedP1Passes": 1, "plannedP1Passes": 3,
            "allFour": sum(hit("P1", i) for i in ids),
            "perField": {f: sum(predictions["P1"][i][f] == labels[i][f] for i in ids) for f in FIELDS},
            "matchedP0": {"allFour": sum(hit("P0", i) for i in ids),
                "changedIds": [i for i in ids if predictions["P0"][i] != predictions["P1"][i]],
                "gainedIds": [i for i in ids if hit("P1", i) and not hit("P0", i)],
                "lostIds": [i for i in ids if hit("P0", i) and not hit("P1", i)]},
            "inputTokens": inputs, "outputTokens": sum(u["output_tokens"] for u in usage),
            "inputPriceEstimateUsd": str(Decimal(inputs) * Decimal("0.24") / Decimal(1000000)),
            "priceSource": "https://developers.cloudflare.com/workers-ai/models/clef/",
            "providerBilledUsd": None, "pureInferenceLatencyAvailable": False,
            "repeatabilityClaim": False}


def clef_flash_latest_p0_interruption(root, bindings):
    """Verify the closed parent and suffix before projecting their fixed 60 IDs."""
    unknown = []
    previous_completion = None
    for directory, rid, remainder in (
            (CLEF_FLASH_P0_PARENT, "DEV-001", list(range(2, 61))),
            (CLEF_FLASH_P0_SUFFIX, "DEV-002", list(range(3, 61)))):
        done = read(root, directory + "/completion.json", bindings)
        if (done.get("model") != "clef-flash" or done.get("status") != "stopped" or
                done.get("stage") != directory.removeprefix("results/clef-native-v1/") or
                done.get("attempted") != 1 or done.get("counts") != {
                    "valid": 0, "invalid_output": 0, "service_error": 0, "unknown_outcome": 1} or
                done.get("never_sent") != [f"DEV-{i:03d}" for i in remainder]):
            raise ValueError("Clef Flash interruption boundary differs")
        for name, key in [("claim.json", "claim_sha256"), ("journal.jsonl", "journal_sha256"),
                          ("raw.jsonl", "raw_sha256"), ("records.jsonl", "records_sha256")]:
            name = directory + "/" + name
            bindings[name] = sha(root / name)
            if bindings[name] != done.get(key):
                raise ValueError("Clef Flash interruption source hash differs")
        records = [json.loads(line) for line in (root / directory / "records.jsonl").read_text().splitlines()]
        if (len(records) != 1 or records[0].get("id") != rid or
                records[0].get("status") != "unknown_outcome" or
                records[0].get("parsed") is not None or records[0].get("reference_labels_read") is not False):
            raise ValueError("Clef Flash interruption terminal record differs")
        audit = read(root, directory + "/external-error-audit.json", bindings)
        if (audit.get("completion_sha256") != bindings[directory + "/completion.json"] or
                audit.get("id") != rid or audit.get("attempt_id") != records[0].get("attempt_id") or
                audit.get("no_replay") is not True or audit.get("provider_envelope_available") is not False):
            raise ValueError("Clef Flash interruption audit differs")
        if previous_completion is not None and done.get("parent_completion_sha256") != previous_completion:
            raise ValueError("Clef Flash suffix parent differs")
        previous_completion = bindings[directory + "/completion.json"]
        unknown.append(rid)
    return {"status": "interrupted_unscored", "unknownOutcomeIds": unknown,
            "neverSentCount": 58, "neverSentIds": [f"DEV-{i:03d}" for i in range(3, 61)],
            "valid": 0, "score": None, "reviewCount": 60,
            "source": CLEF_FLASH_P0_SUFFIX + "/completion.json"}


def qwen_prompt_pairs(root, phases, labels, bindings):
    """Compare the same reviews; report invalid transitions outside shared-valid flips."""
    decisions = {}
    for condition in CONDITIONS:
        source = phases[condition]["evidence"]["development"]["records"]
        path = source["path"]
        digest = sha(root / path)
        if digest != source["sha256"]:
            raise ValueError(f"Qwen prompt-pair record hash differs: {path}")
        bindings[path] = digest
        rows = [json.loads(line) for line in (root / path).read_text().splitlines()]
        if (len(rows) != 60 or [r["id"] for r in rows] != sorted(labels)
                or any(r.get("reference_labels_read") is not False for r in rows)):
            raise ValueError("Qwen prompt-pair membership or isolation differs")
        decisions[condition] = {r["id"]: r["decision"] for r in rows}
        valid_rows = {r["id"]: r["decision"]["prediction"] for r in rows
                      if r["decision"]["status"] == "ok"}
        if any(set(pred) != set(FIELDS) for pred in valid_rows.values()):
            raise ValueError("Qwen valid prediction fields differ")
        score = phases[condition]["score"]
        if (len(valid_rows) != score["valid"] or
                sum(pred == labels[rid] for rid, pred in valid_rows.items()) != score["allFour"]):
            raise ValueError("Qwen prompt-pair score differs")
    output = {}
    base = decisions["P0"]
    for condition in ("P1", "P2"):
        other = decisions[condition]
        shared = [rid for rid in sorted(labels)
                  if base[rid]["status"] == other[rid]["status"] == "ok"]
        correct_a = {rid for rid in shared if base[rid]["prediction"] == labels[rid]}
        correct_b = {rid for rid in shared if other[rid]["prediction"] == labels[rid]}
        invalidated = [rid for rid in sorted(labels)
                       if base[rid]["status"] == "ok" and other[rid]["status"] != "ok"]
        output[condition] = {
            "sharedValid": len(shared), "baseMatchesOnShared": len(correct_a),
            "promptMatchesOnShared": len(correct_b),
            "gainedMatchIds": sorted(correct_b - correct_a),
            "lostMatchIds": sorted(correct_a - correct_b),
            "changedLabelIds": [rid for rid in shared if base[rid]["prediction"] != other[rid]["prediction"]],
            "validToInvalidIds": invalidated,
            "previouslyCorrectNowInvalidIds": [rid for rid in invalidated if base[rid]["prediction"] == labels[rid]],
            "invalidToValidIds": [rid for rid in sorted(labels)
                                  if base[rid]["status"] != "ok" and other[rid]["status"] == "ok"],
            "fixedDenominator": 60,
        }
    return output


def build(root=ROOT):
    bindings = {}
    data = {name: read(root, name, bindings) for name in SOURCES if not name.endswith(".jsonl")}
    labels_path = "data/pilot/proposed_labels.jsonl"
    bindings[labels_path] = sha(root / labels_path)
    rows = [json.loads(line) for line in (root / labels_path).read_text().splitlines()]
    labels = {row["id"]: row["proposed_labels"] for row in rows}
    if len(labels) != 60 or any(row["review_version"] != "0.2" for row in rows):
        raise ValueError("Expected 60 frozen v0.2 references")

    clef_p1 = clef_p1_first_pass(root, labels, bindings)
    kev_native_prompts = kev_native_prompt_summary(
        root, data[KEV_NATIVE_PROMPT_PUBLIC], bindings)
    import build_e4b_interruption_findings as e4b_report
    e4b_source = "public-site/e4b-interruption-findings.json"
    e4b = data[e4b_source]
    bind_report_sources(root, e4b, bindings, "E4B interrupted report")
    if e4b != e4b_report.build(root):
        raise ValueError("E4B interrupted report differs from raw evidence")
    jev_native_prompts = jev_native_prompt_summary(
        root, data[JEV_NATIVE_PROMPT_PUBLIC], bindings)
    gemini_authority = gemini_authority_summary(
        root, data[GEMINI_AUTHORITY_PUBLIC], bindings)
    hosted_fresh = hosted_fresh_summary(root, data[HOSTED_FRESH_PUBLIC], bindings)
    import build_deepseek_low_p1_successor_findings as low_p1_builder
    low_p1 = data[LOW_P1_SUCCESSOR_PUBLIC]
    if low_p1 != low_p1_builder.build(root):
        raise ValueError('DeepSeek low P1 continuation differs from bound evidence')
    bind_report_sources(root, low_p1, bindings, 'DeepSeek low P1 continuation')
    import build_deepseek_low_remaining6_price_v2_findings as low_revised_builder
    low_revised = data[LOW_REVISED_PUBLIC]
    if low_revised != low_revised_builder.build(root):
        raise ValueError('Revised-price DeepSeek low report differs from closed evidence')
    bind_report_sources(root, low_revised, bindings, 'Revised-price DeepSeek low')

    import build_deepseek_high_remaining6_successor_findings as high_successor_builder
    high_successor = data[HIGH_SUCCESSOR_PUBLIC]
    if high_successor != high_successor_builder.build(root):
        raise ValueError('DeepSeek high successor report differs from closed evidence')
    bind_report_sources(root, high_successor, bindings, 'DeepSeek high successor')

    import build_liquid_d1_native_full_aggregate as liquid_builder
    liquid = data[LIQUID_PUBLIC]
    if liquid != liquid_builder.build(root):
        raise ValueError('Liquid report differs from closed evidence')
    bind_report_sources(root, liquid, bindings, 'Liquid native decision results')

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
    import build_deepseek_low_final_suffix_findings as deepseek_final_builder
    deepseek_final = data["public-site/deepseek-low-final-suffix-findings.json"]
    if deepseek_final != deepseek_final_builder.build(root):
        raise ValueError("DeepSeek final suffix differs from closed evidence")
    for item in deepseek_final["sourceBindings"]:
        bindings[item["path"]] = item["sha256"]
    deepseek_latest = deepseek_final["series"][0]
    gemma = data["public-site/gemma26-second-continuation-findings.json"]
    gemma_postabort = data["public-site/gemma26-postabort-findings.json"]
    gemma_p2_repeat = data["public-site/gemma26-p2-repeat-findings.json"]
    gemma_p0 = data["public-site/gemma26-fresh3-p0-checkpoint.json"]
    gemma_p1 = data["public-site/gemma26-fresh3-p1-interrupted-checkpoint.json"]
    if (gemma_p0.get("schema") != "gemma26-on-v2-fresh3-checkpoint-v1" or
            gemma_p0.get("cutoff") != "P0" or gemma_p0.get("scoredSeriesConditions") != 8 or
            gemma_p0.get("denominator") != 60 or gemma_p0.get("cleanMatchedThreeEligible") is not False):
        raise ValueError("Gemma P0 checkpoint differs from reviewed sources")
    for item in gemma_p0["sourceBindings"]:
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts or sha(root / path) != item["sha256"]:
            raise ValueError("Gemma P0 checkpoint source hash differs")
        bindings[item["path"]] = item["sha256"]
    p1_scores = gemma_p1.get("conditions", {}).get("P1", {}).get("fixed60Scores", {})
    p1_shared = gemma_p1.get("conditions", {}).get("P1", {}).get("allThreeSharedValid", {})
    p1_usage = gemma_p1.get("conditions", {}).get("P1", {}).get("thirdPassUsage", {})
    if (gemma_p1.get("schema") != "gemma26-fresh3-p1-interrupted-checkpoint-v1" or
            gemma_p1.get("cutoff") != "P1_interrupted_after_DEV060" or
            gemma_p1.get("denominator") != 60 or
            gemma_p1.get("scoredSeriesConditions") != 9 or
            gemma_p1.get("plannedConditions") != 9 or
            gemma_p1.get("cleanMatchedThreeEligible") is not False or
            gemma_p1.get("conditions", {}).get("P0") != gemma_p0["conditions"]["P0"] or
            [p1_scores.get(name, {}).get("allFour") for name in ("fresh1", "fresh2", "fresh3")]
                != [58, 58, 57] or
            [p1_scores.get(name, {}).get("valid") for name in ("fresh1", "fresh2", "fresh3")]
                != [60, 60, 59] or
            any(p1_scores.get(name, {}).get("denominator") != 60 or
                p1_scores[name].get("scoreKind") != "fixed_60"
                for name in ("fresh1", "fresh2", "fresh3")) or
            gemma_p1["conditions"]["P1"].get("failureIdsByPass") !=
                {"fresh1": [], "fresh2": [], "fresh3": ["DEV-059"]} or
            p1_shared.get("denominator") != 59 or
            p1_shared.get("excludedIds") != ["DEV-059"] or
            p1_shared.get("allFourMatches") !=
                {"fresh1": 57, "fresh2": 57, "fresh3": 57} or
            p1_usage.get("reportedKnownCostUsd") != "0.01941923" or
            p1_usage.get("reportedCostCount") != 59 or
            p1_usage.get("missingCostCount") != 1 or
            p1_usage.get("providerBilledUsd") is not None or
            p1_usage.get("pureInferenceSeconds") is not None or
            p1_usage.get("reportedReasoningExceedsCompletion") is not True or
            "categories conflict" not in p1_usage.get("tokenCategoryCaveat", "") or
            len(gemma_p1.get("sourceBindings", [])) != 17):
        raise ValueError("Gemma P1 interrupted checkpoint differs from reviewed source")
    for item in gemma_p1["sourceBindings"]:
        path = Path(item["path"])
        if (path.is_absolute() or ".." in path.parts or
                sha(root / path) != item["sha256"]):
            raise ValueError("Gemma P1 checkpoint source hash differs")
        bindings[item["path"]] = item["sha256"]
    clef = data["public-site/clef-findings.json"]
    clef_repeat = data["public-site/clef-p0-repeat-findings.json"]
    clef_third = data["public-site/clef-p0-third-checkpoint.json"]
    latest_flash_p0_interruption = clef_flash_latest_p0_interruption(root, bindings)
    mistral_original = data[MISTRAL_ORIGINAL]
    mistral_first = data[MISTRAL_FIRST_SUFFIX]
    mistral_second = data[MISTRAL_SECOND_SUFFIX]
    gemma_terminal = data[GEMMA_TERMINAL]
    clef_flash_p1 = data[CLEF_FLASH_P1]
    public_clef_flash_p1 = root / CLEF_FLASH_P1_PUBLIC
    if (not public_clef_flash_p1.is_file() or
            public_clef_flash_p1.read_bytes() != (root / CLEF_FLASH_P1).read_bytes()):
        raise ValueError("Public Clef Flash P1 projection differs from reviewed source")
    bindings[CLEF_FLASH_P1_PUBLIC] = sha(public_clef_flash_p1)
    flash_p2 = data[CLEF_FLASH_P2]
    if (root / CLEF_FLASH_P2_PUBLIC).read_bytes() != (root / CLEF_FLASH_P2).read_bytes():
        raise ValueError("Public Clef Flash P2 projection differs from reviewed source")
    bindings[CLEF_FLASH_P2_PUBLIC] = sha(root / CLEF_FLASH_P2_PUBLIC)
    if (flash_p2.get("schema") != "clef-flash-p2-findings-v1" or
            flash_p2.get("controls", {}).get("fullPassesCompleted") != 3 or
            set(flash_p2.get("phaseByPass", {})) != {"fresh1", "fresh2", "fresh3"}):
        raise ValueError("Clef Flash P2 coverage differs")
    for phase in flash_p2["phaseByPass"].values():
        if phase["counts"] != {"valid": 60, "invalidOutput": 0, "serviceError": 0,
                               "unknownOutcome": 0, "neverSent": 0}:
            raise ValueError("Clef Flash P2 outcomes differ")
    for pair in ("p2Repeatability", "p2Fresh1Fresh3", "p2Fresh2Fresh3"):
        comparison = flash_p2["controls"][pair]
        if comparison["sharedValid"] != 60 or any(comparison[field] for field in (
                "predictionVectorChangedIds", "nativeDistributionsChangedIds",
                "vendorConfidenceChangedIds")):
            raise ValueError("Clef Flash P2 repeat findings differ")
    mistral_p0 = data[MISTRAL_P0_PUBLIC]
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
    p1_passes = clef_flash_p1.get("phaseByPass") or {}
    p1_repeat = (clef_flash_p1.get("controls") or {}).get("p1Repeatability") or {}
    p1_matched = (clef_flash_p1.get("controls") or {}).get("matchedFresh1P0") or {}
    p1_expected_passes = {"fresh1", "fresh2", "fresh3"}
    if (clef_flash_p1.get("schema") != "clef-flash-p1-findings-v1" or
            clef_flash_p1.get("configuration", {}).get("model") != "clef-flash" or
            clef_flash_p1.get("configuration", {}).get("condition") != "P1" or
            clef_flash_p1.get("configuration", {}).get("referenceLabelsSent") is not False or
            set(p1_passes) != p1_expected_passes or
            any(p.get("counts", {}).get("valid") != 60 or
                p.get("counts", {}).get("invalidOutput") != 0 or
                p.get("counts", {}).get("serviceError") != 0 or
                p.get("counts", {}).get("unknownOutcome") != 0 or
                p.get("counts", {}).get("neverSent") != 0 or
                p.get("allFourCorrect") != 47 or p.get("allFourDenominator") != 60
                for p in p1_passes.values()) or
            p1_repeat.get("sharedValid") != 60 or
            p1_repeat.get("predictionVectorChangedIds") != [] or
            p1_repeat.get("nativeDistributionsChangedIds") != [] or
            p1_repeat.get("vendorConfidenceChangedIds") != [] or
            p1_matched.get("auditPassed") is not True or
            p1_matched.get("sharedValid") != 60 or
            p1_matched.get("p0AllFourCorrect") != 45 or
            p1_matched.get("p1AllFourCorrect") != 47 or
            p1_matched.get("comparison", {}).get("allFourBecameCorrectIds") !=
                ["DEV-027", "DEV-044"] or
            p1_matched.get("comparison", {}).get("allFourBecameIncorrectIds") != [] or
            clef_flash_p1.get("cost", {}).get("providerBilledUsd") is not None):
        raise ValueError("Clef Flash P1 source or coverage differs")
    if (mistral_p0.get("schema") != "mistral119-fresh1-p0-partial-findings-v1" or
            mistral_p0.get("status") != "partial_unscored_as_repeat" or
            mistral_p0.get("condition") != "P0" or
            mistral_p0.get("freshPass") != "fresh1" or
            mistral_p0.get("denominator") != 60 or
            mistral_p0.get("outcomes", {}).get("valid") != 55 or
            mistral_p0.get("outcomes", {}).get("failed") != 5 or
            mistral_p0.get("outcomes", {}).get("neverSent") != 0 or
            mistral_p0.get("scoring", {}).get("allFourMatches") != 40 or
            mistral_p0.get("scoring", {}).get("allFourDenominator") != 60 or
            mistral_p0.get("scoring", {}).get("allFourAmongValid") != 0.727273 or
            mistral_p0.get("lineage", {}).get("cleanRepeatabilityClaim") is not False or
            mistral_p0.get("lineage", {}).get("referenceLabelsSent") is not False):
        raise ValueError("Mistral 119B interrupted P0 source or coverage differs")
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
                       "qwen3-0.6b-sdk-thinking-off",
                       "qwen3-1.7b-sdk-thinking-on")
    legacy_pending = ("qwen3-1.7b-sdk-thinking-off",
                      "qwen3.5-4b-sdk-thinking-on")
    if (legacy_qwen.get("schema") != "legacy-qwen-closed-phase-report-v1" or
            set(legacy_series) != set(legacy_complete + legacy_pending) or
            any(legacy_series[name].get("completedConditions") != 9 or
                legacy_series[name].get("plannedConditions") != 9 or
                legacy_series[name].get("missingPasses") or
                not legacy_series[name].get("sourceBindings")
                for name in legacy_complete) or
            any(not isinstance(legacy_series[name].get("completedConditions"), int) or
                not 0 <= legacy_series[name]["completedConditions"] <= 9 or
                legacy_series[name].get("plannedConditions") != 9
                for name in legacy_pending)):
        raise ValueError("Legacy Qwen SDK and HTTP cohort coverage differs")
    qwen17_first = legacy_series["qwen3-1.7b-sdk-thinking-on"]["passes"]["fresh1"]
    qwen17_scores = {}
    for condition in ("P0", "P1", "P2"):
        phase = qwen17_first.get(condition, {})
        score = phase.get("score", {})
        if (phase.get("completionStatus") != "complete" or score.get("denominator") != 60
                or not 0 <= score.get("allFour", -1) <= score.get("valid", -1) <= 60):
            raise ValueError("Qwen1.7B first-pass prompt evidence is incomplete")
        qwen17_scores[condition] = score
    qwen17_series = legacy_series["qwen3-1.7b-sdk-thinking-on"]
    qwen17_p2 = {"scores": [qwen17_series["passes"][p]["P2"]["score"]
                            for p in ("fresh1", "fresh2", "fresh3")],
                 "comparison": next(x for x in qwen17_series["pairwiseFlips"]
                                    if x["condition"] == "P2" and x["from"] == "fresh1"
                                    and x["to"] == "fresh2"),
                 "requiredPasses": 3, "completedPasses": 3,
                 "summary": qwen17_series["threePassSummary"]["P2"],
                 "changesAcrossThreePasses": qwen17_series["changesAcrossThreePasses"]["P2"]}
    qwen17_p1 = {"scores": [qwen17_series["passes"][p]["P1"]["score"]
                            for p in ("fresh1", "fresh2", "fresh3")],
                 "comparison": next(x for x in qwen17_series["pairwiseFlips"]
                                    if x["condition"] == "P1" and x["from"] == "fresh1"
                                    and x["to"] == "fresh2"),
                 "requiredPasses": 3, "completedPasses": 3,
                 "summary": qwen17_series["threePassSummary"]["P1"],
                 "changesAcrossThreePasses": qwen17_series["changesAcrossThreePasses"]["P1"]}
    qwen17_p0 = {"scores": [qwen17_series["passes"][p]["P0"]["score"]
                            for p in ("fresh1", "fresh2", "fresh3")],
                 "comparison": next(x for x in qwen17_series["pairwiseFlips"]
                                    if x["condition"] == "P0" and x["from"] == "fresh1"
                                    and x["to"] == "fresh2"),
                 "requiredPasses": 3, "completedPasses": 3,
                 "summary": qwen17_series["threePassSummary"]["P0"],
                 "changesAcrossThreePasses": qwen17_series["changesAcrossThreePasses"]["P0"]}
    qwen17_p1["matchedP0AllFourDeltas"] = [b["allFour"] - a["allFour"]
        for a, b in zip(qwen17_p0["scores"], qwen17_p1["scores"])]
    qwen17_p2["matchedP0AllFourDeltas"] = [b["allFour"] - a["allFour"]
        for a, b in zip(qwen17_p0["scores"], qwen17_p2["scores"])]
    qwen17_off_first = legacy_series["qwen3-1.7b-sdk-thinking-off"]["passes"]["fresh1"]
    for condition in ("P0", "P1", "P2"):
        phase = qwen17_off_first.get(condition, {})
        if (phase.get("completionStatus") != "complete" or
                phase.get("score", {}).get("denominator") != 60):
            raise ValueError("Qwen1.7B thinking-off first prompt pass is not closed")
    qwen17_off_p0 = qwen17_off_first["P0"]
    qwen17_off_repeat = qwen17_off_repeat_summary(legacy_series["qwen3-1.7b-sdk-thinking-off"])
    qwen35_repeat = qwen35_repeat_summary(legacy_series["qwen3.5-4b-sdk-thinking-on"])
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
        "schema": "analysis-refresh-v1", "generatedAt": "2026-10-05",
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
            "deepseekHighSuccessor": {"source": HIGH_SUCCESSOR_PUBLIC, **high_successor},
            "liquidNative": {"source": LIQUID_PUBLIC, **liquid},
            "e4bInterrupted": {"source": e4b_source,
                "score": e4b["descriptiveScore"], "unknownIds": e4b["unknownIds"],
                "neverSentIds": e4b["neverSentIds"], "cleanRepeatEligible": False,
                "status": e4b["status"], "usage": e4b["usage"]},
            "clefP1FirstPass": clef_p1,
            "kevNativePrompts": kev_native_prompts,
            "jevNativePrompts": jev_native_prompts,
            "geminiAuthority": gemini_authority,
            "hostedFresh": hosted_fresh,
            "deepseekLowP1Successor": {"source": LOW_P1_SUCCESSOR_PUBLIC, **low_p1},
            "deepseekLowRevisedPrice": {"source": LOW_REVISED_PUBLIC,
                                        **low_revised['series'][0]},
            "qwen27": {"source": "public-site/qwen27-final-descriptive-findings.json",
                        "seriesCount": len(qwen["series"]),
                        "cleanMatchedThreeEligible": qwen["cleanMatchedThreeEligible"]},
            "legacyQwen": {"source": "public-site/legacy-qwen-repeats.json",
                           "qwen17FirstPass": {"scores": qwen17_scores, "firstPassOnly": True},
                           "qwen17RepeatStudyComplete": True,
                           "qwen17OffFirstPass": {"scores": {c: qwen17_off_first[c]["score"] for c in ("P0", "P1", "P2")},
                               "usage": {c: qwen17_off_first[c]["usage"] for c in ("P0", "P1", "P2")},
                               "firstPassOnly": True,
                               "matchedP0": qwen_prompt_pairs(root, qwen17_off_first, labels, bindings)},
                           "qwen17OffFirstP0": {"score": qwen17_off_p0["score"],
                               "usage": qwen17_off_p0["usage"], "firstPassOnly": True},
                           "qwen17OffRepeat": qwen17_off_repeat,
                           "qwen35Repeat": qwen35_repeat,
                           "qwen17P2Repeat": qwen17_p2,
                           "qwen17P1Repeat": qwen17_p1,
                           "qwen17P0Repeat": qwen17_p0,
                           "completedConfigurations": list(legacy_complete) +
                               [name for name in legacy_pending
                                if legacy_series[name]["completedConditions"] == 9],
                           "remainingConfigurations": {name:
                               {"completedConditions": legacy_series[name]["completedConditions"],
                                "plannedConditions": 9} for name in legacy_pending
                                if legacy_series[name]["completedConditions"] < 9},
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
            "latestFlashP0Interruption": latest_flash_p0_interruption,
            "clefFlashP1": {"source": CLEF_FLASH_P1_PUBLIC,
                "sourceEvidence": CLEF_FLASH_P1,
                "passes": {name: {"valid": p1_passes[name]["counts"]["valid"],
                    "allFour": p1_passes[name]["allFourCorrect"], "denominator": 60}
                    for name in ("fresh1", "fresh2", "fresh3")},
                "predictionVectorsStable": True,
                "nativeDistributionsStable": True,
                "vendorConfidenceStable": True,
                "repeatSharedValid": p1_repeat["sharedValid"],
                "matchedFresh1P0": {"sharedValid": p1_matched["sharedValid"],
                    "p0AllFour": p1_matched["p0AllFourCorrect"],
                    "p1AllFour": p1_matched["p1AllFourCorrect"],
                    "allFourDelta": p1_matched["comparison"]["allFourDelta"],
                    "becameCorrectIds": p1_matched["comparison"]["allFourBecameCorrectIds"],
                    "becameIncorrectIds": p1_matched["comparison"]["allFourBecameIncorrectIds"]},
                "inputTokensPerPass": {name: p1_passes[name]["observedInputTokens"]
                    for name in ("fresh1", "fresh2", "fresh3")},
                "inputPriceEstimateUsdPerPass": clef_flash_p1["cost"]["publishedInputPriceEstimateUsdByPass"],
                "providerBilledUsd": None,
                "pureInferenceLatencyAvailable": clef_flash_p1["timing"]["inferenceLatencyAvailable"]},
            "clefFlashP2": {"source": CLEF_FLASH_P2_PUBLIC,
                "passes": {name: {"valid": phase["counts"]["valid"],
                    "allFour": phase["allFourCorrect"], "denominator": phase["allFourDenominator"]}
                    for name, phase in flash_p2["phaseByPass"].items()},
                "repeatSharedValid": 60,
                "predictionVectorsStable": True,
                "nativeDistributionsStable": True,
                "vendorConfidenceStable": True,
                "matchedFresh1P0": flash_p2["controls"]["matchedFresh1P0"],
                "matchedFresh1P1": flash_p2["controls"]["matchedFresh1P1"],
                "inputTokensPerPass": {name: phase["observedInputTokens"]
                    for name, phase in flash_p2["phaseByPass"].items()},
                "inputPriceEstimateUsdPerPass": flash_p2["cost"]["publishedInputPriceEstimateUsdByPass"],
                "providerBilledUsd": flash_p2["cost"]["providerBilledUsd"],
                "pureInferenceLatencyAvailable": flash_p2["timing"]["inferenceLatencyAvailable"]},
            "mistral119Fresh1P0": {"source": MISTRAL_P0_PUBLIC,
                "status": mistral_p0["status"], "condition": "P0", "pass": "fresh1",
                "valid": mistral_p0["outcomes"]["valid"],
                "failed": mistral_p0["outcomes"]["failed"],
                "failedIds": mistral_p0["outcomes"]["failedIds"],
                "neverSent": mistral_p0["outcomes"]["neverSent"],
                "allFourMatches": mistral_p0["scoring"]["allFourMatches"],
                "fixed60Denominator": mistral_p0["scoring"]["allFourDenominator"],
                "allFourAmongValid": mistral_p0["scoring"]["allFourAmongValid"],
                "observedKnownCostUsd": mistral_p0["usage"]["observedKnownCostUsd"],
                "unknownChargeUpperBoundUsd": mistral_p0["usage"]["unknownChargeUpperBoundUsd"],
                "cleanRepeatabilityClaim": False},
            "deepseekLow": {"source": "public-site/deepseek-low-final-suffix-findings.json",
                            "priorSource": "public-site/deepseek-low-third-interruption-findings.json",
                            "scoredConditions": 3,
                            "neverSent": 0,
                            "cleanMatchedThreeEligible": False,
                            "firstPassScores": deepseek_latest["historicalFirstPass"],
                            "promptComparisons": deepseek_latest["withinPassComparisons"],
                            "observedUsage": deepseek_latest["p2ObservedUsage"],
                            "seriesCount": len(deepseek["series"]),
                            "completedConditions": [item["completedConditions"] for item in deepseek["series"]],
                            "plannedConditions": [item["plannedConditions"] for item in deepseek["series"]],
                            "latestInterruptedPhase": deepseek["series"][0]["thirdInterruptionCheckpoint"]["phase"],
                            "latestInterruptedOutcomes": deepseek_latest["finalP2Outcomes"],
                            "latestInterruptedScore": deepseek_latest["historicalFirstPass"]["P2"]},
            "gemma26": {"source": "public-site/gemma26-fresh3-p1-interrupted-checkpoint.json",
                        "priorP0Source": "public-site/gemma26-fresh3-p0-checkpoint.json",
                        "p0Checkpoint": gemma_p0["conditions"]["P0"],
                        "p1Checkpoint": {"fixed60AllFourByPass": {
                            name: p1_scores[name]["allFour"] for name in ("fresh1", "fresh2", "fresh3")},
                            "validByPass": {name: p1_scores[name]["valid"]
                                for name in ("fresh1", "fresh2", "fresh3")},
                            "failedIds": ["DEV-059"],
                            "sharedValidDenominator": p1_shared["denominator"],
                            "sharedValidAllFourByPass": p1_shared["allFourMatches"],
                            "thirdPassKnownCostUsd": p1_usage["reportedKnownCostUsd"],
                            "thirdPassMissingCostCount": p1_usage["missingCostCount"],
                            "cleanMatchedThreeEligible": False},
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
                        "completedConditions": gemma_p1["scoredSeriesConditions"],
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
                        "unscoredConditionsAtCutoff": [],
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
