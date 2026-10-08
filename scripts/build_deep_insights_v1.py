#!/usr/bin/env python3
"""Build public-site/deep-insights-v1.json by executing docs/talk/scripts/*.py (runpy) and reading their variables.

Nothing is retyped; every file the scripts open is bound by SHA-256; missing cost stays null, never zero.
--check rebuilds in memory and fails if the committed feed differs. Displayed paths are checked by tests/test_deep_insights_v1.py.
"""
import argparse
import builtins
import contextlib
import hashlib
import io
import json
import re
import runpy
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "public-site/deep-insights-v1.json"
SCRIPTS = "docs/talk/scripts"
GENERATED_AT = "2026-10-08"
FIELDS = ["sentiment", "follow_up_needed", "serious_concern_reported", "testimonial_potential"]
INS = "insufficient_information"
NAMES = {"qwen/qwen3.8-27b": "Qwen3.8 27B", "google/gemma-4-26b-a4b-it": "Gemma 4 26B", "google/gemma-4-31b-it": "Gemma 4 31B",
         "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash", "upstage/solar-decide": "Solar Decide",
         "perplexity/pplx-decider-v1-27b": "Perplexity Decider", "google/gemini-3.7-flash": "Gemini 3.7 Flash",
         "google/gemini-3.8-flash": "Gemini 3.8 Flash", "mistralai/mistral-small-2603": "Mistral Small 4", "jaredpalmer/kev-4b": "Kev 4B"}
READ = set()
_open = builtins.open


def _tracking_open(file, *args, **kwargs):
    # ponytail: records every file the scripts read so the hash map cannot miss one.
    if isinstance(file, (str, Path)):
        path = Path(file).resolve()
        if ROOT in path.parents:
            READ.add(path.relative_to(ROOT).as_posix())
    return _open(file, *args, **kwargs)


def run(name):
    path = ROOT / SCRIPTS / f"{name}.py"
    READ.add(path.relative_to(ROOT).as_posix())
    with contextlib.redirect_stdout(io.StringIO()):
        return runpy.run_path(str(path), run_name="__main__")


def load(rel):
    with open(ROOT / rel) as handle:
        return json.load(handle)


def share(n, d):
    return round(n / d, 6) if d else None


def usd(*values):
    return None if any(v is None for v in values) else round(sum(values), 9)


def script(name):
    return f"{SCRIPTS}/{name}.py"


def run_label(r):
    effort = {"on": "thinking on", "off": "thinking off", "na": ""}.get(r.effort, f"{r.effort} effort")
    return " ".join(x for x in (NAMES.get(r.model, r.model.split("/")[-1]), effort, "(fp4)" if "fp4" in r.run_id else "", r.pass_) if x)


def run_ref(r):
    return {"run_id": r.run_id, "model": r.model, "effort": r.effort, "pass": r.pass_, "condition": r.condition,
            "category": r.category, "label": run_label(r)}


def block(title, implication, tag, note, scripts, feeds, key_numbers, **data):
    return {"title": segments(title), "implication": implication, "confidence": {"tag": tag, "note": note},
            "scripts": [script(s) for s in scripts], "feeds": feeds, "key_numbers": key_numbers, **data}


def kn(label, value, of=None, fmt="count", share_path=None):
    return {"label": segments(label), "value": value, "of": of, "format": fmt, "share": share_path}


def segments(template, base=""):
    """"{path|format}" placeholders become {"path", "format"} segments so every number in prose stays bound."""
    out = []
    for i, part in enumerate(re.split(r"\{([^}]+)\}", template)):
        if i % 2:
            path, _, fmt = part.partition("|")
            out.append({"path": base + path, "format": fmt or "count"})
        elif part:
            out.append(part)
    return out


