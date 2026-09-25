# Gemma 26 repeat 3, P0

All 60 development requests completed with valid categorical responses after inspection of the three-record smoke. P0 now has three completed passes, including its eligible historical first pass.

The [frozen manifest](../manifest.json) preserves exact requests and controls: `google/gemma-4-26b-a4b-it`, `deepinfra/fp8`, FP8, reasoning disabled, temperature 0, 4,096 maximum output tokens, strict JSON schema, no fallback or retries. Runtime: OpenRouter HTTP v1. Remote hardware is undisclosed. Reference labels were excluded from inference.

| Phase | Requests | Input tokens | Output tokens | Reported charge USD | Summed client request seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| smoke | 3 | 4377 | 108 | 0.00034311 | 8.723 |
| development | 60 | 87688 | 2174 | 0.00687732 | 115.463 |

Pure inference time is unavailable. Client request duration includes transport and service overhead. Charges are reported by the provider, not reconciled to an invoice. The shared-cap allocation remains open.

Offline evaluation against provisional v0.2 references gives all-four scores of 53/60, 52/60 and 52/60 across the three passes. At least one classification changed across passes for DEV-018, DEV-022. The original reference labels remain unchanged.
