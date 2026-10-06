# Qwen3.5: first P2 result

## Closed result

The [development completion](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P2/development.completion.json) records 60 attempted and 60 saved responses. Nine are intrinsic invalid outputs. The [host audit](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P2/development.host-audit.json) passed and binds the completion and approved development receipt.

The source-bound reporter independently accepted all 60 IDs in order, checked their request hashes and frozen SDK controls, reclassified each raw response, and reproduced these scores:

- Valid outputs: 51 of 60, or 85.0%.
- All four fields match the reference: 50 of 60, or 83.3%.
- Sentiment matches: 51 of 60, or 85.0%.
- Follow-up matches: 51 of 60, or 85.0%.
- Serious-concern matches: 50 of 60, or 83.3%.
- Testimonial-potential matches: 51 of 60, or 85.0%.
- Invalid outputs: 9 of 60, or 15.0%.

All nine invalid outputs failed as `non_json`; none were repaired or replayed. Their IDs are DEV-005, DEV-006, DEV-013, DEV-015, DEV-018, DEV-022, DEV-028, DEV-057, and DEV-058.

DEV-030 is the only valid response that missed a reference field. The model returned `serious_concern_reported: no`; reference v0.2 says `insufficient_information`. Its other three fields matched. The remaining 50 valid responses matched all four fields.

The report has no P2 pairwise flips because only fresh1/P2 is closed. The descriptive fresh1/P0 composite remains outside the clean pass set. Its 47 all-four matches cannot supply clean P0 versus P2 evidence, and it must stay out of paired metrics.

## Usage and host limits

The 60 client calls took 4,845.771 seconds in total. The mean was 80.763 seconds, the median 70.773 seconds, and the observed range was 26.062 to 165.558 seconds. These are client wall-clock durations. They include runtime and transport overhead and do not isolate model inference time or model-load time.

The calls used 161,670 input tokens, 141,624 output tokens, and 303,294 total tokens. The LM Studio records do not expose a separately verified reasoning-token total. Local electricity use and dollar cost were not measured.

The host audit found the same boot and sleep-wake count at the recorded checks, with AC power before and after the phase. This supports `matching_pre_post_checks`. It does not prove continuous AC power between checks and does not measure energy use.

## Evidence chain

The [approved successor manifest](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/manifest.json) has SHA-256 `5b74a42cfa922219813c4e83037f05cbe4f769094c3776e5a9a48f24ed8423ae`. It binds the [successor controller](../scripts/qwen35_remaining_phases_v1.cjs) at `25628fb191433c83991b31de34db67760f184d7f973bb8825d4dedfc36447e33` and the [descriptive P0 composite review](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-p0-unsent-suffix-v1/composite.root-review.json) at `469188fcc9d84d431cef68c8a2695ac6ede728b87351894d38148ffa7cf5210e`.

The [development receipt](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P2/development.root-review.json) has SHA-256 `c168d01f92007bbf9f01130500e7ff0343639a04cc604c4609a2f6636488196e`. The claim and host audit both bind that receipt. The completion has SHA-256 `eda8c82adf5642d6fca8704fea3959c89b568e5f53ee1bd6166af5516a203a1b` and binds the raw, records, and journal hashes.

The three-record smoke completed without invalid outputs. Its [inspection](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1/fresh1/P2/smoke-inspection.json) is approved and binds the smoke completion, raw evidence, and parsed records.
