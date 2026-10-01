# Jev native Choice confidence on the development set

The three historical TypeSafe Jev conditions saved a `confidence` value and a separate option distribution for every Choice head. The [offline report](../public-site/jev-confidence-findings.json) compares those reported confidence values with the [provisional development labels](../data/pilot/proposed_labels.jsonl). It uses the [existing source validator](../scripts/build_jev_native_prompt_report_v1.py), which checks the frozen request plan, raw responses, parser, attempt journals and review receipts before labels are read for scoring. No new request was sent.

P0 has 60 valid four-field outputs. P1 and P2 each have 59; the remaining response in each condition has a probability distribution summing to 0.99, outside the [unchanged parser's](../scripts/jev_benchmark.py) tolerance. Those two responses are unavailable for confidence scoring, not wrong categorical decisions. The [native prompt audit](JEV_PROMPT_AND_TIMING_AUDIT.md) records their IDs and the original attempt history.

| Condition | Field | Wrong among valid | Retained at confidence ≥ 0.7 | Wrong retained ≥ 0.7 | Retained ≥ 0.9 | Wrong retained ≥ 0.9 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| P0 | Sentiment | 4/60 | 55 | 1 | 47 | 0 |
| P0 | Follow-up | 2/60 | 58 | 1 | 52 | 0 |
| P0 | Serious concern | 3/60 | 57 | 2 | 53 | 1 |
| P0 | Testimonial | 2/60 | 58 | 2 | 54 | 1 |
| P1 | Sentiment | 4/59 | 55 | 1 | 46 | 0 |
| P1 | Follow-up | 2/59 | 56 | 0 | 51 | 0 |
| P1 | Serious concern | 3/59 | 57 | 2 | 53 | 1 |
| P1 | Testimonial | 2/59 | 57 | 2 | 54 | 1 |
| P2 | Sentiment | 3/59 | 53 | 0 | 47 | 0 |
| P2 | Follow-up | 2/59 | 57 | 2 | 53 | 0 |
| P2 | Serious concern | 3/59 | 55 | 2 | 50 | 0 |
| P2 | Testimonial | 2/59 | 56 | 2 | 54 | 1 |

At 0.9, Jev would still retain a serious-concern mismatch on DEV-029 in P0 and P1, and a testimonial mismatch on DEV-027 in all three conditions. For P0 DEV-029, reported confidence is 0.91 while the selected option's distribution value is 0.94. The two fields must not be treated as the same measure. The [feed](../public-site/jev-confidence-findings.json) lists every wrong record with both values, plus retained and withheld counts at 0.5, 0.7 and 0.9.

For example, the 0.9 cutoff would withhold six P0 testimonial answers: five that matched the draft reference and one that disagreed. The 54 retained answers would still include one disagreement. A stricter cutoff therefore reduces coverage as well as removing some mismatches; this test does not establish a suitable operating threshold.

These thresholds describe **counterfactual withholding of individual field decisions**. Jev did not abstain. Each threshold's retained and withheld valid counts add to 60 in P0 or 59 in P1/P2; the latter also report one unavailable invalid output against the fixed 60-record denominator. `insufficient_information` remains an actual classification option, not an abstention. The confidence values have no demonstrated calibration as probabilities of being correct. P0 was historical, and P1/P2 each have one pass, so the table does not establish a causal prompt effect or a fair threshold comparison with Kev, Laya or AnyJev.

The [builder](../scripts/build_jev_confidence_findings.py) regenerates the feed offline. `python3 scripts/build_jev_confidence_findings.py --check` verifies the saved bytes against current source-bound evidence; [tests](../tests/test_build_jev_confidence_findings.py) cover invalid exclusion, malformed confidence, prediction mismatch, request drift and the distinction between reported confidence and selected-option probability.
