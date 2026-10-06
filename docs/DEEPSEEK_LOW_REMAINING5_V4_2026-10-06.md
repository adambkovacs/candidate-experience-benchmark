# DeepSeek low: five remaining phases

The earlier low-effort continuation completed the DEV-006–060 suffix of fresh2/P2: 55 usable answers and $0.029383074137 in known development cost. The original DEV-005 call still has an unknown cost, reserved at its full $0.06905856 bound. Together they describe 59 usable answers across the 60 records, but they do not form a clean, uninterrupted 60-record result. The [closure audit](../results/repeatability-v1/deepseek-low-remaining6-price-v2/unsent-continuation-v1/fresh2-p2-suffix-closure-audit.json), [sealed ledger snapshot](../results/repeatability-v1/deepseek-low-remaining6-price-v2/unsent-continuation-v1/closure-ledger-snapshot-after-dev060.jsonl), and [reconciliation](../results/repeatability-v1/deepseek-low-remaining6-price-v2/unsent-continuation-v1/reconciliation-after-dev060.json) are the evidence for that boundary.

This separate offline proposal includes exactly five untouched phases, in the frozen order: fresh2/P0, fresh2/P1, fresh3/P1, fresh3/P2, fresh3/P0. Each phase keeps its original 60 development payloads and first three smoke payloads. It excludes fresh2/P2 entirely; there is no replay of DEV-001–060 from the interrupted phase. The [proposal](../results/repeatability-v1/deepseek-low-remaining6-price-v2/remaining5-v4/proposal.json) and [execution adapter manifest](../results/repeatability-v1/deepseek-low-remaining6-price-v2/remaining5-v4/execution-adapter-v1/manifest.json) bind the frozen requests and source files.

The proposed new child cap is $0.50 from the OpenRouter-only pool. Each call reserves up to $0.06905856 before dispatch; the runner stops when the remaining child balance cannot cover another reservation. The cap is a ceiling, not a prediction that every phase will finish. The adapter requires the v4 authority transition, an exact new child budget, independent root review of the adapter and each stage, a fresh live route and request check, and inspection of each three-call smoke before development. Its checked-in review is unapproved. This preparation made no allocation or inference request.

Offline checks:

```sh
PYTHONPATH=scripts python3 scripts/deepseek_low_remaining5_v4.py verify
PYTHONPATH=scripts python3 scripts/deepseek_low_remaining5_v4_execution.py verify
PYTHONPATH=scripts python3 -m pytest -q tests/test_deepseek_low_remaining5_v4.py tests/test_deepseek_low_remaining5_v4_execution.py
```
