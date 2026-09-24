# Exact local prompt tail: ten conditions

This controller admits the ten frozen conditions after `qwen3.5-4b-sdk-thinking-on/P1`. It does not run that P1 condition or change its evidence. The first tail smoke requires P1's completed, 60-row development terminal. Every later smoke requires the preceding tail condition's completed, 60-row terminal. Saved output and attempt hashes, request hashes, identities, and row order are checked before admission. A stopped or partial condition cannot be skipped or replayed.

| Order | Configuration | Variant |
| --- | --- | --- |
| 1 | `qwen3.5-4b-sdk-thinking-off` | P1 |
| 2 | `qwen3.5-4b-sdk-thinking-off` | P2 |
| 3 | `gemma4-e2b-sdk-thinking-on` | P1 |
| 4 | `gemma4-e2b-sdk-thinking-on` | P2 |
| 5 | `gemma4-e2b-sdk-thinking-off` | P2 |
| 6 | `gemma4-e2b-sdk-thinking-off` | P1 |
| 7 | `gemma4-e4b-sdk-thinking-on` | P1 |
| 8 | `gemma4-e4b-sdk-thinking-on` | P2 |
| 9 | `gemma4-e4b-sdk-thinking-off` | P2 |
| 10 | `gemma4-e4b-sdk-thinking-off` | P1 |

Offline checks, which perform no inference or GPU lock change:

```sh
node scripts/local_prompt_tail_v3.cjs --mode validate
node --test scripts/local_prompt_tail_v3.test.cjs
node scripts/local_prompt_tail_v3.cjs --mode admission --config qwen3.5-4b-sdk-thinking-off --variant P1
```

`admission` is expected to refuse until scoped P1 is terminal. For each condition, a fresh OpenRouter availability file must be root-reviewed. It must contain `configuration`, the manifest's `exact_hosted_model`, `exact_routes: []`, `source: "https://openrouter.ai/api/v1/models"`, and `checked_utc` within 24 hours of each run. The root execution receipt must bind that file's hash, the v3 manifest and controller hashes, the condition, and the exact predecessor terminal, output, and journal hashes. Required receipt fields are `approved_for_execution: true`, `manifest_sha256`, `controller_sha256`, `configuration`, `variant`, `predecessor_terminal_sha256`, `predecessor_output_sha256`, `predecessor_journal_sha256`, `route_evidence`, `route_evidence_sha256`, and `approved_phases` containing the phase. The reviewer must independently confirm that the route check actually searched the exact model; a declaration of zero routes alone is insufficient evidence.

Run these read-only admission checks one at a time, in order, after each predecessor finishes:

```sh
node scripts/local_prompt_tail_v3.cjs --mode admission --config qwen3.5-4b-sdk-thinking-off --variant P1
node scripts/local_prompt_tail_v3.cjs --mode admission --config qwen3.5-4b-sdk-thinking-off --variant P2
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e2b-sdk-thinking-on --variant P1
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e2b-sdk-thinking-on --variant P2
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e2b-sdk-thinking-off --variant P2
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e2b-sdk-thinking-off --variant P1
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e4b-sdk-thinking-on --variant P1
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e4b-sdk-thinking-on --variant P2
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e4b-sdk-thinking-off --variant P2
node scripts/local_prompt_tail_v3.cjs --mode admission --config gemma4-e4b-sdk-thinking-off --variant P1
```

After predecessor and route review, the first smoke command is:

```sh
node scripts/local_prompt_tail_v3.cjs --mode run \
  --config qwen3.5-4b-sdk-thinking-off --variant P1 --phase smoke \
  --approved-manifest-sha256 <current-manifest-sha256> \
  --review-receipt results/local-prompt-tail-v3/qwen3.5-4b-sdk-thinking-off/P1/execution-review-root.json \
  --review-receipt-sha256 <current-review-receipt-sha256>
```

Inspect all three raw smoke responses, their request and attempt links, runtime controls, and completed terminal. A separate `smoke-inspection.json` in that condition's folder must have `configuration`, `variant`, `accepted_for_development: true`, `smoke_ids_inspected: 3`, and the exact `smoke_output_sha256`, `smoke_journal_sha256`, and `smoke_terminal_sha256`. Run the same command with `--phase development --inspection-receipt <path> --inspection-receipt-sha256 <hash>`. Development independently issues DEV-001–060 under the original saved P0 sampling config and exact prompt. Intrinsic invalid outputs are preserved; control, service, and timeout failures stop the phase. A timeout without acknowledged cancellation retains the shared GPU lock.

For later conditions, substitute the next manifest row's configuration and variant and use its own root receipt and smoke inspection. If its prior condition stopped, a separately reviewed continuation is required; this controller will not invent a completed predecessor.
