# Hosted Qwen8 P0 smoke recovery preparation

The `off` and `on` manifests each plan a new DEV-001 through DEV-003 smoke against `qwen/qwen3-8b` on the sole `alibaba` endpoint. The saved [first smoke](../openrouter-qwen3-8b-hosted-plan-2026-09-24/SMOKE_RESULTS.md) remains separate: off has two valid results then HTTP 429; on has one invalid output then HTTP 429. These new attempts do not replace or repair those records.

The [public route audit](../hosted-qwen-recovery-route-audit-2026-09-24.json) listed the Alibaba endpoint at status 0 at 19:36:24 UTC on 2026-09-24. That observation does not prove current capacity. The unchanged [adapter](../../scripts/qwen8_hosted_adapter.py) checks the live endpoint, prices and controls again before dispatch. It sends only feedback, uses explicit reasoning off/on and JSON-object response mode, then applies the strict four-field schema locally. It has no automatic retries or provider fallback.

The [recovery wrapper](../../scripts/qwen8_hosted_recovery_v1.py) binds the old approved preview and receipt, historical outputs and terminal journals, source hashes, exclusive new outputs, a new root review receipt and an allocated partition. It routes the unchanged adapter through the [$10-compatible partition helper](../../scripts/paid_budget_partitions_v2.py). The per-call reserve is $0.017199104, so three calls require $0.051597312. The proposed partition cap is $0.06 for each mode. This preparation did not allocate money or send a request.

Offline preflight commands:

```sh
python3 scripts/qwen8_hosted_recovery_v1.py --manifest results/qwen8-hosted-recovery-prep-v1/off-smoke-manifest.json --sha256 b54042366856d7f18ae5351d26eda15a5d725d3ea5f2afc0214499ff38a895b8
python3 scripts/qwen8_hosted_recovery_v1.py --manifest results/qwen8-hosted-recovery-prep-v1/on-smoke-manifest.json --sha256 a49a667f0a279e738aa77821f2b045a9ab8b3c1c029d205b791379c447ddba5e
```

After root review and separate partition allocation, append `--execute --budget-partition-manifest <allocated-manifest> --budget-partition-id <matching-id> --review <root-receipt>` to each command. The receipt binds the exact wrapper, recovery manifest, budget manifest and partition ID. Stop each condition on a service, control or unknown-cost failure. Preserve every output and reconcile the child ledger; a full-60 run needs separate smoke inspection and approval.