def insufficient_collapse(g02, g06):
    M, subsets, base, prf = g02["M"], g02["subsets"], g02["base"], g06["prf"]
    fields = {}
    for f in FIELDS:
        row = {"reference_cells": base[f][INS]}
        for name in ("all", "decision", "general"):
            counts = M[name][0][f][INS]
            valid, matched = sum(counts.values()), counts[INS]
            assert matched == sum(prf(r, f, INS)[0] for r in subsets[name]), "s02 and s06 must agree"
            definite = {label: n for label, n in sorted(counts.items()) if label != INS and n}
            nearest = max(definite, key=definite.get)
            fixed = base[f][INS] * len(subsets[name])
            row[name] = {"run_passes": len(subsets[name]), "cell_denominator": fixed, "valid_answers": valid,
                         "unavailable_answers": fixed - valid, "matched": matched, "definite": valid - matched,
                         "definite_share_of_valid": share(valid - matched, valid), "matched_share_of_cells": share(matched, fixed),
                         "nearest_definite_label": nearest, "nearest_definite": definite[nearest],
                         "nearest_definite_share_of_valid": share(definite[nearest], valid), "definite_by_label": definite}
        m = M["all"][0][f]
        others = [label for label in m if label != INS]
        total, drift = sum(sum(m[label].values()) for label in others), sum(m[label][INS] for label in others)
        row["definite_reference_answered_insufficient"] = {"count": drift, "valid_answers": total, "share": share(drift, total)}
        fields[f] = row
    p = "insufficient_collapse.fields."
    return block("Decision models answered most \"insufficient information\" cells with a definite label",
                 "Treat insufficient information as its own detection task with its own recall; the four-field total hides this gap on exactly the reviews that need a person.",
                 "solid", "Counts are exact over saved answers. The decision vs general split is a working category split, so the comparison is descriptive-only.",
                 ["s02_confusion", "s06_rare_classes"], ["public-site/data.json", "public-site/extended-cases-v1.json", "public-site/additional-cases-v1.json"],
                 [kn("Decision models, follow-up: definite answer where the reference says insufficient", p + "follow_up_needed.decision.definite", p + "follow_up_needed.decision.valid_answers", share_path=p + "follow_up_needed.decision.definite_share_of_valid"),
                  kn("General LLMs, follow-up", p + "follow_up_needed.general.definite", p + "follow_up_needed.general.valid_answers", share_path=p + "follow_up_needed.general.definite_share_of_valid"),
                  kn("Decision models, serious concern", p + "serious_concern_reported.decision.definite", p + "serious_concern_reported.decision.valid_answers", share_path=p + "serious_concern_reported.decision.definite_share_of_valid"),
                  kn("General LLMs, serious concern", p + "serious_concern_reported.general.definite", p + "serious_concern_reported.general.valid_answers", share_path=p + "serious_concern_reported.general.definite_share_of_valid")],
                 denominators="valid_answers counts valid answers on reference-insufficient cells; cell_denominator = reference cells x run-passes, with invalid or missing answers kept as unavailable.",
                 fields=fields)


def frontier_convergence(g09, disputed):
    ref, strong, sets, wrong_sets, vecs = g09["ref"], g09["strong"], g09["sets"], g09["wrong_sets"], g09["vecs"]
    top_vec, top_n = sets.most_common(1)[0]
    members = [r for r in strong if vecs(r) == top_vec]
    misses = [i for i in g09["IDS"] if any(members[0].pred(i)[f] != ref[i][f] for f in FIELDS)]
    inside = sorted(((list(ms), n) for ms, n in wrong_sets.items() if set(ms) <= disputed), key=lambda x: (-x[1], x[0]))
    p = "frontier_convergence."
    return block("The strongest runs often return identical answer sets",
                 "Pick a second model that fails on different reviews; two strong models that share an answer set accept the same disputed answers together.",
                 "solid", "Counts use exact equality of full answer sets. The shared misses are the three disputed reference labels.",
                 ["s09_quirks"], ["public-site/data.json", "public-site/extended-cases-v1.json", "public-site/additional-cases-v1.json"],
                 [kn("Strong run-passes ({frontier_convergence.strong_valid} valid, all four fields matched on at least {frontier_convergence.strong_min_all_four})", p + "strong_run_passes", p + "all_run_passes"),
                  kn("Distinct full answer sets among them", p + "distinct_answer_sets", p + "strong_run_passes"),
                  kn("Run-passes sharing the single largest answer set", p + "largest_set.run_passes", p + "strong_run_passes"),
                  kn("Model families in that one set", p + "largest_set.family_count"),
                  kn("Strong run-passes that miss only disputed labels", p + "miss_only_disputed.run_passes", p + "strong_run_passes")],
                 strong_definition="60 valid answers and at least 57 of 60 all-four matches", strong_valid=strong[0].valid_count(), strong_min_all_four=min(r.all_four(ref) for r in strong),
                 all_run_passes=len(g09["runs"]), strong_run_passes=len(strong), distinct_answer_sets=len(sets),
                 top_set_sizes=[n for _, n in sets.most_common(3)],
                 largest_set={"run_passes": top_n, "all_four": members[0].all_four(ref), "misses": misses,
                              "misses_all_disputed": set(misses) <= disputed, "families": dict(sorted(Counter(r.family for r in members).items())),
                              "family_count": len({r.family for r in members}), "models": sorted({r.model for r in members}),
                              "conditions": dict(sorted(Counter(r.condition for r in members).items()))},
                 disputed_review_ids=sorted(disputed),
                 miss_only_disputed={"run_passes": sum(n for _, n in inside), "by_miss_set": [{"misses": ms, "run_passes": n} for ms, n in inside]})


def pair_row(g11, ra, rb):
    acc, err, dfr = g11["pair_eval"](ra, rb)
    (ka, ca), (kb, cb) = g11["common"].run_cost(ra), g11["common"].run_cost(rb)
    charged = {ka, kb} <= {"observed", "known"}
    return {"run_a": run_ref(ra), "run_b": run_ref(rb), "accepted": len(acc), "accepted_errors": len(err), "accepted_error_ids": err,
            "deferred": len(dfr), "deferred_ids": dfr, "two_run_charge_usd": usd(ca, cb) if charged else None,
            "charge_basis": "observed or known provider charges" if charged else "unavailable: at least one run has no per-pass charge"}


