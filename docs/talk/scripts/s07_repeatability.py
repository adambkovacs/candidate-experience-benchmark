"""Section 7: repeatability across 3+ passes of the same configuration. Run: python3 -I docs/talk/scripts/s07_repeatability.py"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from collections import Counter, defaultdict

ref = common.reference()
runs = common.load_all()
F = common.FIELDS
IDS = common.IDS


def config_key(r):
    """Configuration identity without the pass. Uses experimentId/sourceStage prefix so batch10 and
    phase2 variants stay separate. ponytail: string surgery on the saved stage names; good enough here."""
    if r.feed == "data.json":
        base = r.meta.get("experimentId") or r.run_id
    elif r.feed == "extended":
        base = r.meta.get("sourceStage", "").split("/")[0]
    else:
        base = r.meta.get("sourceStage", "").split("/")[0]
    # pass family: original+repeat2/repeat3 form one series; fresh1-3 another; pass1-3 another
    pf = "repeat" if r.pass_ in ("original", "repeat2", "repeat3") else ("pass" if r.pass_.startswith("pass") else "fresh")
    return (r.family, base, r.effort, r.condition, pf)


groups = defaultdict(list)
for r in runs:
    groups[config_key(r)].append(r)

# merge data.json original into extended repeat2/repeat3 groups where experimentId matches the stage prefix
# (both use the same experimentId string, so they already share a key) and sonnet55 pass1 (additional) with pass2/3 (extended)
triples = {k: v for k, v in groups.items() if len(v) >= 3}
print(f"configurations with >=3 passes under one condition: {len(triples)} (of {len(groups)} configuration-conditions)")

ref_vec = {rid: tuple(ref[rid][f] for f in F) for rid in IDS}


def analyse(rs):
    per = {}
    for rid in IDS:
        vecs = [r.vector(rid) or ("INVALID",) for r in rs]
        per[rid] = len(set(vecs))
    unstable = [rid for rid in IDS if per[rid] > 1]
    scores = [r.all_four(ref) for r in rs]
    return per, unstable, scores


results = []
for k, rs in sorted(triples.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
    rs = sorted(rs, key=lambda r: r.pass_)
    per, unstable, scores = analyse(rs)
    results.append((k, rs, per, unstable, scores))

print("\n## Every configuration with >=3 passes: passes, all-four per pass, unstable reviews")
rows = []
for k, rs, per, unstable, scores in results:
    rows.append([k[0], k[1], k[2], k[3], k[4], len(rs), "/".join(str(s) for s in scores), "/".join(str(r.valid_count()) for r in rs), len(unstable),
                 ", ".join(unstable) if len(unstable) <= 8 else ", ".join(unstable[:8]) + f" (+{len(unstable)-8})"])
print(common.md_table(["family", "configuration", "effort", "cond", "series", "passes", "all-four per pass", "valid per pass", "unstable n", "unstable IDs"], rows))
interrupted = [(k, [r.valid_count() for r in rs]) for k, rs, per, u, sc in results if min(r.valid_count() for r in rs) < 50]
print(f"\nGroups containing an interrupted/partial pass (valid < 50 in some pass): {len(interrupted)}")
for k, v in interrupted:
    print(f"  {k} valid per pass {v}")
clean = [x for x in results if min(r.valid_count() for r in x[1]) >= 50]
print(f"Clean groups (every pass valid >= 50): {len(clean)} of {len(results)}")

print("\n## Reviews unstable in the most configurations (denominator = %d configurations)" % len(results))
print("Pass-count distribution:", dict(sorted(Counter(len(rs) for _, rs, _, _, _ in results).items())))
cnt = Counter()
for k, rs, per, unstable, scores in results:
    for rid in unstable:
        cnt[rid] += 1
top10 = [rid for rid, _ in cnt.most_common(10)]
print(common.md_table(["review", "configurations unstable", "share"], [[rid, c, common.pct(c, len(results))] for rid, c in cnt.most_common(15)]))

hard10 = common.hardest(runs, ref, 10)
inter = set(top10) & set(hard10)
print(f"\nTop-10 unstable: {top10}")
print(f"Top-10 hardest (cohort a): {hard10}")
print(f"Overlap: {len(inter)} ({sorted(inter)}); Jaccard = {len(inter)/len(set(top10)|set(hard10)):.2f}")
never = [rid for rid in IDS if cnt[rid] == 0]
print(f"Reviews never unstable in any configuration: {len(never)}: {never}")

print("\n## Overall: distribution of unstable-review counts across configurations")
dist = Counter(len(u) for _, _, _, u, _ in results)
print(common.md_table(["unstable reviews", "configurations"], [[n, dist[n]] for n in sorted(dist)]))
same_score_diff_answers = [(k, scores, len(u)) for k, rs, per, u, scores in results if len(set(scores)) == 1 and len(u) > 0]
print(f"Configurations with identical all-four in every pass but changed answers: {len(same_score_diff_answers)}")
for k, scores, n in same_score_diff_answers:
    print(f"  {k[0]} {k[1]} {k[2]} {k[3]}: all-four {scores[0]} every pass, {n} reviews changed")

print("\n## Perfectly stable but wrong (0 unstable reviews, all-four < 60)")
rows = []
for k, rs, per, unstable, scores in results:
    if not unstable and scores[0] < 60:
        wrong = [rid for rid in IDS if rs[0].vector(rid) != ref_vec[rid]]
        rows.append([k[0], k[1], k[2], k[3], len(rs), scores[0], len(wrong), ", ".join(wrong) if len(wrong) <= 8 else f"{len(wrong)} reviews"])
rows.sort(key=lambda r: -r[5])
print(common.md_table(["family", "configuration", "effort", "cond", "passes", "all-four", "fixed wrong n", "fixed wrong IDs"], rows))

print("\n## Unstable but right on average (>=5 unstable reviews, mean all-four >= 54)")
rows = []
for k, rs, per, unstable, scores in results:
    if len(unstable) >= 5 and sum(scores) / len(scores) >= 54:
        rows.append([k[0], k[1], k[2], k[3], "/".join(map(str, scores)), f"{sum(scores)/len(scores):.1f}", len(unstable), ", ".join(unstable)])
rows.sort(key=lambda r: -r[6])
print(common.md_table(["family", "configuration", "effort", "cond", "all-four per pass", "mean", "unstable n", "unstable IDs"], rows))

print("\n## Most unstable configurations overall (clean groups only, every pass valid >= 50)")
rows = sorted(clean, key=lambda x: -len(x[3]))[:12]
print(common.md_table(["family", "configuration", "effort", "cond", "series", "passes", "all-four per pass", "unstable n"],
                      [[k[0], k[1], k[2], k[3], k[4], len(rs), "/".join(map(str, s)), len(u)] for k, rs, per, u, s in rows]))

# which fields flip most
print("\n## Field-level flips across all configurations (reviews with >1 distinct label for that field)")
fc = Counter()
for k, rs, per, unstable, scores in results:
    for rid in IDS:
        for f in F:
            labs = set((r.pred(rid) or {}).get(f, "INVALID") for r in rs)
            if len(labs) > 1:
                fc[f] += 1
print(common.md_table(["field", "review-configuration flips"], [[f, fc[f]] for f in F]))
