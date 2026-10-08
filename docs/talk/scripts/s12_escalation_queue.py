"""Human-queue size under the full talk policy, per agreement pair.

Policy (docs/talk/05-session-outline.md, beat 7):
  1. accept a review only when both runs return the identical four-field answer (agreement rule);
  2. any serious_concern_reported == "yes" from either run goes to escalation review, even if accepted;
  3. any "insufficient_information" from either run on any field goes to a person, even if accepted.
Queue = deferred  OR  accepted-with-concern  OR  accepted-with-insufficient.
Sources: public-site/native-agreement-policy-v1.json (pairs, deferred ids) and
public-site/disputed-reviews-v1.json (per-model predictions). No inference, no new labels.
Run: python3 -I docs/talk/scripts/s12_escalation_queue.py
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
pol = json.load(open(os.path.join(ROOT, "public-site/native-agreement-policy-v1.json")))
dis = json.load(open(os.path.join(ROOT, "public-site/disputed-reviews-v1.json")))

names = {m["id"]: m["display_name"] for m in dis["models"]}
pred = {}  # (model_id, review_id) -> prediction dict
for r in dis["reviews"]:
    for a in r["answers"]:
        pred[(a["model_id"], r["id"])] = a["prediction"]
ids = [r["id"] for r in dis["reviews"]]
ref = {r["id"]: r["reference"] for r in dis["reviews"]}
soup = "DEV-029"

def flags(model, rid):
    p = pred[(model, rid)]
    concern = p.get("serious_concern_reported") == "yes"
    insuff = any(v == "insufficient_information" for v in p.values())
    return concern, insuff

rows = []
zero_err, soup_wrong_accepted = 0, 0
for pr in pol["pairs"]:
    L, R = pr["left"], pr["right"]
    deferred = set(pr["deferred_ids"])
    acc_concern, acc_insuff = set(), set()
    for rid in pr["accepted_ids"]:
        for m in (L, R):
            c, i = flags(m, rid)
            if c: acc_concern.add(rid)
            if i: acc_insuff.add(rid)
    queue = deferred | acc_concern | acc_insuff
    if pr["accepted_all_four_error_count"] == 0: zero_err += 1
    if soup in pr["accepted_ids"] and soup in pr["accepted_all_four_error_ids"]: soup_wrong_accepted += 1
    rows.append((names[L], names[R], pr["accepted_count"], pr["accepted_all_four_error_count"],
                 len(deferred), len(acc_concern), len(acc_insuff), len(queue), soup in pr["accepted_ids"]))

print(f"pairs: {len(rows)}  zero-accepted-error pairs: {zero_err}  pairs accepting soup with wrong answer: {soup_wrong_accepted}")
print("pair | accepted | acc.errors | deferred | accepted+concern | accepted+insufficient | human queue /60 | soup accepted")
for r in sorted(rows, key=lambda x: (-x[2], x[7])):
    print(f"{r[0]} + {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]}")

# reference base rates for context
ref_yes = sum(1 for rid in ids if ref[rid]["serious_concern_reported"] == "yes")
ref_insuff = sum(1 for rid in ids if any(v == "insufficient_information" for v in ref[rid].values()))
print(f"reference: serious_concern yes = {ref_yes}; reviews with any insufficient_information = {ref_insuff}")