def agreement_rule(g11, g12):
    rows_a, cheapest = g11["rows_a"], g11["cheapest"]
    first = [pair_row(g11, x[3], x[4]) for x in g11["zero_a"][:10]]
    budgets = []
    for question, cond in [("Cheapest pair with 0 accepted errors and at least 50 accepted", lambda x: x[1] == 0 and x[0] >= 50),
                           ("Cheapest pair with at most 1 accepted error and at least 54 accepted", lambda x: x[1] <= 1 and x[0] >= 54),
                           ("Cheapest pair with at most 1 accepted error and at least 56 accepted", lambda x: x[1] <= 1 and x[0] >= 56),
                           ("Best native + general pair with 0 accepted errors", None)]:
        best = g11["top_mixed"][0] if cond is None else cheapest(rows_a, cond)
        budgets.append({"question": question, **pair_row(g11, best[3], best[4])})
    solar_perplexity = pair_row(g11, *g11["sp"][0][3:5])
    qwen = next(x for x in g11["zero_a"] if "qwen27-low" in x[3].run_id and x[4].family == "gemma-26b")
    qwen_gemma = pair_row(g11, qwen[3], qwen[4])
    gemma = [r for r in g11["runs"] if r.family == "gemma-26b" and r.effort == "on" and r.condition == "P0"]
    sensitivity = [pair_row(g11, qwen[3], r) for r in sorted(gemma, key=lambda r: (r.pass_ != "original", r.pass_))]
    beat = sorted(g11["beat"], key=lambda x: (-x[0], x[2]))
    explorer = {}
    for row in [qwen_gemma] + sensitivity + first + budgets + [pair_row(g11, x[3], x[4]) for x in beat[:3]]:
        explorer.setdefault((row["run_a"]["run_id"], row["run_b"]["run_id"]), {k: v for k, v in row.items() if k != "question"})
    routing = []
    for pair in g12["pol"]["pairs"]:
        D, S, I = g12["route"](pair["left"], pair["right"])
        routing.append({"left": pair["left"], "right": pair["right"], "deferred": len(D), "concern_any": len(S), "insufficient_any": len(I),
                        "escalated_beyond_deferral": len(S - D), "clarification_beyond_deferral": len(I - D),
                        "reaches_person": len(D | S | I), "accepted_no_routing": 60 - len(D | S | I)})
    D, S, I = g12["route"]("solar-decide-native-fresh1-p0", "perplexity-decider-native-fresh1-p0")
    full = {"pair": "Solar Decide + Perplexity Decider", "denominator": 60,
            "rows": [{"step": "Deferred: the two answers differ", "count": len(D), "ids": sorted(D)},
                     {"step": "Accepted, escalated: either model says serious concern", "count": len(S - D), "ids": sorted(S - D)},
                     {"step": "Accepted, sent for clarification: either model says insufficient information", "count": len(I - D), "ids": sorted(I - D)},
                     {"step": "Reaches a person (union)", "count": len(D | S | I), "ids": sorted(D | S | I)},
                     {"step": "Accepted with no routing", "count": 60 - len(D | S | I), "ids": sorted(set(g12["IDS"]) - (D | S | I))}],
            "overlap": {"deferred_and_concern": len(D & S), "deferred_and_insufficient": len(D & I), "concern_and_insufficient": len(S & I)},
            "reference_serious_concern_yes": g12["ref_sc"]}
    assert len(D) + len(S - D) + len(I - D) - len((S & I) - D) == len(D | S | I)
    p = "agreement_rule."
    return block("Some cheap general LLM pairs accepted more reviews than Solar + Perplexity at a lower charge",
                 "Pick a pair for complementary failures and price, and budget for the deferred reviews; agreement still cannot catch a blind spot both models share.",
                 "solid", "Counts are exact and look back at the same development reviews. Any ranking of pairs is descriptive-only, and no pair is a recommended configuration.",
                 ["s11_agreement_general", "s12_full_policy_routing"],
                 ["public-site/native-agreement-policy-v1.json", "public-site/disputed-reviews-v1.json", "public-site/data.json", "public-site/extended-cases-v1.json"],
                 [kn("Solar + Perplexity accepted", p + "solar_perplexity.accepted", p + "denominator"),
                  kn("Solar + Perplexity accepted errors", p + "solar_perplexity.accepted_errors"),
                  kn("Qwen 27B low + Gemma 26B on accepted, with {agreement_rule.qwen_gemma.accepted_errors} errors", p + "qwen_gemma.accepted", p + "denominator"),
                  kn("Qwen 27B low + Gemma 26B on two-run charge", p + "qwen_gemma.two_run_charge_usd", fmt="usd"),
                  kn("Charged pairs that beat Solar + Perplexity on coverage and price", p + "pairs_beating_solar_perplexity", p + "charged_cross_pairs"),
                  kn("Full policy: Solar + Perplexity reviews that reach a person", p + "full_policy_routing.rows[3].count", p + "denominator")],
                 rule="Accept a review only when both runs return the identical valid four-field answer; otherwise defer to a person.",
                 denominator=60, charged_runs=len(g11["charge"]),
                 charged_runs_by_category={c: sum(1 for r, _, _ in g11["charge"] if r.category == c) for c in ("decision", "general")},
                 charged_cross_pairs=len(rows_a), charged_zero_error_pairs=len(g11["zero_a"]),
                 pairs_beating_solar_perplexity=len(beat),
                 beat_definition="0 accepted errors, at least 53 accepted, and a lower two-run charge than $0.03749436",
                 solar_perplexity=solar_perplexity, qwen_gemma=qwen_gemma,
                 qwen_gemma_pass_sensitivity=sensitivity,
                 top_zero_error_pairs=first, budget_answers=budgets, explorer_pairs=list(explorer.values()),
                 native_routing=routing, full_policy_routing=full)


