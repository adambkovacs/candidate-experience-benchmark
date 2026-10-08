"""Section 8: confidence / calibration for native decision models. Run: python3 -I s08_confidence.py
Retrospective only: no abstention was executed; provider confidence is uncalibrated."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common
from collections import defaultdict

ref = common.reference()
runs = common.load_all()
conf = common.load_confidence()
F, IDS = common.FIELDS, common.IDS
BINS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 0.99), (0.99, 1.0001)]
MODELS = ["jev", "solar", "tev", "liquid", "clef", "clef-flash", "luna-decisions"]
FIRST = {"jev": "direct/P0"}  # others fresh1/P0


def first_stage(m):
    return FIRST.get(m, "fresh1/P0")


def chosen_prob(rec, f):
    p = rec["prob"].get(f) or {}
    return p.get(rec["prediction"][f])


def bin_of(x):
    for i, (lo, hi) in enumerate(BINS):
        if lo <= x < hi:
            return i
    return len(BINS) - 1


def ece(pairs):
    """pairs = [(score, correct_bool)]; 5-bin weighted ECE."""
    b = defaultdict(list)
    for s, c in pairs:
        b[bin_of(s)].append((s, c))
    n = len(pairs)
    return sum(len(v) / n * abs(sum(s for s, _ in v) / len(v) - sum(c for _, c in v) / len(v)) for v in b.values()) if n else None


by_model = defaultdict(list)
for r in conf:
    by_model[r["model"]].append(r)
print("records per model:", {m: len(by_model[m]) for m in MODELS})
print("stages per model:", {m: sorted({r['stage'] for r in by_model[m]}) for m in MODELS})

print("\n## Calibration bins per model and field, all stages pooled within model (provider confidence)")
rows = []
summary = []
for m in MODELS:
    for f in F:
        pairs = [(r["conf"][f], r["prediction"][f] == ref[r["id"]][f]) for r in by_model[m] if r["conf"][f] is not None]
        cp = [(chosen_prob(r, f), r["prediction"][f] == ref[r["id"]][f]) for r in by_model[m] if chosen_prob(r, f) is not None]
        b = defaultdict(list)
        for s, c in pairs:
            b[bin_of(s)].append((s, c))
        cells = []
        for i in range(len(BINS)):
            v = b.get(i, [])
            cells.append(f"{len(v)}: {100*sum(c for _, c in v)/len(v):.0f}% @{sum(s for s, _ in v)/len(v):.2f}" if v else "0")
        e, ecp = ece(pairs), ece(cp)
        rows.append([m, common.FIELD_SHORT[f], len(pairs)] + cells + [f"{e:.3f}", f"{ecp:.3f}" if ecp is not None else "n/a"])
        summary.append((m, f, len(pairs), e, ecp, sum(c for _, c in pairs) / len(pairs)))
print(common.md_table(["model", "field", "N", "[0,.5)", "[.5,.7)", "[.7,.9)", "[.9,.99)", "[.99,1]", "ECE conf", "ECE chosen-prob"], rows))
print("cell format: n: accuracy @mean confidence")

print("\n## ECE summary (provider confidence) and accuracy per model, all fields pooled")
rows = []
for m in MODELS:
    pairs = [(r["conf"][f], r["prediction"][f] == ref[r["id"]][f]) for r in by_model[m] for f in F if r["conf"][f] is not None]
    cp = [(chosen_prob(r, f), r["prediction"][f] == ref[r["id"]][f]) for r in by_model[m] for f in F if chosen_prob(r, f) is not None]
    mc = sum(s for s, _ in pairs) / len(pairs); acc = sum(c for _, c in pairs) / len(pairs)
    rows.append([m, len(pairs), f"{mc:.3f}", f"{acc:.3f}", f"{mc-acc:+.3f}", f"{ece(pairs):.3f}", f"{ece(cp):.3f}"])
print(common.md_table(["model", "N field answers", "mean conf", "accuracy", "conf - acc", "ECE conf", "ECE chosen-prob"], rows))

print("\n## Provider confidence vs chosen-option probability")
rows = []
for m in MODELS:
    gaps = []
    for r in by_model[m]:
        for f in F:
            cpv = chosen_prob(r, f)
            if cpv is not None and r["conf"][f] is not None:
                gaps.append(cpv - r["conf"][f])
    big = sum(1 for g in gaps if abs(g) > 0.2)
    rows.append([m, len(gaps), f"{sum(gaps)/len(gaps):+.3f}", f"{max(gaps):+.3f}", big, f"{100*big/len(gaps):.1f}%"])
print(common.md_table(["model", "N", "mean (prob - conf)", "max", "|gap|>0.2", "share"], rows))

hard10 = common.hardest(runs, ref, 10)
print("\nhardest 10 (all 1004 run-passes):", hard10)
print("\n## Low-confidence reviews at first P0 vs hard reviews")
rows = []
for m in MODELS:
    st = [r for r in by_model[m] if r["stage"] == first_stage(m)]
    if not st:
        continue
    minc = {r["id"]: min(r["conf"][f] for f in F) for r in st}
    low10 = sorted(minc, key=lambda i: (minc[i], i))[:10]
    ov = sorted(set(low10) & set(hard10))
    rows.append([m, first_stage(m), ", ".join(i[4:] for i in low10), len(ov), ", ".join(i[4:] for i in ov),
                 ", ".join(i[4:] for i in low10 if i in ("DEV-029", "DEV-030")) or "none"])
print(common.md_table(["model", "stage", "10 lowest min-field confidence", "overlap w/ hard10", "overlap ids", "029/030 in low10"], rows))

print("\n## DEV-029 (off-topic soup review) at first P0: confidence / chosen prob per field, rank of min confidence (1 = least confident of 60)")
rows = []
for m in MODELS:
    st = [r for r in by_model[m] if r["stage"] == first_stage(m)]
    rec = next((r for r in st if r["id"] == "DEV-029"), None)
    if not rec:
        continue
    minc = {r["id"]: min(r["conf"][f] for f in F) for r in st}
    rank = sorted(minc, key=lambda i: (minc[i], i)).index("DEV-029") + 1
    cells = [f"{rec['prediction'][f]} {rec['conf'][f]:.2f}/{(chosen_prob(rec, f) or 0):.2f}" for f in F]
    rows.append([m] + cells + [rank, sum(1 for f in F if rec["prediction"][f] == ref["DEV-029"][f])])
print(common.md_table(["model", "sentiment", "follow_up", "serious_concern", "testimonial", "min-conf rank/60", "fields matched"], rows))
print("reference DEV-029:", ref["DEV-029"])

print("\n## Wrong field answers at confidence >= 0.9 and >= 0.99, per model (all stages) and at first P0")
rows = []
for m in MODELS:
    recs = by_model[m]
    stages = sorted({r["stage"] for r in recs})
    w9 = w99 = wrong = 0
    for r in recs:
        for f in F:
            if r["prediction"][f] != ref[r["id"]][f]:
                wrong += 1
                if r["conf"][f] >= 0.9:
                    w9 += 1
                if r["conf"][f] >= 0.99:
                    w99 += 1
    st = [r for r in recs if r["stage"] == first_stage(m)]
    f9 = [(r["id"][4:], common.FIELD_SHORT[f], f"{r['conf'][f]:.2f}") for r in st for f in F if r["prediction"][f] != ref[r["id"]][f] and r["conf"][f] >= 0.9]
    rows.append([m, len(stages), len(recs) * 4, wrong, w9, w99, "; ".join("-".join(x) for x in f9) or "none"])
print(common.md_table(["model", "stages", "field answers", "wrong", "wrong @>=0.9", "wrong @>=0.99", "first-P0 wrong @>=0.9 (id-field-conf)"], rows))

print("\n## Smallest retrospective threshold removing every wrong answer per field at first P0, and coverage it leaves")
rows = []
for m in MODELS:
    st = [r for r in by_model[m] if r["stage"] == first_stage(m)]
    cells = []
    for f in F:
        wrong = [r["conf"][f] for r in st if r["prediction"][f] != ref[r["id"]][f]]
        if not wrong:
            cells.append("0 wrong; 60/60")
            continue
        t = max(wrong)
        kept = sum(1 for r in st if r["conf"][f] > t)
        cells.append(f">{t:.2f}: keeps {kept}/60 ({len(wrong)} wrong)")
    rows.append([m] + cells)
print(common.md_table(["model"] + [common.FIELD_SHORT[f] for f in F], rows))
