# Draft subscription batch P0 schedule

This is an offline planning snapshot, not a frozen execution roster. The [source-bound artifact](../results/subscription-batch-p0-schedule-draft-2026-09-23.json) accounts for all 52 entries in the Codex and Claude registries, including historical exclusions and overlapping result views. No reference labels were read and no requests were sent.

The [pairing protocol](PROMPT_VARIANTS.md#controls-and-execution) requires the same context unit across P0/P1/P2. The user's batch10 requirement therefore needs 15 explicitly scheduled new baselines:

| Model | Efforts | New P0 configurations |
|---|---|---:|
| Claude Sonnet5 | low, medium, high, xhigh | 4 |
| Claude Opus5 | low, medium, high, xhigh | 4 |
| Claude Fable5.1 | low, medium, high, xhigh | 4 |
| Claude Haiku4.5 (`claude-haiku-4-5-20251001`) | not applicable | 1 |
| Codex GPT5.6 Luna | low | 1 |
| Codex GPT6 Astra | low | 1 |

Each new baseline gets a distinct ID and output files. Preserve the old single-record results as historical configurations; never pair them with batch variants. Sonnet5-low first-pass and retry-inclusive outputs describe one configuration, so they require one new baseline, not two.

For each configuration, schedule one three-record P0 smoke request, inspect it, then six development requests of ten records. This is **90 development requests plus 15 smoke requests**, before any explicitly recorded retries. Freeze membership as DEV-001–010, DEV-011–020, DEV-021–030, DEV-031–040, DEV-041–050 and DEV-051–060, in that order within each condition. Reuse precisely those boundaries for P1/P2. New P0 model, effort, runtime, generation limits, schema, parser and isolation settings must match its variants.

There are 24 existing batch10 P0 reuse candidates: 20 Codex configurations and four Claude Opus5.5 efforts. Their full request bodies exist. This is an inventory finding, not blanket extractor or protocol approval. Reuse them when the strict evidence and unchanged runtime/control requirements are satisfied; do not rerun them merely because their results are historical. Record historical timing/cache and competing-work limitations. Existing full-body retry histories remain included in accounting.

GPT6 Sol-low and Luna-low already use batch10, but six early attempts across those two histories lack full saved request bodies. This is a raw-evidence gap, not a context-unit mismatch. They remain pending evidence resolution in this draft. Hash reconstruction does not satisfy the strict full-body extractor; failed attempts cannot be silently removed. This draft does not schedule replacement P0 runs for those two configurations or silently exclude them.

Across all 41 unique in-scope subscription configurations, P1/P2 would require 492 development requests (12 per configuration), subject to the unresolved gates. With the 90 new P0 requests, that is a conditional 582 development requests. The 39 configurations outside the two evidence gaps account for 558 of those requests. If each condition needs one separate three-record smoke, the corresponding all-roster planning total is 97 smoke requests: 45 for the 15 new-P0 configurations and 52 for the 26 existing batch configurations. These are request counts, not token or quota estimates, and exclude retries and any later evidence-repair P0 decision.

Before final freeze, reconcile executable baseline work and every completed, excluded or blocked configuration; verify token/context fit without truncation; audit exact runtime controls; and counterbalance P1/P2 order across configurations. The Claude batch runner now explicitly accepts the 13 planned Sonnet5/Opus5/Fable5.1/Haiku configurations alongside the existing four Opus5.5 configurations. Offline roster, command and preview tests cover all 17 combinations; Haiku omits the effort flag and accepts only not applicable. Max, ultra, unknown model IDs and incompatible effort combinations are rejected before authentication. This implements the adapter prerequisite, not the runtime smoke or token/context gates; no new baseline has launched. Existing user authorization covers the intended subscription work; these are technical protocol gates, not a request for new permission. No paid API fallback, credit redemption, overage, new model, max or ultra effort is introduced. Preserve completed historical max results without scheduling future variants for them.

## P0 preparation scheduled

The [separate P0 execution manifest](../results/subscription-batch-p0-execution-2026-09-23.json) now binds the fifteen necessary new batch baselines, clean inputs, schema, controller sources and unchanged P0 policy before their smoke calls. These may run alongside the remaining local baselines through existing subscriptions. Each has a separate smoke gate and exclusive artifacts; prior single-record results remain intact. P1/P2 inference and the final paired roster remain gated. No compatible batch baseline is scheduled for an unnecessary rerun.
