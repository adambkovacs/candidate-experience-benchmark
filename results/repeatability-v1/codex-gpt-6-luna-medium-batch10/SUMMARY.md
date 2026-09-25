# Codex GPT-6 Luna medium repeatability run summary

Configuration: `codex-gpt-6-luna-medium-batch10`, Codex CLI `0.155.0-alpha.16.4`, ChatGPT subscription, requested model `gpt-6-luna`, reasoning effort `medium`, batch size 10, 600-second controller timeout. The two frozen manifests were verified at execution time: repeat2 SHA-256 `ac6b282c5527ea1a263fd26c474e09b9475d36c7666b6bbde122166e72aca1f3`; repeat3 SHA-256 `b29ff4b0de2712beaacd66680bf6efdcc3f4ad6293df176477d6b01759b74c45`.

All six smoke requests returned three ordered records with strict four-field categorical outputs, no repairs, and passing response diagnostics. Each raw response was inspected and an unchanged-acceptance receipt was written before its development phase. No reference labels were read during inference or smoke inspection. All 36 development batch requests completed `ok`; each phase has 60 unique `ok` records, six successful attempts, six request completions, and a terminal `phase_completed` journal event.

| Pass | Condition | Smoke input/output tokens | Smoke elapsed (s) | Development input/output tokens | Development summed request time (s) | Amortized batch share per record (s) |
|---|---:|---:|---:|---:|---:|---:|
| repeat2 | P2 | 11,185 / 111 | 18.414 | 69,079 / 2,028 | 119.482 | 1.991 |
| repeat2 | P1 | 10,287 / 111 | 17.107 | 63,667 / 2,032 | 117.657 | 1.961 |
| repeat2 | P0 | 10,117 / 111 | 15.546 | 62,631 / 2,028 | 133.446 | 2.224 |
| repeat3 | P1 | 10,285 / 111 | 14.981 | 63,661 / 2,030 | 116.819 | 1.947 |
| repeat3 | P0 | 10,113 / 111 | 14.987 | 62,623 / 2,030 | 128.132 | 2.135 |
| repeat3 | P2 | 11,185 / 111 | 16.252 | 69,075 / 2,032 | 113.903 | 1.898 |

Across these repeats, the runner recorded 42 successful requests: six smoke calls and 36 development batches. Total usage was 453,908 input tokens and 12,846 output tokens (smoke totals: 63,172 / 666; development totals: 390,736 / 12,180). Summed request elapsed time was 826.726 seconds (smoke 97.287; development 729.439). Timings include the CLI/controller request path and are not isolated model-inference latency. Development per-record figures divide each ten-record batch duration across its ten records; they are amortized shares, not individual-record measurements. Smoke was a three-record request and is kept separate.

Billing was through the ChatGPT subscription. No API-dollar cost is assigned; subscription cost for these calls is unknown. No API keys, overage, or reset credits were used. The returned model revision and effective seed were not exposed; the CLI patch transition and any hidden serving revision remain observational limitations.

Evidence is under this directory's `repeat2/` and `repeat3/` folders. No runner, frozen manifest, input, prompt, or reference file was changed.