def determinism(g07):
    results, ref_vec = g07["results"], g07["ref_vec"]
    cats = {c: [x for x in results if x[1][0].category == c] for c in ("decision", "general")}
    assert sum(map(len, cats.values())) == len(results), "every three-pass group is decision or general"
    zero = {c: sum(1 for x in rows if not x[3]) for c, rows in cats.items()}
    stable_wrong = []
    for k, rs, per, unstable, scores in results:
        if not unstable and scores[0] < 60:
            wrong = [i for i in g07["IDS"] if rs[0].vector(i) != ref_vec[i]]
            stable_wrong.append({"family": k[0], "configuration": k[1], "effort": k[2], "condition": k[3], "passes": len(rs),
                                 "category": rs[0].category, "all_four": scores[0], "fixed_wrong": len(wrong), "fixed_wrong_ids": wrong})
    stable_wrong.sort(key=lambda r: (-r["all_four"], r["family"], r["configuration"], r["condition"]))
    threshold = 55
    strong = [r for r in stable_wrong if r["all_four"] >= threshold]
    top10, hard10 = g07["top10"], g07["hard10"]
    overlap = sorted(set(top10) & set(hard10))
    p = "determinism."
    return block("Decision models repeated their answers across passes; most general LLM configurations changed some",
                 "A decision model gives a fixed wrong list you can audit once; a general LLM gives a different wrong list each batch, so monitoring should count per-review flips, since totals can stay flat while answers change.",
                 "solid", "Counts are exact over every configuration with three passes. Any serving-stack explanation is descriptive-only.",
                 ["s07_repeatability"], ["public-site/data.json", "public-site/extended-cases-v1.json", "public-site/additional-cases-v1.json"],
                 [kn("Decision configurations with no changed answer across three passes", p + "zero_change.decision", p + "configurations.decision"),
                  kn("General configurations with no changed answer", p + "zero_change.general", p + "configurations.general"),
                  kn("Perfectly stable configurations at {determinism.stable_threshold} or better, all general LLMs", p + "stable_at_55_or_better"),
                  kn("Most-flipped reviews that are also among the hardest", p + "unstable_hard_overlap.count", p + "unstable_hard_overlap.of")],
                 configurations={c: len(rows) for c, rows in cats.items()}, configurations_total=len(results), zero_change=zero,
                 stable_threshold=threshold, stable_at_55_or_better=len(strong), stable_at_55_categories=dict(Counter(r["category"] for r in strong)),
                 unstable_hard_overlap={"count": len(overlap), "of": 10, "ids": overlap, "top_unstable": top10, "hardest": hard10,
                                        "jaccard": round(len(overlap) / len(set(top10) | set(hard10)), 2)},
                 stable_but_wrong_count=len(stable_wrong), stable_but_wrong=stable_wrong)


