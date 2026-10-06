# DeepSeek high fresh2/P2 interruption, 6 October 2026

The revised-price `deepseek/deepseek-v4.1-flash` high-effort fresh2/P2 development stage stopped after DEV-027 returned HTTP 429. The frozen [fresh2 plan](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/fresh2/manifest.json) has 60 ordered requests. The [sanitized audit](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/fresh2/P2/interruption.audit.json) binds the plan, claim, root receipt, journal, 27 attempt records and 27 raw response files by SHA-256. DEV-001–026 each have one completed `ok` attempt. DEV-027 has one `service_error` attempt and an unknown provider charge. DEV-028–060 are 33 never-sent requests, listed by ID and request/input/instruction hash in the audit. **There is no full-phase score or clean repeat credit.** Do not replay DEV-001–027.

Stage observed known cost is **$0.012422496185**. The child ledger's cumulative known settlements across earlier stages and this prefix are **$0.047026223585**. Its sole open reserve is DEV-027 at the full **$0.06905856** upper bound, so current child accounted cost is **$0.116084783585** under its $1.00 allocation. Known cost is not a provider invoice for the failed request. No unknown bound was reduced. The [immutable child snapshot](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/fresh2/P2/interruption-child-ledger-snapshot.jsonl) is SHA-256 `adb0a7ef860818775a50631968f3b97f807d3ff00e6991b0f24018b03038bd62`. Its fields are limited to event, cap, attempt/record IDs and USD; raw response bodies and account identifiers are excluded. The [sanitized unknown-cost evidence](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/fresh2/P2/interruption-unknown-cost-evidence.jsonl) is SHA-256 `35a88eda0f552046d29833e1ef385a9bec515c240fd4d2487a24536d07498a27` and binds the private attempt file by hash without copying it.

The audit made no ledger change or reconciliation. Root can settle the one open reserve at its full upper bound only after verifying the original process is stopped and the private attempts file still matches the audit. The required APIs are `openrouter_budget_v4.BudgetLedger.finalize_unknown_at_reserved_upper_bound` on the **child** ledger, followed by `paid_budget_partitions_v4.reconcile_partition` on its existing partition. The exact arguments are:

```python
from pathlib import Path
from openrouter_budget_v4 import BudgetLedger
import paid_budget_partitions_v4 as partitions

root = Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo')
base = root / 'results/repeatability-v1/deepseek-high-remaining7-price-v1'
stage = base / 'execution-adapter-v1/fresh2/P2'
child = base / 'budget-deepseek-high-remaining7-price-v1.jsonl'
ledger = BudgetLedger(child, cap_limit='1.00')
try:
    ledger.finalize_unknown_at_reserved_upper_bound(
        '972fb28d-a76c-4824-9d82-e2023e851086',
        'DEV-027 HTTP 429; provider charge unknown; retain full reserved upper bound',
        stage / 'interruption-unknown-cost-evidence.jsonl',
    )
finally:
    ledger.close()
partitions.reconcile_partition(
    root / 'results/openrouter-paid-budget.jsonl',
    base / 'budget.json',
    'deepseek-high-remaining7-price-v1',
)
```

This is a root-only accounting action, not a request to dispatch or a statement of actual DEV-027 cost. A later DEV-028–060 continuation needs its own exact-unsent plan, route check, child allocation and review. The independently closed fresh1/P2 result remains separate from this interrupted phase.
