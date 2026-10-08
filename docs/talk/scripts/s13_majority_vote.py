"""Majority-of-3 and self-unanimity on saved repeat passes. No inference.
Run: python3 -I docs/talk/scripts/s13_majority_vote.py
Groups = configuration-conditions with >=3 passes (same key as s07). First three passes by pass name.
Majority: per field, a label wins with >=2 of 3 votes; invalid output is a vote that never matches.
Self-unanimity rule: accept a review only when all three passes return the identical valid 4-field vector."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from collections import Counter, defaultdict

ref, F, IDS = common.reference(), common.FIELDS, common.IDS


def config_key(r):  # copied from s07_repeatability.py
    base = (r.meta.get("experimentId") or r.run_id) if r.feed == "data.json" else r.meta.get("sourceStage", "").split("/")[0]
    pf = "repeat" if r.pass_ in ("original", "repeat2", "repeat3") else ("pass" if r.pass_.startswith("pass") else "fresh")
    return (r.family, base, r.effort, r.condition, pf)


groups = defaultdict(list)
for r in common.load_all():
    groups[config_key(r)].append(r)
triples = {k: sorted(v, key=lambda r: r.pass_)[:3] for k, v in groups.items() if len(v) >= 3}


def maj3(rs):
    hit = 0
    for rid in IDS:
        ok = True
        for f in F:
            votes = Counter((p[f] if (p := r.pred(rid)) else "INVALID") for r in rs)
            lab, n = votes.most_common(1)[0]
            ok &= n >= 2 and lab == ref[rid][f]
        hit += ok
    return hit


def unanimous(rs):
    acc = err = 0
    for rid in IDS:
        vs = {r.vector(rid) for r in rs}
        if len(vs) == 1 and None not in vs:
            acc += 1
            err += vs.pop() != tuple(ref[rid][f] for f in F)
    return acc, err


stats = defaultdict(lambda: Counter())
gain = defaultdict(list)
for k, rs in triples.items():
    cat = rs[0].category
    s = [r.all_four(ref) for r in rs]
    m = maj3(rs)
    mean = sum(s) / 3
    st = stats[cat]
    st["groups"] += 1
    st["maj>mean"] += m > mean
    st["maj=mean"] += m == mean
    st["maj<mean"] += m < mean
    st["maj>best"] += m > max(s)
    st["maj<worst"] += m < min(s)
    st["no_flip"] += len({tuple(r.vector(i) for i in IDS) for r in rs}) == 1
    acc, err = unanimous(rs)
    st["unan_acc"] += acc
    st["unan_err"] += err
    st["unan_zero_err_groups"] += err == 0
    gain[cat].append(m - mean)

print(f"groups with >=3 passes: {len(triples)}")
rows = []
for cat in sorted(stats):
    st, g = stats[cat], sorted(gain[cat])
    n = st["groups"]
    rows.append([cat, n, st["no_flip"], st["maj>mean"], st["maj=mean"], st["maj<mean"], st["maj>best"], st["maj<worst"],
                 f"{sum(g)/n:+.2f}", f"{g[0]:+.1f} to {g[-1]:+.1f}",
                 f"{st['unan_acc']}/{60*n}", st["unan_err"], st["unan_zero_err_groups"]])
print(common.md_table(["category", "groups", "no answer changed", "maj3 > mean pass", "maj3 = mean", "maj3 < mean",
                       "maj3 > best pass", "maj3 < worst pass", "mean gain (reviews)", "gain range",
                       "unanimous accepted", "unanimous accepted errors", "groups unanimous 0 errors"], rows))

# Clean (60 valid in every pass) and strong (mean all-four >= 54): does voting add judgment, not just repair?
print("\n## Clean and strong groups only (every pass 60 valid, mean all-four >= 54)")
rows, err_by_review = [], Counter()
for cat in ("decision", "general"):
    c, g = Counter(), []
    for k, rs in triples.items():
        s = [r.all_four(ref) for r in rs]
        if rs[0].category != cat or any(r.valid_count() < 60 for r in rs) or sum(s) / 3 < 54:
            continue
        mj, mean = maj3(rs), sum(s) / 3
        acc, err = unanimous(rs)
        c["n"] += 1; c["up"] += mj > mean; c["same"] += mj == mean; c["down"] += mj < mean; c["best"] += mj > max(s)
        c["acc"] += acc; c["err"] += err; c["zero"] += err == 0
        c["noflip"] += len({tuple(r.vector(i) for i in IDS) for r in rs}) == 1
        g.append(mj - mean)
        if cat == "general":
            for rid in IDS:
                vs = {r.vector(rid) for r in rs}
                if len(vs) == 1 and None not in vs and vs.pop() != tuple(ref[rid][f] for f in F):
                    err_by_review[rid] += 1
    rows.append([cat, c["n"], c["noflip"], c["up"], c["same"], c["down"], c["best"], f"{sum(g)/len(g):+.2f}", f"{min(g):+.1f} to {max(g):+.1f}",
                 f"{c['acc']}/{60*c['n']}", c["err"], c["zero"]])
print(common.md_table(["category", "groups", "no answer changed", "maj3 > mean", "maj3 = mean", "maj3 < mean", "maj3 > best pass", "mean gain", "range",
                       "unanimous accepted", "accepted errors", "groups 0 errors"], rows))
print("strong general, unanimous accepted errors by review:", err_by_review.most_common(8))

if __name__ == "__main__":
    # self-check: a group whose three passes are identical must have maj3 == single-pass score
    for k, rs in triples.items():
        if len({tuple(r.vector(i) for i in IDS) for r in rs}) == 1:
            assert maj3(rs) == rs[0].all_four(ref) or any(r.valid_count() < 60 for r in rs), k
    print("self-check ok")
