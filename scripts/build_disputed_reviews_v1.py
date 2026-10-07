#!/usr/bin/env python3
"""Build a source-bound, offline seven-model review dataset from frozen evidence."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("results/disputed-reviews-v1")
PUBLIC_OUTPUT = Path("public-site/disputed-reviews-v1.json")
FEED = Path("public-site/supplemental-decision-runs-v1.json")
INPUTS = Path("data/pilot/inputs.jsonl")
REFERENCES = Path("data/pilot/proposed_labels.jsonl")
PERPLEXITY_FINDINGS = Path("results/perplexity-decider-v1/full-v2/findings.json")
PERPLEXITY_PROJECTION = Path("results/perplexity-decider-v1/full-v2/public-projection.json")
EXPECTED_SHA256 = {
    str(INPUTS): "bd79e602f45f6aff78796ebdca4f2d0b1585c48665b6b8a9af1fe0b5e52d2b9e",
    str(REFERENCES): "440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464",
    "results/solar-decide-native-full-v1/execution-adapter-v2/first-pass.public-projection.json": "52c2ef28b7156d1846e7ccef962a8318e6c5ae6d708a1b7782ee45d4472afb41",
    "results/liquid-d1-native-v1/full-v1/fresh1/P0/development.public.json": "be428da40efef67a9db9bc8334f176c45f235fdbd02af8c128d93f188d61dbb9",
    "results/tev-native-v1/full-v1/public-projection.json": "0a90f0ef00ee699910ada1826ec2d23834e936301bb90df8e6826082fd43e732",
    "results/clef-openrouter-v1/findings-v1/public-projection.json": "81bb51e9d95b92124642d7efa6a546b29873772dd72b400fc2b695409789bae6",
    str(PERPLEXITY_FINDINGS): "3b738756fb63ce4406f9eba18f759ee09708d50f57ffaf4d2d8ee05eafb67ef5",
    str(PERPLEXITY_PROJECTION): "0afd1a31adc6171cd013170b456be2c26b4480a8e1eb873493c5c423ebad7035",
}
FIELDS = (
    "sentiment",
    "follow_up_needed",
    "serious_concern_reported",
    "testimonial_potential",
)
MODELS = (
    ("liquid-d1-native-fresh1-p0", "Liquid D1", None),
    ("tev1-4b-native-fresh1-p0", "Tev 1 4B", None),
    ("solar-decide-native-fresh1-p0", "Solar Decide", None),
    ("clef-openrouter-native-fresh1-p0", "Clef", "clef"),
    ("clef-flash-openrouter-native-fresh1-p0", "Clef Flash", "clef-flash"),
    ("luna-decisions-openrouter-native-fresh1-p0", "Luna Decisions", "luna-decisions"),
    ("perplexity-decider-native-fresh1-p0", "Perplexity Decider V1 27B", None),
)
GITHUB_SOURCE = "https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path, expected_ids: set[str]) -> dict[str, dict]:
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    by_id = {record["id"]: record for record in records}
    require(len(records) == len(by_id) == len(expected_ids), f"Duplicate or missing review ID: {path}")
    require(set(by_id) == expected_ids, f"Review IDs differ from the 60 frozen cases: {path}")
    return by_id


def source_rows(projection: dict, model_id: str, model_key: str | None) -> list[dict]:
    if "stages" not in projection:
        require(model_id == "liquid-d1-native-fresh1-p0", f"Unexpected ungrouped projection: {model_id}")
        config = projection["configuration"]
        require(config["pass"] == "fresh1" and config["condition"] == "P0", "Liquid projection stage changed")
        return projection["records"]
    stages = [stage for stage in projection["stages"] if stage["stage"] == "fresh1/P0"]
    if model_key:
        stages = [stage for stage in stages if stage.get("model_key") == model_key]
    require(len(stages) == 1, f"Missing or ambiguous first P0 stage: {model_id}")
    return stages[0]["records"]


def build(root: Path = ROOT) -> dict:
    expected_ids = {f"DEV-{index:03d}" for index in range(1, 61)}
    for relative, expected_hash in EXPECTED_SHA256.items():
        path = root / relative
        require(path.is_file(), f"Missing pinned source: {relative}")
        require(digest(path) == expected_hash, f"Pinned source SHA-256 mismatch: {relative}")

    feedback = load_jsonl(root / INPUTS, expected_ids)
    references = load_jsonl(root / REFERENCES, expected_ids)
    require(all(isinstance(feedback[case].get("feedback"), str) for case in expected_ids), "Missing review text")
    require(all(set(references[case]["proposed_labels"]) == set(FIELDS) for case in expected_ids), "Reference field set changed")
    off_topic = {
        case for case in expected_ids
        if "off-topic" in references[case].get("rationale", "").lower()
    }
    require(off_topic == {"DEV-029"}, "Source-grounded off-topic set changed")
    require(all(set(references[case]["proposed_labels"].values()) == {"insufficient_information"} for case in off_topic), "Off-topic reference labels changed")

    feed = json.loads((root / FEED).read_text())
    require(feed["schema"] == "supplemental-decision-runs-v1" and feed["denominator"] == 60, "Normalized feed schema or denominator changed")
    feed_runs = {run["id"]: run for run in feed["runs"]}
    require(len(feed_runs) == len(feed["runs"]), "Duplicate normalized run IDs")
    perplexity_findings = json.loads((root / PERPLEXITY_FINDINGS).read_text())
    require(perplexity_findings["projection_sha256"] == EXPECTED_SHA256[str(PERPLEXITY_PROJECTION)], "Perplexity findings projection hash changed")
    require(perplexity_findings["reference_sha256"][str(REFERENCES)] == EXPECTED_SHA256[str(REFERENCES)], "Perplexity findings reference hash changed")
    perplexity_scores = [score for score in perplexity_findings["scores"] if score["stage"] == "fresh1/P0"]
    require(len(perplexity_scores) == 1, "Perplexity first P0 score missing or duplicated")
    perplexity_projection = json.loads((root / PERPLEXITY_PROJECTION).read_text())
    require(perplexity_projection["schema"] == "perplexity-decider-native-public-projection-v1", "Perplexity projection schema changed")
    require(perplexity_projection["model"] == "perplexity/pplx-decider-v1-27b", "Perplexity model identity changed")
    require(perplexity_projection["reference_labels_sent"] is False, "Perplexity projection reports reference exposure")

    model_metadata = []
    predictions: dict[str, dict[str, dict]] = {}
    for model_id, display_name, model_key in MODELS:
        if model_id.startswith("perplexity-"):
            require(model_id in feed_runs, f"Missing normalized Perplexity run: {model_id}")
            run = feed_runs[model_id]
            require(run["condition"] == "P0" and run["repeatPass"] == "fresh1", "Wrong normalized Perplexity stage")
            require(run["model"] == perplexity_projection["model"] and run["complete"] and run["records"] == run["valid"] == 60, "Perplexity run identity or coverage changed")
            require(run["sourceRecordSha256"] == EXPECTED_SHA256[str(PERPLEXITY_PROJECTION)] and run["sourceRecordsUrl"] == GITHUB_SOURCE + str(PERPLEXITY_PROJECTION), "Perplexity run source binding changed")
            relative = PERPLEXITY_PROJECTION
            rows = source_rows(perplexity_projection, model_id, model_key)
            published_score = perplexity_scores[0]["all_four_correct"]
            published_fields = perplexity_scores[0]["field_correct"]
            require(perplexity_scores[0]["denominator"] == perplexity_scores[0]["valid"] == 60, "Perplexity first P0 is not 60 valid cases")
            require(run["metrics"]["all_four"] == published_score and all(run["metrics"][field] == published_fields[field] for field in FIELDS), "Normalized Perplexity score differs from source findings")
            model_name = perplexity_projection["model"]
        else:
            require(model_id in feed_runs, f"Missing native run: {model_id}")
            run = feed_runs[model_id]
            require(run["condition"] == "P0" and run["repeatPass"] == "fresh1", f"Wrong native pass: {model_id}")
            require(run["surface"] == "OpenRouter native Choice", f"Wrong native interface: {model_id}")
            require(run["complete"] and run["records"] == run["valid"] == 60, f"Native run not fully valid: {model_id}")
            url = run["sourceRecordsUrl"]
            require(url.startswith(GITHUB_SOURCE), f"Unexpected projection URL: {model_id}")
            relative = Path(url.removeprefix(GITHUB_SOURCE))
            require(EXPECTED_SHA256.get(str(relative)) == run["sourceRecordSha256"], f"Native source hash changed: {model_id}")
            projection = json.loads((root / relative).read_text())
            rows = source_rows(projection, model_id, model_key)
            published_score = run["metrics"]["all_four"]
            published_fields = {field: run["metrics"][field] for field in FIELDS}
            model_name = run["model"]
        by_id = {row["id"]: row for row in rows}
        require(len(rows) == len(by_id) == 60 and set(by_id) == expected_ids, f"Projection review IDs changed: {model_id}")
        predictions[model_id] = {case: by_id[case]["prediction"] for case in sorted(expected_ids)}
        require(all(set(prediction) == set(FIELDS) for prediction in predictions[model_id].values()), f"Prediction field set changed: {model_id}")
        field_scores = {
            field: sum(predictions[model_id][case][field] == references[case]["proposed_labels"][field] for case in expected_ids)
            for field in FIELDS
        }
        all_four = sum(predictions[model_id][case] == references[case]["proposed_labels"] for case in expected_ids)
        require(all_four == published_score and field_scores == published_fields, f"Published score differs from projection: {model_id}")
        model_metadata.append({
            "id": model_id,
            "id_kind": "normalized_run_id",
            "display_name": display_name,
            "model": model_name,
            "condition": "P0",
            "repeat_pass": "fresh1",
            "source_stage": "fresh1/P0",
            "eligible_reviews": 60,
            "source_path": str(relative),
            "source_url": GITHUB_SOURCE + str(relative),
            "source_sha256": EXPECTED_SHA256[str(relative)],
            "all_four_matches": all_four,
        })

    reviews = []
    for case in sorted(expected_ids):
        reference = references[case]["proposed_labels"]
        answers = []
        field_union = set()
        for model_id, _, _ in MODELS:
            prediction = predictions[model_id][case]
            different = [field for field in FIELDS if prediction[field] != reference[field]]
            field_union.update(different)
            answers.append({
                "model_id": model_id,
                "prediction": prediction,
                "different_fields": different,
                "all_four_match": not different,
            })
        mismatch_count = sum(not answer["all_four_match"] for answer in answers)
        reviews.append({
            "id": case,
            "feedback": feedback[case]["feedback"],
            "reference": reference,
            "reference_testimonial_positive": reference["testimonial_potential"] == "yes",
            "off_topic": case in off_topic,
            "off_topic_basis": "frozen reference rationale" if case in off_topic else None,
            "eligible_model_count": 7,
            "models_with_any_mismatch": mismatch_count,
            "distinct_fields_with_mismatch": len(field_union),
            "fields_with_mismatch": [field for field in FIELDS if field in field_union],
            "answers": answers,
        })
    reviews.sort(key=lambda row: (-row["models_with_any_mismatch"], -row["distinct_fields_with_mismatch"], row["id"]))
    require(len(reviews) == 60 and len(MODELS) == 7, "Review or model denominator changed")
    counts = Counter(row["models_with_any_mismatch"] for row in reviews)
    require(sum(counts.values()) == 60, "Mismatch histogram does not cover 60 reviews")
    for model in model_metadata:
        computed = sum(answer["all_four_match"] for row in reviews for answer in row["answers"] if answer["model_id"] == model["id"])
        require(computed == model["all_four_matches"], f"All-four reconciliation failed: {model['id']}")
    testimonial_ids = [row["id"] for row in reviews if row["reference_testimonial_positive"]]
    require(len(testimonial_ids) == 9, "Frozen testimonial-positive count changed")
    return {
        "schema": "disputed-reviews-v1",
        "scope": "Seven distinct OpenRouter native Choice models, exact fresh1/P0 runs; not the full benchmark roster",
        "review_denominator": 60,
        "model_denominator": 7,
        "reference_status": "Frozen proposed_labels v0.2, human-checked with disputed cases; agreement is not truth",
        "source_sha256": {str(FEED): digest(root / FEED), **dict(sorted(EXPECTED_SHA256.items()))},
        "inputs_url": GITHUB_SOURCE + str(INPUTS),
        "references_url": GITHUB_SOURCE + str(REFERENCES),
        "rubric_url": GITHUB_SOURCE + "docs/LABELING_GUIDE.md",
        "models": model_metadata,
        "mismatch_count_histogram": {str(index): counts[index] for index in range(8)},
        "testimonial_reference_positive": {"count": len(testimonial_ids), "review_ids_in_display_order": testimonial_ids},
        "off_topic_review_ids": sorted(off_topic),
        "sort": "models_with_any_mismatch descending, distinct_fields_with_mismatch descending, review ID ascending",
        "reviews": reviews,
    }


def readme(result: dict) -> str:
    top = result["reviews"][:5]
    top_rows = "\n".join(
        f"| [{row['id']}](../../data/pilot/inputs.jsonl) | {row['models_with_any_mismatch']}/7 | {row['distinct_fields_with_mismatch']} |"
        for row in top
    )
    hist = ", ".join(
        f"{count} {'review' if count == 1 else 'reviews'} with {models}/7 configurations differing"
        for models, count in result["mismatch_count_histogram"].items() if count
    )
    testimonial = ", ".join(result["testimonial_reference_positive"]["review_ids_in_display_order"])
    return f"""# Frequently disputed reviews in seven native decision-model first passes

