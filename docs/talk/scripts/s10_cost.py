"""Section 10: cost-efficiency frontier. Run: python3 -I docs/talk/scripts/s10_cost.py

Table A: observed or known provider charges only.  Table B: API-equivalent
estimates (subscription CLI runs, Jev direct token-price estimate), separate
accounting category, never merged with A.  Table C: unknown-cost runs.
Missing cost is unknown, not zero. Fixed denominator 60.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common  # noqa: E702
from collections import Counter, defaultdict

ref = common.reference()
runs = common.load_all()
SUB = common.load_json("public-site/subscription-price-estimates.json")
JEV = common.load_json("public-site/jev-native-prompt-findings.json")["passes"]
F = common.FIELDS


def cost(r):
    # Jev OpenRouter native-prompt stages: jev-native-prompt-findings reports knownCostUsd (provider charge);
    # the extended catalog files the same amount under estimatedUsd. The findings feed wins here; flagged in the report.
    if r.family == "jev" and "native-prompts" in r.run_id and r.condition in JEV and r.pass_ in JEV[r.condition]:
        st = JEV[r.condition][r.pass_]
        if st["status"] == "complete":
            return "known", float(st["knownCostUsd"])
    k, v = common.run_cost(r)
    if k != "unknown":
        return k, v
    exp = (r.meta or {}).get("experimentId") or r.run_id
    if r.feed == "data.json" and r.run_id in SUB["runs"] and SUB["runs"][r.run_id].get("estimateUsd"):
        return "estimate", float(SUB["runs"][r.run_id]["estimateUsd"])
    key = f"{exp}:{r.pass_}:{r.condition}"
    if key in SUB["repeatPhases"] and SUB["repeatPhases"][key].get("estimateUsd"):
        return "estimate", float(SUB["repeatPhases"][key]["estimateUsd"])
    if r.family == "jev" and r.feed == "extended" and r.condition in JEV and r.pass_ in JEV[r.condition]:
        st = JEV[r.condition][r.pass_]
        if st["status"] == "complete":
            return "known", float(st["knownCostUsd"])
    return "unknown", None


def recall_prec(r, field, label):
    tp = fp = fn = 0
    for i in common.IDS:
        p = r.pred(i)
        pos = ref[i][field] == label
        if p is None:
            fn += pos
            continue
        if p[field] == label:
            tp += pos
            fp += (not pos)
        elif pos:
            fn += 1
    return tp, fp, fn


priced = []
for r in runs:
    k, v = cost(r)
    priced.append((r, k, v))

A = [(r, k, v) for r, k, v in priced if k in ("observed", "known")]
B = [(r, k, v) for r, k, v in priced if k == "estimate"]
C = [(r, k, v) for r, k, v in priced if k == "unknown"]
print(f"# Section 10 cost tables: A observed/known N={len(A)}, B estimate N={len(B)}, C unknown N={len(C)}, total {len(runs)}\n")

hdr = ["run", "model", "effort", "cond", "pass", "valid", "all4", "cost kind", "usd per 60-review pass", "matches per $"]


def table(rows_in, title, limit=None):
    rows = []
    for r, k, v in sorted(rows_in, key=lambda x: x[2]):
        rows.append([r.run_id, r.model, r.effort, r.condition, r.pass_, r.valid_count(), r.all_four(ref), k, f"{v:.6f}", f"{r.all_four(ref) / v:,.0f}"])
    print(f"\n## {title} (N={len(rows)})")
    print(common.md_table(hdr, rows if limit is None else rows[:limit]))


def frontier(rows_in):
    pts = sorted(((v, r.all_four(ref), r, k) for r, k, v in rows_in), key=lambda x: (x[0], -x[1]))
    best = -1
    out = []
    for v, af, r, k in pts:
        if af > best:
            out.append((r, k, v, af))
            best = af
    return out


def frontier_table(rows_in, title):
    rows = [[r.run_id, r.model, r.effort, r.condition, r.pass_, r.valid_count(), af, k, f"{v:.6f}", f"{af / v:,.0f}"] for r, k, v, af in frontier(rows_in)]
    print(f"\n## {title} (N={len(rows)} frontier points)")
    print(common.md_table(hdr, rows))


def cheapest_at(rows_in, title):
    print(f"\n## {title}: cheapest run at each all-four level >= 57")
    for lvl in (57, 58, 59, 60):
        c = sorted([x for x in rows_in if x[0].all_four(ref) == lvl], key=lambda x: x[2])
        print(f"  all4 = {lvl}: " + (f"{c[0][0].run_id} ({c[0][0].model}, {c[0][0].effort}, {c[0][0].condition}/{c[0][0].pass_}) {c[0][1]} ${c[0][2]:.6f}; {len(c)} runs at this level" if c else "none"))
    c = sorted([x for x in rows_in if x[0].all_four(ref) >= 57], key=lambda x: x[2])
    print(f"  cheapest >= 57: " + (f"{c[0][0].run_id} {c[0][0].all_four(ref)}/60 ${c[0][2]:.6f} ({c[0][1]})" if c else "none"))


# Table A
table(A, "Table A: observed/known provider charges, all runs sorted by cost")
frontier_table(A, "Table A frontier (no other observed/known run is both cheaper and at least as good)")
cheapest_at(A, "Table A")
print("\nTable A runs at all-four 59:", [(x[0].run_id, x[1], round(x[2], 6)) for x in A if x[0].all_four(ref) == 59])
print("\nTable A P0 first-pass subset frontier (original/fresh1/pass1 only):")
A0 = [x for x in A if x[0].condition == "P0" and x[0].pass_ in ("original", "fresh1", "pass1")]
print(f"Table A P0 first passes N={len(A0)}")
frontier_table(A0, "Table A, P0 first passes")
cheapest_at(A0, "Table A P0 first passes")

# Table B
table(B, "Table B: API-equivalent ESTIMATES (not bills): subscription CLI and Jev direct token-price estimate")
frontier_table(B, "Table B frontier (estimates only)")
cheapest_at(B, "Table B (estimates)")

# Table C
print("\n## Table C: unknown-cost run-passes by family (local hardware, subscription without estimate, interrupted)")
cnt = Counter(r.family for r, k, v in C)
print(common.md_table(["family", "unknown-cost run-passes"], sorted(cnt.items(), key=lambda x: -x[1])))

# serious concern recall
print("\n\n# serious_concern_reported = yes recall (25 reference positives), testimonial = yes recall (9), insufficient_information cells (10)\n")
ins_cells = [(i, f) for i in common.IDS for f in F if ref[i][f] == "insufficient_information"]
stats = []
for r, k, v in priced:
    tp, fp, fn = recall_prec(r, "serious_concern_reported", "yes")
    ttp, tfp, tfn = recall_prec(r, "testimonial_potential", "yes")
    ins_hits = sum(1 for i, f in ins_cells if (p := r.pred(i)) is not None and p[f] == "insufficient_information")
    stats.append((r, k, v, tp, fp, fn, ttp, tfp, tfn, ins_hits))
n25 = [s for s in stats if s[3] == 25]
print(f"runs with serious_concern recall 25/25: {len(n25)} of {len(stats)} run-passes; by category: {Counter(s[0].category for s in n25)}")
print(f"runs with testimonial recall 9/9: {sum(1 for s in stats if s[6] == 9)} of {len(stats)}")
print(f"runs matching all 10 insufficient_information cells: {sum(1 for s in stats if s[9] == 10)} of {len(stats)}")

hdr4 = ["run", "model", "effort", "cond/pass", "all4", "concern TP/FP/FN", "concern precision", "testi TP/FP/FN", "insuff cells /10", "cost kind", "usd"]


def pick(flt, title, kinds, n=8):
    c = sorted([s for s in stats if s[1] in kinds and flt(s)], key=lambda s: s[2])
    rows = [[s[0].run_id, s[0].model, s[0].effort, f"{s[0].condition}/{s[0].pass_}", s[0].all_four(ref), f"{s[3]}/{s[4]}/{s[5]}",
             f"{s[3] / (s[3] + s[4]):.3f}" if s[3] + s[4] else "n/a", f"{s[6]}/{s[7]}/{s[8]}", s[9], s[1], f"{s[2]:.6f}"] for s in c[:n]]
    print(f"\n## {title} (N matching={len(c)}, cheapest {min(n, len(c))} shown)")
    print(common.md_table(hdr4, rows))


pick(lambda s: s[3] == 25, "Observed/known charge, serious_concern recall 25/25", ("observed", "known"))
pick(lambda s: s[3] == 25, "Estimate-only (not a bill), serious_concern recall 25/25", ("estimate",))
pick(lambda s: s[3] == 25 and s[4] == 0, "Observed/known charge, serious_concern recall 25/25 AND precision 1.0", ("observed", "known"))
pick(lambda s: s[6] == 9, "Observed/known charge, testimonial recall 9/9", ("observed", "known"))
pick(lambda s: s[9] == 10, "Observed/known charge, all 10 insufficient_information cells matched", ("observed", "known"))
pick(lambda s: s[9] == 10, "Estimate-only, all 10 insufficient_information cells matched", ("estimate",))
print("\nUnknown-cost runs with 25/25 concern recall:", len([s for s in n25 if s[1] == "unknown"]),
      "e.g.", [s[0].run_id for s in n25 if s[1] == "unknown"][:8])

if __name__ == "__main__":
    # self-check: frontier must be monotone in all-four and cost
    fr = frontier(A)
    assert all(fr[i][2] < fr[i + 1][2] and fr[i][3] < fr[i + 1][3] for i in range(len(fr) - 1))
    assert all(s[3] + s[5] == 25 for s in stats), "TP+FN must equal 25 positives"
