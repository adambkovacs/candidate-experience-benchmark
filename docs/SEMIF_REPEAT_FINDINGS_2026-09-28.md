# SemIf native repeat findings, 28 September 2026

All three native modes completed three full passes. Every pass contains 60 valid classifications, with no changed predictions within a mode. This closes the SemIf native P0 stability study; it does not close the wider benchmark roster.

| Native mode | All four fields | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direct | 36/60 | 50/60 | 56/60 | 50/60 | 54/60 |
| Serial | 35/60 | 50/60 | 56/60 | 49/60 | 54/60 |
| Shared | 35/60 | 50/60 | 56/60 | 49/60 | 54/60 |

These scores are identical across the completed passes of each mode. Valid means that an output satisfies the required classification format; agreement means that it matches the provisional reference labels. Neither establishes performance on independently sampled real reviews.

## What the field scores conceal

All three modes identify four of the nine reviews labeled suitable for a testimonial, missing five. They correctly return no on all 50 reference-negative reviews, and return no on the one review labeled insufficient information. Thus 54/60 testimonial agreement includes only 4/9 reference-positive matches. A classifier that always returns no already matches 50/60 references.

For serious concerns, all three modes identify 19 of 25 reference-positive reviews and return no on the other six. Direct mode matches all 29 reference-negative reviews; serial and shared match 28 of 29. Each mode correctly retains insufficient information for two of the six reviews with that reference label.

Serial and shared produce identical four-field predictions on all 60 reviews. Direct differs from them on only DEV-038, in the serious-concern field. Its one additional all-four match therefore comes from that single decision, rather than a broad improvement across the dataset.

## Comparison boundaries

This measures repeated categorical outputs through SemIf's native interface. P0 identifies that native condition; generative P1/P2 prompt variations do not apply to this interface. Three native modes are separate configurations, not three repeat passes of one configuration.

The frozen runtime uses local MLX Metal on an Apple M4 Max with 128 GB memory, BF16/FP32 parameters and no quantization. The [frozen manifest](../results/repeatability-v1/semif-native-mlx-v1/manifest.json) records the exact artifact, source revisions, package versions and request signatures. Reference labels and prior predictions are excluded from inference requests.

Saved elapsed durations are client-observed request times, not isolated model inference measurements. Input token counts are recorded; output-token counts, pure inference duration, and local hardware/electricity costs remain unavailable. These results do not support a hosted-versus-local speed ranking.

References remain version 0.2, AI reviewed and provisional. Repeated responses to the same 60 synthetic reviews do not add independent test cases. The [offline report builder](../scripts/build_semif_repeat_findings.py) verifies source hashes, raw predictions, stage completion and smoke admission before computing scores; it omits unfinished phases.
