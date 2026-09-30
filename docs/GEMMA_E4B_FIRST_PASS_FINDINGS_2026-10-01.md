# Gemma E4B thinking-off: first prompt comparison

All three first-pass phases returned 60 valid responses. The base prompt matched all four reference answers on 38 reviews; classifier instructions matched on 41, and the decision procedure on 42. These are first-pass observations, not a demonstrated prompt improvement. Repeated passes are still running.

| Prompt | Valid / 60 | All four match / 60 | Sentiment / 60 | Follow-up / 60 | Serious concern / 60 | Testimonial / 60 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | 60 | 38 | 46 | 58 | 52 | 57 |
| P1 | 60 | 41 | 48 | 58 | 52 | 57 |
| P2 | 60 | 42 | 48 | 58 | 54 | 58 |

The same 60 fictional reviews appear in every phase. A match means agreement with the provisional v0.2 references; it does not establish hiring accuracy. All references stayed outside inference requests and were used only for offline scoring.

We ran the exact Q4_K_M artifact locally because the dated OpenRouter catalog had no matching E4B route. The frozen plan records the Apple M4 Max hardware, 8,192-token context, sampling controls and load-time cache observation. The selected backend was 2.22.0; the loaded engine version could not be independently read. Client durations include overhead and are not pure inference times. Token counts are local runtime reports. Hardware and electricity costs are unavailable.

Sources: [saved first-pass evidence](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh1/), [frozen plan](../results/repeatability-v1/small-local-v1/manifest.json), [hosted-route audit](../results/route-audits/small-local-admission-20260930T200956Z/catalog-audit.json), and [public repeat report](../public-site/small-local-repeats.json). The publication cutoff is evidence commit ce384ea8; later in-flight responses are excluded.
