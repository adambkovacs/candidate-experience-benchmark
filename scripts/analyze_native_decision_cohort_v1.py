#!/usr/bin/env python3
"""Offline, source-bound comparison of six OpenRouter native Choice P0 first passes."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "public-site/supplemental-decision-runs-v1.json"
REFERENCE = ROOT / "data/pilot/proposed_labels.jsonl"
OUTPUT = ROOT / "results/analysis-native-cohort-v1"
FIELDS = (
    "sentiment",
    "follow_up_needed",
    "serious_concern_reported",
    "testimonial_potential",
)
RUN_IDS = (
    "liquid-d1-native-fresh1-p0",
    "tev1-4b-native-fresh1-p0",
    "solar-decide-native-fresh1-p0",
    "clef-openrouter-native-fresh1-p0",
    "clef-flash-openrouter-native-fresh1-p0",
    "luna-decisions-openrouter-native-fresh1-p0",
)
MODEL_KEYS = {
    "clef-openrouter-native-fresh1-p0": "clef",
    "clef-flash-openrouter-native-fresh1-p0": "clef-flash",
    "luna-decisions-openrouter-native-fresh1-p0": "luna-decisions",
}
DISPLAY_NAMES = {
    "liquid-d1-native-fresh1-p0": "Liquid D1",
    "tev1-4b-native-fresh1-p0": "Tev 1 4B",
    "solar-decide-native-fresh1-p0": "Solar Decide",
    "clef-openrouter-native-fresh1-p0": "Clef",
    "clef-flash-openrouter-native-fresh1-p0": "Clef Flash",
    "luna-decisions-openrouter-native-fresh1-p0": "Luna Decisions",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def rows_by_id(rows: list[dict], ids: set[str]) -> dict[str, dict]:
    indexed = {row["id"]: row for row in rows}
    require(len(indexed) == len(rows) == len(ids), "Duplicate or missing records")
    require(set(indexed) == ids, "Record cohort differs from frozen references")
    return indexed


def projection_rows(run: dict) -> tuple[Path, dict[str, dict]]:
    url = run["sourceRecordsUrl"]
    prefix = "https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/"
    require(url.startswith(prefix), f"Unexpected source URL: {url}")
    path = ROOT / url.removeprefix(prefix)
    require(path.is_file(), f"Source projection missing: {path}")
    require(digest(path) == run["sourceRecordSha256"], f"Source projection SHA-256 mismatch: {path}")
    data = json.loads(path.read_text())
    if "stages" not in data:
        require(run["id"] == "liquid-d1-native-fresh1-p0", "Unexpected ungrouped projection")
        require(data["configuration"]["model"] == run["model"], "Ungrouped projection model mismatch")
        require(data["configuration"]["pass"] == "fresh1", "Ungrouped projection pass mismatch")
        require(data["configuration"]["condition"] == "P0", "Ungrouped projection condition mismatch")
        return path, data["records"]
    stages = [stage for stage in data["stages"] if stage["stage"] == "fresh1/P0"]
    key = MODEL_KEYS.get(run["id"])
    if key:
        stages = [stage for stage in stages if stage.get("model_key") == key]
    require(len(stages) == 1, f"Ambiguous projection stage for {run['id']}")
    return path, stages[0]["records"]


def analysis() -> dict:
    feed = json.loads(FEED.read_text())
    require(feed["schema"] == "supplemental-decision-runs-v1", "Unexpected normalized feed schema")
    require(feed["denominator"] == 60, "Normalized feed denominator is not 60")
    all_runs = {run["id"]: run for run in feed["runs"]}
    require(len(all_runs) == len(feed["runs"]), "Duplicate run IDs in normalized feed")
    references = [json.loads(line) for line in REFERENCE.read_text().splitlines() if line]
    reference = rows_by_id(references, {f"DEV-{i:03d}" for i in range(1, 61)})
    labels = {case: reference[case]["proposed_labels"] for case in sorted(reference)}
    require(all(set(value) == set(FIELDS) for value in labels.values()), "Reference field set mismatch")
    ids = set(labels)

    runs = []
    predictions: dict[str, dict[str, dict]] = {}
    sources: dict[str, str] = {}
    for run_id in RUN_IDS:
        run = all_runs[run_id]
        require(run["condition"] == "P0" and run["repeatPass"] == "fresh1", f"Wrong pass or condition: {run_id}")
        require(run["surface"] == "OpenRouter native Choice", f"Wrong execution surface: {run_id}")
        require(run["complete"] and run["records"] == run["valid"] == 60, f"Incomplete or invalid run: {run_id}")
        path, records = projection_rows(run)
        records = rows_by_id(records, ids)
        predictions[run_id] = {case: records[case]["prediction"] for case in sorted(ids)}
        require(all(set(value) == set(FIELDS) for value in predictions[run_id].values()), f"Prediction field set mismatch: {run_id}")
        sources[str(path.relative_to(ROOT))] = digest(path)
        confusion = {}
        rare_positive = {}
        field_correct = {}
        for field in FIELDS:
            pairs = Counter((labels[case][field], predictions[run_id][case][field]) for case in ids)
            values = sorted({value for pair in pairs for value in pair})
            confusion[field] = {
                expected: {predicted: pairs[expected, predicted] for predicted in values}
                for expected in values
            }
            field_correct[field] = sum(labels[case][field] == predictions[run_id][case][field] for case in ids)
            require(sum(sum(row.values()) for row in confusion[field].values()) == 60, f"Confusion total mismatch: {run_id} {field}")
            if field != "sentiment":
                tp = pairs["yes", "yes"]
                ref_yes = sum(labels[case][field] == "yes" for case in ids)
                pred_yes = sum(predictions[run_id][case][field] == "yes" for case in ids)
                rare_positive[field] = {
                    "true_positive": tp,
                    "reference_yes": ref_yes,
                    "predicted_yes": pred_yes,
                    "recall": tp / ref_yes if ref_yes else None,
                    "precision": tp / pred_yes if pred_yes else None,
                }
        all_four = sum(predictions[run_id][case] == labels[case] for case in ids)
        require(all_four == run["metrics"]["all_four"], f"All-four score mismatch: {run_id}")
        require(all(field_correct[field] == run["metrics"][field] for field in FIELDS), f"Field score mismatch: {run_id}")
        cost = run["cost"]
        require(cost["actualUsd"] is None and cost["estimatedUsd"] is None, f"Unexpected cost basis: {run_id}")
        require(Decimal(str(cost["unknownUpperBoundUsd"])) == 0, f"Unknown cost bound exists: {run_id}")
        known = Decimal(str(cost["knownUsd"]))
        require(sum(Decimal(str(records[case]["actual_cost_usd"])) for case in ids) == known, f"Cost total mismatch: {run_id}")
        runs.append({
            "id": run_id,
            "model": run["model"],
            "provider": run["provider"],
            "surface": run["surface"],
            "source_url": run["sourceRecordsUrl"],
            "source_sha256": run["sourceRecordSha256"],
            "known_development_cost_usd": str(known),
            "valid": 60,
            "all_four_matches": all_four,
            "field_matches": field_correct,
            "confusion_reference_rows": confusion,
            "yes_class": rare_positive,
        })

    case_errors = []
    for case in sorted(ids):
        errors = {
            run_id: [field for field in FIELDS if predictions[run_id][case][field] != labels[case][field]]
            for run_id in RUN_IDS
        }
        errors = {run_id: fields for run_id, fields in errors.items() if fields}
        if errors:
            case_errors.append({"id": case, "models_with_error": errors, "error_count": len(errors)})
    oracle_matches = sum(any(predictions[run_id][case] == labels[case] for run_id in RUN_IDS) for case in ids)
    require(oracle_matches == 60 - sum(item["error_count"] == 6 for item in case_errors), "Oracle union reconciliation failed")

    pairs = []
    for left, right in combinations(RUN_IDS, 2):
        field_disagreements = {
            field: sum(predictions[left][case][field] != predictions[right][case][field] for case in ids)
            for field in FIELDS
        }
        vector_disagreements = sum(predictions[left][case] != predictions[right][case] for case in ids)
        require(max(field_disagreements.values()) <= vector_disagreements <= sum(field_disagreements.values()), f"Pairwise disagreement reconciliation failed: {left} {right}")
        pairs.append({
            "left": left,
            "right": right,
            "shared_valid": 60,
            "prediction_vector_disagreements": vector_disagreements,
            "field_disagreements": field_disagreements,
            "both_all_four_match": sum(predictions[left][case] == predictions[right][case] == labels[case] for case in ids),
        })

    majority = {}
    for field in FIELDS:
        counts = Counter(labels[case][field] for case in ids)
        choice = sorted(counts, key=lambda value: (-counts[value], value))[0]
        majority[field] = {"choice": choice, "reference_count": counts[choice], "reference_total": 60}
    baseline_vector = {field: majority[field]["choice"] for field in FIELDS}
    majority_all_four = sum(labels[case] == baseline_vector for case in ids)

    frontier = []
    for run in runs:
        cost = Decimal(run["known_development_cost_usd"])
        dominated = any(
            (Decimal(other["known_development_cost_usd"]) <= cost and other["all_four_matches"] >= run["all_four_matches"])
            and (Decimal(other["known_development_cost_usd"]) < cost or other["all_four_matches"] > run["all_four_matches"])
            for other in runs if other is not run
        )
        if not dominated:
            frontier.append(run["id"])
    require(len(runs) == 6 and len(pairs) == 15, "Cohort or pair count mismatch")
    require(sum(item["all_four_matches"] for item in runs) == sum(6 - item["error_count"] for item in case_errors) + 6 * (60 - len(case_errors)), "Case error reconciliation failed")
    return {
        "schema": "analysis-native-cohort-v1",
        "scope": "Six exact fresh1/P0 OpenRouter native Choice configurations, same 60 development records; offline scoring only",
        "inputs_sha256": {
            str(FEED.relative_to(ROOT)): digest(FEED),
            str(REFERENCE.relative_to(ROOT)): digest(REFERENCE),
            **dict(sorted(sources.items())),
        },
        "denominator": 60,
        "reference_status": "Frozen proposed_labels v0.2; human-checked with disputed cases, not ground truth",
        "runs": runs,
        "all_four_errors_by_case": case_errors,
        "pairwise": pairs,
        "oracle_union": {"matches": oracle_matches, "denominator": 60, "meaning": "Hindsight ceiling: per case, select any configuration that matched all four reference fields; not a deployable ensemble"},
        "reference_majority_baseline": {"fields": majority, "all_four_matches": majority_all_four, "meaning": "Always output each field's modal frozen reference label; hindsight description, not a learned or deployable rule"},
        "observed_development_cost_frontier": {"run_ids": frontier, "meaning": "Pareto frontier among these six runs only: maximize all-four matches, minimize known development charges; excludes smoke and unknown invoice effects"},
    }


def readme(result: dict) -> str:
    runs = result["runs"]
    best = max(runs, key=lambda run: run["all_four_matches"])
    rare = {run["id"]: run["yes_class"]["testimonial_potential"] for run in runs}
    uncovered = [case["id"] for case in result["all_four_errors_by_case"] if case["error_count"] == 6]
    disagreement_counts = [pair["prediction_vector_disagreements"] for pair in result["pairwise"]]
    source = "../../public-site/supplemental-decision-runs-v1.json"
    refs = "../../data/pilot/proposed_labels.jsonl"
    table = "\n".join(
        f"| {DISPLAY_NAMES[run['id']]} | {run['all_four_matches']}/60 | {run['field_matches']['testimonial_potential']}/60 | "
        f"{rare[run['id']]['true_positive']}/{rare[run['id']]['reference_yes']} | "
        f"{rare[run['id']]['true_positive']}/{rare[run['id']]['predicted_yes']} | "
        f"${run['known_development_cost_usd']} |"
        for run in runs
    )
    frontier = ", ".join(DISPLAY_NAMES[run_id] for run_id in result["observed_development_cost_frontier"]["run_ids"])
    return f"""# Native decision model first-pass analysis

