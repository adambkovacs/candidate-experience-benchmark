# Codex GPT-6 Sol medium repeatability run summary

Configuration: `codex-gpt-6-sol-medium-batch10`, requested model `gpt-6-sol`, reasoning effort `medium`, Codex CLI `0.155.0-alpha.16.4`, ChatGPT subscription, batch size 10, 600-second controller timeout. Frozen manifest SHA-256 values: repeat2 `2a2ea73fee8c393c44d8224f15a5d58ff5e29bae3bb05df53d058967e5b46cc3`; repeat3 `b708bc3cbaba4cbde3210f3ce476dc6b6c315860ca666fc5c928279b9ff70b6c`.

All six scheduled smoke phases completed with three ordered records each, strict four-field categorical responses, no repair, and passing response diagnostics. Raw responses were inspected and inspection receipts recorded before development runs. No reference labels were read for inference or smoke admission.

| Pass | Condition | Smoke input/output tokens | Smoke elapsed (s) | Development input/output tokens | Development summed request time (s) | Amortized batch share per record (s) |
|---|---|---:|---:|---:|---:|---:|
| repeat2 | P2 | 11,368 / 154 | 18.877 | 70,149 / 3,053 | 221.261 | 3.688 |
| repeat2 | P1 | 10,466 / 158 | 26.918 | 64,735 / 3,036 | 197.831 | 3.297 |
| repeat2 | P0 | 10,294 / 179 | 25.816 | 63,709 / 3,216 | 289.856 | 4.831 |
| repeat3 | P1 | 10,466 / 157 | 26.627 | 64,745 / 3,273 | 398.427 | 6.640 |
| repeat3 | P0 | 10,294 / 179 | 27.209 | 63,709 / 3,108 | 185.977 | 3.100 |
| repeat3 | P2 | 11,368 / 155 | 17.038 | 70,234 / 2,914 | 468.171 | 7.803 |

Each development phase has six successful batch attempts, 60 unique successful records, six request-completion events, and a terminal `phase_completed` journal entry. Overall, 42 requests completed successfully: six smoke calls and 36 development batches. There are 18 successful smoke rows and 360 successful development rows across the six conditions. Recorded usage totals 461,537 input tokens and 19,582 output tokens (smoke: 64,256 / 982; development: 397,281 / 18,600). Summed request elapsed time was 1,904.007 seconds (smoke 142.484; development 1,761.522). These timings cover the CLI/controller request path and are not isolated model-inference latency. Development per-record figures divide each ten-record batch duration across its ten records; they are amortized shares, not independent per-record measurements. Smoke timings are separate three-record requests.

Billing was through the ChatGPT subscription. No API-dollar cost is assigned; subscription cost for these calls is unknown. API keys were removed, no overage was enabled, and no reset credits were redeemed. Fresh quota reads before each condition and its development phase reported `ordinaryUsageAllowed=true`; observed weekly usage rose from 90% to 92%. One quota read transiently failed before repeat2/P1; no new inference began until the next read succeeded. The returned model revision and effective seed were not exposed; CLI patch equivalence and hidden serving revision remain observational limits.

All evidence is under this directory's `repeat2/` and `repeat3/` folders. No controller, frozen manifest, input, prompt, or reference file was changed. No commit was created.
