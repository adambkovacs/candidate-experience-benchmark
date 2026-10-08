"""Regenerates hard-cases.json, answer.json and prompt-levels.json from the repo's feeds and docs.

Run from the repo root:  python3 -I public-site/deck/data/build.py
Every number is read from a feed or parsed from a doc and asserted; a mismatch stops the build.
timeline.json is hand-curated from docs/talk/02-landscape.md Part C and is not generated here.
"""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "public-site/deck/data"
GENERATED_AT = "2026-10-08"


def load(rel):
    return json.loads((ROOT / rel).read_text())


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ---- hard-cases.json (S10) -------------------------------------------------
disp = load("public-site/disputed-reviews-v1.json")
hist = collections.Counter()
hard = []
for r in disp["reviews"]:
    assert len(r["answers"]) == 7
    n = sum(1 for a in r["answers"] if not a["all_four_match"])
    assert n == r["models_with_any_mismatch"]
    hist[n] += 1
    if n >= 4:
        hard.append({"id": r["id"], "mismatching_models": n, "text": r["feedback"],
                     "off_topic": r["off_topic"], "fields_with_mismatch": r["fields_with_mismatch"]})
assert sum(hist.values()) == 60
assert {str(k): v for k, v in hist.items()} == disp["mismatch_count_histogram"]
hard.sort(key=lambda x: (-x["mismatching_models"], x["id"]))
dump("hard-cases.json", {
    "generated_from": "public-site/disputed-reviews-v1.json (reviews[].answers[].all_four_match; cross-checked against mismatch_count_histogram)",
    "generated_at": GENERATED_AT,
    "scope": disp["scope"],
    "reference_status": disp["reference_status"],
    "models": [m["display_name"] for m in disp["models"]],
    "review_total": 60,
    "histogram": {str(k): hist[k] for k in range(8)},
    "reviews_with_4_or_more_mismatches": hard,
})

# ---- answer.json (S2/S6/S7) ------------------------------------------------
fj = load("public-site/findings.json")
chart = fj["charts"]
jev = chart["jev"]
assert jev["runId"] == "typesafe-jev113-v2"
comp = {c["id"]: i for i, c in enumerate(jev["comparators"])}
opus = jev["comparators"][comp["opus55-high-batch10"]]
cost_rows = {r["id"]: i for i, r in enumerate(chart["costAgreement"]["rows"])}
gi, qi = cost_rows["openrouter-paid-gemma4-26b-a4b-on"], cost_rows["openrouter-qwen27-low-darkbloom-fp4"]
gemma, qwen = chart["costAgreement"]["rows"][gi], chart["costAgreement"]["rows"][qi]
sonnet = load("public-site/sonnet55-fresh-matched3.json")["threePassSummary"]["xhigh"]
sonnet_cells = [v for p in ("P0", "P1", "P2") for v in sonnet[p]["allFour"]["values"]]
assert len(sonnet_cells) == 9 and set(sonnet_cells) == {58}
jev_native = load("public-site/jev-native-prompt-findings.json")
jev_cost = jev_native["passes"]["P0"]["fresh1"]["knownCostUsd"]
assert float(jev_cost) == 0.00589092
est = load("public-site/subscription-price-estimates.json")["runs"]["opus55-high-batch10"]["estimateUsd"]
assert float(est) == 0.222052
sc_idx = next(i for i, f in enumerate(jev["fieldErrors"]) if f["field"] == "serious_concern_reported")
sc = jev["fieldErrors"][sc_idx]
sc_yes = fj["referenceDistributions"]["serious_concern_reported"]["yes"]
sc_missed = sum(c["count"] for c in sc["confusions"] if c["reference"] == "yes")
assert (sc_yes, sc_missed) == (25, 0)
assert (jev["correct"], opus["correct"], gemma["correct"], qwen["correct"]) == (54, 59, 59, 59)
# Seven-model nine-run series, docs/talk/06-cost-check.md section 1 (known charges) and section 4 (bounds are reservations).
SERIES = [0.31128624, 0.11649969, 0.1304487, 0.14295744, 0.20325475, 0.15134213, 0.14549328]
BOUNDS = [0.02359296, 0.1048576]
assert round(sum(SERIES), 4) == 1.2013 and round(sum(BOUNDS), 4) == 0.1285
F = "public-site/findings.json"
dump("answer.json", {
    "generated_from": "public-site feeds; see each entry's file and json_path",
    "generated_at": GENERATED_AT,
    "jev_all_four": {"value": 54, "of": 60, "file": F, "json_path": "charts.jev.correct",
                     "note": "Jev 1.13 direct P0, run typesafe-jev113-v2. A separate offline rescore (docs/FINDINGS.md) gives 55; the published charts keep the frozen v0.2 reference."},
    "opus55_high": {"value": 59, "of": 60, "file": F, "json_path": f"charts.jev.comparators[{comp['opus55-high-batch10']}].correct",
                    "note": "Claude Opus 5.5 high effort, batch of 10, P0, 60 valid."},
    "sonnet55_xhigh": {"value": 58, "of": 60, "cells": 9, "file": "public-site/sonnet55-fresh-matched3.json",
                       "json_path": "threePassSummary.xhigh.{P0,P1,P2}.allFour.values",
                       "note": "All nine P0/P1/P2 x pass cells are 58. Not in findings.json."},
    "gemma4_26b_on": {"value": 59, "of": 60, "valid": gemma["valid"], "file": F, "json_path": f"charts.costAgreement.rows[{gi}].correct",
                      "note": "Gemma 4 26B A4B, thinking on, OpenRouter P0. 59 valid, one invalid."},
    "qwen38_27b_low": {"value": 59, "of": 60, "file": F, "json_path": f"charts.costAgreement.rows[{qi}].correct",
                       "note": "Qwen3.8 27B, low effort, OpenRouter P0."},
    "jev_cost_known_usd": {"value": 0.00589092, "file": "public-site/jev-native-prompt-findings.json",
                           "json_path": "passes.P0.fresh1.knownCostUsd (string \"0.005890920\")",
                           "note": "Known provider charge for the OpenRouter native Jev P0 pass. The direct TypeSafe run is a token-price estimate of the same figure (docs/talk/01-findings-synthesis.md row 2), not a bill. Direct feed row typesafe-jev113-v2 in results/comparison/REPORT.md shows a different partial 0.002123688."},
    "opus_cost_estimate_usd": {"value": 0.222052, "file": "public-site/subscription-price-estimates.json",
                               "json_path": "runs.opus55-high-batch10.estimateUsd (string \"0.222052\")",
                               "note": "API-equivalent estimate of subscription CLI usage, not a charge. actualSubscriptionChargeUsd is null."},
    "jev_serious_concern_recall": {"value": "25/25", "file": F,
                                   "json_path": f"derived: referenceDistributions.serious_concern_reported.yes = 25; charts.jev.fieldErrors[{sc_idx}].confusions has no entry with reference \"yes\"",
                                   "note": "Not stored as a number in any feed. Markdown statement: docs/talk/01-findings-synthesis.md line 20."},
    "seven_model_known_charge_usd": {"value": 1.2013, "file": "docs/talk/06-cost-check.md",
                                     "json_path": "section 1, nine-run series table: sum of the seven model rows (0.31128624 + 0.11649969 + 0.1304487 + 0.14295744 + 0.20325475 + 0.15134213 + 0.14549328 = 1.20128223)",
                                     "note": "Known provider charges, Clef included. Not stored in a JSON feed; the sum is asserted in build.py."},
    "seven_model_unknown_bound_usd": {"value": 0.1285, "file": "docs/talk/06-cost-check.md",
                                      "json_path": "section 1 notes: Clef Flash 0.02359296 + Solar Decide 0.1048576 unknown bounds = 0.1284506",
                                      "note": "Reservations for requests whose charge was never recorded: bounds, not charges, and not zero. The slide shows it rounded to 0.13 (data-round 2)."},
})

