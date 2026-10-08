"""Section 2: confusion structure per field, overall and decision vs general. Run: python3 -I docs/talk/scripts/s02_confusion.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from collections import Counter, defaultdict

ref = common.reference()
runs = common.load_all()
F = common.FIELDS
IDS = common.IDS
L = common.LABELS

base = {f: Counter(ref[rid][f] for rid in IDS) for f in F}


def confusion(subset):
    """{field: {ref_label: Counter(pred_label)}} over valid predictions."""
    m = {f: defaultdict(Counter) for f in F}
    n = 0
    for r in subset:
        for rid in IDS:
            p = r.pred(rid)
            if p is None:
                continue
            n += 1
            for f in F:
                m[f][ref[rid][f]][p[f]] += 1
    return m, n


def print_matrix(name, m, n, f):
    labs = L[f]
    print(f"\n### {name} / {f}: N valid predictions={n}; rows = reference, cols = prediction (count, row %)")
    rows = []
    for a in labs:
        tot = sum(m[f][a].values())
        rows.append([f"{a} (ref n={base[f][a]})", tot] + [f"{m[f][a][b]} ({common.pct(m[f][a][b], tot)})" for b in labs])
    print(common.md_table(["ref \\ pred", "row N"] + labs, rows))


def pairs(m, f):
    out = []
    for a in L[f]:
        tot = sum(m[f][a].values())
        for b in L[f]:
            if a != b and m[f][a][b]:
                out.append((m[f][a][b], a, b, tot))
    return sorted(out, reverse=True)


subsets = {
    "all": runs,
    "decision": [r for r in runs if r.category == "decision"],
    "general": [r for r in runs if r.category == "general"],
}
M = {}
for name, sub in subsets.items():
    M[name] = confusion(sub)
    print(f"\n## {name}: {len(sub)} run-passes, {M[name][1]} valid predictions")
    for f in F:
        print_matrix(name, M[name][0], M[name][1], f)

print("\n## Top confused pairs per field (all run-passes): count, rate per reference instance")
for f in F:
    m, n = M["all"]
    rows = [[f"{a} -> {b}", c, tot, common.pct(c, tot)] for c, a, b, tot in pairs(m, f)[:6]]
    print(f"\n{f}")
    print(common.md_table(["ref -> pred", "count", "ref row N", "rate"], rows))

print("\n## Asymmetry (all run-passes): a->b vs b->a as rate per reference instance")
for f in F:
    m, n = M["all"]
    seen = set()
    rows = []
    for a in L[f]:
        for b in L[f]:
            if a >= b or (a, b) in seen:
                continue
            seen.add((a, b))
            ta, tb = sum(m[f][a].values()), sum(m[f][b].values())
            ab, ba = m[f][a][b], m[f][b][a]
            if ab + ba < 20:
                continue
            rows.append([f"{a}<->{b}", f"{ab}/{ta} ({common.pct(ab, ta)})", f"{ba}/{tb} ({common.pct(ba, tb)})"])
    print(f"\n{f}")
    print(common.md_table(["pair", "a->b", "b->a"], rows))

print("\n## Decision vs general: pairs whose confusion rate differs most (rate per reference instance; min 10 combined errors)")
rows = []
for f in F:
    md, _ = M["decision"]
    mg, _ = M["general"]
    for a in L[f]:
        td, tg = sum(md[f][a].values()), sum(mg[f][a].values())
        for b in L[f]:
            if a == b:
                continue
            cd, cg = md[f][a][b], mg[f][a][b]
            if cd + cg < 10 or not td or not tg:
                continue
            rd, rg = cd / td, cg / tg
            rows.append((abs(rd - rg), f, f"{a}->{b}", f"{cd}/{td} ({100*rd:.1f}%)", f"{cg}/{tg} ({100*rg:.1f}%)", f"{100*(rd-rg):+.1f} pts"))
rows.sort(reverse=True)
print(common.md_table(["field", "ref->pred", "decision", "general", "diff (decision - general)"], [r[1:] for r in rows[:14]]))

print("\n## insufficient_information prediction share per field vs reference base rate")
rows = []
for f in F:
    rr = []
    for name in ("decision", "general", "all"):
        m, n = M[name]
        tot = sum(sum(c.values()) for c in m[f].values())
        ins = sum(c["insufficient_information"] for c in m[f].values())
        rr.append(f"{ins}/{tot} ({common.pct(ins, tot)})")
    rows.append([f, f"{base[f]['insufficient_information']}/60 ({common.pct(base[f]['insufficient_information'], 60)})"] + rr)
print(common.md_table(["field", "reference base", "decision preds", "general preds", "all preds"], rows))

# per-run: runs that never predict insufficient_information in any field
print("\n## Runs with zero insufficient_information predictions (any field), by category")
for name in ("decision", "general"):
    sub = subsets[name]
    zero = 0
    for r in sub:
        if not any(p[f] == "insufficient_information" for rid in IDS if (p := r.pred(rid)) for f in F):
            zero += 1
    print(f"{name}: {zero}/{len(sub)} run-passes never predict insufficient_information")
