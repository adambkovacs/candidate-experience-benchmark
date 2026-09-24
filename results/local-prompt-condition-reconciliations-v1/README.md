# Local prompt condition reconciliations

This directory is reserved for immutable offline reports from [the local condition scorer](../../scripts/reconcile_local_prompt_conditions.py). No report exists here until an operator runs it after a condition has a sealed development terminal.

The scorer covers the scoped Qwen 3.5 4B thinking-on P1 condition in [v2](../local-prompt-remaining-v2/manifest.json) and the ten later conditions in the [v3 allowlist](../local-prompt-tail-v3/manifest.json). It does not run inference, acquire the GPU lock, retry a request, or score an active condition. Run it from the repository root:

```bash
python3 scripts/reconcile_local_prompt_conditions.py --config qwen3.5-4b-sdk-thinking-on --variant P1
```

Without `--write`, the verified report prints to stdout. After review, append `--write` to create `results/local-prompt-condition-reconciliations-v1/<config>/<P1|P2>.json`; an existing report is never overwritten. The selected condition must have completed smoke evidence, an inspected smoke receipt, an execution review, and a sealed development terminal. A stopped development terminal can yield a partial report; a live or unstarted condition cannot.

The scorer reconstructs requests from source-hashed frozen inputs and prompts, checks saved output and attempt journals against their terminal hashes, and binds each v3 condition to the actual completed predecessor files. Reports retain intrinsic invalid outputs, stopped outcomes, unknown started attempts and never-sent IDs separately. The denominator remains 60 provisional development references. Smoke usage is separate from development usage. Local request times are diagnostics; `cost_usd` is null because no provider bill was observed. See the [prompt protocol](../../docs/PROMPT_VARIANTS.md) for comparison controls and the [status document](../../docs/MVP_STATUS.md) for current execution state.