This is an offline comparison of six exact `fresh1/P0` OpenRouter native Choice configurations on the same 60 fictional development comments. Each record is counted once per configuration. The [normalized feed]({source}) names the runs and binds their [saved projections](../../results/); the [frozen proposed labels]({refs}) supply the offline reference. `findings.json` records SHA-256 hashes for all inputs, per-field confusion tables, case errors and all 15 model pairs. No model was called for this analysis.

## What the first passes show

{DISPLAY_NAMES[best['id']]} had the most four-field matches in this six-run set: {best['all_four_matches']}/60. The six totals alone hide which fields and reviews differ. The "testimonial potential = yes" reference class has only {rare[best['id']]['reference_yes']}/60 cases; its recall and precision need those denominators visible. The counts below describe agreement with the saved reference, not truth or hiring suitability.

| Configuration | All four match | Testimonial field matches | Testimonial yes recall | Testimonial yes precision | Known development charge |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

The per-field majority reference baseline is {result['reference_majority_baseline']['all_four_matches']}/60 on all four together. It repeats the modal reference label for each field and is a hindsight description of this sample, not a learned or deployable rule. The per-field choices and counts are in `findings.json`.

The hindsight oracle union is {result['oracle_union']['matches']}/60: for each review it selects a model *after seeing the reference* if any of the six matched all four fields. It cannot be deployed as an ensemble and is not a prediction of ensemble performance. All six configurations differed from the reference on {', '.join(uncovered)}. `all_four_errors_by_case` shows every error and its field. Across 15 pairs, prediction vectors differed on {min(disagreement_counts)} to {max(disagreement_counts)} of 60 shared-valid reviews. Disagreement does not tell us which answer is right.