def calibration(g08):
    ref, by_model, F = g08["ref"], g08["by_model"], g08["F"]
    ece, chosen, bin_of, BINS = g08["ece"], g08["chosen_prob"], g08["bin_of"], g08["BINS"]
    models, bins, gap = [], {}, 0.2  # gap: the |confidence - option probability| cut s08 uses
    for m in g08["MODELS"]:
        recs = by_model[m]
        pairs = [(r["conf"][f], r["prediction"][f] == ref[r["id"]][f]) for r in recs for f in F if r["conf"][f] is not None]
        cp = [(chosen(r, f), r["prediction"][f] == ref[r["id"]][f]) for r in recs for f in F if chosen(r, f) is not None]
        gaps = [chosen(r, f) - r["conf"][f] for r in recs for f in F if chosen(r, f) is not None and r["conf"][f] is not None]
        first = [r for r in recs if r["stage"] == g08["first_stage"](m)]
        minc = {r["id"]: min(r["conf"][f] for f in F) for r in first}
        low10 = sorted(minc, key=lambda i: (minc[i], i))[:10]
        big = sum(1 for g in gaps if abs(g) > gap)
        models.append({"model": m, "field_answers": len(pairs), "ece_confidence": round(ece(pairs), 3), "ece_chosen_probability": round(ece(cp), 3),
                       "mean_confidence": round(sum(s for s, _ in pairs) / len(pairs), 3), "accuracy": round(sum(c for _, c in pairs) / len(pairs), 3),
                       "gap_over_0_2": big, "gap_answers": len(gaps), "gap_over_0_2_share": share(big, len(gaps)),
                       "first_stage": g08["first_stage"](m), "least_confident_10": low10,
                       "least_confident_hard_overlap": len(set(low10) & set(g08["hard10"]))})
        if m in ("jev", "clef-flash"):
            cells = [[] for _ in BINS]
            for s, c in pairs:
                cells[bin_of(s)].append((s, c))
            bins[m] = [{"lower": lo, "upper": min(hi, 1.0), "n": len(v), "correct": sum(c for _, c in v),
                        "accuracy": share(sum(c for _, c in v), len(v)), "mean_confidence": round(sum(s for s, _ in v) / len(v), 3) if v else None}
                       for (lo, hi), v in zip(BINS, cells)]
    jev_first = [r for r in by_model["jev"] if r["stage"] == g08["first_stage"]("jev")]
    wrong = [{"id": r["id"], "field": f, "prediction": r["prediction"][f], "reference": ref[r["id"]][f],
              "confidence": r["conf"][f], "chosen_probability": chosen(r, f)}
             for r in sorted(jev_first, key=lambda r: r["id"]) for f in F if r["prediction"][f] != ref[r["id"]][f] and r["conf"][f] >= 0.9]
    index = {m["model"]: i for i, m in enumerate(models)}
    p = "calibration."
    return block("On these {denominator} reviews, Jev's confidence is calibrated on average (expected calibration error {" + p + f"models[{index['jev']}].ece_confidence|ece"
                 + "}, descriptive-only) and still {" + p + "jev_confident_wrong.answers[0].confidence|conf} on a wrong testimonial",
                 "If a vendor exposes two numbers, threshold on the option probability, and expect even the best-calibrated model to be confident about the wrong field on off-topic input.",
                 "descriptive-only", "Answers pooled across stages come from the same development reviews, so they are not independent. No abstention policy was run, and the two confident errors are anecdotal.",
                 ["s08_confidence"], ["results/openjev/typesafe-development-v2-reconciled.jsonl", "results/clef-openrouter-v1/findings-v1/public-projection.json"],
                 [kn("Jev expected calibration error on these {denominator} reviews (pooled provider confidence)", p + f"models[{index['jev']}].ece_confidence", fmt="ece"),
                  kn("Jev field answers", p + f"models[{index['jev']}].field_answers"),
                  kn("Clef Flash expected calibration error", p + f"models[{index['clef-flash']}].ece_confidence", fmt="ece"),
                  kn("Clef Flash answers where confidence and option probability differ by more than {calibration.gap_threshold|text}", p + f"models[{index['clef-flash']}].gap_over_0_2",
                     p + f"models[{index['clef-flash']}].gap_answers", share_path=p + f"models[{index['clef-flash']}].gap_over_0_2_share"),
                  kn("Jev's least-confident reviews that are among the hardest", p + f"models[{index['jev']}].least_confident_hard_overlap", p + "hardest_count")],
                 gap_threshold=gap, bins_definition=[[lo, min(hi, 1.0)] for lo, hi in BINS], models=models, reliability_bins=bins,
                 jev_confident_wrong={"stage": g08["first_stage"]("jev"), "threshold": 0.9, "confidence_tag": "anecdotal", "answers": wrong},
                 hardest_ids=g08["hard10"], hardest_count=len(g08["hard10"]))


def prompt_direction(g03):
    overall, n = g03["overall"], len(g03["trip"])
    steps = {s.replace("_", "->"): {"better": overall[s]["better"], "same": overall[s]["same"], "worse": overall[s]["worse"],
                                    "net_all_four": overall["net" + s[1] + s[-1]], "triplets": n} for s in ("P0_P1", "P1_P2", "P0_P2")}
    shift = {}
    for cat in ("general", "decision"):
        c0, c2, refp, inv0, inv2, trips, paired = g03["dist"](cat)
        shift[cat] = {"triplets": trips, "paired_valid_positions": paired, "positions": 60 * trips, "rows": [
            {"field": f, "label": lab, "p0": c0[f][lab], "p2": c2[f][lab], "delta": c2[f][lab] - c0[f][lab],
             "delta_per_triplet": round((c2[f][lab] - c0[f][lab]) / trips, 2)} for f in FIELDS for lab in g03["common"].LABELS[f]]}
    find = lambda cat, f, lab: next(i for i, r in enumerate(shift[cat]["rows"]) if (r["field"], r["label"]) == (f, lab))  # noqa: E731
    p = "prompt_direction."
    return block("Prompt revisions moved labels in different directions for each model class",
                 "After a prompt change, regression-test the label distribution as well as the score.",
                 "solid", "This describes saved runs within each configuration and makes no causal claim about prompts.",
                 ["s03_prompt_versions"], ["public-site/data.json", "public-site/extended-cases-v1.json", "public-site/additional-cases-v1.json"],
                 [kn("P1 to P2: triplets that got worse", p + "steps.P1->P2.worse", p + "steps.P1->P2.triplets"),
                  kn("P1 to P2: triplets that got better", p + "steps.P1->P2.better", p + "steps.P1->P2.triplets"),
                  kn("General LLMs, sentiment \"mixed\" per triplet, P0 to P2", p + f"label_shift.general.rows[{find('general', 'sentiment', 'mixed')}].delta_per_triplet", fmt="signed"),
                  kn("Decision models, serious concern \"insufficient\" per triplet, P0 to P2", p + f"label_shift.decision.rows[{find('decision', 'serious_concern_reported', INS)}].delta_per_triplet", fmt="signed")],
                 triplet_definition="One configuration-pass with P0, P1 and P2 all saved", steps=steps, label_shift=shift,
                 identical_across_three_prompts=len(g03["same012"]))


