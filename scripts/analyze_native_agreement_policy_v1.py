#!/usr/bin/env python3
"""Evaluate one fixed two-model agreement rule on saved native P0 answers."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

import build_disputed_reviews_v1 as disputed


ROOT = Path(__file__).resolve().parents[1]
FEED = Path("public-site/disputed-reviews-v1.json")
RUNS = Path("public-site/supplemental-decision-runs-v1.json")
OUTPUT = Path("results/native-agreement-policy-v1")
PUBLIC_OUTPUT = Path("public-site/native-agreement-policy-v1.json")
FIELDS = disputed.FIELDS


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def decimal_string(value: object) -> Decimal:
    require(type(value) in (str, int, float), "Invalid saved cost type")
    amount = Decimal(str(value))
    require(amount.is_finite() and amount >= 0, "Invalid saved cost")
    return amount


def model_costs(root: Path, models: list[dict], feed: dict) -> dict[str, Decimal | None]:
    require(feed.get("schema") == "supplemental-decision-runs-v1" and feed.get("denominator") == 60,
            "Normalized run feed changed")
    runs = feed.get("runs")
    require(isinstance(runs, list), "Normalized run list missing")
    by_id = {run["id"]: run for run in runs}
    require(len(by_id) == len(runs), "Duplicate normalized run ID")
    costs = {}
    model_keys = {"clef-openrouter-native-fresh1-p0": "clef",
                  "clef-flash-openrouter-native-fresh1-p0": "clef-flash",
                  "luna-decisions-openrouter-native-fresh1-p0": "luna-decisions"}
    for model in models:
        name = model["id"]
        run = by_id.get(name)
        require(isinstance(run, dict), f"Normalized run missing: {name}")
        require(run.get("condition") == "P0" and run.get("repeatPass") == "fresh1" and
                run.get("surface") == "OpenRouter native Choice" and
                run.get("model") == model["model"] and
                run.get("complete") is True and run.get("records") == run.get("valid") == 60 and
                run.get("sourceRecordsUrl") == model["source_url"] and
                run.get("sourceRecordSha256") == model["source_sha256"],
                f"Normalized run identity or source changed: {name}")
        cost = run.get("cost")
        require(isinstance(cost, dict), f"Cost missing: {name}")
        # A cost sum is published only when all 60 saved response charges reconcile.
        if (cost.get("knownUsd") is None or cost.get("actualUsd") is not None or
                cost.get("estimatedUsd") is not None or
                cost.get("unknownUpperBoundUsd") is None or
                decimal_string(cost["unknownUpperBoundUsd"]) != 0):
            costs[name] = None
            continue
        projection_path = root / model["source_path"]
        require(digest(projection_path) == model["source_sha256"],
                f"Cost projection SHA-256 changed: {name}")
        projection = json.loads(projection_path.read_text())
        rows = disputed.source_rows(projection, name, model_keys.get(name))
        ids = {f"DEV-{i:03d}" for i in range(1, 61)}
        row_ids = [row["id"] for row in rows]
        require(len(row_ids) == len(set(row_ids)) == 60 and set(row_ids) == ids,
                f"Cost projection review IDs changed: {name}")
        charges = [row.get("actual_cost_usd") for row in rows]
        if any(charge is None for charge in charges):
            costs[name] = None
            continue
        total = sum((decimal_string(charge) for charge in charges), Decimal(0))
        require(total == decimal_string(cost["knownUsd"]),
                f"Saved charges do not reconcile with normalized run: {name}")
        costs[name] = total
    return costs


def evaluate_pair(reviews: list[dict], left: str, right: str) -> dict:
    """Accept from prediction equality alone, then score accepted cases offline."""
    accepted, deferred, accepted_correct, accepted_error = [], [], [], []
    confusions = {field: Counter() for field in FIELDS}
    field_error_ids = {field: [] for field in FIELDS}
    for review in sorted(reviews, key=lambda row: row["id"]):
        answers = {answer["model_id"]: answer["prediction"] for answer in review["answers"]}
        require(left in answers and right in answers, "Pair answer missing")
        if answers[left] != answers[right]:
            deferred.append(review["id"])
            continue
        accepted.append(review["id"])
        prediction = answers[left]
        reference = review["reference"]
        if prediction == reference:
            accepted_correct.append(review["id"])
        else:
            accepted_error.append(review["id"])
        for field in FIELDS:
            confusions[field][(reference[field], prediction[field])] += 1
            if reference[field] != prediction[field]:
                field_error_ids[field].append(review["id"])
    require(len(accepted) + len(deferred) == 60 and
            len(accepted_correct) + len(accepted_error) == len(accepted),
            "Pair outcome denominator changed")
    field_confusion = {}
    for field in FIELDS:
        values = sorted({value for pair in confusions[field] for value in pair})
        field_confusion[field] = {
            reference: {predicted: confusions[field][(reference, predicted)] for predicted in values}
            for reference in values
        }
        require(sum(sum(row.values()) for row in field_confusion[field].values()) == len(accepted),
                f"Accepted field confusion does not reconcile: {field}")
    return {
        "left": left, "right": right,
        "accepted_count": len(accepted), "accepted_ids": accepted,
        "accepted_all_four_correct": len(accepted_correct),
        "accepted_all_four_correct_ids": accepted_correct,
        "accepted_all_four_error_count": len(accepted_error),
        "accepted_all_four_error_ids": accepted_error,
        "deferred_count": len(deferred), "deferred_ids": deferred,
        "accepted_field_confusion_reference_rows": field_confusion,
        "accepted_field_error_ids": field_error_ids,
    }


def analysis(root: Path = ROOT, feed_path: Path = FEED) -> dict:
    saved_path = root / feed_path
    saved = json.loads(saved_path.read_text())
    # The established builder rechecks pinned source hashes, exact run identity,
    # frozen labels, prediction vectors and all published component scores.
    require(saved == disputed.build(root), "Disputed-review feed differs from pinned source rebuild")
    require(saved["review_denominator"] == 60 and saved["model_denominator"] == 7,
            "Agreement cohort denominator changed")
    models = saved["models"]
    model_ids = [model["id"] for model in models]
    require(len(model_ids) == len(set(model_ids)) == 7, "Duplicate or missing model")
    reviews = saved["reviews"]
    review_ids = [review["id"] for review in reviews]
    require(len(review_ids) == len(set(review_ids)) == 60 and
            set(review_ids) == {f"DEV-{i:03d}" for i in range(1, 61)},
            "Duplicate or missing review")
    runs = json.loads((root / RUNS).read_text())
    require(digest(root / RUNS) == saved["source_sha256"][str(RUNS)],
            "Normalized run feed SHA-256 changed")
    costs = model_costs(root, models, runs)
    baseline = []
    for model in models:
        name = model["id"]
        answers = {
            review["id"]: next(answer for answer in review["answers"]
                               if answer["model_id"] == name)
            for review in reviews
        }
        correct = [review["id"] for review in reviews if answers[review["id"]]["all_four_match"]]
        require(len(correct) == model["all_four_matches"], f"Component baseline changed: {name}")
        field_correct = {}
        field_error_ids = {}
        for field in FIELDS:
            errors = [review["id"] for review in reviews if
                      answers[review["id"]]["prediction"][field] != review["reference"][field]]
            field_correct[field] = 60 - len(errors)
            field_error_ids[field] = sorted(errors)
        baseline.append({
            "id": name, "model": model["model"], "display_name": model["display_name"],
            "all_four_correct": len(correct), "denominator": 60,
            "all_four_correct_ids": sorted(correct),
            "field_correct": field_correct, "field_error_ids": field_error_ids,
            "known_development_cost_usd": str(costs[name]) if costs[name] is not None else None,
            "source_path": model["source_path"], "source_sha256": model["source_sha256"],
        })
    pairs = []
    for left, right in combinations(model_ids, 2):
        result = evaluate_pair(reviews, left, right)
        result["known_two_run_development_cost_usd"] = (
            str(costs[left] + costs[right])
            if costs[left] is not None and costs[right] is not None else None
        )
        pairs.append(result)
    require(len(pairs) == 21 and len({(pair["left"], pair["right"]) for pair in pairs}) == 21,
            "Twenty-one distinct model pairs required")
    return {
        "schema": "native-agreement-policy-v1",
        "scope": "Seven exact OpenRouter native Choice fresh1/P0 configurations, 60 fictional development reviews",
        "reference_status": saved["reference_status"],
        "policy": "For each pair, accept the four-field vector only if both saved valid predictions are identical; otherwise defer human review. The reference is used only after that decision to score accepted cases.",
        "policy_origin": "fixed_before_calculation; all 21 pairs reported without pair selection",
        "inference_requests": 0,
        "denominator": 60,
        "source_sha256": {str(FEED): digest(saved_path), **saved["source_sha256"]},
        "cost_basis": "Sum of both saved known development charges for all 60 requests per run, only when every record charge reconciles. Excludes smoke, uncertain invoices, deployment and human review of deferred cases.",
        "components": baseline,
        "pairs": pairs,
    }


def readme(result: dict) -> str:
    names = {model["id"]: model["display_name"] for model in result["components"]}
    rows = "\n".join(
        f"| {names[pair['left']]} + {names[pair['right']]} | "
        f"{pair['accepted_count']}/60 | {pair['accepted_all_four_correct']}/{pair['accepted_count']} | "
        f"{pair['accepted_all_four_error_count']} | {pair['deferred_count']} | "
        f"{('$' + pair['known_two_run_development_cost_usd']) if pair['known_two_run_development_cost_usd'] is not None else 'unavailable'} |"
        for pair in result["pairs"]
    )
    return f"""# Two-model agreement and human-review deferral

