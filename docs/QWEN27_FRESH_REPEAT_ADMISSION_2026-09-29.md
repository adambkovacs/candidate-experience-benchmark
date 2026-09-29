# Qwen27 fresh matched-series admissions

These are offline plans for two separate fresh studies: `openrouter-paid-qwen3.8-27b-medium` and `openrouter-paid-qwen3.8-27b-xhigh`. No provider calls or allocations were made. The aggregate OpenRouter cap remains $10; the requested increase to $17 is pending. The proposed child budgets below are not funded.

The [historical audits](HOSTED_REMAINING_PAIR_AUDIT_2026-09-28.md) classify both old triples as descriptive because continuation rows departed from the original counterbalanced schedule and lack fields required by the unchanged paired evaluator. The [per-configuration audit records](../results/prompt-comparison-v1-2026-09-24/paired-reports/hosted-remaining-audit-v1/index.json) retain the source-bound decisions and row-level failures. The new manifests use only the exact saved request bodies: all 60 IDs per condition were present, and each request body matched its saved prompt and input feedback. Continuation request hashes were checked against their attempt journals where the row omitted the hash. No reference-label file was read.

Each proposed fresh series has three passes with condition orders P0/P1/P2, P1/P2/P0, and P2/P0/P1. Each condition schedules a three-record smoke followed by up to 60 development requests. Requests use single-record fresh contexts and the exact historical model, provider, quantization, effort, sampling, schema, and token controls. The fresh plan stops on an invalid output; it has no retries or replays. Existing historical failures remain recorded as historical outcomes and are not resubmitted.

Historical failures kept in the source evidence:

- Medium: P0 has one service error, P1 has one service error, and P2 has none.
- Xhigh: P0 has one invalid output, P1 has none, and P2 has one service error.

The saved historical endpoint records show `qwen/qwen3.8-27b` through `deepinfra/bf16`, 262,144 context tokens, and prices of $0.15/M input and $1.875/M output. This is historical route evidence only. A fresh live endpoint, status, price, and parameter check is required before any dispatch.

For medium, the three-pass known-cost proxy is $0.596691675. The separate unknown-bound sensitivity is $0.282009600, for a combined sensitivity of $0.878701275. The maximum request reserve is $0.047001600. The proposed child budget is $1.00, leaving $0.121298725 over the combined sensitivity.

For xhigh, the three-pass known-cost proxy is $0.552591675. The separate unknown-bound sensitivity is $0.141004800, for a combined sensitivity of $0.693596475. The maximum request reserve is $0.047001600. The proposed child budget is $0.80, leaving $0.106403525 over the combined sensitivity.

Each one-pass cost proxy uses 189 historical rows: 180 development rows and nine smoke rows. The unknown sensitivity multiplies the historical unknown-charge bounds by three; it is not part of the known-cost proxy. Each full series schedules 567 calls. Reserving all 567 at the maximum per-request amount would be $26.649907200, a stress bound rather than a spend forecast. A future runner must reserve sequentially, settle known charges, retain unknown reserves, and stop before any call that does not fit its funded child budget. Budget figures do not guarantee completion or final cost.

The [offline planner](../scripts/qwen27_fresh_repeat_study.py) creates and verifies the six hash-bound manifests. Four tests cover request-level source proof, counterbalanced input-only phases, preservation of historical failures, separate cost bounds, and hash rejection. The manifests and source hashes are recorded below.

The medium manifest hashes are:

- Fresh 1: `6824a780ddfe33a34fb547fa27c9426ce518150f1145617b436ab66acef796f0`
- Fresh 2: `692f42760d5843860563e01d86c3b3fec849b31254e1761fea0ad177f01e701b`
- Fresh 3: `d5953fdcf75aac340ebc841c9a018976f7f0234bb0b3ee4015cbf9904b11c35a`

The xhigh manifest hashes are:

- Fresh 1: `aec48d2734c47016e4a5bc906cbedc839b3bf9a727ed966b98528d857ecf013b`
- Fresh 2: `d053f7da53652737c39d6a0c5d98cbfa1ebbde03a64e84f6ac43df27c54142ca`
- Fresh 3: `80e21da94f6cd71ecc32317c35a026985be93a1812cbcad13bc90ac301c03f18`

## Offline execution candidate

The [execution controller](../scripts/qwen27_fresh_repeat_execution.py) is an offline candidate for the six plans. Its [separate execution manifest](../results/repeatability-v1/qwen27-fresh-matched3-v1/execution-manifest.json) (SHA-256 `74ef71977f41425675d413dc7927200d87e27c97f41a786a7c17439e1f1560e6`) binds both configuration triples, the planner and controller bytes, the HTTP opener, and the paid transport and budget libraries. Its status is `offline_frozen_not_approved`; a frozen manifest is not permission to spend. Neither proposed child partition has been allocated.

For each stage, the controller requires a stage-specific root review receipt, the exact frozen plan and execution-manifest hashes, and an active child partition with the configuration's proposed cap ($1.00 for medium, $0.80 for xhigh). It checks the live model and endpoint metadata against the saved DeepInfra `deepinfra/bf16` route, limits, parameters, and price, then reconstructs the 60 request bodies before loading a key. It opens the child ledger under its exclusive lock before making a phase claim. Every request is durably reserved before a provider call. The controller captures at most 16 MiB of response bytes, HTTP status, and selected headers in a durable raw journal before parsing a 200 response; HTTP error bodies have the same bound. The attempt, timing, and known charge are retained separately. A malformed or truncated response with no known charge retains the full $0.047001600 bound. A stopped or claimed phase cannot be replayed by this controller.

Fresh passes and conditions remain in their frozen counterbalanced order. A development stage requires three known-billed valid smoke outcomes plus an explicit hash-bound inspection. Later conditions and passes require strict predecessor closure. The new plans stop after an invalid output, a service error, an unknown charge, or a budget failure. Historical medium's different invalid-output policy remains source evidence; it does not govern this fresh series. Each child cap is an admission ceiling, not a completion guarantee.

The offline tests use temporary ledgers and mocked provider transport. They cover both efforts, the exact live-route check, a full smoke-to-development transition, a duplicate-claim stop, a billed invalid output, an unknown-charge 429, malformed and oversized 200 responses, bounded HTTP error bytes, and child lock/cap failure before a request. No hosted completion, key read, production allocation, or production stage claim was made. Raw response and attempt files may contain private provider fields and must stay local until a separately reviewed sanitized public projection exists; the controller does not publish them. Dispatch remains gated on funding, independent code review, a reviewed root receipt, and fresh live route and price evidence.
