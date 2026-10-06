# Jev native Choice P0/P1/P2 findings

Date: 2026-10-06

These are standalone OpenRouter native Choice runs of the Jev 1.13 model. They are a separate route and prompt surface, not a distinct Jev model. The 60 development references are provisional and were read only for offline scoring.

## Saved pass status

| Condition | Pass | Valid | Invalid | Unknown cost | Never sent | All-four matches |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| P0 | fresh1 | 60 | 0 | 0 | 0 | 54/60 |
| P0 | fresh2 | 60 | 0 | 0 | 0 | 53/60 |
| P0 | fresh3 | 59 | 1 | 0 | 0 | 52/60 |
| P1 | fresh1 | 60 | 0 | 0 | 0 | 54/60 |
| P1 | fresh2 | 59 | 1 | 0 | 0 | 53/60 |
| P1 | fresh3 | 60 | 0 | 0 | 0 | 54/60 |
| P2 | fresh1 | 60 | 0 | 0 | 0 | 54/60 |
| P2 | fresh2 | 17 | 0 | 1 | 42 | 15/60 |
| P2 | fresh2 tail continuation | 40 | 1 | 1 | 0 | 35/42 |
| P2 | fresh2 combined interrupted | 57 | 1 | 2 | 0 | 50/60 |

P0 fresh1: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
P0 fresh2: 53/60 all-four; sentiment: 57/60, follow_up_needed: 57/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
P0 fresh3: 52/60 all-four; sentiment: 55/60, follow_up_needed: 56/60, serious_concern_reported: 56/60, testimonial_potential: 57/60. DEV-040 returned HTTP 200 with a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.
P1 fresh1: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
P1 fresh2: 53/60 all-four; sentiment: 55/60, follow_up_needed: 57/60, serious_concern_reported: 56/60, testimonial_potential: 57/60. DEV-056 returned HTTP 200 and a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.
P1 fresh3: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60. All 60 responses were valid and the child allocation was reconciled.
P2 fresh1: 54/60 all-four; sentiment: 56/60, follow_up_needed: 58/60, serious_concern_reported: 57/60, testimonial_potential: 58/60.
The original P2 fresh2 stage has 17 valid responses and 15 all-four matches among those 17. DEV-018 received HTTP 429 with an unknown charge bounded at $0.001344000. At that stage, DEV-019 through DEV-060 were never sent. Its original terminal record and 17-valid/42-unsent counters remain intact.
The separate DEV-019 through DEV-060 continuation attempted all 42 positions: 40 valid, one invalid, and one timeout with unknown cost. DEV-040 returned HTTP 200, but its native sentiment probabilities sum to 0.99. DEV-060 timed out without a response; its full $0.001344000 reserve remains an unknown-charge upper bound. The continuation has 35/42 all-four matches, with only its 40 valid answers scored.
Together, the stopped parent and stopped continuation cover all 60 original positions: 57 valid, one invalid, two unknown-cost attempts, and no never-sent positions. The 50/60 all-four figure is an interrupted composite accounting value. It is not a clean P2 fresh2 repeat or a repaired DEV-018/DEV-060 observation.

## Prompt comparison and repeat variation

The frozen P0, P1, and P2 native requests share record order, feedback, policy, criteria, labels, route, and parser. The four Choice question instructions distinguish the conditions. They are native analogues of the three prompts, not byte-identical chat prompts.

Across P0 fresh1 and fresh2, 3/60 answer vectors changed (DEV-013, DEV-030, DEV-056). Fresh2 and fresh3 changed 1/59 shared valid vectors (DEV-030); DEV-040 is excluded from that pair. P0 fresh1 and P1 fresh1 changed 1/60 vectors (DEV-013). These are observed pairwise differences, not a causal estimate of prompt effect.
In fresh1, P1 and P2 differ on 1/60 four-field answer vectors: DEV-013. Field answer changes: sentiment 1, follow_up_needed 0, serious_concern_reported 0, testimonial_potential 0. P1 and P2 have 54/60 and 54/60 all-four matches respectively. Native probability dictionary changes by field: sentiment 32/60, follow_up_needed 21/60, serious_concern_reported 26/60, testimonial_potential 12/60. Vendor confidence changes: sentiment 27/60, follow_up_needed 22/60, serious_concern_reported 26/60, testimonial_potential 14/60.
Across P1 fresh1 and fresh2, 0/59 shared valid records changed a four-field answer vector. DEV-056 is excluded from this paired repeat comparison because fresh2 is invalid. Native probability dictionaries and vendor confidence are compared separately; neither is a calibrated correctness probability.
P1 repeat probability dictionary changes by field: sentiment 25/59, follow_up_needed 15/59, serious_concern_reported 11/59, testimonial_potential 8/59. Vendor confidence changes: sentiment 22/59, follow_up_needed 17/59, serious_concern_reported 17/59, testimonial_potential 9/59.
P1 fresh3 is the third attempted full pass. Across fresh2 and fresh3, 1/59 shared valid answer vectors changed (DEV-013); DEV-056 remains excluded because fresh2 was invalid. Fresh1 and fresh3 differ at DEV-013 across 60 shared valid records. The three P1 passes have 60, 59, and 60 valid outcomes respectively.
The original fresh2 parent cross-condition comparison is restricted to 17 shared valid records. With the stopped continuation included, P1 fresh2 and the interrupted P2 composite share 56 valid positions; 2 four-field vectors differ (DEV-013, DEV-053). DEV-018, DEV-040, DEV-056, and DEV-060 are excluded. This comparison remains conditional on the two interrupted P2 stages.