The [input comments](../../data/pilot/inputs.jsonl) and [labeling rubric](../../docs/LABELING_GUIDE.md) explain why those two reviews need care. DEV-029 is an off-topic restaurant review ("Great soup, tiny portions..."); its frozen reference uses `insufficient_information` for every recruitment decision. DEV-030 says an accessibility issue in an assessment may have been resolved, but the candidate does not know whether another assessment is available. Its reference asks for follow-up while leaving the serious-concern field unresolved. These shared misses can reflect task-boundary handling and disputed reference judgments; they are not six proven real-world model errors. The original scores are unchanged.

On known development charges and all-four matches, the nondominated runs in this six-run set are: {frontier}. This frontier excludes smoke calls, invoice uncertainty, latency and other operational qualities. Prices, providers, request controls and model behavior differ; no cost difference here is a causal model-efficiency claim. Charges are the saved known development amounts, not invoices.

## Limits and reproduction

The 60 synthetic comments are one development set, and the original reference remains disputed in some cases. These six routes have distinct models, providers, controls and prices; all use the same first P0 condition, but they are not matched interventions. Repeats are excluded rather than treated as more cases. Positive-class precision has no value when a run predicts zero positives. Confusion tables use reference labels as rows and model predictions as columns. All full-run scores use 60, including invalid outputs if any; these selected six each have 60 valid outputs.

