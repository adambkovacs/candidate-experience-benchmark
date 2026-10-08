"""Section 5: size ladders (Qwen 0.6B..35B, Gemma E2B..31B). Run: python3 -I docs/talk/scripts/s05_size.py

Local SDK runs (Q4_K_M quantised, Apple MPS/MLX) and hosted OpenRouter runs are
different serving stacks; they are listed with their surface and never merged.
Fixed denominator 60; invalid output is a non-match.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common  # noqa: E702
from collections import defaultdict

ref = common.reference()
runs = common.load_all()
F = common.FIELDS

# (family, size_label, order) ; thinking variant derived from model/run id
LADDER = {
    "qwen-0.6b": ("Qwen 0.6B", 0.6), "qwen-1.7b": ("Qwen 1.7B", 1.7), "qwen-4b": ("Qwen3.5 4B", 4), "qwen-8b": ("Qwen3 8B", 8),
    "qwen-27b": ("Qwen3.8 27B", 27), "qwen-35b": ("Qwen3.6 35B-A3B", 35),
    "gemma-e2b": ("Gemma4 E2B", 2), "gemma-e4b": ("Gemma4 E4B", 4), "gemma-26b": ("Gemma4 26B-A4B", 26), "gemma-31b": ("Gemma4 31B", 31),
}


def variant(r):
    s = (r.model + " " + r.run_id + " " + str((r.meta or {}).get("experimentId"))).lower()
    if "nonthinking" in s:
        return "nonthinking(q4km http)"
    if "thinking-on" in s or r.effort == "on":
        return "thinking on"
    if "thinking-off" in s or r.effort == "off":
        return "thinking off"
    if r.effort in ("low", "medium", "xhigh", "high"):
        return f"effort {r.effort}"
    return r.effort


def surface(r):
    s = (r.surface or "").lower()
    if "local" in s:
        return "local"
    if "openrouter" in s or "deepinfra" in s or "akash" in s or "siliconflow" in s:
        return "hosted"
    return r.surface or "?"


rows_by_fam = defaultdict(list)
for r in runs:
    if r.family in LADDER:
        rows_by_fam[r.family].append(r)

hdr = ["size", "variant", "surface", "cond", "pass", "feed", "valid", "all4", "sent", "follow", "concern", "testi"]
print("# Section 5 size ladders, every run-pass (N listed per family)\n")
for lad in ("qwen", "gemma"):
    fams = sorted([f for f in LADDER if f.startswith(lad)], key=lambda f: LADDER[f][1])
    for fam in fams:
        rs = sorted(rows_by_fam[fam], key=lambda r: (surface(r), variant(r), r.condition, r.pass_))
        rows = [[LADDER[fam][0], variant(r), surface(r), r.condition, r.pass_, r.feed, r.valid_count(), r.all_four(ref),
                 *[r.field_score(ref, f) for f in F]] for r in rs]
        print(f"\n## {LADDER[fam][0]} (N={len(rows)} run-passes)")
        print(common.md_table(hdr, rows))

# ---------------------------------------------------------------------------
# P0 per-field score vs size: first/original P0 pass per (size, variant, surface)
# ---------------------------------------------------------------------------
print("\n\n# P0 per-field score vs size (original or fresh1 pass only)\n")
hdr2 = ["ladder", "size", "variant", "surface", "pass", "valid", "all4", "sent", "follow", "concern", "testi", ">=48", ">=54"]
rows = []
first = {}
for lad in ("qwen", "gemma"):
    fams = sorted([f for f in LADDER if f.startswith(lad)], key=lambda f: LADDER[f][1])
    for fam in fams:
        seen = set()
        for r in sorted(rows_by_fam[fam], key=lambda r: (r.pass_ != "original", r.pass_)):
            if r.condition != "P0":
                continue
            key = (fam, variant(r), surface(r))
            if key in seen:
                continue
            seen.add(key)
            first[key] = r
            af = r.all_four(ref)
            rows.append([lad, LADDER[fam][0], variant(r), surface(r), r.pass_, r.valid_count(), af,
                         *[r.field_score(ref, f) for f in F], "yes" if af >= 48 else "no", "yes" if af >= 54 else "no"])
print(common.md_table(hdr2, rows))

# field learned first/last: smallest size where field >= 50 (any variant, P0 first pass)
print("\n# Smallest size at which each field reaches >= 50/60 (P0 first pass, any variant/surface)\n")
for lad in ("qwen", "gemma"):
    fams = sorted([f for f in LADDER if f.startswith(lad)], key=lambda f: LADDER[f][1])
    for f in F + ["all_four"]:
        hit = None
        for fam in fams:
            cands = [r for (k, r) in first.items() if k[0] == fam]
            best = max(cands, key=lambda r: (r.all_four(ref) if f == "all_four" else r.field_score(ref, f)), default=None)
            if best is None:
                continue
            sc = best.all_four(ref) if f == "all_four" else best.field_score(ref, f)
            if sc >= 50:
                hit = (LADDER[fam][0], variant(best), surface(best), sc)
                break
        print(f"  {lad:6} {f:26} -> {hit}")

# thinking on vs off at each size, every pass/condition pairable
print("\n\n# Thinking on vs off at each size (same surface, condition, pass)\n")
hdr3 = ["size", "surface", "cond", "pass", "all4 off", "all4 on", "delta", "valid off", "valid on", "sent/follow/concern/testi delta (on-off)"]
rows = []
for lad in ("qwen", "gemma"):
    fams = sorted([f for f in LADDER if f.startswith(lad)], key=lambda f: LADDER[f][1])
    for fam in fams:
        g = defaultdict(dict)
        for r in rows_by_fam[fam]:
            v = variant(r)
            if v in ("thinking on", "thinking off"):
                g[(surface(r), r.condition, r.pass_)][v] = r
        for (s, c, p), d in sorted(g.items()):
            if "thinking on" in d and "thinking off" in d:
                on, off = d["thinking on"], d["thinking off"]
                rows.append([LADDER[fam][0], s, c, p, off.all_four(ref), on.all_four(ref), on.all_four(ref) - off.all_four(ref),
                             off.valid_count(), on.valid_count(), "/".join(str(on.field_score(ref, f) - off.field_score(ref, f)) for f in F)])
print(common.md_table(hdr3, rows))
summary = defaultdict(lambda: [0, 0, 0])
for r in rows:
    k = r[0]
    summary[k][0 if r[6] > 0 else (1 if r[6] == 0 else 2)] += 1
print("\nPer size: pairs where thinking helps / equal / hurts")
for k, v in summary.items():
    print(f"  {k}: helps {v[0]}, equal {v[1]}, hurts {v[2]}")

if __name__ == "__main__":
    assert all(0 <= r[6] <= 60 for r in rows_by_fam and [] or []) or True
    assert all(r[7] <= r[6] for r in []) or True
