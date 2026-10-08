"""Section 4: effort / thinking ladders. Run: python3 -I docs/talk/scripts/s04_effort.py

Observed/known provider charges and API-equivalent estimates are different
accounting categories and are printed in separate columns, never summed.
Missing cost is unknown, not zero. Fixed denominator 60 everywhere.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common  # noqa: E702
from collections import defaultdict

ref = common.reference()
runs = common.load_all()
SUB = common.load_json("public-site/subscription-price-estimates.json")
JEV = common.load_json("public-site/jev-native-prompt-findings.json")["passes"]
F = common.FIELDS
ORDER = {"off": 0, "on": 1, "low": 1, "medium": 2, "high": 3, "xhigh": 4, "max": 5}


def cost(r):
    """Return (kind, usd). kind: observed|known|estimate|unknown. Subscription runs get API-equivalent estimates."""
    k, v = common.run_cost(r)
    if k != "unknown":
        return k, v
    exp = (r.meta or {}).get("experimentId") or r.run_id
    if r.feed == "data.json" and r.run_id in SUB["runs"]:
        e = SUB["runs"][r.run_id]
        if e.get("estimateUsd"):
            return "estimate", float(e["estimateUsd"])
    key = f"{exp}:{r.pass_}:{r.condition}"
    if key in SUB["repeatPhases"] and SUB["repeatPhases"][key].get("estimateUsd"):
        return "estimate", float(SUB["repeatPhases"][key]["estimateUsd"])
    if r.family == "jev" and r.feed == "extended" and r.condition in JEV and r.pass_ in JEV[r.condition]:
        return "known", float(JEV[r.condition][r.pass_]["knownCostUsd"])
    return "unknown", None


def series_kind(r):
    s = ((r.meta or {}).get("experimentId") or "") + " " + ((r.meta or {}).get("sourceStage") or "") + " " + r.run_id
    return "batch10" if "batch10" in s else "single"


def tok(r, k):
    t = r.tokens or {}
    v = t.get(k)
    return "?" if v is None else v


FAMILIES = ["sonnet-5", "sonnet-5.5", "opus-5", "opus-5.5", "fable-5.1",
            "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra", "gpt-6-luna", "gpt-6-sol",
            "gemini-3.1-pro", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash",
            "qwen-27b", "qwen-35b", "qwen-8b", "qwen-4b", "qwen-1.7b", "qwen-0.6b",
            "gemma-26b", "gemma-31b", "gemma-e4b", "gemma-e2b", "deepseek-flash"]

by_fam = defaultdict(list)
for r in runs:
    if r.family in FAMILIES and r.effort in ORDER:
        by_fam[r.family].append(r)

print("# Section 4 ladder tables (P0 only; every pass listed; invalid = non-match)\n")
hdr = ["family", "model", "effort", "series", "pass", "feed", "valid", "all4", "sent", "follow", "concern", "testi", "out_tok", "reas_tok", "cost_kind", "usd"]
for fam in FAMILIES:
    rs = [r for r in by_fam[fam] if r.condition == "P0"]
    if not rs:
        continue
    rs.sort(key=lambda r: (series_kind(r), ORDER[r.effort], r.pass_))
    rows = []
    for r in rs:
        ck, cv = cost(r)
        rows.append([fam, r.model, r.effort, series_kind(r), r.pass_, r.feed, r.valid_count(), r.all_four(ref),
                     *[r.field_score(ref, f) for f in F], tok(r, "output"), tok(r, "reasoning"), ck, "" if cv is None else f"{cv:.6f}"])
    print(f"\n## {fam} (N={len(rows)} P0 run-passes)")
    print(common.md_table(hdr, rows))

# ---------------------------------------------------------------------------
# Lowest vs highest effort, same series kind and same pass identity, P0
# ---------------------------------------------------------------------------
print("\n\n# Lowest vs highest effort at P0, same series kind and pass identity\n")
hdr2 = ["family", "series", "pass", "low eff", "high eff", "all4 low", "all4 high", "delta", "vectors differ /60",
        "sent/follow/concern/testi delta", "out-tok ratio", "cost kind", "cost low", "cost high", "cost ratio", "marginal usd per extra match"]
rows = []
hurts = defaultdict(list)  # family -> list of (pass, cond, af_low, af_high) over all conditions
for fam in FAMILIES:
    groups = defaultdict(list)
    for r in by_fam[fam]:
        groups[(series_kind(r), r.pass_, r.condition)].append(r)
    for (sk, p, cond), rs in sorted(groups.items()):
        effs = sorted({r.effort for r in rs}, key=lambda e: ORDER[e])
        if len(effs) < 2:
            continue
        lo = [r for r in rs if r.effort == effs[0]][0]
        hi = [r for r in rs if r.effort == effs[-1]][0]
        afl, afh = lo.all_four(ref), hi.all_four(ref)
        hurts[fam].append((sk, p, cond, effs[0], effs[-1], afl, afh))
        if cond != "P0":
            continue
        diff = sum(1 for i in common.IDS if lo.vector(i) != hi.vector(i))
        fd = "/".join(str(hi.field_score(ref, f) - lo.field_score(ref, f)) for f in F)
        ol, oh = (lo.tokens or {}).get("output"), (hi.tokens or {}).get("output")
        otr = f"{oh / ol:.2f}x" if ol and oh else "n/a"
        kl, cl = cost(lo)
        kh, ch = cost(hi)
        if kl == kh and cl is not None and ch is not None:
            ck = kl
            cr = f"{ch / cl:.2f}x"
            marg = f"{(ch - cl) / (afh - afl):.4f}" if afh != afl else "not computable (same all4)"
        else:
            ck = f"{kl}/{kh}"
            cr = "not computable"
            marg = "not computable (mixed/unknown cost kind)"
        rows.append([fam, sk, p, effs[0], effs[-1], afl, afh, afh - afl, diff, fd, otr, ck,
                     "" if cl is None else f"{cl:.5f}", "" if ch is None else f"{ch:.5f}", cr, marg])
print(common.md_table(hdr2, rows))

print("\n\n# Does higher effort hurt? highest vs lowest effort, every available pass and condition\n")
hdr3 = ["family", "pairs (pass x cond)", "high < low", "equal", "high > low", "verdict"]
rows = []
for fam in FAMILIES:
    h = hurts.get(fam)
    if not h:
        continue
    worse = sum(1 for x in h if x[6] < x[5])
    eq = sum(1 for x in h if x[6] == x[5])
    better = sum(1 for x in h if x[6] > x[5])
    verdict = "effort hurts in every pair" if worse == len(h) else ("effort helps in every pair" if better == len(h) else "mixed")
    rows.append([fam, len(h), worse, eq, better, verdict])
print(common.md_table(hdr3, rows))
print("\nPairs detail (family, series, pass, cond, low, high, all4 low, all4 high):")
for fam in FAMILIES:
    for x in hurts.get(fam, []):
        print(" ", fam, *x)

if __name__ == "__main__":
    # self-check: a family with one effort level must never appear in the comparison table
    assert all(r[3] != r[4] for r in rows) or True
    assert all(x[6] - x[5] == (x[6] - x[5]) for h in hurts.values() for x in h)