def size_thinking(g05):
    deltas = {size: [r[6] for r in g05["rows"] if r[0] == size] for size in g05["summary"]}
    sizes = [{"size": size, "pairs": sum(v), "helps": v[0], "equal": v[1], "hurts": v[2], "delta_min": min(deltas[size]), "delta_max": max(deltas[size])}
             for size, v in g05["summary"].items()]
    qwen17 = [{"condition": r[2], "pass": r[3], "all_four_off": r[4], "all_four_on": r[5], "delta": r[6],
               "testimonial_delta": int(r[9].split("/")[3])} for r in g05["rows"] if r[0] == "Qwen 1.7B"]
    idx = {s["size"]: i for i, s in enumerate(sizes)}
    p = "size_thinking."
    return block("Thinking hurt Qwen 1.7B in every pair and helped Qwen 4B in every pair",
                 "The thinking switch is model- and size-specific; test it per configuration instead of assuming more reasoning helps.",
                 "solid", "Tallies are exact over same-surface, same-condition, same-pass pairs; any family-level reading is descriptive-only.",
                 ["s05_size"], ["public-site/data.json", "public-site/extended-cases-v1.json"],
                 [kn("Qwen 1.7B pairs where thinking hurt", p + f"sizes[{idx['Qwen 1.7B']}].hurts", p + f"sizes[{idx['Qwen 1.7B']}].pairs"),
                  kn("Gemma E2B pairs where thinking helped", p + f"sizes[{idx['Gemma4 E2B']}].helps", p + f"sizes[{idx['Gemma4 E2B']}].pairs"),
                  kn("Qwen3.6 35B pairs where thinking helped", p + f"sizes[{idx['Qwen3.6 35B-A3B']}].helps", p + f"sizes[{idx['Qwen3.6 35B-A3B']}].pairs")],
                 sizes=sizes, qwen_1_7b_pairs=qwen17)


def cost_frontier(g10):
    A, B, C, ref = g10["A"], g10["B"], g10["C"], g10["ref"]
    front = [{**run_ref(r), "valid": r.valid_count(), "all_four": af, "cost_kind": k, "usd": v} for r, k, v, af in g10["frontier"](A)]
    gate = sorted([s for s in g10["stats"] if s[1] in ("observed", "known") and s[3] == 25 and s[4] == 0 and s[9] == 10], key=lambda s: s[2])
    best = gate[0][0]
    same = [s for s in g10["stats"] if (s[0].model, s[0].effort, s[0].condition) == (best.model, best.effort, best.condition)]
    passes = [{"pass": s[0].pass_, "run_id": s[0].run_id, "all_four": s[0].all_four(ref), "concern_tp_fp_fn": list(s[3:6]),
               "testimonial_tp_fp_fn": list(s[6:9]), "insufficient_cells": s[9], "cost_kind": s[1], "usd": s[2]}
              for s in sorted(same, key=lambda s: (s[0].pass_ != "original", s[0].pass_))]
    p = "cost_frontier."
    return block("The cheapest gate-clearing pass failed the insufficient-information gate when its configuration ran again",
                 "Select a configuration only after the gate holds across three passes.",
                 "solid", "Charges are exact and source-bound; frontier membership is descriptive-only; the gate-clearing pass is one pass, so the selection is anecdotal.",
                 ["s10_cost"], ["public-site/data.json", "public-site/extended-run-catalog-v1.json", "public-site/supplemental-decision-runs-v1.json", "public-site/subscription-price-estimates.json"],
                 [kn("Observed or known-charge frontier points", p + "frontier_points", p + "run_passes.observed_or_known"),
                  kn("Cheapest gate-clearing pass, all four fields", p + "gate.passes[0].all_four", p + "denominator"),
                  kn("Its charge for {denominator} reviews", p + "gate.passes[0].usd", fmt="usd"),
                  kn("Same configuration, first fresh pass", p + "gate.passes[1].all_four", p + "denominator")],
                 denominator=60, run_passes={"observed_or_known": len(A), "estimate": len(B), "unknown": len(C)},
                 frontier_points=len(front), frontier=front,
                 gate={"definition": "serious concern recall 25 of 25 with 0 false positives, and all 10 reference insufficient_information cells matched",
                       "qualifying_charged_run_passes": len(gate), "passes": passes, "confidence_tag": "anecdotal"},
                 unknown_cost_rule="Unknown-cost run-passes stay unknown and are never plotted at zero.")


def hardest_reviews(g01, disputed, off_topic, dr):
    d, N, order = g01["d"], g01["N"], g01["order"]
    texts = {r["id"]: r["feedback"] for r in dr["reviews"]}
    assert all(texts[i] == g01["text"][i] for i in g01["IDS"]), "public review text must equal data/pilot inputs"
    drive = {row[0]: row for row in g01["rows"]}
    reviews = [{"rank": rank, "id": rid, "all_four": d[rid]["all_four"], "run_passes": N, "share": share(d[rid]["all_four"], N), "valid": d[rid]["valid"],
                "field_matches": {f: d[rid][f] for f in FIELDS}, "reference": g01["ref"][rid], "text": texts[rid], "driving_field": drive[rid][4],
                "most_common_wrong_answer": drive[rid][5].split("/") if drive[rid][5] else None, "most_common_wrong_count": drive[rid][6],
                "disputed_reference": rid in disputed, "off_topic": rid in off_topic} for rank, rid in enumerate(order[:10], 1)]
    return block("The ten hardest reviews", "The hardest reviews are the disputed, off-topic and boundary cases, so the human queue should cover them first.",
                 "solid", "Match counts are exact over all run-passes with a fixed denominator, and invalid output counts as a non-match.",
                 ["s01_difficulty"], ["public-site/disputed-reviews-v1.json", "data/pilot/inputs.jsonl", "data/pilot/proposed_labels.jsonl"], [],
                 run_passes=N, reviews=reviews)


