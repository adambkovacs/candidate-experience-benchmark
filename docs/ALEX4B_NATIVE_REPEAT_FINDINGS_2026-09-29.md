# Alex OpenJev 4B: stable answers, with recurring serious-concern misses

All three fresh native passes returned valid classifications for the same 60 synthetic reviews. Each matched all four provisional reference labels on **39/60** reviews. No review changed any label between passes. The larger model improved agreement over the separate 0.8B native study, but repeated the same eight missed serious-concern cases in every pass.

| Decision | Matches in each pass | Class-level finding |
| --- | ---: | --- |
| Sentiment | 49/60 | Matched 11/11 positive, 26/31 negative, 7/8 mixed and 5/8 neutral references; neither insufficient-information reference matched. |
| Follow-up needed | 57/60 | Found all 35 reference-positive follow-ups; two reference-no reviews were marked yes. |
| Serious concern | 47/60 | Found 17/25 reference-positive concerns; the other eight were marked no. |
| Testimonial potential | 57/60 | Found 8/9 reference-positive testimonials and matched 49/50 reference-no reviews. |
| All four together | 39/60 | All four labels must match on the same review. |

The 0.8B model scored 3/60 all-field matches in each of its three passes. It predicted testimonial yes on 59 reviews, compared with 10 for the 4B model. The 4B result therefore reflects a substantial change in that decision pattern, not merely identical output formatting. Both native series produced unchanged classifications across their three passes. These observations apply to the tested models, label hypotheses and synthetic data; they do not establish performance on real candidate feedback.

This is native NLI classification: each review is scored against 14 label hypotheses. P1/P2 chat-instruction variants do not apply to this native interface. The historical observation stays separate from the fresh three-pass series. The references are AI-reviewed provisional labels, and the 180 responses reuse 60 reviews rather than adding independent cases.

## Runtime and measurement limits

The frozen model is `qwen3.5-4b-nli-v2`, revision `f004f37e52695d6ddfb914a64dbf93942839ba1e`, running unquantized float32 on MPS with batch size four and context limit 4,096. The machine is an Apple M4 Max, Mac16,5, with 128 GB memory. Exact package and artifact hashes are recorded in the [frozen manifest](../results/repeatability-v1/alex-openjev4b-native-p0-v1/manifest.json).

Each pass recorded 1,251,194 native NLI input-token positions. These are model input positions, not billed API tokens. Client prediction durations total 4,729.86, 4,422.31 and 4,465.06 seconds for passes one, two and three. They include local runtime overhead. Pure inference time, generated output-token counts and attributable hardware/electricity cost are unavailable; no hosted charge was incurred by these local passes.

The [public report](../public-site/alex-native-repeats.json) binds the closed raw probabilities, projected outputs, inspected smokes and completion files. The third-pass record SHA-256 is `735d57d41427f43ff4a0befa0608e3e3cffe16858d8a7881fbc9570bcefdee50`. See the separate [0.8B findings](ALEX_NATIVE_REPEAT_FINDINGS_2026-09-28.md) for that model's class distribution.
