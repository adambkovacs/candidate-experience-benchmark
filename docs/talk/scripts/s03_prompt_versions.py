"""Section 3: prompt versions P0 -> P1 -> P2 on matched triplets.

A triplet = one configuration-pass with P0, P1 and P2 all saved
(same feed, same experiment/source-stage prefix, same pass identity).
Differences are descriptions of these saved runs, not causal prompt effects.
Run: python3 -I docs/talk/scripts/s03_prompt_versions.py
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

F = common.FIELDS
ref = common.reference()
runs = common.load_all()


def tkey(r):
    if r.feed == "data.json":
        return ("data.json", r.meta.get("experimentId"), "original")
    parts = (r.meta.get("sourceStage") or r.label).split("/")
    return (r.feed, "/".join(parts[:-2]), parts[-2])


groups = defaultdict(dict)
for r in runs:
    groups[tkey(r)][r.condition] = r
trip = {k: v for k, v in groups.items() if set(v) == {"P0", "P1", "P2"}}
print(f"# Triplets: {len(trip)} of {len(groups)} configuration-passes have P0+P1+P2 saved")
print(Counter(k[0] for k in trip))

# cross-check against data.json promptComparisons
pc = common.load_json("public-site/data.json")["promptComparisons"]
pc_ids = {p["id"] for p in pc}
mine = {k[1] for k in trip if k[0] == "data.json"}
print(f"data.json promptComparisons: {len(pc)} listed, {len(pc_ids & mine)} reproduced by my pairing, "
      f"{len(mine - pc_ids)} extra data.json triplets not in promptComparisons (local/native conditions): "
      f"{sorted(mine - pc_ids)}")


def af(r):
    return r.all_four(ref)


def fs(r, f):
    return r.field_score(ref, f)


def sgn(d):
    return "better" if d > 0 else ("worse" if d < 0 else "same")


# ---- per family deltas ----
fam_rows = defaultdict(lambda: {"n": 0, "P0_P1": Counter(), "P1_P2": Counter(), "P0_P2": Counter(),
                                "net01": 0, "net12": 0, "net02": 0, "field02": Counter(), "cat": None})
overall = {"P0_P1": Counter(), "P1_P2": Counter(), "P0_P2": Counter(), "net01": 0, "net12": 0, "net02": 0,
           "field01": Counter(), "field12": Counter(), "field02": Counter()}
consistent = {}
for k, v in trip.items():
    r0, r1, r2 = v["P0"], v["P1"], v["P2"]
    fam = r0.family
    d01, d12, d02 = af(r1) - af(r0), af(r2) - af(r1), af(r2) - af(r0)
    fr = fam_rows[fam]
    fr["n"] += 1
    fr["cat"] = r0.category
    fr["P0_P1"][sgn(d01)] += 1
    fr["P1_P2"][sgn(d12)] += 1
    fr["P0_P2"][sgn(d02)] += 1
    fr["net01"] += d01
    fr["net12"] += d12
    fr["net02"] += d02
    for f in F:
        fr["field02"][f] += fs(r2, f) - fs(r0, f)
        overall["field01"][f] += fs(r1, f) - fs(r0, f)
        overall["field12"][f] += fs(r2, f) - fs(r1, f)
        overall["field02"][f] += fs(r2, f) - fs(r0, f)
    overall["P0_P1"][sgn(d01)] += 1
    overall["P1_P2"][sgn(d12)] += 1
    overall["P0_P2"][sgn(d02)] += 1
    overall["net01"] += d01
    overall["net12"] += d12
    overall["net02"] += d02
    consistent.setdefault(fam, []).append(d02)

print("\n## All-four deltas over triplets (N = triplets)")
rows = []
for step in ("P0_P1", "P1_P2", "P0_P2"):
    c = overall[step]
    rows.append([step.replace("_", "->"), len(trip), c["better"], c["same"], c["worse"],
                 overall["net" + step[1] + step[-1]]])
print(common.md_table(["Step", "N triplets", "better", "same", "worse", "net all-four"], rows))
print("\n## Sum of field-score deltas over all triplets (which field moves)")
rows = [[step, *[overall["field" + step][f] for f in F]] for step in ("01", "12", "02")]
print(common.md_table(["Step (P)", *[common.FIELD_SHORT[f] for f in F]], rows))

print("\n## Per family (P0->P2 unless stated)")
rows = []
for fam, fr in sorted(fam_rows.items(), key=lambda x: (-x[1]["n"], x[0])):
    c01, c12, c02 = fr["P0_P1"], fr["P1_P2"], fr["P0_P2"]
    rows.append([fam, fr["cat"], fr["n"],
                 f"{c01['better']}/{c01['same']}/{c01['worse']} ({fr['net01']:+d})",
                 f"{c12['better']}/{c12['same']}/{c12['worse']} ({fr['net12']:+d})",
                 f"{c02['better']}/{c02['same']}/{c02['worse']} ({fr['net02']:+d})",
                 " ".join(f"{common.FIELD_SHORT[f]}{fr['field02'][f]:+d}" for f in F)])
print(common.md_table(["Family", "cat", "N", "P0->P1 b/s/w (net)", "P1->P2 b/s/w (net)", "P0->P2 b/s/w (net)", "field delta P0->P2"], rows))

gain = [f for f, ds in consistent.items() if len(ds) >= 2 and all(d > 0 for d in ds)]
loss = [f for f, ds in consistent.items() if len(ds) >= 2 and all(d < 0 for d in ds)]
flat = [f for f, ds in consistent.items() if len(ds) >= 2 and all(d == 0 for d in ds)]
print(f"\nConsistent P0->P2 gain in every triplet (>=2 triplets): {gain}")
print(f"Consistent P0->P2 loss in every triplet (>=2 triplets): {loss}")
print(f"Flat P0->P2 in every triplet (>=2 triplets): {flat}")

# ---- review flips P0 -> P2 ----
flip = defaultdict(Counter)  # id -> {"w2r": n, "r2w": n}
for k, v in trip.items():
    r0, r2 = v["P0"], v["P2"]
    for rid in common.IDS:
        p0, p2 = r0.pred(rid), r2.pred(rid)
        ok0 = p0 is not None and all(p0[f] == ref[rid][f] for f in F)
        ok2 = p2 is not None and all(p2[f] == ref[rid][f] for f in F)
        if ok0 != ok2:
            flip[rid]["w2r" if ok2 else "r2w"] += 1
print(f"\n## Reviews whose all-four status flips between P0 and P2 (N = {len(trip)} triplets)")
rows = []
for rid in sorted(flip, key=lambda i: -(flip[i]["w2r"] + flip[i]["r2w"]))[:12]:
    w, r_ = flip[rid]["w2r"], flip[rid]["r2w"]
    share = max(w, r_) / (w + r_)
    rows.append([rid, w + r_, w, r_, "shared " + ("wrong->right" if w >= r_ else "right->wrong") if share >= 0.75 else "idiosyncratic",
                 f"{100*share:.0f}%", " / ".join(ref[rid][f] for f in F)])
print(common.md_table(["Review", "flips", "wrong->right", "right->wrong", "direction", "majority share", "reference"], rows))
tot_w = sum(c["w2r"] for c in flip.values())
tot_r = sum(c["r2w"] for c in flip.values())
print(f"Total flips P0->P2: {tot_w + tot_r} (wrong->right {tot_w}, right->wrong {tot_r}) across {len(flip)} distinct reviews")

# ---- label distribution shift P0 vs P2 ----
refc = {f: Counter(ref[i][f] for i in common.IDS) for f in F}


def dist(cat=None):
    """Label counts at P0 and P2 over positions valid under BOTH conditions of the same triplet."""
    c0 = {f: Counter() for f in F}
    c2 = {f: Counter() for f in F}
    refp = {f: Counter() for f in F}
    inv0 = inv2 = paired = 0
    n = 0
    for v in trip.values():
        r0, r2 = v["P0"], v["P2"]
        if cat and r0.category != cat:
            continue
        n += 1
        for rid in common.IDS:
            p0, p2 = r0.pred(rid), r2.pred(rid)
            inv0 += p0 is None
            inv2 += p2 is None
            if p0 is None or p2 is None:
                continue
            paired += 1
            for f in F:
                c0[f][p0[f]] += 1
                c2[f][p2[f]] += 1
                refp[f][ref[rid][f]] += 1
    return c0, c2, refp, inv0, inv2, n, paired


for cat in (None, "general", "decision"):
    c0, c2, refp, inv0, inv2, n0, paired = dist(cat)
    print(f"\n## Label counts P0 vs P2 on paired-valid positions, {'all' if cat is None else cat} triplets "
          f"(N={n0} triplets; paired-valid positions={paired} of {60*n0}; invalid positions P0={inv0}, P2={inv2})")
    rows = []
    for f in F:
        for lab in common.LABELS[f]:
            a, b = c0[f][lab], c2[f][lab]
            rows.append([common.FIELD_SHORT[f], lab, refc[f][lab], refp[f][lab], a, b, b - a, f"{(b - a) / n0:+.2f}"])
    print(common.md_table(["field", "label", "ref /60", "ref on paired positions", "P0 count", "P2 count", "delta", "delta per triplet"], rows))

# ---- identical vectors ----
def vecs(r):
    return tuple(r.vector(i) for i in common.IDS)


same12 = [k for k, v in trip.items() if vecs(v["P1"]) == vecs(v["P2"])]
same012 = [k for k in same12 if vecs(trip[k]["P0"]) == vecs(trip[k]["P1"])]
same01 = [k for k, v in trip.items() if vecs(v["P0"]) == vecs(v["P1"])]
print(f"\n## Identical 60-vector sets: P1==P2 in {len(same12)} triplets; P0==P1 in {len(same01)}; P0==P1==P2 in {len(same012)}")
print("P1==P2:", Counter(trip[k]["P0"].family for k in same12))
print("P0==P1==P2:", Counter(trip[k]["P0"].family for k in same012))
print("P0==P1==P2 ids:", sorted(f"{k[1]}/{k[2]}" for k in same012))