This offline dataset keeps all 60 fictional development reviews. It shows each review's exact text, frozen reference answers, and seven models' saved first-pass P0 answers. Rows are sorted by how many distinct configurations differ on at least one of the four fields, then by the number of fields involved, then review ID. The selection covers Liquid D1, Tev 1 4B, Solar Decide, Clef, Clef Flash, Luna Decisions and Perplexity Decider V1 27B. It does not represent every model in the benchmark. Three later passes for the same model are not three new models or reviews.

The [machine-readable findings](findings.json) include all 60 rows, every answer, each differing field, seven exact normalized saved-run IDs and their projection links. It records SHA-256 hashes for the inputs, references, Perplexity findings and projections. The [review text](../../data/pilot/inputs.jsonl), [frozen proposed labels](../../data/pilot/proposed_labels.jsonl), [labeling rubric](../../docs/LABELING_GUIDE.md) and [human reference review](../../docs/REFERENCE_REVIEW_V1.md) are the sources for interpretation. Agreement means agreement with those labels, not proven correctness.

| Review | Configurations with any mismatch | Distinct fields involved |
| --- | ---: | ---: |
{top_rows}

Across all 60 rows: {hist}. A row with zero mismatches remains in the dataset. "Off-topic" is flagged only for DEV-029 because its frozen reference rationale explicitly says the restaurant comment is off-topic; the builder does not infer that flag from model answers. The nine reference-positive testimonial reviews, in display order, are {testimonial}. Each also carries a boolean flag in `findings.json`, so readers can filter that subset without changing the denominator.