## Cost and timing

- P0 fresh1: known provider cost $0.005890920; unknown-charge bound $0; provider-reported input/output tokens 140260/11176; client-observed request time 32.501 seconds.
- P0 fresh2: known provider cost $0.005890920; unknown-charge bound $0; provider-reported input/output tokens 140260/11176; client-observed request time 42.683 seconds.
- P0 fresh3: known provider cost $0.005890920; unknown-charge bound $0; provider-reported input/output tokens 140260/11176; client-observed request time 40.562 seconds.
- P1 fresh1: known provider cost $0.006405000; unknown-charge bound $0; provider-reported input/output tokens 152500/11176; client-observed request time 32.260 seconds.
- P1 fresh2: known provider cost $0.006405000; unknown-charge bound $0; provider-reported input/output tokens 152500/11176; client-observed request time 35.986 seconds.
- P1 fresh3: known provider cost $0.006405000; unknown-charge bound $0; provider-reported input/output tokens 152500/11176; client-observed request time 31.993 seconds.
- P2 fresh1: known provider cost $0.006851040; unknown-charge bound $0; provider-reported input/output tokens 163120/11176; client-observed request time 32.841 seconds.
- P2 fresh2: known provider cost $0.001940694; unknown-charge bound $0.001344000; provider-reported input/output tokens 46207/3166; client-observed request time 10.295 seconds.
- P2 fresh2 tail continuation: known provider cost $0.004681740; unknown-charge bound $0.001344000; provider-reported input/output tokens 111470/7634; client-observed request time 83.771 seconds.
- P2 fresh2 interrupted composite: known provider cost $0.006622434; unknown-charge bound $0.002688000; provider-reported input/output tokens 157677/10800; client-observed request time 94.066 seconds.

Client time includes network and local work. Provider token totals exclude DEV-018 and DEV-060 because neither attempt returned usage. Client time includes the DEV-060 timeout.

## Evidence and limits

The offline builder verifies frozen requests, the provisional reference SHA, proposed manifests, archived and v2 root receipts, context and smoke reviews, exact saved request bytes, raw responses, terminal records, child-ledger events, and reconciled known and unknown costs. The tail receipt binds the original 60 requests, stopped parent, versioned bridge, and authority module. The builder reconstructs receipt identity from saved budget files and does not read or change the live master budget.

The P2 fresh2 composite combines two interrupted stages and preserves both unknown-charge bounds. P0 and P1 each have three attempted full passes. P2 fresh3 is outside this report, so the native repeatability matrix remains incomplete. The earlier three-record Jev P0 smoke remains separate from these new full passes.

## Sources

- [Offline verifier and renderer](../scripts/build_jev_native_prompt_findings.py)
- [Verifier tests](../tests/test_build_jev_native_prompt_findings.py)
- [P0 frozen manifest](../results/route-audits/jev-native-p0-full-v1-20261006/jev-openrouter-native-p0-choice-v1.json)
- [P0 v2 proposal](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1.json)
- [P1 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1.json)
- [P2 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1.json)
- [P1 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh1/attempts.jsonl)
- [P1 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh2/attempts.jsonl)
- [P1 fresh3 v2 receipt](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3.root-review.json)
- [P1 fresh3 raw attempts](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/attempts.jsonl)
- [P1 fresh3 completion](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/completion.json)
- [P1 fresh3 cost reconciliation](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/budget-reconciliation.json)
- [P2 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/attempts.jsonl)
- [P2 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/attempts.jsonl)
- [P2 fresh2 terminal record](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/terminal-public.json)
- [P2 fresh2 cost reconciliation](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/budget-reconciliation.json)
- [P2 fresh2 unknown-cost raw evidence](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/unknown-cost-evidence.jsonl)
- [Versioned tail proposal](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1.json)
- [Tail root receipt](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail.root-review.json)
- [Tail raw attempts](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/attempts.jsonl)
- [Tail terminal record](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/terminal-public.json)
- [Tail cost reconciliation](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/budget-reconciliation.json)
- [Tail timeout evidence](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/unknown-cost-evidence.jsonl)
- [Versioned bridge](../scripts/openrouter_jev_authority_v2.py)
- [Frozen provisional references](../data/pilot/proposed_labels.jsonl)
- [P0 fresh1 v2 receipt](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh1.root-review.json)
- [P0 fresh1 raw attempts](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh1/attempts.jsonl)
- [P0 fresh1 completion](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh1/completion.json)
- [P0 fresh1 cost reconciliation](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh1/budget-reconciliation.json)
- [P0 fresh2 v2 receipt](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh2.root-review.json)
- [P0 fresh2 raw attempts](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh2/attempts.jsonl)
- [P0 fresh2 completion](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh2/completion.json)
- [P0 fresh2 cost reconciliation](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh2/budget-reconciliation.json)
- [P0 fresh3 v2 receipt](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh3.root-review.json)
- [P0 fresh3 raw attempts](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh3/attempts.jsonl)
- [P0 fresh3 completion](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh3/completion.json)
- [P0 fresh3 cost reconciliation](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh3/budget-reconciliation.json)
