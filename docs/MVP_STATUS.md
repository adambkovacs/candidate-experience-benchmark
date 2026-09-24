# MVP completion status

Status snapshot: 24 September 2026. This separates the original 60-record development benchmark from the later prompt-sensitivity experiment. No remaining 340 records have been generated.

## Original benchmark

Claude and Codex baseline configurations are complete. Completed local, hosted and specialist results are retained in the [comparison report](../results/comparison/REPORT.md). Historical partial runs, superseded surfaces and unavailable configurations remain visible in the [baseline inventory](../results/prompt-comparison-v1-2026-09-24/baseline-inventory.json); its row count is not a count of distinct models or successful 60-record runs.

Outstanding configurations and decisions:

| Configuration | Evidence and next step |
| --- | --- |
| Gemini Flash 3.6 high | Partial service-error run. Any continuation must preserve the existing attempts and explicitly identify its recovery policy. |
| Gemini Flash 3.8 low, medium, high | Partial native CLI runs attempted external tools; headless permission denied those calls. Verify effective tool disablement before treating a future run as an isolated classification comparison. |
| Mistral Small 4 119B none/high | Smoke requests met upstream rate limits. A serving endpoint must recover before new inference can complete these rows. |
| DeepSeek R1 Distill Qwen 32B | Exact hosted checkpoint had no available endpoint. Local download was stopped at the user's direction. Other DeepSeek checkpoints are separate configurations, not replacements. |
| AnyJev L1/L2 | Separate calibration and evaluation design remains required. Do not fit and score on the same labels or generate the withheld 340 records. |

Original malformed JSON, copied schemas and other intrinsic model failures are benchmark outcomes. They do not require repeated attempts until valid. Legacy strict-length Laya rows, replaced hosted endpoints, free-provider failures and tool-restricted Gemini rows must retain their individual history without being counted as additional fresh work after an explicitly separate successful configuration.

To close the initial MVP, reconcile these dispositions in the final report, finish cost reconciliation, refresh the failure explorer, and link all evidence. Full requested model coverage is not achieved merely because a configuration has a documented block.

## Additional prompt experiment

The [frozen roster](../results/prompt-comparison-v1-2026-09-24/roster.json) schedules 79 configuration pairs, with classifier framing (P1) and classifier plus SOP (P2). This is additional work beyond the original baseline. It reuses saved P0 results and does not rerun them solely because Codex CLI changed from 0.155.0-alpha.16 to 0.155.0-alpha.16.3; that accepted runtime difference stays explicit.

At this snapshot:

- Subscription variants are still running. Three conditions stopped during a DNS outage; their partial predictions and failures remain saved.
- All 13 original hosted lanes are terminal: five full P1/P2 pairs, six partial pairs, and two provider-blocked pairs. A remaining-record continuation is only a draft, not an executed recovery.
- AnyJev generated P1/P2 are finished. SemIf P1 is finished; P2 was interrupted after 32 saved responses, with DEV-033 started but unfinished. Its cause is unknown; see the [interruption audit](../results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-interruption-audit.json).
- OpenJev generated variants and seven successful-baseline Gemini configurations still need their prompt comparisons. The 14 inherited local generic configurations need hosted-route reconciliation first; they are not automatically authorized for local reruns.
- Nine complete pairs have an [audited comparison report](../results/prompt-comparison-v1-2026-09-24/paired-reports/nine-comparisons.html). Further partial and native reports still require reconciliation.

Hosted accounting after sealing the 13 original prompt lanes: $0.65091286250 known reported charges across the project, plus $0.548126720 reserved as conservative bounds for unknown charges. This leaves $3.80096041750 under the approved $5 cap after those bounds. Unknown charges are not asserted to be actual spending. The [master ledger](../results/openrouter-paid-budget.jsonl) is the source; TypeSafe's separate $1 approval is not included.

## Future larger run

Harness research and specification are being prepared separately. They should improve orchestration, recovery, evidence collection and reporting before hundreds of questions are run. They are not a prerequisite for publishing the initial MVP findings, and do not authorize generating the remaining records or raising spending caps.