Run `python3 scripts/analyze_native_decision_cohort_v1.py` from the repository root to regenerate the two outputs, then `python3 scripts/analyze_native_decision_cohort_v1.py --check` to compare bytes. The script verifies exact run IDs, source hashes, 60 unique review IDs, field totals, published scores and charges before writing. It does not read private raw responses or send references to a model.

Run `python3 -O scripts/analyze_native_decision_cohort_v1.py --self-test` to verify the same checks under optimized Python, including rejection of a deliberately altered projection in a temporary directory.
"""


def self_test_hash_rejection() -> None:
    global ROOT
    original_root = ROOT
    feed = json.loads(FEED.read_text())
    run = next(item for item in feed["runs"] if item["id"] == "solar-decide-native-fresh1-p0")
    relative = run["sourceRecordsUrl"].split("/blob/main/", 1)[1]
    with TemporaryDirectory() as directory:
        altered = Path(directory) / relative
        altered.parent.mkdir(parents=True)
        altered.write_bytes((original_root / relative).read_bytes() + b" ")
        ROOT = Path(directory)
        try:
            try:
                projection_rows(run)
            except ValueError as error:
                require("Source projection SHA-256 mismatch" in str(error), f"Unexpected self-test rejection: {error}")
            else:
                raise RuntimeError("Altered projection passed SHA-256 validation")
        finally:
            ROOT = original_root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated outputs without writing")
    parser.add_argument("--self-test", action="store_true", help="Check outputs and reject an altered temporary projection")
    args = parser.parse_args()
    result = analysis()
    files = {
        OUTPUT / "findings.json": json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        OUTPUT / "README.md": readme(result),
    }
    if args.self_test:
        self_test_hash_rejection()
    if args.check or args.self_test:
        for path, content in files.items():
            require(path.read_text() == content, f"Stale output: {path}")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content)
    print("Verified six native first-pass configurations and 60 offline references")


if __name__ == "__main__":
    main()