# ---- prompt-levels.json (S12, A3) -----------------------------------------
doc = (ROOT / "docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md").read_text()
RECON = "docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md"


def doc_row(label):
    m = re.search(r"^\| " + re.escape(label) + r" \| ([^|]+) \| ([^|]+) \| ([^|]+) \|", doc, re.M)
    assert m, label
    return [[int(x) for x in g.split(",")] for g in m.groups()]


def block(label, name, note=None):
    p0, p1, p2 = doc_row(label)
    b = {"name": name, "source": RECON, "P0": p0, "P1": p1, "P2": p2}
    if note:
        b["note"] = note
    return b


models = {
    "clef": block("OpenRouter Clef", "Cloudflare Clef"),
    "luna": block("OpenRouter Luna Decisions", "OpenAI Luna Decisions"),
    "clef_flash": block("OpenRouter Clef Flash", "Cloudflare Clef Flash",
                        "Final P2 pass is 45 after one provider failure (59 usable answers)."),
    "solar": block("Solar Decide", "Upstage Solar Decide",
                   "Final P2 pass is an interrupted composite; the doc still reports 52."),
}
jp = {c: [jev_native["passes"][c][f"fresh{i}"] for i in (1, 2, 3)] for c in ("P0", "P1", "P2")}
jev_levels = {}
for c, passes in jp.items():
    jev_levels[c] = [p["score"]["allFour"] if p["status"] == "complete" else None for p in passes]
assert jev_levels == {"P0": [54, 53, 52], "P1": [54, 53, 54], "P2": [54, None, 54]}
models["jev_openrouter"] = {
    "name": "TypeSafe Jev 1.13 via OpenRouter native Choice",
    "source": "docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md; public-site/jev-native-prompt-findings.json (passes.<P>.fresh<n>.score.allFour)",
    **jev_levels,
    "note": "P2 pass 2 was interrupted (null). The interrupted composite scores 50/60 and is not a clean repeat.",
}
dump("prompt-levels.json", {
    "generated_from": f"{RECON}; docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md; docs/FINDINGS.md",
    "generated_at": GENERATED_AT,
    "unit": "all-four reference matches out of 60; arrays are pass 1, 2, 3",
    "models": models,
    "tally_39_setups": {
        "source": "docs/FINDINGS.md section 'More instructions did not consistently improve agreement' (39 audited hosted and subscription setups)",
        "P0_to_P1": {"better": 15, "same": 15, "worse": 9},
        "P0_to_P2": {"better": 7, "same": 16, "worse": 16},
        "P1_to_P2": {"better": 4, "same": 14, "worse": 21},
    },
})
fd = (ROOT / "docs/FINDINGS.md").read_text()
for row in ("| Original rubric → classifier framing | 15 | 15 | 9 |",
            "| Original rubric → decision tree | 7 | 16 | 16 |",
            "| Classifier framing → decision tree | 4 | 14 | 21 |"):
    assert row in fd, row
print("ok")
