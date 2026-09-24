# Qwen3 0.6B SDK prompt comparison

The four new P1/P2 development conditions each completed 60/60 records under the frozen Q4_K_M local setup. All 240 attempts have saved outputs and terminal records; there were no ambiguous timeouts. Intrinsic invalid outputs remain failed observations.

| SDK mode | Variant | Valid / 60 | All four correct / 60 | Sentiment | Follow-up | Concern | Testimonial |
|---|---|---:|---:|---:|---:|---:|---:|
| thinking-on | P0 | 31 | 0 | 16 | 25 | 14 | 7 |
| thinking-on | P1 | 50 | 1 | 30 | 41 | 24 | 9 |
| thinking-on | P2 | 58 | 2 | 31 | 42 | 19 | 10 |
| thinking-off | P0 | 0 | 0 | 0 | 0 | 0 | 0 |
| thinking-off | P1 | 4 | 0 | 4 | 2 | 1 | 0 |
| thinking-off | P2 | 2 | 0 | 1 | 1 | 0 | 0 |

The thinking-off P1/P2 responses were usually fenced JSON. The strict parser counted those as invalid without removing fences, leaving 4 and 2 valid outputs respectively. Thinking-on P1/P2 yielded 50 and 58 valid outputs. These are observed counts on one stochastic pass, not an estimate of a causal prompt effect.

The P0 columns refer to saved historical baselines; P1/P2 were later continuation runs. All scores use provisional AI-reviewed development references and count failed outputs as incorrect within the 60-record denominator. Model requests contained no reference labels.

Source hashes, paths and full field scores are in [comparison-summary.json](comparison-summary.json); per-condition raw output, attempt journal, terminal, and offline evaluation are under each condition directory. The fresh [route recheck](../local-route-recheck-2026-09-24/README.md) found no serving endpoint for this exact model at the time of the local run.
