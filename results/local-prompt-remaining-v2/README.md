# Qwen3.5 4B thinking-on P1 admission

This separate controller covers only the next frozen condition, `qwen3.5-4b-sdk-thinking-on/P1`. It leaves the original P2 evidence untouched. Original P2 has 18 finished rows and an unresolved claimed DEV-019; its reviewed suffix may supply only DEV-020–060. A completed 41-row suffix terminal, output, and journal are required before P1 smoke. The original P2 is never represented as a 60-row completed run.

`node scripts/local_prompt_remaining_v2.cjs --mode validate` checks frozen source hashes and reconstructs the 60 P1 requests offline. `--mode admission` additionally verifies the completed suffix and its 41 attempt links. Neither mode calls the model or changes the GPU lock. The `run` mode requires a new root review receipt binding this controller, manifest, original interruption audit, and the three suffix artifact hashes. It checks exact LM Studio model, runtime, hardware, artifact, context, prompt counts and saved P0 request config, then acquires the shared GPU lock. An existing phase output, journal, or terminal refuses replay.

After the suffix is complete, a fresh exact hosted availability check is recorded, the root review receipt is prepared, and the GPU lock is free, the next smoke command is:

```sh
node scripts/local_prompt_remaining_v2.cjs --mode run \
  --phase smoke \
  --approved-manifest-sha256 <current-manifest-sha256> \
  --review-receipt results/local-prompt-remaining-v2/execution-review-root.json \
  --review-receipt-sha256 <current-review-receipt-sha256>
```

Inspect all three raw smoke responses and their saved request and attempt links. Save a root-reviewed `results/local-prompt-remaining-v2/smoke-inspection.json` with `configuration`, `variant`, `accepted_for_development: true`, `smoke_ids_inspected: 3`, and exact `smoke_output_sha256`, `smoke_journal_sha256`, and `smoke_terminal_sha256`. Then use the same command with `--phase development --inspection-receipt results/local-prompt-remaining-v2/smoke-inspection.json --inspection-receipt-sha256 <hash>`. Development issues all 60 records separately from smoke; smoke responses are not replayed as development rows.

The remaining ten conditions after P1 need their own admission under the frozen schedule. This scoped controller does not admit them.