This is a retrospective simulation on the same 60 fictional development reviews. For every pair of the seven saved first-pass P0 native decision-model runs, the fixed rule accepts a four-field answer only when both models return the same complete vector. It defers every other review for human review. The rule compares predictions before looking at the frozen proposed labels. The labels are then used to count accepted matches and errors. No pair was selected or tuned as a preferred deployment choice, no new model call was made, and these results do not establish out-of-sample gains.

The [machine-readable findings](findings.json) report all 21 pairs, exact accepted and deferred IDs, accepted all-four errors, per-field error IDs and reference-by-prediction confusion tables. All scores use the fixed 60-review denominator for coverage. “Correct” here means agreement with the provisional v0.2 labels, not a final adjudication of a candidate's experience. The [seven-model review feed](../../public-site/disputed-reviews-v1.json), [original comments](../../data/pilot/inputs.jsonl), [proposed labels](../../data/pilot/proposed_labels.jsonl) and [labeling guide](../../docs/LABELING_GUIDE.md) provide the review-level context. The feed and its source projections are checked by SHA-256 before calculation.

| Pair | Accepted coverage | Accepted all-four matches | Accepted all-four errors | Deferred for review | Known two-run development charge |
| --- | ---: | ---: | ---: | ---: | ---: |
{rows}

