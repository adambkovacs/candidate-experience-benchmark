# Hosted Qwen8 P1/P2 smoke preparation

Four separate P1/P2 smokes are frozen from the existing [Qwen8 preview](../openrouter-qwen3-8b-hosted-plan-2026-09-24/preview-v1/preview-manifest.json): reasoning off/on, each with P1 and P2. Every plan contains DEV-001 through DEV-003 only. The [smoke gate](../../scripts/qwen8_hosted_prompt_smoke_v1.py) verifies the exact prompt audit, feedback-only payload, Alibaba route, JSON-object mode, source hashes, exclusive result path, receipt and partition before calling the unchanged [adapter](../../scripts/qwen8_hosted_adapter.py). It does not read reference labels or alter the P0 evidence.

Each plan needs a $0.051597312 three-call upper bound. The proposed partition is $0.06 per condition. No P1/P2 request or budget allocation occurred during preparation.

Run offline preflights from the repository root:

```sh
python3 scripts/qwen8_hosted_prompt_smoke_v1.py --plan results/qwen8-hosted-prompt-smoke-prep-v1/off-p1-smoke-plan.json --sha256 ccfa71bef3202fcef0c03df797f84fb8e17f409bfab1601e7fd505cf5e973981
python3 scripts/qwen8_hosted_prompt_smoke_v1.py --plan results/qwen8-hosted-prompt-smoke-prep-v1/off-p2-smoke-plan.json --sha256 b7de1f77426615831d15ce15077c099254c28b645e05eae374ca556414235226
python3 scripts/qwen8_hosted_prompt_smoke_v1.py --plan results/qwen8-hosted-prompt-smoke-prep-v1/on-p1-smoke-plan.json --sha256 97ce6069a8f230552c7aff09015a6778e93f703f9c1dff8062994a52e25af9c5
python3 scripts/qwen8_hosted_prompt_smoke_v1.py --plan results/qwen8-hosted-prompt-smoke-prep-v1/on-p2-smoke-plan.json --sha256 503c8e23486c3e0789efd40d81abe874593e68badb430e40ecff93c7a75f4fd9
```

Execution needs separate root review and allocated partitions. Append `--execute --budget-partition-manifest <allocated-manifest> --budget-partition-id <matching-id> --review <root-receipt>` to each approved command. The new receipt must bind the plan hash, wrapper hash, budget manifest hash, partition ID and `continue_on_invalid_output: true`; it must also carry the unchanged adapter's approved preview, manifest, script, catalog, endpoint, mode, variant and phase fields. Preserve invalid outputs and stop each condition on service, control or unknown-cost failure without a retry. Full60 P1/P2 requires separate smoke inspection and budget review.
