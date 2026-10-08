"""Section 9: model-specific quirks computed over all 1,004 run-passes.
Run: python3 -I docs/talk/scripts/s09_quirks.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

F = common.FIELDS
ref = common.reference()
runs = common.load_all()
text = common.inputs()
IDS = common.IDS


def name(r):
    return f"{r.feed}:{r.run_id}" if r.feed == "data.json" else f"{r.feed}:{r.label}"


def vecs(r):
    return tuple(r.vector(i) for i in IDS)


# 1. one label on >= 55 of 60 reviews
print("## Q1 runs predicting one label for a field on >=55/60 reviews (N=1004 run-passes)")
rows = []
for r in runs:
    for f in F:
        c = Counter(p[f] for i in IDS if (p := r.pred(i)) is not None)
        if c and c.most_common(1)[0][1] >= 55:
            lab, n = c.most_common(1)[0]
            refn = sum(1 for i in IDS if ref[i][f] == lab)
            rows.append([name(r), r.condition, common.FIELD_SHORT[f], lab, n, r.valid_count(), r.field_score(ref, f), refn, r.all_four(ref)])
rows.sort(key=lambda x: (x[2], x[3], -x[4]))
print(common.md_table(["run", "cond", "field", "label", "count", "valid", "field score", "ref has label", "all-four"], rows))
print("count by (field,label):", Counter((x[2], x[3]) for x in rows))
print("count of such rows where label is the majority reference label (no/negative/yes-followup):",
      sum(1 for x in rows if x[7] >= 24))

# 2. byte-identical passes within a configuration
def cfg(r):
    if r.feed == "data.json":
        return ("data.json", r.meta.get("experimentId"))
    parts = (r.meta.get("sourceStage") or r.label).split("/")
    return (r.feed, "/".join(parts[:-2]))


by_cfg_cond = defaultdict(list)
for r in runs:
    by_cfg_cond[(cfg(r), r.condition)].append(r)
print("\n## Q2 identical 60-vector sets across passes of the same configuration+condition")
ident = Counter()
tot = Counter()
examples = []
for (c, cond), rs in by_cfg_cond.items():
    if len(rs) < 2:
        continue
    tot[rs[0].family] += 1
    vs = {vecs(r) for r in rs}
    if len(vs) == 1:
        ident[rs[0].family] += 1
        examples.append((rs[0].family, c[1], cond, len(rs), rs[0].all_four(ref)))
rows = [[fam, ident[fam], tot[fam]] for fam in sorted(tot, key=lambda x: (-ident[x], x))]
print(common.md_table(["family", "config+condition with all passes identical", "config+condition with >=2 passes"], rows))
print("examples (family, config, cond, passes, all-four):", sorted(examples)[:40])
print("identical with all-four < 54:", sorted(e for e in examples if e[4] < 54))

# 3. thinking/effort off vs on at same size
print("\n## Q3 thinking-off vs thinking-on (same model, same condition, same pass)")
pairs = []
by_key = defaultdict(dict)
for r in runs:
    base = re.sub(r"-(on|off|low|medium|high|xhigh|max)(?=$|/|-|_)", "-X", cfg(r)[1] or "")
    by_key[(r.feed, base, r.pass_, r.condition)][r.effort] = r
rows = []
for (feed, base, p, cond), d in sorted(by_key.items()):
    if "off" in d and len(d) > 1:
        off = d["off"]
        for e, on in d.items():
            if e == "off":
                continue
            rows.append([base, p, cond, e, off.all_four(ref), on.all_four(ref), off.all_four(ref) - on.all_four(ref),
                         off.valid_count(), on.valid_count(),
                         " ".join(f"{common.FIELD_SHORT[f]}{off.field_score(ref, f) - on.field_score(ref, f):+d}" for f in F)])
print(common.md_table(["config", "pass", "cond", "on-effort", "off all-four", "on all-four", "off-on", "valid off", "valid on", "field off-on"], rows))
agg = Counter()
for x in rows:
    agg[(x[0], "off wins" if x[6] > 0 else ("tie" if x[6] == 0 else "on wins"))] += 1
print("per config tally:", dict(agg))

# 4. failure clustering by review
print("\n## Q4 non-ok case status per review (N=1004 run-passes)")
fail = Counter()
kind = defaultdict(Counter)
for r in runs:
    for i in IDS:
        s = r.cases.get(i, {}).get("status", "missing")
        if s not in ("ok", "valid"):
            fail[i] += 1
            kind[i][s] += 1
ln = {i: len(text[i]) for i in IDS}
rank_len = {i: k for k, i in enumerate(sorted(IDS, key=lambda x: -ln[x]), 1)}
rows = [[i, fail[i], dict(kind[i]), ln[i], rank_len[i]] for i in sorted(IDS, key=lambda x: -fail[x])[:12]]
print(common.md_table(["review", "non-ok runs", "kinds", "chars", "length rank (1=longest)"], rows))
# Spearman between failure count and length
def spearman(xs, ys):
    def rk(v):
        order = sorted(range(len(v)), key=lambda k: v[k])
        rr = [0] * len(v)
        k = 0
        while k < len(v):
            j = k
            while j + 1 < len(v) and v[order[j + 1]] == v[order[k]]:
                j += 1
            for m in range(k, j + 1):
                rr[order[m]] = (k + j) / 2 + 1
            k = j + 1
        return rr
    rx, ry = rk(xs), rk(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0
print(f"Spearman(failure count, text length) over 60 reviews = {spearman([fail[i] for i in IDS], [ln[i] for i in IDS]):.3f}")
print(f"total non-ok positions {sum(fail.values())}; min/max per review {min(fail[i] for i in IDS)}/{max(fail[i] for i in IDS)}; "
      f"status kinds overall {Counter(s for c in kind.values() for s, n in c.items() for _ in range(n))}")

# 5. tokens: reasoning while effort off/low; output ratios; typed heads
print("\n## Q5 token signals")
rows = []
for r in runs:
    t = r.tokens or {}
    if t.get("reasoning") and r.effort in ("off", "low", "na"):
        rows.append([name(r), r.condition, r.effort, t.get("input"), t.get("output"), t.get("reasoning")])
print("reasoning tokens > 0 while effort off/low/na:", len(rows))
print(common.md_table(["run", "cond", "effort", "input", "output", "reasoning"], sorted(rows, key=lambda x: -x[5])[:15]))
fam_eff = defaultdict(list)
for r in runs:
    t = r.tokens or {}
    if t.get("output") and r.condition == "P0":
        fam_eff[(r.family, r.effort)].append(t["output"])
rows = []
for fam in sorted({k[0] for k in fam_eff}):
    effs = {e: sum(v) / len(v) for (f_, e), v in fam_eff.items() if f_ == fam}
    if len(effs) > 1:
        lo = min(effs.values())
        rows.append([fam, " ".join(f"{e}:{int(v)}" for e, v in sorted(effs.items(), key=lambda x: x[1])), f"{max(effs.values()) / lo:.1f}x"])
print(common.md_table(["family", "mean P0 output tokens per effort (runs with tokens)", "max/min"], rows))
proj = common.load_json("results/clef-openrouter-v1/findings-v1/public-projection.json")
zero = Counter()
for st in proj["stages"]:
    zero[st["model_key"]] += sum(1 for rec in st["records"] if rec.get("output_tokens") == 0)
print("Clef/Flash/Luna records with output_tokens == 0 (of 60 x 9 stages):", dict(zero))

# 6. batch10 vs single
print("\n## Q6 batch-of-10 vs single-review runs, same model + effort, P0")
def norm(r):
    e = cfg(r)[1] or ""
    b = "batch10" in e
    base = re.sub(r"-phase2-batch10-p0|-batch10|-first-pass|-with-retry|-recovery", "", e)
    return base, b
bk = defaultdict(lambda: defaultdict(list))
for r in runs:
    if r.condition != "P0" or r.family not in ("opus-5", "sonnet-5", "fable-5.1", "opus-5.5", "haiku-4.5", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra", "gpt-6-luna", "gpt-6-sol"):
        continue
    base, b = norm(r)
    bk[base]["batch10" if b else "single"].append(r)
rows = []
for base, d in sorted(bk.items()):
    if "batch10" in d and "single" in d:
        s, b = d["single"], d["batch10"]
        miss_s = {i for r in s for i in IDS if not (p := r.pred(i)) or any(p[f] != ref[i][f] for f in F)}
        miss_b = {i for r in b for i in IDS if not (p := r.pred(i)) or any(p[f] != ref[i][f] for f in F)}
        rows.append([base, len(s), [r.all_four(ref) for r in s], len(b), [r.all_four(ref) for r in b],
                     sorted(miss_s & miss_b), sorted(miss_s - miss_b), sorted(miss_b - miss_s)])
print(common.md_table(["model-effort", "single runs", "single all-four", "batch10 runs", "batch10 all-four", "missed in both", "single only", "batch10 only"], rows))
# invalid blocks of 10
print("\nInvalid-output runs where every invalid position falls in whole blocks of 10 consecutive IDs:")
blk = []
for r in runs:
    inv = [i for i in IDS if r.pred(i) is None]
    if not inv or len(inv) == 60:
        continue
    blocks = {(int(i[4:]) - 1) // 10 for i in inv}
    if len(inv) % 10 == 0 and all(sum(1 for i in inv if (int(i[4:]) - 1) // 10 == b) == 10 for b in blocks):
        blk.append((name(r), r.condition, len(inv), sorted(b + 1 for b in blocks)))
print(len(blk), blk)

# 7. other oddities: identical vectors across different models; vocab violations
print("\n## Q7 identical full 60-vector sets across DIFFERENT models")
seen = defaultdict(list)
for r in runs:
    if r.valid_count() == 60:
        seen[vecs(r)].append(r)
cross = [(len(rs), sorted({r.model for r in rs}), rs[0].all_four(ref)) for rs in seen.values() if len({r.model for r in rs}) > 1]
print(sorted(cross, key=lambda x: -x[0]))
viol = Counter()
for r in runs:
    for i in IDS:
        c = r.cases.get(i, {})
        p = c.get("prediction")
        if c.get("status") in ("ok", "valid") and p:
            for f in F:
                if p.get(f) not in common.LABELS[f]:
                    viol[(r.family, f, str(p.get(f)))] += 1
print("label vocabulary violations in ok/valid predictions:", dict(viol))

# 7b. what the big shared vector sets miss; concentration of answer sets among strong runs
print("\n## Q7b misses of the largest cross-model identical vector sets (60/60-valid runs)")
big = sorted(((rs, len(rs)) for rs in seen.values() if len({r.model for r in rs}) > 1), key=lambda x: -x[1])[:6]
for rs, n in big:
    r = rs[0]
    miss = [i for i in IDS if any(r.pred(i)[f] != ref[i][f] for f in F)]
    fams = Counter(x.family for x in rs)
    print(f"- {n} run-passes, all-four {r.all_four(ref)}, miss {miss}, families {dict(fams)}, conditions {dict(Counter(x.condition for x in rs))}")
strong = [r for r in runs if r.valid_count() == 60 and r.all_four(ref) >= 57]
sets = Counter(vecs(r) for r in strong)
print(f"runs with 60 valid and all-four>=57: {len(strong)}; distinct full 60-vector answer sets among them: {len(sets)}; "
      f"top-3 set sizes {[n for _, n in sets.most_common(3)]}; run-passes covered by top-3 sets: {sum(n for _, n in sets.most_common(3))}")
wrong_sets = Counter()
for r in strong:
    wrong_sets[tuple(i for i in IDS if any(r.pred(i)[f] != ref[i][f] for f in F))] += 1
print("most common miss-sets among those runs:", wrong_sets.most_common(8))
tally = Counter()
for x in rows:
    pass
# batch tally recomputed from the Q6 pairs
for base, d in sorted(bk.items()):
    if "batch10" in d and "single" in d:
        s = sum(r.all_four(ref) for r in d["single"]) / len(d["single"])
        b = sum(r.all_four(ref) for r in d["batch10"]) / len(d["batch10"])
        tally["single higher" if s > b else ("batch10 higher" if b > s else "tie")] += 1
print("Q6 tally over model-effort pairs (mean all-four):", dict(tally))
print("DEV-010 text:", text["DEV-010"], "| ref:", ref["DEV-010"])
