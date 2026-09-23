# Codex subscription configurations

Current September23 state: GPT-6 Luna low has20 valid development records and Sol low has10, in a separate batch10 workflow. Both medium smoke batches passed; high smoke batches timed out, and xhigh was not attempted. Repeated empty timeouts paused Luna and higher-effort requests. The bounded Sol continuation also timed out at600s after healthy read-only checks and no reported official service incident. Both development results remain partial and all Codex inference is stopped. Max and ultra are excluded from future runs. Historical completed results remain intact.

The user explicitly requested Sol and Terra alongside Luna and Astra. The installed account catalogue fetched 2026-09-21 advertises `gpt-5.6-sol` and `gpt-5.6-terra`, each with low, medium, high, xhigh, max and ultra. Sol defaults to low and Terra to medium. Evidence: `results/codex-catalogue-2026-09-21.json`. Catalogue client 0.155.0 differs from the executable runner 0.154.0; live smoke results must establish compatibility.

Each record runs in a fresh ephemeral context outside the repository, with only the policy and synthetic feedback. Reference labels never enter inference. The adapter strips API credentials, requires ChatGPT sign-in and disables user rules, memory, skills, MCP and supported tools. Built-in CLI instructions remain; server model revision is not exposed. Ultra is advertised with automatic task delegation; any tool or delegation event invalidates the primary isolated run.

Smoke artifacts and development attempts remain separate. Three smoke responses must be inspected before 60 development records. The new Sol/Terra request received fresh scoped approval: both low-effort smoke tests completed with three valid outputs, no observed tools and no event parsing failures. At that September 21 checkpoint, full development runs were held pending the batching decision and the quota check showed 5% weekly remaining. Those observations are historical; remaining development runs now use batches of ten after an inspected smoke. Fresh scoped reviews also approved resuming the existing Luna/Astra low-effort runs. No paid API fallback or credit redemption is permitted.

Sources: [Codex authentication](https://learn.chatgpt.com/docs/auth), [noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode), [configuration](https://learn.chatgpt.com/docs/config-file/config-reference), and the installed account catalogue above.

Luna low and Astra low each completed 60 unique valid development outputs after approved continuations. Each timing view includes 64 attempts: 60 completed records plus four initialization failures. Original and reclassified copies are not double-counted; smoke artifacts are excluded. No observed tool or delegation events occurred. Records and timing evidence are linked by `results/codex-run-registry.json`.

## September 23 roster update

The fresh installed account catalogue confirms `gpt-6-sol` and `gpt-6-luna`. Future efforts are low, medium, high and xhigh only. The user removed max and ultra from future runs; the adapter rejects both. Historical 5.6 Sol/Luna artifacts remain available. Adding GPT-6 models does not remove earlier requested models: 5.6 Sol, Luna and Terra plus GPT-6 Astra remain in scope. Remaining runs use batch10 after smoke inspection and service recovery.

Authentication remains ChatGPT subscription. The initial September 23 quota check reported 1% weekly usage, ordinary use allowed and zero paid-credit balance. No reset was redeemed. Evidence: `results/codex-catalogue-2026-09-23.json`. Smoke batches remain separate from development. The batching decision was subsequently resolved in favour of batches of ten; later quota and run states are recorded below.

## Batch workflow

Remaining subscription configurations use batches of 10, as a distinct workflow. Each batch has a fresh context with policy once and ordered fictional feedback records. Exact returned ID coverage and all four judgments are validated. Raw batch attempts retain request timing, usage and tool audits. Exploded prediction rows carry an amortized time share; the report suppresses per-record latency percentiles and derives batch latency/throughput from raw attempts. Smoke batches contain 3 records and never enter development timing.

GPT-6 Sol/Luna were rejected before generation by the older 0.154.0 executable. The installed ChatGPT bundled executable is 0.155.0-alpha.16 and exposes the same isolation flags; separate smoke retries use that runtime, preserving prior failures. Full batches require a successful inspected smoke.

The sequential Luna retry also reached its documented600s timeout, so no further blind retry was launched. Read-only version/help/login checks each completed within1.1s; ChatGPT sign-in remains valid. A fresh quota check shows21% weekly usage and ordinary usage allowed, with zero paid-credit balance and no reset redeemed. The cause of inference-command stalls remains unconfirmed. `results/codex-startup-diagnostics-2026-09-23.json` records these checks.

The new batch runner now writes and fsyncs an exact prompt/schema journal before each request, then durably records completion. Earlier request payloads were reconstructed and their prompt hashes verified in `results/codex-request-reconstruction-2026-09-23.jsonl`; those records explicitly disclose that reconstruction occurred after execution.

Final saved September23 batch coverage: Sol low10 valid records,10 failed records and40 unattempted; Luna low20 valid records,10 failed records and30 unattempted. Each failed batch was attempted at300s and then600s with concurrency1 on the retry. No further inference is active. Both attempts contribute to service/runtime timing, which must not be described as model-only speed.

Terra 5.6 low subsequently completed all 60 development records in six sequential batches of ten through CLI 0.155.0-alpha.16. All outputs were valid, with no observed tools, parsing failures, metadata warnings or retries. The separate three-record smoke passed before development. Exact prompts and schemas were journaled before each request; smoke is excluded from development scoring and timing. See `results/codex-gpt-5.6-terra-low-batch10-2026-09-23/evaluation.json`.