DEV-029 says "Great soup, tiny portions, wouldn't eat there again." The rubric assigns off-topic feedback `insufficient_information` for all four recruitment decisions. DEV-030 says an accessibility issue from an assessment may have been dealt with, but the candidate does not know whether another assessment is available. Its frozen reference asks for follow-up and leaves serious concern unresolved. A common mismatch can reflect task-boundary handling or a disputable reference judgment. It is not proof that seven models made the same real-world error.

Run `python3 scripts/build_disputed_reviews_v1.py` to regenerate this report and JSON, then `python3 scripts/build_disputed_reviews_v1.py --check` to compare generated bytes. The builder makes no inference request, verifies exact source hashes and published scores, and rejects missing, duplicate or changed review IDs. Run `python3 -m unittest tests/test_disputed_reviews_v1.py` for source-drift and optimized-Python checks. A changed frozen input or projection requires a new version and review rather than a silent replacement.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated bytes without writing")
    args = parser.parse_args()
    result = build()
    public_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    files = {
        ROOT / OUTPUT / "findings.json": public_json,
        ROOT / PUBLIC_OUTPUT: public_json,
        ROOT / OUTPUT / "README.md": readme(result),
    }
    if args.check:
        for path, content in files.items():
            require(path.read_text() == content, f"Generated output differs: {path}")
    else:
        (ROOT / OUTPUT).mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content)
    print("Verified 60 reviews against seven exact first-pass native configurations")


if __name__ == "__main__":
    main()
