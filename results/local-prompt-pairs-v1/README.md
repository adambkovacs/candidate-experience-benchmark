# Offline local prompt pairs

This directory is reserved for separately reviewed P0/P1/P2 evaluations from [the local pairing auditor](../../scripts/evaluate_local_prompt_pairs_v1.py). It contains no evaluation for a live or incomplete condition. The auditor makes no model call, acquires no GPU lock, and does not retry requests.

The auditor accepts a configuration only when its exact P1 and P2 entries appear in the [frozen local tail allowlist](../local-prompt-tail-v3/manifest.json), both terminal-bound [condition reconciliations](../local-prompt-condition-reconciliations-v1/README.md) exist and are complete, and the historical single-record P0 passes its own manifest, output, request and journal audit. It compares the three conditions' saved user inputs, role placement, request settings, resolved SDK controls, returned model identity, artifact and runtime. LM Studio's transient `instanceReference` may differ. The frozen [global schedule](../prompt-comparison-v1-2026-09-24/schedule.json) must match the observed P1/P2 order.

From the repository root, preview an offline evaluation with:

```bash
python3 scripts/evaluate_local_prompt_pairs_v1.py --config qwen3.5-4b-sdk-thinking-off
```

After an independent review, adding `--write` creates `results/local-prompt-pairs-v1/<config>.json` with exclusive creation; it never overwrites a prior report. The output includes 60-record condition scores, valid-label transitions and failure transitions. Historical P0 ran earlier than P1/P2, so time, cache and sampling remain uncontrolled. References are provisional development labels, and the result is an observational within-configuration comparison, not a held-out generalization claim. The [prompt experiment protocol](../../docs/PROMPT_VARIANTS.md) defines the intended comparison.
