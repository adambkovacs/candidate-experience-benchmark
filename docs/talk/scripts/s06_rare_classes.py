"""Section 6: rare positive classes, decision vs general. Run: python3 -I s06_rare_classes.py"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common
from collections import Counter, defaultdict
from statistics import median

ref = common.reference()
runs = common.load_all()
IDS, F = common.IDS, common.FIELDS
RARE = [("testimonial_potential", "yes"), ("serious_concern_reported", "yes"), ("sentiment", "mixed")]
INSUF = [(f, "insufficient_information") for f in F]

print("reference positives:", {f"{f}={l}": sum(1 for i in IDS if ref[i][f] == l) for f, l in RARE + INSUF})


def prf(r, f, l):
    pos = [i for i in IDS if ref[i][f] == l]
    tp = fp = 0
    for i in IDS:
        p = r.pred(i)
        if p is None:
            continue
        if p[f] == l:
            if ref[i][f] == l:
                tp += 1
            else:
                fp += 1
    fn = len(pos) - tp  # invalid output on a positive counts as FN
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / len(pos)
    return tp, fp, fn, prec, rec


def fmt(x):
    return "none" if x is None else f"{100*x:.0f}%"


print("\n## Distribution per category (N = run-passes)")
rows = []
for f, l in RARE:
    for cat in ("decision", "general", "rules"):
        rs = [r for r in runs if r.category == cat]
        stats = [prf(r, f, l) for r in rs]
        precs = [s[3] for s in stats if s[3] is not None]
        recs = [s[4] for s in stats]
        rows.append([f"{common.FIELD_SHORT[f]}={l}", cat, len(rs),
                     f"{100*median(recs):.0f}% ({100*min(recs):.0f}-{100*max(recs):.0f})",
                     f"{100*median(precs):.0f}% ({100*min(precs):.0f}-{100*max(precs):.0f})" if precs else "none",
                     sum(1 for s in stats if s[4] == 1.0), sum(1 for s in stats if s[3] == 1.0),
                     sum(1 for s in stats if s[0] + s[1] == 0)])
print(common.md_table(["class", "category", "N runs", "recall median (range)", "precision median (range)", "recall=100%", "precision=100%", "never predicts"], rows))

print("\n## Over-triggers: FP >= 10 on testimonial=yes or serious_concern=yes")
rows = []
for r in runs:
    for f, l in RARE[:2]:
        tp, fp, fn, prec, rec = prf(r, f, l)
        if fp >= 10:
            rows.append([r.feed, r.run_id, r.condition, r.pass_, f"{common.FIELD_SHORT[f]}={l}", tp, fp, fmt(rec), r.all_four(ref)])
rows.sort(key=lambda x: -x[6])
print(common.md_table(["feed", "run", "cond", "pass", "class", "TP", "FP", "recall", "all-four"], rows))
print("over-trigger run-passes:", len(rows), "distinct families:", Counter(r[1].split("-")[0] for r in rows))

print("\n## Under-triggers: recall <= 50% with valid >= 55")
rows = []
for r in runs:
    if r.valid_count() < 55:
        continue
    for f, l in RARE:
        tp, fp, fn, prec, rec = prf(r, f, l)
        if rec <= 0.5:
            rows.append([r.feed, r.run_id, r.condition, r.pass_, f"{common.FIELD_SHORT[f]}={l}", tp, fn, fp, r.all_four(ref)])
rows.sort(key=lambda x: (x[4], x[5]))
print(common.md_table(["feed", "run", "cond", "pass", "class", "TP", "FN", "FP", "all-four"], rows))
print("under-trigger rows:", len(rows), "by class:", Counter(x[4] for x in rows), "by category:",
      Counter(common.classify(x[1], x[1]) for x in rows))

print("\n## insufficient_information hypothesis")
rows = []
for f in F:
    base = sum(1 for i in IDS if ref[i][f] == "insufficient_information")
    for cat in ("decision", "general"):
        rs = [r for r in runs if r.category == cat]
        zero = 0; total_pred = 0; valid = 0; matched = 0
        for r in rs:
            n = 0
            for i in IDS:
                p = r.pred(i)
                if p is None:
                    continue
                valid += 1
                if p[f] == "insufficient_information":
                    n += 1
                    if ref[i][f] == "insufficient_information":
                        matched += 1
            total_pred += n
            if n == 0:
                zero += 1
        rows.append([common.FIELD_SHORT[f], base, cat, len(rs), zero, f"{100*zero/len(rs):.0f}%", total_pred,
                     f"{100*total_pred/valid:.2f}%" if valid else "n/a", f"{100*base/60:.2f}%",
                     f"{matched}/{base*len(rs)}", f"{100*matched/(base*len(rs)):.0f}%"])
print(common.md_table(["field", "ref insuf n", "category", "N runs", "runs with 0 insuf preds", "share", "insuf preds total", "insuf pred rate", "ref base rate", "ref-insuf cells matched", "match rate"], rows))

print("\n## Native seven fresh1/P0 + Jev direct P0 vs data.json original P0 general runs")
focus = [r for r in runs if r.feed == "additional" and r.model in common.NATIVE_SEVEN and r.pass_ == "fresh1" and r.condition == "P0"]
focus += [r for r in runs if r.feed == "data.json" and r.run_id == "typesafe-jev113-v2" and r.condition == "P0"]
gen = [r for r in runs if r.feed == "data.json" and r.condition == "P0" and r.category == "general"]
rows = []
for r in focus:
    cells = [r.model if r.feed == "additional" else "jev-1.13 direct", r.valid_count(), r.all_four(ref)]
    for f, l in RARE:
        tp, fp, fn, prec, rec = prf(r, f, l)
        cells.append(f"{tp}/{tp+fn} rec, {fmt(prec)} prec (FP {fp})")
    rows.append(cells)
print(common.md_table(["run", "valid", "all-four", "testimonial=yes", "serious_concern=yes", "sentiment=mixed"], rows))
print(f"\ngeneral P0 originals (data.json, N={len(gen)}):")
rows = []
for f, l in RARE:
    stats = [prf(r, f, l) for r in gen]
    recs = [s[4] for s in stats]; precs = [s[3] for s in stats if s[3] is not None]
    rows.append([f"{common.FIELD_SHORT[f]}={l}", f"{100*median(recs):.0f}%", sum(1 for s in stats if s[4] == 1.0),
                 f"{100*median(precs):.0f}%", sum(1 for s in stats if s[3] == 1.0), sum(1 for s in stats if s[1] >= 10)])
print(common.md_table(["class", "median recall", "recall=100% runs", "median precision", "precision=100% runs", "FP>=10 runs"], rows))
best = [(r.run_id, r.all_four(ref)) for r in gen if all(prf(r, f, l)[4] == 1.0 for f, l in RARE)]
print("general P0 originals with 100% recall on all three rare classes:", len(best), best)
best = [(r.run_id, r.all_four(ref)) for r in gen if all(prf(r, f, l)[4] == 1.0 and prf(r, f, l)[3] == 1.0 for f, l in RARE)]
print("general P0 originals with 100% recall AND precision on all three:", len(best), best)
