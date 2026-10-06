# Qwen3.5 4B thinking-on: fresh1 P1 audit

The fresh1 classifier-instruction phase is a closed 60-review successor phase. The offline reporter accepted it only after checking the approved [successor manifest](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/manifest.json), frozen controller, three-review smoke inspection, reviewed development receipt, exact request hashes, raw responses, saved records, journal, completion hashes and [host audit](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P1/development.host-audit.json). The host audit reports a terminal completed phase, matching pre/post host state and AC power.

## Result

The phase saved all 60 reviews. **51 responses were valid and 9 failed the strict parser.** It matched all four provisional reference labels on **47/60** reviews. Invalid responses remain in the fixed denominator and receive no agreement credit.

| Measure | Agreement |
| --- | ---: |
| All four labels | 47/60 |
| Sentiment | 49/60 |
| Follow-up needed | 51/60 |
| Serious concern reported | 49/60 |
| Testimonial potential | 51/60 |

Every invalid response has the saved reason `non_json`. The IDs are **DEV-002, DEV-005, DEV-010, DEV-013, DEV-015, DEV-021, DEV-022, DEV-058 and DEV-059**. The [saved records](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P1/development.records.jsonl) and [raw responses](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P1/development.raw.jsonl) are bound by the [completion receipt](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P1/development.completion.json). No output was repaired or substituted.

## First-pass comparison with P2

The separately closed [fresh1 P2 phase](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P2/development.completion.json) scored 50/60 with 51 valid and 9 invalid outputs. P1 and P2 were both valid on 47 reviews. Two of those 47 changed a label: DEV-009 and DEV-020 changed sentiment and became all-four matches under P2. Follow-up, serious-concern and testimonial labels did not change on the shared-valid set.

Thirteen reviews were excluded from the paired label comparison because P1, P2 or both returned an invalid output: DEV-002, DEV-005, DEV-006, DEV-010, DEV-013, DEV-015, DEV-018, DEV-021, DEV-022, DEV-028, DEV-057, DEV-058 and DEV-059. Those reviews remain in each phase's 60-review score denominator. The observed 47/60 and 50/60 totals compare the two complete phases; the 2/47 changed-label count answers a narrower shared-valid question.

This is a matched first-pass prompt comparison, not a repeatability result. Neither P1 nor P2 has a second clean pass yet. The interrupted fresh1 P0 composite remains descriptive and does not supply a clean baseline or clean paired comparison.

## Resource observations and limits

P1 reported **106,290 input tokens, 127,480 output tokens and 233,770 total tokens**. Summed client-observed request time was **3,772.67 seconds**. The run recorded 60 requests, and the reporter found no provider charge because this was local execution.

The SDK did not report a separate reasoning-token count, pure inference time or model-load time. Client time includes runtime and local client overhead. Local electricity use and hardware cost were not measured. P2 used a longer prompt and produced a different output total, so its longer observed request time does not isolate a speed effect from the instruction change.

The agreement figures use the frozen, provisional human-checked v0.2 reference labels applied offline. They describe these 60 synthetic reviews under this exact model artifact, route and controls. They do not measure performance with real candidates or establish that either instruction set is generally better.
