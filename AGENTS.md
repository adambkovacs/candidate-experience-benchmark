# Project execution and model routing

Follow the user's latest instructions over older plans. Benchmark model settings are experimental inputs; the routing below governs the agents doing the work, not the models being evaluated.

## Agent model selection

- Prefer deterministic scripts for polling, counting, hashing, reconciliation, formatting, and running existing tests. Do not ask an LLM to redo calculations the code can perform.
- Use `gpt-6-luna` with `low` reasoning for bounded routine work: inventories, status checks, straightforward edits, existing-command execution, and source collection against an explicit checklist.
- Use `gpt-6-sol` with `medium` reasoning for ordinary implementation, debugging, and synthesis. Use `high` for substantive research, architecture, difficult debugging, or detailed code review. The harness researcher specifically uses Sol high.
- Use `gpt-6-astra` only for a concrete unresolved problem that needs deeper reasoning, such as a difficult experimental-validity decision, an ambiguous cost/recovery correctness issue, or a problem that Sol could not resolve with evidence. State the reason for escalation. Do not use Astra for routine monitoring or research collection.
- Pass explicit model and reasoning settings when spawning agents. Use a compact task brief and only the relevant files; do not copy the full conversation by default. When tool rules require it, use `fork_turns="none"` for an overridden model.
- If a selected model is unavailable, report that fact and choose the nearest available lower-cost suitable option. Do not silently inherit Astra.
- Existing main-task settings cannot be changed by these instructions. Explain that limitation rather than claiming an in-place model switch. A different agent model requires a new agent with a saved handoff.
- Independent work may use parallel subagents when useful. Give each a bounded deliverable and exclusive file ownership; avoid duplicate research and competing edits. Use scripts and terminal completion signals instead of repeated model-driven polling.
- Do not use max or ultra reasoning unless the user explicitly changes the current prohibition.

## Benchmark invariants

- Use only the existing 60 development records until the user authorizes more. Keep references out of inference requests and score offline.
- Prefer paid OpenRouter for non-Claude/non-GPT hosted models within the approved aggregate $10 cap. TypeSafe has a separate $1 cap. Existing subscriptions serve Claude and Codex. The user also authorized Gemini through OpenRouter on 2026-09-25 within the same aggregate $10 cap; record it as a separate hosted configuration from Antigravity. Never enable paid subscription overage or redeem credits.
- Use local execution only when the required model or native specialist interface has no suitable hosted route. Before launching a pending local generic model, verify hosted availability and document why local execution is necessary. Existing local baselines do not authorize redundant local prompt reruns.
- Do not resume the cancelled DeepSeek R1 Distill download. Preserve its partial artifacts and historical evidence.
- Preserve every attempt, unknown-cost reservation, intrinsic output failure, and provider failure. Never silently repair results, substitute models, or rerun completed configurations.
- A new execution surface or changed control produces a separate configuration. Document gaps in prompt comparisons instead of using comparability as a reason to ignore the user's hosted-routing preference.
- Commit and push useful, verified checkpoints. Stage only immutable completed evidence; never blanket-stage live run folders or the active execution journal.
