# Qwen27 hosted prompt outcomes

Both conditions stopped before completing the 60-record development set. The three-record smoke passed before each development run.

| Condition | Valid | Failed request | Never sent |
| --- | ---: | --- | --- |
| P2: classifier and SOP | 32 | DEV-033: upstream HTTP 429 | DEV-034–060 (27) |
| P1: classifier framing | 9 | DEV-010: 120-second timeout | DEV-011–060 (50) |

No failed request was retried. Unknown charges remain unknown: the sealed partition records $0.0442901 in reported charges and $0.0671744 in conservative bounds. It releases $0.3885355 of the original $0.50 allocation.

The exact configuration was `qwen/qwen3.8-27b`, `darkbloom/fp4`, low reasoning. These hosted results remain separate from the earlier local quantized baseline. Reference labels were excluded from inference. See [coverage and hashes](terminal-coverage-v1.json), [budget reconciliation](budget-terminal-reconciliation.json), and [execution manifest](execution-manifest.json).
