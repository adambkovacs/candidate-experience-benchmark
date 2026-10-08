"""Section 12: route all 60 reviews under the full agree-or-defer policy (01 section 6, lines 2 to 4)
for every pair of the seven native fresh1/P0 decision models.
Run from the worktree root: python3 -I docs/talk/scripts/s12_full_policy_routing.py

Rules, applied to saved first-pass answers only (no inference):
  D  defer:     the two four-field answers differ, or either is missing or invalid
  S  escalate:  either model answers serious_concern_reported = yes (even when the pair agrees)
  I  clarify:   either model answers insufficient_information on any field
A review reaches a person if it is in D, S or I. Retrospective on the same 60 development reviews,
against the provisional v0.2 reference; human review cost is not measured.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common
from itertools import combinations

F, IDS = common.FIELDS, common.IDS
pol = common.load_json("public-site/native-agreement-policy-v1.json")
dr = common.load_json("public-site/disputed-reviews-v1.json")
name = {c["id"]: c["display_name"].replace("Perplexity Decider V1 27B", "Perplexity") for c in pol["components"]}
order = [c["id"] for c in pol["components"]]

pred = {m: {} for m in order}
for r in dr["reviews"]:
    for a in r["answers"]:
        p = a.get("prediction")
        ok = isinstance(p, dict) and all(p.get(f) in common.LABELS[f] for f in F)
        pred[a["model_id"]][r["id"]] = p if ok else None  # invalid answers can only defer
assert all(len(pred[m]) == 60 for m in order), "every model needs a slot for all 60 reviews"


def route(a, b):
    D, S, I = set(), set(), set()
    for i in IDS:
        pa, pb = pred[a][i], pred[b][i]
        if pa is None or pb is None or any(pa[f] != pb[f] for f in F):
            D.add(i)
        for p in (pa, pb):
            if p is None:
                continue
            if p["serious_concern_reported"] == "yes":
                S.add(i)
            if "insufficient_information" in p.values():
                I.add(i)
    return D, S, I


rows = []
for pair in pol["pairs"]:
    a, b = pair["left"], pair["right"]
    D, S, I = route(a, b)
    # self-check: recomputed disagreement set must equal the published policy feed
    assert D == set(pair["deferred_ids"]), (a, b, sorted(D ^ set(pair["deferred_ids"])))
    rows.append((f"{name[a]} + {name[b]}", D, S, I))

ref_sc = sum(1 for r in dr["reviews"] if r["reference"]["serious_concern_reported"] == "yes")
print(f"Reference serious_concern = yes: {ref_sc} of 60 (concern-enriched synthetic set).")
print("Columns: D defer, S serious-concern escalation, I insufficient-information routing, all over 60 reviews.")
print("'+S|I' = reviews the S and I rules add beyond D. Person = D | S | I.\n")
hdr = f"{'pair':<31}{'D':>4}{'S':>4}{'I':>4}{'D&S':>5}{'D&I':>5}{'S&I':>5}{'D&S&I':>7}{'+S|I':>6}{'person':>8}"
print(hdr); print("-" * len(hdr))
for label, D, S, I in rows:
    print(f"{label:<31}{len(D):>4}{len(S):>4}{len(I):>4}{len(D & S):>5}{len(D & I):>5}{len(S & I):>5}"
          f"{len(D & S & I):>7}{len((S | I) - D):>6}{len(D | S | I):>8}")

focus = "solar-decide-native-fresh1-p0", "perplexity-decider-native-fresh1-p0"
D, S, I = route(*focus)
print(f"\nDetail: {name[focus[0]]} + {name[focus[1]]}")
detail = [
    ("D  deferred by disagreement", D),
    ("S  serious_concern = yes, either model", S),
    ("I  insufficient_information, either model", I),
    ("D & S", D & S), ("D & I", D & I), ("S & I", S & I), ("D & S & I", D & S & I),
    ("S - D  accepted, escalated for concern", S - D),
    ("I - D  accepted, routed for clarification", I - D),
    ("(S | I) - D  added beyond deferral", (S | I) - D),
    ("D | S | I  reaches a person", D | S | I),
    ("accepted with no routing", set(IDS) - (D | S | I)),
]
for label, s in detail:
    print(f"  {label:<44}{len(s):>3}  {' '.join(sorted(s))}")
