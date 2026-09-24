# Qwen27 LOW hosted prompt addendum

This append-only addendum schedules `openrouter-qwen27-low-darkbloom-fp4` after the [original 79-condition schedule](../schedule.json). The [original roster](../roster.json), [inventory](../baseline-inventory.json), and [hosted execution manifest](../hosted-execution.json) are unchanged. Their exact entries are the prefix of the addendum copies; Qwen27 LOW is scheduled at position 80, so the frozen order is **P2 then P1**. The [17-entry paid registry snapshot](full-paid-registry-snapshot.json) includes its complete P0 run. The prepared [target fragment](offline-fragments/openrouter-qwen27-low-darkbloom-fp4/configuration.json) binds the Darkbloom FP4 provider, `qwen/qwen3.8-27b`, low reasoning, temperature 0, strict `json_schema`, 4,096 output tokens, 120-second timeout and unchanged baseline instruction. Its development source has exactly 60 canonical IDs, valid four-field predictions and known billing; the raw source remains untouched.

The [execution manifest](execution-manifest.json) has SHA-256 `a7e8a9a8c088b74f0668c60bc32dd19703bc8c8fce4f2acbc020bfbdc26b1859`. It names only this target in `manifest_scope` while binding the complete addendum roster, inventory and 80-entry schedule. The new journal path is `execution-journal.jsonl`; no journal exists yet. [Offline preflight](preflight.json) passed `prompt_admission.admit_smoke` for both P2 and P1 against all 63 frozen requests per condition. This admission is observational: provider rendering/token counts remain unknown, and it is **not** approval to run development. The full structural gate cannot pass until condition-specific token and inspected smoke evidence exist. P2 smoke must run first; after inspection, a hash-bound `prompt-smoke-supplement-v1` can admit P2 development. P1 cannot start until P2 is terminal under the separate append-only schedule.

The [reviewed command wrapper](run_after_review.sh) supplies exact frozen model, provider, prompt, timeout, schema and schedule flags to the unchanged paid adapter. It requires a separately allocated budget partition. It will not start development without a reviewed smoke supplement. The following are **future commands**, not actions performed while preparing this addendum:

```bash
export Q27_BUDGET_MANIFEST=/absolute/path/to/allocated-manifest.json
export Q27_BUDGET_ID=exact-qwen27-low-partition-id
bash results/prompt-comparison-v1-2026-09-24/qwen27-low-hosted-addendum-v1/run_after_review.sh P2 smoke
```

After inspecting P2 smoke and creating a supplement bound to this manifest and condition:

```bash
export Q27_SMOKE_SUPPLEMENT=/absolute/path/to/P2-smoke-supplement.json
export Q27_SMOKE_SUPPLEMENT_SHA256=exact-file-sha256
bash results/prompt-comparison-v1-2026-09-24/qwen27-low-hosted-addendum-v1/run_after_review.sh P2 development
```

Once P2 is terminal, use the same wrapper with `P1 smoke`, inspect it, then `P1 development` with its own P1 supplement. Every output is exclusive. The controller enforces the frozen schedule, exact request bytes, raw response checks and shared-budget reservation. There is no retry, substitution, reference-label read, inference, or budget mutation in this preparation.
