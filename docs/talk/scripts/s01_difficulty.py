"""Section 1: review difficulty ranking across cohorts. Run: python3 -I docs/talk/scripts/s01_difficulty.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from collections import Counter

ref = common.reference()
text = common.inputs()
rat = common.rationales()
runs = common.load_all()
F = common.FIELDS
IDS = common.IDS

cohorts = {
    "a_all": runs,
    "b_data_p0": [r for r in runs if r.feed == "data.json" and r.condition == "P0"],
    "c_native7": [r for r in runs if r.feed == "additional" and r.model in common.NATIVE_SEVEN and r.pass_ == "fresh1" and r.condition == "P0"],
    "d_decision": [r for r in runs if r.category == "decision"],
    "e_general": [r for r in runs if r.category == "general"],
}
diff = {k: common.difficulty(v, ref) for k, v in cohorts.items()}
for k, v in cohorts.items():
    print(f"cohort {k}: N={len(v)} run-passes")

# Full table cohort (a)
N = len(cohorts["a_all"])
d = diff["a_all"]
order = sorted(IDS, key=lambda i: (d[i]["all_four"], i))
rank = {rid: i + 1 for i, rid in enumerate(order)}
print("\n## Cohort (a) all run-passes, N=%d, fixed denominator; share = matches / N" % N)
rows = []
for rid in IDS:
    x = d[rid]
    rows.append([rid, rank[rid], x["valid"], x["all_four"], common.pct(x["all_four"], N)] +
                [common.pct(x[f], N) for f in F] + ["/".join(ref[rid][f][:4] for f in F)])
print(common.md_table(["Review", "Hard rank", "Valid", "All-four", "All-four %", "sent %", "follow %", "concern %", "testi %", "Reference (s/f/c/t)"], rows))

# Top 10 hardest per cohort side by side
print("\n## Top-10 hardest per cohort (all-four share, fixed denominator)")
tops = {k: sorted(IDS, key=lambda i: (diff[k][i]["all_four"], i))[:10] for k in cohorts}
rows = []
for i in range(10):
    row = [i + 1]
    for k in cohorts:
        rid = tops[k][i]
        row.append(f"{rid} {diff[k][rid]['all_four']}/{len(cohorts[k])}")
    rows.append(row)
print(common.md_table(["#"] + [f"{k} (N={len(cohorts[k])})" for k in cohorts], rows))

# Universally easy
easy = [rid for rid in IDS if d[rid]["valid"] and d[rid]["all_four"] / d[rid]["valid"] >= 0.99 and diff["c_native7"][rid]["all_four"] == 7]
print("\n## Universally easy (>=99%% of valid outputs in (a) AND 7/7 native): n=%d" % len(easy))
print(", ".join(easy))
near = [rid for rid in IDS if d[rid]["valid"] and d[rid]["all_four"] / d[rid]["valid"] >= 0.95 and diff["c_native7"][rid]["all_four"] == 7]
print("At >=95%% valid and 7/7 native: n=%d: %s" % (len(near), ", ".join(near)))
# ponytail: cohort (a) contains 0/60 configurations, so define "competent" = run-pass with all-four >= 40 and recompute
comp = [r for r in runs if r.all_four(ref) >= 40]
dc = common.difficulty(comp, ref)
Nc = len(comp)
print("\n## Easiest 10 in cohort (a) and in competent cohort (all-four>=40, N=%d run-passes)" % Nc)
ea = sorted(IDS, key=lambda i: (-d[i]["all_four"], i))[:10]
ec = sorted(IDS, key=lambda i: (-dc[i]["all_four"], i))[:10]
print(common.md_table(["#", "(a) easiest", "all-four/N", "competent easiest", "all-four/N", "valid-share"],
                      [[i + 1, ea[i], f"{d[ea[i]]['all_four']}/{N}", ec[i], f"{dc[ec[i]]['all_four']}/{Nc}", common.pct(dc[ec[i]]['all_four'], dc[ec[i]]['valid'])] for i in range(10)]))
easy_c = [rid for rid in IDS if dc[rid]["valid"] and dc[rid]["all_four"] / dc[rid]["valid"] >= 0.99 and diff["c_native7"][rid]["all_four"] == 7]
print("Universally easy (>=99%% of valid competent outputs AND 7/7 native): n=%d: %s" % (len(easy_c), ", ".join(easy_c)))
easy_c95 = [rid for rid in IDS if dc[rid]["valid"] and dc[rid]["all_four"] / dc[rid]["valid"] >= 0.95 and diff["c_native7"][rid]["all_four"] == 7]
print("At >=95%% competent AND 7/7 native: n=%d: %s" % (len(easy_c95), ", ".join(easy_c95)))
nat7 = [rid for rid in IDS if diff["c_native7"][rid]["all_four"] == 7]
print("Matched by all 7 native fresh1/P0: n=%d: %s" % (len(nat7), ", ".join(nat7)))

# Driving field and mode wrong vector for hardest 12
print("\n## Hardest 12 in cohort (a): driving field, mode wrong vector")
rows = []
for rid in order[:12]:
    x = d[rid]
    miss = {f: x["valid"] - x[f] for f in F}
    drv = max(F, key=lambda f: miss[f])
    vecs = Counter()
    for r in runs:
        v = r.vector(rid)
        if v is not None and v != tuple(ref[rid][f] for f in F):
            vecs[v] += 1
    mode, cnt = vecs.most_common(1)[0] if vecs else (None, 0)
    rows.append([rid, f"{x['all_four']}/{N}", x["valid"], " ".join(f"{common.FIELD_SHORT[f]}={miss[f]}" for f in F), drv,
                 "/".join(mode) if mode else "", cnt, "/".join(ref[rid][f] for f in F)])
print(common.md_table(["Review", "All-four", "Valid", "Field misses (of valid)", "Driving field", "Mode wrong vector", "n", "Reference"], rows))

print("\n## Text of hardest 6")
for rid in order[:6]:
    print(f"- {rid}: \"{text[rid]}\"  reference: {'/'.join(ref[rid][f] for f in F)}  rationale: {rat[rid]}")
print("\n## Text of hard 7-12")
for rid in order[6:12]:
    print(f"- {rid}: \"{text[rid]}\"  reference: {'/'.join(ref[rid][f] for f in F)}  rationale: {rat[rid]}")
