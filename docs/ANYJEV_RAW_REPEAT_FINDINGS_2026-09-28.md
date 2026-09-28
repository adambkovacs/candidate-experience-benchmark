# AnyJev raw: repeatable answers with poor agreement

The native AnyJev raw configuration produced the same four-field classifications on all 60 reviews in three separate P0 passes. Every pass had 60 valid responses, but **none matched all four provisional reference fields**. Repeatability alone would therefore give a misleading impression of this configuration's usefulness.

| Decision | Matches per pass | What the model predicted |
| --- | ---: | --- |
| Sentiment | 8/60 | Neutral for every review |
| Follow-up needed | 35/60 | Yes for every review |
| Serious concern | 25/60 | Yes for every review |
| Testimonial potential | 33/60 | Yes for 36 reviews; no for 24 |
| All four together | 0/60 | No review matched every reference field |

The first three decisions do not distinguish among the reviews. Their agreement counts largely reflect the reference class balance, rather than successful separation of cases. Testimonial predictions vary across reviews, but remain unchanged across the three passes. There are no categorical flips among the 60 comparable reviews. This is evidence about this exact raw readout and prompt construction; it does not establish the performance of AnyJev L0, its other calibration variants, or TypeSafe Jev. Those have separate configurations.

The configuration uses Qwen3-0.6B through AnyJev's native option scoring, MPS BF16, batch size four, context limit 4,096, and a fresh decider for each review. There is no generative P1/P2 prompt in this native protocol; generated controls remain separate work. The raw readout's normalized option scores are not calibrated probabilities of correctness.

The original 23 September pass is admitted using reconstructed prompts from pinned source and tokenizer, with all 240 recorded token lengths matching. Historical prompt hashes were not recorded. The two additional passes have frozen request signatures, separate inspected smokes, raw output before parsing, and exclusive execution claims. Their [manifest](../results/repeatability-v1/anyjev-raw-p0-v1/manifest.json) and [admission note](ANYJEV_RAW_NATIVE_P0_REPEAT_ADMISSION_2026-09-28.md) document the controls and historical limitation.

All scores use provisional version 0.2 references. They are AI-reviewed labels, not independently adjudicated human ground truth. The 180 recorded classifications are repeated measurements of the same 60 synthetic reviews, not 180 independent cases.

Recorded request durations include client and local runtime overhead. They are not pure inference timings or comparable hosted-service latency. Native input-token counts describe the scored prompts; they are not billed API usage. Local electricity and hardware costs, isolated inference time, and generated output-token counts remain unavailable. No missing measurement is treated as zero.
