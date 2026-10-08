"""Section 11: identical-answer accept/defer rule applied to all first-P0 runs with a per-pass charge.
Run: python3 -I s11_agreement_general.py. Retrospective on the same 60 development reviews."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common
from itertools import combinations

ref = common.reference()
runs = common.load_all()
IDS, F = common.IDS, common.FIELDS
sub = common.load_json("public-site/subscription-price-estimates.json")["runs"]

# candidate pool: first-P0 runs with a known/observed charge (A) or API-equivalent estimate (B)
cand = []
for r in runs:
    if r.condition != "P0":
        continue
    first = (r.feed == "data.json") or (r.feed == "additional" and r.pass_ == "fresh1") or (r.feed == "extended" and r.pass_ in ("fresh1", "pass1"))
    if not first:
        continue
    if r.feed == "additional" and r.model not in common.NATIVE_SEVEN:
        continue
    kind, usd = common.run_cost(r)
    if kind in ("observed", "known"):
        cand.append((r, "charge", usd))
    else:
        est = sub.get(r.run_id) or sub.get((r.meta or {}).get("experimentId") or "")
        if est and est.get("estimateUsd") and est.get("estimateStatus") == "complete":
            cand.append((r, "estimate", float(est["estimateUsd"])))
        elif kind == "estimate":
            cand.append((r, "estimate", usd))
# drop exact duplicate run identities (same experimentId appearing in two feeds)
seen = set(); pool = []
for r, k, usd in cand:
    key = ((r.meta or {}).get("experimentId") or r.run_id, r.feed)
    if key in seen:
        continue
    seen.add(key); pool.append((r, k, usd))
charge = [x for x in pool if x[1] == "charge"]
est = [x for x in pool if x[1] == "estimate"]
print(f"pool: {len(pool)} first-P0 runs; {len(charge)} with observed/known charge, {len(est)} with API-equivalent estimate")
print("charge pool by category:", {c: sum(1 for r, _, _ in charge if r.category == c) for c in ("decision", "general", "rules")})


def pair_eval(a, b):
    acc = []; err = []; dfr = []
    for i in IDS:
        va, vb = a.vector(i), b.vector(i)
        if va is not None and va == vb:
            acc.append(i)
            if any(va[k] != ref[i][f] for k, f in enumerate(F)):
                err.append(i)
        else:
            dfr.append(i)
    return acc, err, dfr


def name(r):
    return f"{r.model}|{r.effort}|{r.run_id}"


def same_config(ra, rb):
    return (ra.model, ra.effort) == (rb.model, rb.effort)


def table(pairs, title, top=15, cat_filter=None):
    rows = []
    selfrep = []
    for (ra, ka, ca), (rb, kb, cb) in pairs:
        if cat_filter and not cat_filter(ra, rb):
            continue
        if same_config(ra, rb):  # self-repeat pair: repeat agreement, reported separately
            acc, err, dfr = pair_eval(ra, rb)
            selfrep.append((len(acc), len(err), ca + cb, name(ra)))
            continue
        acc, err, dfr = pair_eval(ra, rb)
        rows.append((len(acc), len(err), ca + cb, ra, rb, err, dfr, ka if ka == kb else "mixed"))
    print(f"\n### {title}: {len(rows)} cross-configuration pairs (+{len(selfrep)} self-repeat pairs excluded)")
    if selfrep:
        print("self-repeat pairs (same model+effort, two passes): " + "; ".join(f"{n.split('|')[0]}|{n.split('|')[1]} {a} acc/{e} err/${c:.4f}" for a, e, c, n in sorted(selfrep, key=lambda x: -x[0])))
    zero = sorted([x for x in rows if x[1] == 0], key=lambda x: (-x[0], x[2]))
    print(f"pairs with 0 accepted errors: {len(zero)}; accepted range {min(x[0] for x in rows)}-{max(x[0] for x in rows)}; errors range {min(x[1] for x in rows)}-{max(x[1] for x in rows)}")
    out = [[x[0], x[1], 60 - x[0], f"${x[2]:.5f}", x[7], name(x[3]), name(x[4]),
            ", ".join(i[4:] for i in x[6] if i in ("DEV-006", "DEV-013", "DEV-029", "DEV-030"))] for x in zero[:top]]
    print(common.md_table(["accepted", "acc. errors", "deferred", "two-run cost", "kind", "run A", "run B", "deferred among 006/013/029/030"], out))
    return rows, zero


pairs_a = list(combinations(charge, 2))
rows_a, zero_a = table(pairs_a, "Table A: both runs with observed/known charge")
# budgets
def cheapest(rows, cond):
    c = [x for x in rows if cond(x)]
    return min(c, key=lambda x: x[2]) if c else None
for label, cond in [("0 errors and >=50 accepted", lambda x: x[1] == 0 and x[0] >= 50),
                    ("0 errors and >=53 accepted", lambda x: x[1] == 0 and x[0] >= 53),
                    ("<=1 error and >=54 accepted", lambda x: x[1] <= 1 and x[0] >= 54),
                    ("<=1 error and >=56 accepted", lambda x: x[1] <= 1 and x[0] >= 56),
                    ("0 errors, two general LLMs", lambda x: x[1] == 0 and x[3].category == "general" and x[4].category == "general"),
                    ("0 errors, one native + one general", lambda x: x[1] == 0 and {x[3].category, x[4].category} == {"general", "decision"})]:
    best = cheapest(rows_a, cond)
    print(f"cheapest charge pair with {label}:", (best[0], best[1], f"${best[2]:.5f}", name(best[3]), name(best[4]), "errors " + ",".join(best[5])) if best else "none")
top_general = sorted([x for x in rows_a if x[1] == 0 and x[3].category == "general" and x[4].category == "general"], key=lambda x: (-x[0], x[2]))[:5]
print("\nbest two-general-LLM pairs with 0 errors (by accepted, then cost):")
print(common.md_table(["accepted", "deferred", "cost", "A", "B", "deferred ids"], [[x[0], 60 - x[0], f"${x[2]:.5f}", name(x[3]), name(x[4]), ", ".join(i[4:] for i in x[6])] for x in top_general]))
top_mixed = sorted([x for x in rows_a if x[1] == 0 and {x[3].category, x[4].category} == {"general", "decision"}], key=lambda x: (-x[0], x[2]))[:5]
print("\nbest native+general pairs with 0 errors:")
print(common.md_table(["accepted", "deferred", "cost", "A", "B", "deferred ids"], [[x[0], 60 - x[0], f"${x[2]:.5f}", name(x[3]), name(x[4]), ", ".join(i[4:] for i in x[6])] for x in top_mixed]))
beat = [x for x in rows_a if x[1] == 0 and x[0] >= 53 and x[2] < 0.03749436]
print(f"\npairs beating saved Solar+Perplexity (53 accepted, 0 errors, $0.03749436) on both axes: {len(beat)}")
for x in sorted(beat, key=lambda x: (-x[0], x[2]))[:10]:
    print("  ", x[0], f"${x[2]:.5f}", name(x[3]), "+", name(x[4]), "deferred:", ", ".join(i[4:] for i in x[6]))
sp = [x for x in rows_a if {x[3].model, x[4].model} == {"upstage/solar-decide", "perplexity/pplx-decider-v1-27b"}]
print("reproduced Solar+Perplexity:", [(x[0], x[1], f"${x[2]:.8f}") for x in sp])

# accepted-error frequency across all charge pairs
from collections import Counter
cnt = Counter(i for x in rows_a for i in x[5])
print("\naccepted-error review frequency across all charge pairs:", cnt.most_common(10))
dcnt = Counter(i for x in rows_a for i in x[6])
print("most deferred reviews across all charge pairs:", dcnt.most_common(10))

pairs_b = [(a, b) for a, b in combinations(pool, 2) if a[1] == "estimate" or b[1] == "estimate"]
rows_b, zero_b = table(pairs_b, "Table B: at least one run costed by API-equivalent estimate (estimate, not a bill)", top=10)
best = cheapest(rows_b, lambda x: x[1] == 0 and x[0] >= 55)
print("cheapest estimate-involving pair with 0 errors and >=55 accepted:", (best[0], f"${best[2]:.5f}", name(best[3]), name(best[4])) if best else "none")
print(f"\ntotal pairs evaluated: {len(pairs_a) + len(pairs_b)} (A {len(pairs_a)}, B {len(pairs_b)}; self-repeat pairs excluded from tables)")