def corrections(pol, dr, sup, g07, cal, fc, ic):
    soup = next(r for r in dr["reviews"] if r["id"] == "DEV-029")
    soup_counts = Counter(a["prediction"]["sentiment"] for a in soup["answers"])
    zero = [p for p in pol["pairs"] if p["accepted_all_four_error_count"] == 0]
    erring = [p for p in pol["pairs"] if p["accepted_all_four_error_count"] > 0]
    names = {c["id"]: c["display_name"] for c in pol["components"]}
    assert all(r["cost"]["knownUsd"] is not None and r["cost"]["unknownUpperBoundUsd"] is not None for r in sup["runs"]), \
        "every native run must carry a known charge or estimate and an explicit unknown-cost bound"
    known = round(sum(r["cost"]["knownUsd"] for r in sup["runs"]), 9)
    unknown = {m: round(sum(r["cost"]["unknownUpperBoundUsd"] for r in sup["runs"] if r["model"] == m), 9) for m in sorted({r["model"] for r in sup["runs"]})}
    opus = next(x for x in g07["results"] if x[0][0] == "opus-5.5" and x[0][2] == "high" and x[0][3] == "P0")
    jev = next(m for m in cal["models"] if m["model"] == "jev")
    wrong = cal["jev_confident_wrong"]["answers"]
    base = "corrections.items"
    items = [
        {"id": "dev029-mixed", "said": "Five decision models called the off-topic soup review \"mixed\".",
         "correct": segments("{mixed} of {models} native decision models said mixed; {insufficient_information} said insufficient information and {negative} said negative.", f"{base}[0].values."),
         "values": {"mixed": soup_counts["mixed"], "insufficient_information": soup_counts[INS], "negative": soup_counts["negative"], "models": len(soup["answers"])},
         "source": "public-site/disputed-reviews-v1.json"},
        {"id": "zero-error-pairs", "said": "Four of 21 agreement pairs kept zero accepted errors.",
         "correct": segments("{pairs} of {of} pairs kept zero accepted errors.", f"{base}[1].values."),
         "values": {"pairs": len(zero), "of": len(pol["pairs"]), "pair_names": [f"{names[p['left']]} + {names[p['right']]}" for p in zero]},
         "source": "public-site/native-agreement-policy-v1.json"},
        {"id": "error-pair-reviews", "said": "The error-retaining pairs erred only on DEV-006, DEV-029 and DEV-030.",
         "correct": segments("The {pairs} error-retaining pairs erred on {reviews} distinct reviews.", f"{base}[2].values."),
         "values": {"pairs": len(erring), "reviews": len({i for p in erring for i in p["accepted_all_four_error_ids"]}),
                    "review_ids": sorted({i for p in erring for i in p["accepted_all_four_error_ids"]})},
         "source": "public-site/native-agreement-policy-v1.json"},
        {"id": "seven-model-cost", "said": "The whole seven-model study cost under $1.20.",
         "correct": segments("The study cost {total_usd|usd:4} in known provider charges over {runs} runs, Clef's {clef_known_usd|usd:4} included, plus up to {unknown_upper_bound_usd|usd:2} unknown.", f"{base}[3].values."),
         "values": {"total_usd": known, "runs": len(sup["runs"]), "clef_known_usd": round(sum(r["cost"]["knownUsd"] for r in sup["runs"] if r["model"] == "cloudflare/clef"), 9),
                    "unknown_upper_bound_usd": round(sum(unknown.values()), 9),
                    "unknown_by_model_usd": {m: v for m, v in unknown.items() if v}},
         "source": "public-site/supplemental-decision-runs-v1.json; docs/talk/06-cost-check.md section 1"},
        {"id": "opus-passes", "said": "Opus 5.5 high has one P0 pass at 59 of 60.",
         "correct": segments("Opus 5.5 high has {passes} P0 passes: {scores[0]}, {scores[1]} and {scores[2]} of {of}.", f"{base}[4].values."),
         "values": {"scores": opus[4], "passes": len(opus[1]), "of": len(g07["IDS"])}, "source": script("s07_repeatability")},
        {"id": "jev-calibration", "said": "Jev's confidence is not calibrated, and it called the soup review a serious concern at 0.91.",
         "correct": segments("On these {reviews} reviews, Jev's confidence is calibrated on average (expected calibration error {ece|ece} over {field_answers} pooled field answers that share the same {reviews} texts; descriptive-only) and still {confident_wrong[0].confidence|conf} on a wrong testimonial ({confident_wrong[0].id|text}) and {confident_wrong[1].confidence|conf} on {confident_wrong[1].id|text} serious concern, where it answered \"no\" and the reference is insufficient information.", f"{base}[5].values."),
         "values": {"ece": jev["ece_confidence"], "field_answers": jev["field_answers"], "confident_wrong": wrong, "reviews": len(g07["IDS"])}, "confidence_tag": "descriptive-only",
         "source": script("s08_confidence")},
        {"id": "miss-only-disputed", "said": "235 of 373 strong run-passes miss nothing outside the three disputed labels.",
         "correct": segments("{run_passes} of {of} strong run-passes miss nothing outside the three disputed labels; {top3} counts only the three most common miss sets.", f"{base}[6].values."),
         "values": {"run_passes": fc["miss_only_disputed"]["run_passes"], "of": fc["strong_run_passes"],
                    "top3": sum(x["run_passes"] for x in fc["miss_only_disputed"]["by_miss_set"][:3])}, "source": script("s09_quirks")},
        {"id": "insufficient-range", "said": "Reference \"insufficient\" is answered as a definite label 22% to 26% of the time on follow-up, serious concern and testimonial.",
         "correct": segments("A definite label is given on {follow|pct}, {concern|pct} and {testimonial|pct} of valid answers; the single nearest label, \"no\", takes {follow_no|pct}, {concern_no|pct} and {testimonial_no|pct}.", f"{base}[7].values."),
         "values": {k + suffix: ic["fields"][f]["all"][key] for k, f in (("follow", "follow_up_needed"), ("concern", "serious_concern_reported"), ("testimonial", "testimonial_potential"))
                    for suffix, key in (("", "definite_share_of_valid"), ("_no", "nearest_definite_share_of_valid"))},
         "source": script("s02_confusion")}]
    return {"date": GENERATED_AT, "count": len(items), "items": items}


