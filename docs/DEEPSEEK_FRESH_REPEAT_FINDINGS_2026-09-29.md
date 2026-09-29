# DeepSeek Flash: three-pass findings

All nine runs finished with 60 valid responses each. This series uses DeepSeek V4.1 Flash through OpenInference fp4, reasoning off, temperature 0, and the same 60 synthetic reviews. Each prompt condition was dispatched three times. References remain provisional v0.2.

**The more detailed prompts scored lower on all-four agreement in each matched pass.** P1 was 1–3 reviews below P0; P2 was 2–5 below P0. This was not a uniform decline across fields: both variants improved testimonial agreement by 1–2 reviews, while sentiment agreement fell. P2 also lost 3–4 serious-concern matches.

| Prompt | All four labels match, passes 1 / 2 / 3 | Reviews changing at least one label |
| --- | --- | --- |
| P0 | 48 / 49 / 48 out of 60 | 2 of 60 |
| P1 | 47 / 47 / 45 out of 60 | 3 of 60 |
| P2 | 43 / 45 / 46 out of 60 | 4 of 60 |

P0 is the original classification instruction; P1 adds classifier-role guidance; P2 adds an SOP and decision tree. The observed variation within each prompt condition matters when interpreting a small score difference. The P2 score changed by three reviews across passes without any prompt change. These are descriptive results for this configuration and dataset, not evidence that detailed instructions generally hurt performance.

## Agreement by field

| Prompt | Sentiment range | Follow-up range | Serious concern range | Testimonial range |
| --- | --- | --- | --- |
| P0 | 52–53 | 59 | 57–58 | 55 |
| P1 | 49–50 | 59–60 | 57–58 | 56–57 |
| P2 | 47–49 | 60 | 54–55 | 56–57 |

Every cell is a count out of 60. All-four agreement requires every field to match on the same review. Valid JSON alone does not establish agreement.

## Cost and timing

The 540 development requests and 27 smoke requests cost **$0.02913576** in observed provider charges, with no unknown-charge reservations. The unused $0.43086424 of the $0.46 allocation was released through terminal reconciliation. An allocation is a spending limit, not a charge.

The public report contains request token counts and summed client HTTP durations for each full run. These durations include transport and service overhead; pure inference time is unavailable. Smoke requests are excluded from per-development-run usage totals.

The same 60 reviews appear in every run, so 540 responses are not 540 independent cases. Serving revision, caching behavior and effective seed are not fully observable. Reference disagreements and class imbalance limit the conclusions.

Evidence: [source-bound report](../public-site/deepseek-fresh-repeats.json), [frozen plan](../results/repeatability-v1/deepseek-flash-off-fresh3-v1/admission-plan.json), [budget reconciliation](../results/repeatability-v1/deepseek-flash-off-fresh3-v1/budget-reconciliation.json).
