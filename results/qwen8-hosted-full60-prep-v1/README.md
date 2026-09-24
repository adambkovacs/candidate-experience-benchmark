# Hosted Qwen8 P0 full60 preparation

Both conditions use the unchanged [Qwen8 adapter](../../scripts/qwen8_hosted_adapter.py) and its existing frozen 60-request previews. The [full60 gate](../../scripts/qwen8_hosted_full60_v1.py) binds canonical DEV-001 through DEV-060, exact input-only JSON-object requests, the recovery-smoke result and terminal journal, and the versioned [$10 partition helper](../../scripts/paid_budget_partitions_v2.py). It does not alter the earlier smoke results or read reference labels.

The [off inspection](off-smoke-inspection.json) records three valid outputs. The [on inspection](on-smoke-inspection.json) records three JSON strings that fail the required four-field object schema. Each on response came from `qwen/qwen3-8b` on Alibaba, ended with `stop`, had no choice error, tool call or refusal, and had known billing. The strings remain invalid outputs. The original reviewed smoke receipt already declared continuation after such known-billing intrinsic failures.

The adapter reserves $0.017199104 per call. Sixty calls require a $1.031946240 upper bound, within each proposed $1.05 partition. These are separate full60 runs that include DEV-001 through DEV-003 again by the frozen full60 preview; the recovery smokes remain separate evidence. No full60 request or allocation occurred during preparation.

Offline preflight:

```sh
python3 scripts/qwen8_hosted_full60_v1.py --plan results/qwen8-hosted-full60-prep-v1/off-full60-plan.json --sha256 0344b386038eb1cdccac249f6fc45c565744b7dceb7f5acf6c2f35d5ec1edf0a
python3 scripts/qwen8_hosted_full60_v1.py --plan results/qwen8-hosted-full60-prep-v1/on-full60-plan.json --sha256 0174f0dec2b790e21cf74dae004cb417417838d3d9ecb18ece5a7226ff967e96
```

After review and allocation, append `--execute --budget-partition-manifest <allocated-manifest> --budget-partition-id <matching-id> --review <root-receipt>` to each command. Each new root receipt must bind `approved`, `full60_plan_sha256`, `wrapper_sha256`, `budget_manifest_sha256`, `partition_id`, and `continue_on_invalid_output: true`. It must also satisfy the unchanged adapter's receipt fields: `decision: approved`, exact preview and preview-manifest hashes, adapter script and saved catalog/endpoint hashes, `reasoning`, `variant: P0`, `phase: full60`, and `smoke_inspection` with `decision: approved`, matching mode and variant, absolute recovery-smoke result path and its SHA-256. The full60 gate and adapter both validate these fields before a request. A service, control or unknown-cost failure stops that condition without an automatic retry.
