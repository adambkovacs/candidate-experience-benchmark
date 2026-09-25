# Gemma 26 repeat 2, P0

All 60 development requests completed with valid categorical responses after the three-record smoke was inspected. This completes the second pass across P0, P1 and P2 for this configuration.

Exact route: `google/gemma-4-26b-a4b-it`, `deepinfra/fp8`, FP8, reasoning disabled, OpenRouter HTTP v1. Remote hardware is undisclosed. Temperature 0, 4,096 output-token limit, strict JSON schema, no fallback or retries. The [frozen manifest](../manifest.json) preserves exact requests and source hashes; reference labels were excluded.

| Phase | Requests | Input tokens | Output tokens | Reported charge USD | Summed client request seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| smoke | 3 | 4377 | 108 | 0.00034311 | 13.642 |
| development | 60 | 87688 | 2175 | 0.00687766 | 167.707 |

Pure inference time is unavailable. Client request duration includes transport and local handling. Costs are reported request charges, not invoice reconciliation. The $0.20 shared-cap allocation remains open.

Offline comparison against the original provisional v0.2 labels gives 52/60 agreement on all four fields, compared with 53/60 in the historical P0 pass. Sentiment changed for DEV-022 and serious-concern classification changed for DEV-018. References were opened only for this post-inference comparison.
