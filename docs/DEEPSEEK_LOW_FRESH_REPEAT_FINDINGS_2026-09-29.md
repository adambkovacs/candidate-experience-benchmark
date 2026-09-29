# DeepSeek low effort: strong first-pass agreement, one truncated output

The first fresh P0 pass returned 59 valid classifications for the 60 synthetic reviews. All four labels matched the provisional reference on **58/60** reviews. Sentiment and testimonial labels matched on all 59 valid reviews; follow-up and serious-concern labels each matched on 58/60. This is one pass, not a completed repeat study or evidence of a stable advantage.

DEV-030 produced no valid classification: the provider reported `finish_reason: length` and 4,096 completion tokens, all attributed to reasoning. The output remains invalid and in the 60-review denominator. It was not repaired or repeated. This illustrates why label agreement and valid-output coverage must be reported separately.

The development calls recorded 85,717 input tokens, 32,176 completion tokens and **$0.01743459** in provider-reported charges. Completion tokens include reasoning under the provider's accounting. Their summed client durations were 4,095.35 seconds, including network and service overhead; pure inference time is unavailable. Smoke usage is separate.

The exact route is `deepseek/deepseek-v4.1-flash`, OpenInference `open-inference/fp4`, with low reasoning effort. P1's smoke is closed, but its development admission stopped before sending a request because the frozen endpoint selector found status `-2` instead of available status `0`. No substitute provider was used. Eight full prompt/pass combinations remain unfinished.

The [source-bound report](../public-site/additional-hosted-fresh-repeats.json) contains the closed pass, per-field confusion counts, token and cost evidence, and missing combinations. References are provisional AI-reviewed labels; the same 60 synthetic reviews are reused across repeats.
