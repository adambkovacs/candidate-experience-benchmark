# Alex 0.8B: testimonial overprediction across three fresh passes

Alex OpenJev 0.8B returned valid native NLI decisions for all 60 fictional development reviews in each of three fresh P0 passes. Only **3/60** reviews in each pass matched all four provisional reference answers. The clearest error pattern is testimonial suitability: the model predicted yes for 59 reviews, including 49 of the 50 reviews labeled no by the reference. It identified all nine reference-positive testimonials, but that sensitivity came with many false positives.

| Decision | Reference matches | What the class counts show |
| --- | ---: | --- |
| Sentiment | 39/60 | Matched 27/31 negative and 8/11 positive references, but only 1/8 mixed and 3/8 neutral references. |
| Follow-up needed | 37/60 | Matched 25/35 reference-yes and 12/24 reference-no reviews. |
| Serious concern | 20/60 | Found only 3/25 reference-yes concerns; 20 of those 25 were classified as insufficient information. |
| Testimonial potential | 9/60 | Predicted yes 59 times and insufficient information once; never predicted no. |
| All four together | 3/60 | Valid response structure did not imply agreement with the reference. |

All 60 reviews kept the same four decisions across the three passes; every pairwise comparison has zero flips on 60 shared-valid reviews. The 180 outputs are repeated measurements of the same 60 reviews, not independent cases.

These counts come from the [closed first-pass records](../results/repeatability-v1/alex-openjev08-native-p0-v1/fresh1/P0/development.records.jsonl) and the [source-bound analysis](../public-site/alex-native-repeats.json). The [report builder](../scripts/build_alex_native_repeat_findings.py) checks the smoke inspection, request signatures, raw probability captures, projected decisions and completion hashes before scoring. Invalid or missing answers would remain in the denominator of 60; none of these passes has any. References are [AI-reviewed provisional judgments](../data/pilot/proposed_labels.jsonl), not independently adjudicated ground truth.

All three fresh 0.8B passes are complete. The all-four score range is 3–3/60, with no per-field classification changes. This describes observed stability on these inputs, not a guarantee of deterministic future behavior. The separate [4B fresh series](ALEX4B_NATIVE_REPEAT_FINDINGS_2026-09-29.md) subsequently completed all three passes, with 39/60 all-field agreement and no changed classifications. Earlier historical results remain observational and are excluded from fresh repeat statistics. This native NLI procedure scores label hypotheses; P1/P2 chat-instruction conditions do not apply to it.

The frozen model is `qwen3.5-0.8b-nli-v2s-long`, revision `f004f37e52695d6ddfb914a64dbf93942839ba1e`, running without quantization in float32 on MPS, with batch size four and context limit 4,096. Hardware is an Apple M4 Max, Mac16,5, with 128 GB memory. The [frozen manifest](../results/repeatability-v1/alex-openjev08-native-p0-v1/manifest.json) records package versions and artifact hashes.

Each pass used 1,251,194 native NLI input-token positions across its 14 hypotheses per review. These are model input positions, not billed API tokens. Client prediction durations total 1,321.63, 1,300.14 and 1,450.02 seconds across passes one, two and three. They include local runtime overhead and are not isolated inference measurements. Generated output-token counts, pure inference time, and local hardware/electricity costs are unavailable.
