# Legacy Qwen repeat findings, 2 October 2026

The [source-bound report](../public-site/legacy-qwen-repeats.json) covers the six exact configurations in the [frozen fresh-three plan](../results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json). All nine full development phases are closed for **Qwen3 0.6B · local HTTP · thinking off**. Each phase saved 60 of 60 responses and passed the report's raw-response, request-identity, runtime-control and completion-hash checks. **Qwen3 0.6B · SDK · thinking on** and **thinking off** each have a complete first pass of P0, P1 and P2. Their other six phases and the three larger SDK configurations remain pending. This does not complete the legacy Qwen roster.

The two SDK fresh1/P0 smokes were originally stopped after three attempts because strict parsing found intrinsic fenced-JSON output (two invalid with thinking on; three with thinking off). The separately approved [SDK format successor](../results/repeatability-v1/legacy-qwen-sdk-format-successor-v1/manifest.json) admitted new development phases without repairing or replaying those smokes. The report binds each terminal smoke, successor inspection and receipt, and development completion and raw response. At P0, thinking on saved 60/60 with **27 valid and 33 invalid outputs**; thinking off saved 60/60 with **1 valid and 59 invalid outputs**. Both score **0/60 all-four exact matches** against the frozen provisional key. At P2, thinking on saved 60/60 with **56 valid, 4 invalid, and 3/60 all-four matches**; thinking off saved 60/60 with **1 valid, 59 invalid, and 0/60 all-four matches**. The thinking-on P2 smoke was all valid; the thinking-off P2 smoke stopped with three invalid outputs and had only a successor inspection, which the report binds directly. Invalid outputs remain in the fixed denominator. These are one fresh pass per exact SDK condition, not three-pass repeatability results. The [thinking-on P2 completion](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3-0.6b-sdk-thinking-on/fresh1/P2/development.completion.json) and [thinking-off P2 completion](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3-0.6b-sdk-thinking-off/fresh1/P2/development.completion.json) retain the outcomes.

The completed SDK first pass now includes P1, the classifier-instruction condition. Thinking on returned 53 valid outputs and one complete match; thinking off returned four valid outputs and no complete matches. Every row below includes all 60 reviews, including invalid responses.

| SDK setting | Prompt | Valid format | All four labels match |
| --- | --- | ---: | ---: |
| Thinking on | P0: base task | 27/60 | 0/60 |
| Thinking on | P1: classifier instructions | 53/60 | 1/60 |
| Thinking on | P2: instructions and decision tree | 56/60 | 3/60 |
| Thinking off | P0: base task | 1/60 | 0/60 |
| Thinking off | P1: classifier instructions | 4/60 | 0/60 |
| Thinking off | P2: instructions and decision tree | 1/60 | 0/60 |

The added instructions improved format compliance in this thinking-on first pass, while complete-label agreement stayed low. This is an observed difference across the frozen prompt conditions, not yet evidence that the size of the improvement repeats reliably. The strict parser rejects Markdown fences; stripping those fences after execution would change the measured task. The original outputs remain available for a separately declared parsing study if desired.

For the nine HTTP nonthinking phases, all 60 classifications in each phase are schema-valid, yet **0/60 match all four fields** of the frozen, provisional [v0.2 reference key](../data/pilot/proposed_labels.jsonl). Field agreement is identical across the three fresh passes within each prompt condition:

| Prompt | Sentiment | Follow-up | Serious concern | Testimonial potential | Four fields |
| --- | ---: | ---: | ---: | ---: | ---: |
| P0 | 37/60 | 54/60 | 13/60 | 9/60 | 0/60 |
| P1 | 43/60 | 43/60 | 11/60 | 11/60 | 0/60 |
| P2 | 19/60 | 38/60 | 15/60 | 15/60 | 0/60 |

The [per-phase class counts and confusion tables](../public-site/legacy-qwen-repeats.json) show a marked testimonial-potential “yes” concentration in this exact configuration. The reference key has 9 “yes,” 50 “no” and 1 “insufficient information” labels. In each pass, P0 predicts “yes” for all 60 records, including all 50 reference “no” records. P1 predicts “yes” for 58, including 48 reference “no” records. P2 predicts “yes” for 54, including 44 reference “no” records. Valid JSON and schema compliance therefore did not translate into agreement with this reference key. These counts describe this Qwen3 0.6B artifact through the local HTTP nonthinking route; they are not findings about every Qwen model or a measure of hiring accuracy.

The three fresh passes produce the same four-field prediction for every record within each prompt condition: all nine pairwise comparisons have 0/60 changed answer vectors, and no field changes across all three passes. That is output stability on the *same* 60 synthetic reviews, not independent-case performance. The fixed denominator for scores is 60; change comparisons use shared valid records, which are all 60 here. The [phase completions and bound raw evidence](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3-0.6b-q4km-nonthinking/) retain the separate pass and prompt identities. Historical Qwen predictions remain separate observations and do not fill these fresh cells.

The [plan](../results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json) fixes each configuration's model artifact, context, output reserve and cache policy; each stage binds its runtime attestation. The HTTP nonthinking route uses an 8,192-token context, 512-token output reserve, temperature zero and no controlled seed. Across its nine development phases, reported usage totals 996,960 tokens and 204.09 seconds of client-observed request time. That time includes runtime and transport overhead, so pure inference and model-load times are unavailable. The local runs have no measured per-request API charge; hardware and electricity costs were not measured. The other three SDK configurations remain unscored until their own full phases close.

The snapshot can be rebuilt offline with `python3 scripts/build_legacy_qwen_repeat_findings.py --check` and checked with `python3 -m unittest tests.test_build_legacy_qwen_repeat_findings -v`.
