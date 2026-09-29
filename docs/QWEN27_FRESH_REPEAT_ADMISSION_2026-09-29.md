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

The plans are ready for independent controller review. Dispatch still requires a reviewed execution controller, a fresh live route check, and funded child partitions.
