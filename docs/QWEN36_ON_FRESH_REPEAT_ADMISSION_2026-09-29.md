# Qwen 3.6 reasoning-on fresh repeat admission

The [offline planner](../scripts/qwen36_on_fresh_repeat_study.py) has prepared three separate, input-only P0/P1/P2 passes for `openrouter-paid-qwen36-35b-a3b-on`. No allocation or provider request was made. The proposed $1.50 child is unfunded under the existing $10 aggregate OpenRouter cap. The [hosted pending matrix](HOSTED_PENDING_MATRIX_2026-09-29.md) records only $0.04151065850 unallocated at its snapshot; the live ledger must be reconciled again before any allocation.

The saved configuration requests `qwen/qwen3.6-35b-a3b` through AkashML `akashml/fp8`, with reasoning enabled, temperature 0, 4,096 maximum output tokens, a strict JSON schema, no fallback and a 300-second timeout. Each reconstructed request matches its saved request hash and its input-only prompt. The P1 and P2 requests also match the frozen prepared request files. All three conditions account for the exact 60 development IDs. P2 retains 54 valid outputs and six service errors, including DEV-043; none is repaired or counted as a fresh pass. The [P2 episode record](QWEN36_ON_P2_EPISODES.md) explains its interrupted history, and the [scope gap](REPEAT_SCOPE_GAPS_2026-09-28.md) treats it as separate from a clean matched series.

The new passes rotate condition order as P0/P1/P2, P1/P2/P0 and P2/P0/P1. Each condition has three smoke and 60 development requests, for 567 proposed requests. The manifests contain request payloads, source hashes and historical status labels only. They contain no reference labels, past predictions or saved response bodies. The historical series remains descriptive because its suffixes changed the schedule.

The 190 historical development and smoke attempts have $0.2043159 in known charges and $0.2093056 in retained unknown-charge bounds. Multiplying each separately by three gives a $0.6129477 known-charge proxy and a $0.6279168 unknown-bound sensitivity. Their sum, $1.2408645, leaves $0.2591355 below the proposed $1.50 child, but neither the proxy nor that margin guarantees a full future run. One request's full context/output reserve is $0.0299008; reserving all 567 at that maximum would require $16.9537536. An execution controller must reserve and settle requests sequentially, retaining the full bound when a charge is unknown and stopping before a request that cannot fit.

The three frozen manifests are [fresh1](../results/repeatability-v1/qwen36-on-fresh-matched3-v1/fresh1/manifest.json), [fresh2](../results/repeatability-v1/qwen36-on-fresh-matched3-v1/fresh2/manifest.json) and [fresh3](../results/repeatability-v1/qwen36-on-fresh-matched3-v1/fresh3/manifest.json). Their SHA-256 values are:

- fresh1: `59680c07460a3abb31e1460b5a2a662b748066b45a1ac002b344eefd6028b96b`
- fresh2: `6c6a1681d813c5e0002a03c5e3eaa0d857b237437f9e5f5fce58c2ee42c1c913`
- fresh3: `c6fcfefefc44dfc09271c7b349d433798451ae3e816f957f95859472ee3b3999`

Dispatch requires an independent controller review, an exact live route and control check, a funded child partition and stage receipts. Inspect all three raw smoke outcomes before each development phase. The planner neither implements nor authorizes dispatch. Historical request reconstruction relies on saved local attempt files; a checkout missing those files cannot authenticate the manifests.

Independent offline review approved these plans after four focused tests and all three manifest reconstructions passed. The manifests bind historical evidence but not this planner or its tests; the future execution freeze must bind the reviewed planner, tests and controller before dispatch. This is a remaining execution gate, not a completed live run.
