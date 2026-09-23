# Claude subscription runs

On 2026-09-23 the user added Opus 5.5 and removed max/ultra from future effort sweeps. Completed historical max results remain in the registry. Existing Sonnet 5, Opus 5, Fable 5.1 and Haiku results are reused.

Native Claude Code 2.1.280 authenticated through Claude.ai Max. Its model picker exposed Opus 5.5. The exact model ID is `claude-opus-5-5`; scheduled efforts are low, medium, high and xhigh. [Official model details](https://platform.claude.com/docs/en/models/opus-5-5/overview) and [effort support](https://platform.claude.com/docs/en/build-with-claude/effort) confirm these controls. Thinking is always adaptive; low effort does not disable it. Applied reasoning depth is not independently verified from the CLI setting.

The native usage panel showed usage credits off and approximately 15% weekly utilization before smoke. The smoke event independently reported overage disabled at organization level. These snapshots are account-wide, not attributable benchmark usage. CLI API-equivalent cost estimates are not subscription charges. Hosted hardware and quantization are undisclosed.

All four Opus 5.5 efforts completed 60 valid development outputs each after inspected three-record smoke tests. There were no controller retries. Medium, high and xhigh ran concurrently; their end-to-end timings include shared client contention. Final rate-limit events reported approximately 16% weekly utilization and no overage.

## Batch workflow

The new adapter, `scripts/claude_batch_benchmark.py`, submits one ordered batch per fresh empty temporary workspace. A three-record batch smoke precedes six development batches of ten. Requests contain the fixed rubric, categorical schema and `{id, feedback}` records only. Each response must contain exactly the requested IDs once and all four valid judgments. The model sees other feedback records in its batch, so these results are a separate workflow from historical one-record contexts.

The controller retains batch order, raw responses, model identity, settings hashes, token usage and duration. Exploded record rows contain batch duration divided by batch size, explicitly labeled amortized timing. This is not individual-record latency. Usage is stored once in the batch audit. Pre-request journal events are flushed to disk; unmatched starts remain uncertain. New exclusive filenames preserve every attempt. No automatic retries occur, and any service or invalid-output failure stops the run.

CLI safe mode, empty settings sources, replacement system prompt and no tools/MCP/skills/session persistence remain enabled. The existing environment disables fast mode and the expanded 1M context; the smoke reports a 200,000-token context. Temperature remains the unexposed CLI default.

CLI2.1.280 reports two built-in plugins even in safe mode. The official [agents-md source documentation](https://github.com/anthropics/claude-code/blob/main/mods/agents-md/README.md) states that safe mode adds no instruction files. The [telemetry plugin](https://github.com/anthropics/claude-code/blob/main/mods/telemetry/README.md) provides first-party analytics rather than task context. The adapter accepts only these exact built-in identities and StructuredOutput calls, rejecting unknown plugins and other tools. This is a CLI workflow, not an unwrapped-model measurement.

The first low smoke was initially marked as a guard failure because these new built-in entries were unexpected. Its three valid responses and raw envelope were retained and separately reviewed after the source audit; no duplicate request was sent. The original artifact remains unchanged.

See the [Claude registry](../results/claude-subscription-2026-09-21/run-registry.json) for current status and the [September23 artifacts](../results/claude-subscription-2026-09-23/) for raw evidence. No Gemini request is authorized by this procedure.
