# Gemma 26 repeat 2, P1

All 60 development requests completed with valid categorical responses after the three-record smoke was inspected. This is one completed condition in the six-condition additional-repeat schedule.

Exact route: `google/gemma-4-26b-a4b-it`, `deepinfra/fp8`, FP8, reasoning disabled, OpenRouter HTTP v1. Remote hardware is undisclosed. Temperature 0, 4,096 output-token limit, strict JSON schema, no fallback or retries. The [frozen manifest](../manifest.json) preserves exact requests and source hashes; reference labels were excluded.

| Phase | Requests | Input tokens | Output tokens | Reported charge USD | Summed client request seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| smoke | 3 | 4917 | 107 | 0.00038057 | 3.806 |
| development | 60 | 98488 | 2135 | 0.00762006 | 113.114 |

Pure inference time is unavailable. Client request duration includes transport and local handling. Costs are reported request charges, not invoice reconciliation. The $0.20 shared-cap allocation remains open.

Offline comparison against the original provisional v0.2 labels gives 52/60 agreement on all four fields, the same total as the historical P1 pass. Serious-concern classifications changed for DEV-018 and DEV-022. This illustrates why a stable total does not prove stable per-review decisions. References were opened only for this post-inference comparison.
