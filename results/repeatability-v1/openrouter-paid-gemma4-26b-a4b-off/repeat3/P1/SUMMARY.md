# Gemma 26 repeat 3, P1

All 60 development requests completed with valid responses after inspection of the three-record smoke. P1 now has three completed passes, including its eligible original pass.

The [frozen manifest](../manifest.json) preserves exact requests and controls: `google/gemma-4-26b-a4b-it`, `deepinfra/fp8`, FP8, reasoning disabled, temperature 0, 4,096 maximum output tokens, strict JSON schema, no fallback or retries. Runtime: OpenRouter HTTP v1. Remote hardware is undisclosed. Reference labels were excluded from inference.

| Phase | Requests | Input tokens | Output tokens | Reported charge USD | Summed client request seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| smoke | 3 | 4917 | 106 | 0.00038023 | 21.671 |
| development | 60 | 98488 | 2128 | 0.00761768 | 130.730 |

Pure inference time is unavailable. Client request duration includes transport and service overhead. Charges are reported by the provider, not reconciled to an invoice. The shared-cap allocation remains open.

Offline evaluation against provisional v0.2 references gives 52/60 all-four agreement in each of the three P1 passes. Decisions nevertheless changed for DEV-018 and DEV-022 across those passes. Stable scores therefore do not establish stable classifications. The reference labels remain unchanged.