Every pair runs both models on all 60 reviews. The cost column sums their saved known development charges, including reviews later deferred. It excludes smoke calls, human review, deployment and any invoice difference; if either run lacks a reconciled charge, the pair cost is unavailable. The [normalized run feed](../../public-site/supplemental-decision-runs-v1.json) and each model's saved projection are the cost sources. Lower accepted-error counts can result from deferring more reviews, so interpret errors beside accepted coverage and the exact deferred IDs. The same review appears in many pairs; 21 rows are not 21 independent samples.

Run `python3 scripts/analyze_native_agreement_policy_v1.py` to rebuild the two files, or add `--check` to verify saved bytes. The script rebuilds the seven-model feed from its pinned sources, checks all 60 record charges where a cost is shown, and makes no inference request.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare saved bytes without writing")
    args = parser.parse_args()
    result = analysis()
    files = {
        ROOT / OUTPUT / "findings.json": json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        ROOT / OUTPUT / "README.md": readme(result),
        ROOT / PUBLIC_OUTPUT: json.dumps(result, indent=2, ensure_ascii=False) + "\n",
    }
    if args.check:
        for path, content in files.items():
            require(path.read_text() == content, f"Generated output differs: {path}")
    else:
        (ROOT / OUTPUT).mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content)
    print("Verified all 21 two-model agreement and deferral pairs")


if __name__ == "__main__":
    main()
