# Gemma 26B reasoning-on fresh repeat admission

This is a reviewed offline preparation, not a completed benchmark or spending authorization. No new allocation or provider requests have been made. The proposed $0.40 child cannot be funded from the current $0.04151065850 unallocated headroom; the aggregate OpenRouter cap remains $10 unless the user changes it.

The exact route is `google/gemma-4-26b-a4b-it`, DeepInfra `deepinfra/fp8`, reasoning enabled, temperature 0, maximum 4,096 output tokens, strict structured output and no fallback. The [planner](../scripts/gemma26_on_fresh_repeat_study.py) reconstructs input-only requests from saved evidence. Historical P2 continuations changed the planned schedule, so none of those historical passes is counted as a pass in this fresh series. Their invalid outputs and service failures remain intact.

The three fresh passes rotate conditions as P0/P1/P2, P1/P2/P0 and P2/P0/P1. Each condition has a separate three-record smoke and 60-record development phase: 567 requests total. No request contains reference labels or previous predictions. A separate stage receipt must bind the controller, all three frozen manifests and budget allocation. The [execution candidate](../scripts/gemma26_on_fresh_repeat_execution.py) checks the live route before key access, holds the child lock, reserves each call, retains unknown-charge bounds and refuses replay. Development requires inspected smoke evidence; later phases require exact ordered predecessor closure.

Historical known charges imply $0.19825584 for three full passes. Adding a sensitivity based on historical unknown-charge bounds gives $0.31671216. The proposed $0.40 child leaves a planning margin; none of these figures guarantees the final bill. The maximum per-call reserve is $0.01974272. Reserving all 567 requests at that maximum would be $11.19412224, a stress bound rather than a forecast. Actual dispatch reserves sequentially and stops before sending when the next full reservation does not fit.

Independent review approved the frozen candidate, and ten offline tests pass. They exercise real child-ledger locking, known settlements, retained unknown bounds after HTTP failure, an inspected smoke followed by 60 mocked development responses, receipt bindings and strict predecessor checks. Tests made no provider calls.

Residual limits: a cap stop is safely before HTTP but uses the generic `phase_aborted` journal event. Plan reconstruction requires the private hash-bound historical P2 source retained on the execution host; a clean public checkout cannot authenticate those missing original bytes. Raw future attempts and responses are ignored by Git. Public reporting must use a separately reviewed sanitized projection. `elapsed_seconds` is request-to-record timing including evidence writes and settlement, not pure inference time.

Frozen manifest SHA-256 values:

- fresh1: `be8addff3bd3e1c4780e496dfee4dd8d92f2c2ad5996e4d616b199e080792922`
- fresh2: `01d7ae55efe0d5fdbaaaa560c1c7b71ab964b1470980f44d1c2396ee5e318e07`
- fresh3: `3ffb6746379aa765524e9e7e8e397dff998821399c484569da196e48466e853c`

See [the remaining hosted roster](HOSTED_PENDING_MATRIX_2026-09-29.md) and [the historical pairing audit](HOSTED_REMAINING_PAIR_AUDIT_2026-09-28.md). Funding, fresh route admission and exact stage receipts remain prerequisites to dispatch.