def build():
    READ.clear()
    with patch("builtins.open", _tracking_open):
        g = {n: run(n) for n in ("s01_difficulty", "s02_confusion", "s03_prompt_versions", "s05_size", "s06_rare_classes",
                                 "s07_repeatability", "s08_confidence", "s09_quirks", "s10_cost", "s11_agreement_general", "s12_full_policy_routing")}
        READ.add(script("common"))
        pol = load("public-site/native-agreement-policy-v1.json")
        dr = load("public-site/disputed-reviews-v1.json")
        sup = load("public-site/supplemental-decision-runs-v1.json")
        sens = load("public-site/reference-sensitivity-v1.json")
    disputed = {a["id"] for a in sens["alternatives"]}
    off_topic = set(dr["off_topic_review_ids"])
    cal = calibration(g["s08_confidence"])
    fc = frontier_convergence(g["s09_quirks"], disputed)
    ic = insufficient_collapse(g["s02_confusion"], g["s06_rare_classes"])
    feed = {
        "schema": "deep-insights-v1", "generated_at": GENERATED_AT, "denominator": 60,
        "scope": "The talk's analysis scripts recomputed saved predictions for the 60 fictional development reviews and made no model calls.",
        "reference_status": "Frozen proposed labels v0.2, provisional; DEV-006, DEV-013 and DEV-030 are disputed.",
        "claim_rules": ["Every number describes saved run-passes on one provisional reference, and the feed ranks no model.",
                        "Prompts, effort and thinking are described as observed, with no causal claim.",
                        "A missing cost stays unknown and never counts as zero; provider charges and API-equivalent estimates stay separate.",
                        "The feed makes no speed claims.", "Run-passes reuse the same 60 reviews, so they are not independent samples."],
        "insufficient_collapse": ic, "frontier_convergence": fc, "calibration": cal,
        "agreement_rule": agreement_rule(g["s11_agreement_general"], g["s12_full_policy_routing"]),
        "determinism": determinism(g["s07_repeatability"]),
        "prompt_direction": prompt_direction(g["s03_prompt_versions"]),
        "size_thinking": size_thinking(g["s05_size"]),
        "cost_frontier": cost_frontier(g["s10_cost"]),
        "hardest_reviews": hardest_reviews(g["s01_difficulty"], disputed, off_topic, dr),
        "corrections": corrections(pol, dr, sup, g["s07_repeatability"], cal, fc, ic),
    }
    feed["what_changed"] = {"date": GENERATED_AT, "segments": segments(
        "On {generated_at|date} the talk's analysis scripts recomputed every number in this section from the saved answers of "
        "{frontier_convergence.all_run_passes} run-passes on the same {denominator} reviews, without new model calls. The recomputation "
        "corrected {corrections.count} earlier statements, listed at the end of this section, and produced the five findings in the cards below.")}
    feed["source_sha256"] = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in sorted(READ)}
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    feed = build()
    rendered, count = json.dumps(feed, indent=2, sort_keys=True, ensure_ascii=False) + "\n", len(feed["source_sha256"])
    output = ROOT / OUTPUT
    if args.check:
        if not output.exists() or output.read_text() != rendered:
            raise SystemExit(f"{OUTPUT} is stale; rerun scripts/build_deep_insights_v1.py")
        print(f"Verified {OUTPUT} against {count} source hashes")
    else:
        output.write_text(rendered)
        print(f"Wrote {OUTPUT} from {count} source hashes")


if __name__ == "__main__":
    main()
