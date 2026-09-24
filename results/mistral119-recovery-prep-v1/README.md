# Mistral 119B smoke recovery preparation

The `none` and `high` P0 recovery smokes each target DEV-001 through DEV-003 on `mistralai/mistral-small-2603` through `mistral/zdr`. The original attempts returned HTTP 429 before any valid smoke response. Their raw outputs and unknown-cost upper-bound accounting remain unchanged. These are new, separately named smoke attempts. They are not evidence that the provider is currently serving requests.

The [endpoint audit](../mistral119-recovery-audit-2026-09-24.json) recorded `mistral/zdr` as listed with status 0 at 19:20:17 UTC on 2026-09-24. The live runner checks model identity, endpoint status, required controls and price ceilings again before a request. It uses the unchanged [paid benchmark runner](../../scripts/openrouter_paid_benchmark.py) for requests and raw attempt records, with the [$10 ledger](../../scripts/openrouter_budget_v2.py) through the [versioned partition helper](../../scripts/paid_budget_partitions_v2.py). The [wrapper](../../scripts/openrouter_mistral119_recovery_v1.py) checks source hashes, canonical input-only requests, exact routing, output exclusivity, a root review receipt and an allocated partition. It does not read reference labels.

Each manifest fixes a $0.04177920 upper bound per request, so three requests require $0.12533760. The proposed partition is $0.15 for each condition. No partition has been allocated and no inference has run from this preparation.

Offline preflight:

```sh
python3 scripts/openrouter_mistral119_recovery_v1.py --manifest results/mistral119-recovery-prep-v1/none-smoke-manifest.json --sha256 1234adf67d6dffee82bf6d939b2b9f107531458c7f49bdc161a70b3f2fb84aed
python3 scripts/openrouter_mistral119_recovery_v1.py --manifest results/mistral119-recovery-prep-v1/high-smoke-manifest.json --sha256 bd4e1cd0e65e38749c6c69fb710884e3710eb707be17e75cbc525a828c4c3dd4
```

After root review and separate budget allocation, append `--execute --budget-partition-manifest <allocated-manifest> --budget-partition-id <exact-id> --review <root-receipt>` to each command. Run each condition against its own partition. The receipt must bind the wrapper hash, recovery manifest hash, budget manifest hash and partition ID. HTTP 429, unknown cost, identity mismatch or other non-success stops that condition without an automatic retry. Preserve the raw output and reconcile its child ledger before any later attempt.
