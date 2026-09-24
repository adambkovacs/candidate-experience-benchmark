# Hosted Qwen8 P1/P2 full60 preparation

The four [Qwen8 prompt smokes](../qwen8-hosted-prompt-smoke-prep-v1/README.md) completed DEV-001 through DEV-003 on `qwen/qwen3-8b` through Alibaba with known billing. Off-P1 and off-P2 each returned three valid objects. On-P1 returned two valid objects and one intrinsic invalid output. On-P2 returned three intrinsic invalid outputs; DEV-001 and DEV-003 stopped at the 4,096-token limit. Their raw content remains unchanged. The reviewed adapter's continuation rule permits known-billing intrinsic failures with `stop` or `length`, absent refusal or tool calls.

The [full60 gate](../../scripts/qwen8_hosted_prompt_full60_v1.py) binds each smoke's raw file, terminal journal, factual inspection, existing frozen 60-request preview, exact prompt audit, canonical input-only DEV-001 through DEV-060, review receipt and exclusive output. It uses the unchanged [hosted adapter](../../scripts/qwen8_hosted_adapter.py) with the [$10-compatible partition helper](../../scripts/paid_budget_partitions_v2.py). The full60 runs are separate calls that include DEV-001 through DEV-003 again. No prompt full60 request or allocation occurred during preparation.

Each condition reserves at most $1.031946240 across 60 calls. The proposed cap is $1.05 per partition. Review the four [smoke inspections](off-p1-smoke-inspection.json) and their sibling files before allocation. The inspections are factual records, not execution approval.

Offline preflights from the repository root:

```sh
python3 scripts/qwen8_hosted_prompt_full60_v1.py --plan results/qwen8-hosted-prompt-full60-prep-v1/off-p1-full60-plan.json --sha256 74bc6a84575ad3757fbed75df89eef8b41e4df5fb4ea6f30fb52d282d266469f
python3 scripts/qwen8_hosted_prompt_full60_v1.py --plan results/qwen8-hosted-prompt-full60-prep-v1/off-p2-full60-plan.json --sha256 a90d352960b14f434e84f397877d5449ef8c64daf2193870692acc5acb966b70
python3 scripts/qwen8_hosted_prompt_full60_v1.py --plan results/qwen8-hosted-prompt-full60-prep-v1/on-p1-full60-plan.json --sha256 d17b73503021c41a15dbbd31442518021d03c74f6683a2becb3f14a683d462a2
python3 scripts/qwen8_hosted_prompt_full60_v1.py --plan results/qwen8-hosted-prompt-full60-prep-v1/on-p2-full60-plan.json --sha256 03d30c6a7af7c11e1acc29682df5bc6216289411445168a9e70e5e9a52f33f0b
```

A separately approved execution appends `--execute --budget-partition-manifest <allocated-manifest> --budget-partition-id <matching-id> --review <root-receipt>` to each command. The receipt must bind the plan, wrapper, budget manifest, partition, `continue_on_invalid_output: true`, exact adapter preview/source fields and an approved `smoke_inspection` tied to that condition's raw smoke SHA-256. The unchanged adapter checks the receipt again before inference. Service, control or unknown-cost failures stop that condition without automatic retry. Preserve all invalid outputs in place.
