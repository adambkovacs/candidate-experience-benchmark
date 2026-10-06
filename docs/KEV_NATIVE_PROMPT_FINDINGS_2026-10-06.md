# Kev native P1/P2 prompt findings

Date: 2026-10-06

Kev completed three 60-record development passes under each native Choice prompt condition. All 360 requests produced valid outcomes. Within each condition, all three passes returned the same categorical answers, native probability dictionaries, vendor confidence values, provider token counts, and observed provider costs.

## Result

<table>
  <thead><tr><th>Condition</th><th>Complete passes</th><th>All four fields</th><th>Sentiment</th><th>Follow-up</th><th>Serious concern</th><th>Testimonial</th></tr></thead>
  <tbody>
    <tr><td>P1</td><td>3/3</td><td>49/60</td><td>53/60</td><td>58/60</td><td>55/60</td><td>58/60</td></tr>
    <tr><td>P2</td><td>3/3</td><td>46/60</td><td>54/60</td><td>53/60</td><td>55/60</td><td>59/60</td></tr>
  </tbody>
</table>

The P1 and P2 comparison is paired by record and pass. P2 changed seven four-field vectors relative to P1: `DEV-001`, `DEV-005`, `DEV-022`, `DEV-030`, `DEV-035`, `DEV-041`, and `DEV-059`. The field changes were one sentiment answer, five follow-up answers, no serious-concern answers, and one testimonial answer. P2 gained one correct sentiment answer and one correct testimonial answer, lost five correct follow-up answers, and left serious-concern agreement unchanged. Its all-four score was three records lower.

Every probability dictionary and every vendor confidence value differed between P1 and P2 on all 60 records. These are separate native response fields. The report does not interpret vendor confidence as the probability assigned to the selected choice or as a calibrated probability of correctness.

## Repeat variation

P1 returned the same 49/60 all-four score and the same four field scores in fresh1, fresh2, and fresh3. P2 returned the same 46/60 all-four score and the same four field scores in all three passes. Each of the three within-condition pass pairs had zero categorical changes, zero probability-dictionary changes, and zero vendor-confidence changes across 60 records and four fields.

This is strong evidence of repeatability for these saved requests on the observed route. It does not establish behavior under another provider, model version, dataset, or prompt construction. Three identical passes also do not estimate a nonzero rare-change probability with precision.

## Native prompt equivalence

The adapter verifies all 60 P1/P2 request pairs before comparison. Feedback, policy, criteria, choice labels, label order, requested model, provider restriction, parser, and record order match. Only the instruction text inside each of the four native Choice questions differs. P1 and P2 are native Choice analogues of the benchmark prompt conditions; they are not byte-identical chat prompts.

## Historical P0 context

The historical P0 comparison is separate because it comes from the earlier native Kev series. The existing P0 verifier rechecks its route, raw responses, references, costs, and completion evidence before the adapter uses it. Only clean P0 fresh1 and fresh2 enter this comparison. The interrupted third P0 attempt and its separately admitted continuation do not count as a clean third pass.

Both clean P0 passes scored 48/60 on all four fields, with field agreement of 52/60 sentiment, 58/60 follow-up, 55/60 serious concern, and 59/60 testimonial. Relative to P0, P1 was one record higher on all four fields; P2 was two records lower. These are descriptive differences on 60 provisional development labels, not estimates of population-level prompt effects.

## Cost, tokens, and timing

Each P1 pass used 123,986 input tokens and 17,339 output tokens and cost $0.005207412. Across three passes, P1 used 371,958 input tokens, 52,017 output tokens, and $0.015622236.

Each P2 pass used 134,246 input tokens and 17,365 output tokens and cost $0.005638332. Across three passes, P2 used 402,738 input tokens, 52,095 output tokens, and $0.016914996.

P1 total client-observed request time ranged from 50.928 to 51.461 seconds per pass. P2 ranged from 53.639 to 54.239 seconds. These durations include network and local client work. They are not provider inference times, and the small difference is not a controlled latency experiment.

## Evidence gate

The report admits a pass only when all of the following hold:

- the exact 60-record manifest and request hashes verify against the frozen native plan;
- the context proof, inspected smoke evidence, root review receipt, model, provider, and parser controls match;
- the attempt journal contains exactly 60 ordered four-event outcomes;
- each saved request and raw response matches its SHA-256 digest;
- every categorical prediction can be reproduced from the raw native response;
- completion binds the manifest, receipt, endpoint catalog, and attempt journal;
- the child ledger hash and zero-unknown-cost reconciliation match the observed cost.

An active, partial, terminal-but-unreconciled, malformed, or source-drifted pass is excluded from scoring.

## Findings

- **BLOCKING:** None found in the six closed P1/P2 passes or in the report adapter's admission checks.
- **RESIDUAL:** The 60 development references remain provisional. The scores should not be presented as held-out performance.
- **RESIDUAL:** P1/P2 timing is client-observed and sequential. It cannot isolate provider inference latency.
- **RESIDUAL:** The clean historical P0 comparison has two passes. Its interrupted third attempt cannot support a three-pass P0 repeatability claim.

## Sources

- [Source-bound report adapter](../scripts/build_kev_native_prompt_findings.py)
- [Adapter tests](../tests/test_build_kev_native_prompt_findings.py)
- [Native decision prompt protocol](NATIVE_DECISION_PROMPT_PROTOCOL_2026-09-30.md)
- [P1 full-pass manifest](../results/route-audits/native-variants-full-v1-20261006/kev-openrouter-native-p1-choice-v1.json)
- [P2 full-pass manifest](../results/route-audits/native-variants-full-v1-20261006/kev-openrouter-native-p2-choice-v1.json)
- [Frozen provisional development references](../data/pilot/proposed_labels.jsonl)
- [Historical native P0 verifier](../scripts/build_kev_native_findings.py)
