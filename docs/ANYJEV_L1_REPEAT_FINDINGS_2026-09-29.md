# AnyJev L1: two calibrated passes

The first two direct-native L1 passes each produced 60 valid outputs and matched all four provisional reference labels on **6/60 reviews**. Each pass matched sentiment on 38/60, follow-up on 16/60, serious concern on 31/60 and testimonial potential on 49/60. Their 60 four-label prediction vectors are identical, with zero pairwise flips. The third pass remains unscored, so the planned three-pass range is unavailable. Agreement across two or three runs does not prove deterministic behavior.

Both passes have the same follow-up errors. The model chose "insufficient information" for 41 reviews, compared with one such reference label. This included 21 of the 35 reference-positive follow-up cases and 19 of the 24 reference-negative cases. It identified 14 of 35 reference-positive follow-up cases. For serious concerns, it identified nine of the 25 reference-positive cases and labeled the other 16 "no."

The testimonial count also needs context. In both passes the model identified eight of nine reference-positive testimonials but marked nine reference-negative reviews as positive. Its 49/60 agreement count includes those false positives. These labels are provisional AI-reviewed references, not human ground truth.

## Calibration and comparison limits

This configuration uses native AnyJev calibration and readout, not generated JSON from a hosted chat model. Five fixed outer folds each fit on 48 reviews and predict only the complementary 12. Each full pass contains 20 fits, one for each field in each fold, and 240 held-out field decisions. The three smoke records belong to held-out folds; development reuses their already fitted fold artifacts and predicts the other 57 records. No held-out reference label or previous prediction is included in an inference request.

The model is Qwen3-0.6B with the frozen local MPS bfloat16 runtime, batch size four and 4,096-token context on the M4 Max host with 128 GB memory. Exact source/runtime/model hashes are in the [frozen manifest](../results/repeatability-v1/anyjev-l1-direct-native-cv5-v1/manifest.json). This trained-on-development-folds protocol must be distinguished from uncalibrated specialist and hosted prompt runs; the scores do not establish a general calibration advantage.

Each pass accounts for 10,540,800 input-token positions across calibration and prediction operations. These are local processing counts, not billed API tokens. Client and isolated inference timing, output-token billing and local hardware/electricity cost are unavailable in this evidence and remain null. No hosted charge is inferred as zero.

The [public report](../public-site/anyjev-l1-repeats.json) binds the two completed passes' source files and includes confusion counts, class distributions, a paired comparison over all 60 valid IDs and measurement limits. It shows the fresh3 stage as claimed and unscored. The reporter verifies the native artifact's frozen backend path and hashed question key; that reporting correction changed no fitted artifact or prediction. A third completed pass is still required for the planned repeat summary.
