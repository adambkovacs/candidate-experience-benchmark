# Jev native Choice P1/P2 findings

Date: 2026-10-06

These are standalone OpenRouter native Choice runs of the Jev 1.13 model. They are a separate route and prompt surface, not a distinct Jev model. The 60 development references are provisional and were read only for offline scoring.

## Saved pass status

| Condition | Pass | Valid | Invalid | Unknown cost | Never sent | All-four matches |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| P1 | fresh1 | 60 | 0 | 0 | 0 | 54/60 |
| P1 | fresh2 | 59 | 1 | 0 | 0 | 53/60 |
| P2 | fresh1 | 60 | 0 | 0 | 0 | 54/60 |
| P2 | fresh2 | 17 | 0 | 1 | 42 | 15/60 |

P1 fresh1: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
P1 fresh2: 53/60 all-four; sentiment: 55/60, follow_up_needed: 57/60, serious_concern_reported: 56/60, testimonial_potential: 57/60. DEV-056 returned HTTP 200 and a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.
P2 fresh1: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
P2 fresh2 has 17 valid responses and 15 all-four matches among those 17. DEV-018 received HTTP 429 with an unknown charge bounded at $0.001344000. DEV-019 through DEV-060 were never sent. The 15/60 entry above is a partial-denominator accounting value, not a completed 60-record score.

## Prompt comparison and repeat variation

The frozen P1 and P2 native requests share record order, feedback, policy, criteria, labels, route, and parser. Only the four Choice question instructions differ. They are native analogues of P1 and P2, not byte-identical chat prompts.

In fresh1, P1 and P2 differ on 1/60 four-field answer vectors: DEV-013. Field answer changes: sentiment 1, follow_up_needed 0, serious_concern_reported 0, testimonial_potential 0. P1 and P2 have 54/60 and 54/60 all-four matches respectively. Native probability dictionary changes by field: sentiment 32/60, follow_up_needed 21/60, serious_concern_reported 26/60, testimonial_potential 12/60. Vendor confidence changes: sentiment 27/60, follow_up_needed 22/60, serious_concern_reported 26/60, testimonial_potential 14/60.
Across P1 fresh1 and fresh2, 0/59 shared valid records changed a four-field answer vector. DEV-056 is excluded from this paired repeat comparison because fresh2 is invalid. Native probability dictionaries and vendor confidence are compared separately; neither is a calibrated correctness probability.
P1 repeat probability dictionary changes by field: sentiment 25/59, follow_up_needed 15/59, serious_concern_reported 11/59, testimonial_potential 8/59. Vendor confidence changes: sentiment 22/59, follow_up_needed 17/59, serious_concern_reported 17/59, testimonial_potential 9/59.
The fresh2 cross-condition comparison is restricted to 17 shared valid records. It does not stand in for a 60-record P2 repeat or a full P1/P2 comparison.

## Cost and timing

- P1 fresh1: known provider cost $0.006405000; unknown-charge bound $0; provider-reported input/output tokens 152500/11176; client-observed request time 32.260 seconds.
- P1 fresh2: known provider cost $0.006405000; unknown-charge bound $0; provider-reported input/output tokens 152500/11176; client-observed request time 35.986 seconds.
- P2 fresh1: known provider cost $0.006851040; unknown-charge bound $0; provider-reported input/output tokens 163120/11176; client-observed request time 32.841 seconds.
- P2 fresh2: known provider cost $0.001940694; unknown-charge bound $0.001344000; provider-reported input/output tokens 46207/3166; client-observed request time 10.295 seconds.

Client time includes network and local work. The stopped P2 fresh2 token totals include only the 17 successful responses because the HTTP 429 has no provider usage.

## Evidence and limits

The offline builder verifies frozen requests, the provisional reference SHA, proposed manifests, archived root receipts, context and smoke reviews, saved request and raw response hashes, completion or terminal status, child-ledger events, and reconciled known and unknown costs. It reconstructs receipt identity from archived budget files and never reads or changes the live master budget.

P1 fresh3, P2 fresh3, and the remaining 42 P2 fresh2 records have no scored full-pass evidence here. This report does not call the repeatability matrix complete. The saved Jev P0 evidence is a three-record OpenRouter smoke, not a full P0 pass.

## Sources

- [Offline verifier and renderer](../scripts/build_jev_native_prompt_findings.py)
- [Verifier tests](../tests/test_build_jev_native_prompt_findings.py)
- [P1 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1.json)
- [P2 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1.json)
- [P1 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh1/attempts.jsonl)
- [P1 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh2/attempts.jsonl)
- [P2 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/attempts.jsonl)
- [P2 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/attempts.jsonl)
- [P2 fresh2 terminal record](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/terminal-public.json)
- [P2 fresh2 cost reconciliation](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/budget-reconciliation.json)
- [P2 fresh2 unknown-cost raw evidence](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/unknown-cost-evidence.jsonl)
- [Frozen provisional references](../data/pilot/proposed_labels.jsonl)
