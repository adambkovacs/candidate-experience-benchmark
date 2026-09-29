# Qwen reasoning off: prompt differences and repeat variation

All nine planned prompt/pass combinations have closed evidence: **538 valid outputs and two service errors across 540 development responses** to the same 60 synthetic reviews. Both failed requests remain in the results. This is a descriptive continuation after provider interruptions, not a clean matched-three experiment.

| Prompt | Pass 1 | Pass 2 | Pass 3 | Reviews with changed labels across passes |
| --- | ---: | ---: | ---: | ---: |
| P0: base task |48/60|51/60|50/60|3/59 comparable reviews|
| P1: classifier instructions |51/60|50/60|50/60|2/59 comparable reviews|
| P2: instructions and decision tree |51/60|52/60|52/60|1/60 reviews|

Scores require all four labels to match the provisional reference on the same review. The fixed score denominator includes failures. Flip counts use only reviews with valid responses in every compared pass: DEV-006 is excluded from P0 flips and DEV-031 from P1 flips. Both remain in score denominators.

P2 has more all-field matches than P0 in each pass, by 3, 1 and 2 reviews. After restricting each paired comparison to reviews valid in both conditions, those differences are 2/59, 1/60 and 2/60. P1 is less consistent: its shared-valid differences are +2/59, −1/60 and +1/59. These are small descriptive differences on development data with changed dispatch timing after service errors. They do not establish a general prompt advantage.

P0's three changed reviews are DEV-005 and DEV-020 for sentiment, and DEV-028 for testimonial potential. P1 changes testimonial labels on DEV-010 and DEV-028. P2 changes only the testimonial label on DEV-027. Equal aggregate scores can therefore hide different classifications.

## Failures, route and measurements

The exact hosted route is `qwen/qwen3.6-35b-a3b`, AkashML `akashml/fp8`, reasoning off, temperature 0, maximum 4,096 completion tokens, strict structured output, with no provider fallback or automatic retry. First-pass P0 stopped at DEV-006 with HTTP 429; third-pass P1 stopped at DEV-031 with HTTP 429. Separately reviewed continuations sent only the remaining never-sent reviews. Neither failure was replaced.

Across all 567 development and smoke requests, observed provider charges total **$0.0803883**. The two unresolved charges retain upper bounds of **$0.0299008 each**, or **$0.0598016 combined**; these bounds are not invoiced charges. Both child allocations are terminally reconciled. Development-only usage and client request durations are recorded per phase in the [public report](../public-site/qwen36-off-second-interruption-findings.json); client durations include network and service overhead and are not pure inference time.

The public report binds raw evidence for successful phases and sanitized projections for interrupted phases. Readers can verify the published files and hashes, but cannot independently reproduce omitted private provider-error bytes. Original experimental manifests and failures remain preserved. The references are AI-reviewed provisional labels, and repeated reviews are not new independent cases.
