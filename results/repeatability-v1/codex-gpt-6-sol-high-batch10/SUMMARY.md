# Codex GPT-6 Sol high repeatability run summary

Configuration: `codex-gpt-6-sol-high-batch10`, requested model `gpt-6-sol`, reasoning effort `high`, Codex CLI `0.155.0-alpha.16.4`, ChatGPT subscription, batch size 10, 600-second controller timeout. Frozen manifest SHA-256 values: repeat2 `a8ea850980a39ebc723c09e31d11c7e5a85701f3bb248b1d39630d630be07a48`; repeat3 `5572258506b20d3308e504399b4deea337fe1642325b37453d87076871152c1e`.

All six scheduled smoke phases completed with three ordered records each, strict four-field categorical responses, no repair, and passing response diagnostics. Raw smoke outputs were inspected and inspection receipts recorded before the corresponding development phase. The repeat2/P1 smoke was run and inspected by the root before this lane continued. No reference labels were read for inference or smoke admission.

| Pass | Condition | Smoke input/output tokens | Smoke elapsed (s) | Development input/output tokens | Development summed request time (s) | Amortized batch share per record (s) |
|---|---|---:|---:|---:|---:|---:|
| repeat2 | P1 | 10,468 / 165 | 16.571 | 64,743 / 3,729 | 147.038 | 2.451 |
| repeat2 | P2 | 11,368 / 167 | 17.950 | 70,153 / 3,155 | 139.247 | 2.321 |
| repeat2 | P0 | 10,292 / 172 | 22.672 | 63,699 / 3,567 | 145.129 | 2.419 |
| repeat3 | P2 | 11,366 / 171 | 15.640 | 70,155 / 3,632 | 149.675 | 2.495 |
| repeat3 | P0 | 10,290 / 179 | 17.059 | 63,695 / 3,553 | 148.032 | 2.467 |
| repeat3 | P1 | 10,466 / 180 | 18.205 | 64,733 / 3,556 | 159.051 | 2.651 |

Each of the six development phases has six successful batch attempts, 60 unique successful records, six request-completion events, and a terminal `phase_completed` journal entry. Overall, 42 requests completed successfully: six smoke calls and 36 development batches. Recorded usage totals 461,428 input tokens and 22,226 output tokens (smoke: 64,250 / 1,034; development: 397,178 / 21,192). Summed request elapsed time was 996.268 seconds (smoke 108.097; development 888.172). These timings cover the CLI/controller request path and are not isolated model-inference latency. Development per-record figures divide each ten-record batch duration across its ten records; they are amortized shares, not independent per-record measurements. Smoke timings are separate three-record requests.

Billing was through the ChatGPT subscription. No API-dollar cost is assigned; subscription cost for these calls is unknown. API keys were removed, no overage was enabled, and no reset credits were redeemed. The returned model revision and effective seed were not exposed; CLI patch equivalence and hidden serving revision remain observational limits.

All evidence is under this directory's `repeat2/` and `repeat3/` folders. No controller, frozen manifest, input, prompt, or reference file was changed. No commit was created.
