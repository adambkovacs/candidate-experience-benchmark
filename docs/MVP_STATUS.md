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

- Subscription variants are still running. Partial conditions that stopped on DNS, connection-reset or timeout failures remain saved; these are provider/runtime failures, not classifier errors.
- All 13 original hosted lanes are terminal: five full P1/P2 pairs, six partial pairs, and two provider-blocked pairs. Two explicitly versioned DeepSeek remaining-record continuations also ran and stopped on transport failures. The [low-P2 reconciliation](../results/prompt-comparison-v1-2026-09-24/hosted-continuations-v1/low-P2/reconciliation-v1.json) records 43 valid outputs across 45 attempts; the [high-P1 reconciliation](../results/prompt-comparison-v1-2026-09-24/hosted-continuations-v1/high-P1/reconciliation-v1.json) records 34 valid outputs across 38 attempts. Both retain a denominator of 60, original failures, unattempted records and the changed execution order.
- AnyJev generated P1/P2 are finished. The separate [cached-score L1 calibration](../results/anyjev-cached-l1-cv5-2026-09-24/README.md) also completed five grouped folds with 60 held-out predictions. All four confidence metrics comparisons improved NLL, Brier score and ECE; accuracy and option ranks stayed unchanged. This exploratory calibration uses 48 labels per fit and is not a deployable calibration artifact. SemIf P1 is finished; P2 was interrupted after 32 saved responses, with DEV-033 started but unfinished. Its cause is unknown; see the [interruption audit](../results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-interruption-audit.json). A separate continuation completed DEV-034–060. The [combined reconciliation](../results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-continuation-v1/reconciliation.json) has 59 saved responses, 57 valid outputs, two intrinsic invalid outputs, and DEV-033 still unknown; it is not an uninterrupted complete run.
- OpenJev generated prompt runs are complete: thinking requested off has 54/60 valid P1 outputs and 56/60 P2; thinking requested on has 50/60 P1 and 53/60 P2. All four saved 60 records, with intrinsic invalid outputs retained and no service/control failures or retries. See the [condition evidence](../results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1/). Effective reasoning for requested-on remains unverified; integration into the central paired auditor is still pending.
- Seven successful-baseline Gemini configurations have a [reviewed controller and 28 frozen previews](../results/prompt-comparison-v1-2026-09-24/gemini-exact-v1/root-review.json), covering smoke and development for both prompt variants. Live results remain pending.
- The [hosted-route review](LOCAL_HOSTED_ROUTING_REVIEW.md) found routes for three of the 14 inherited generic configurations (Qwen 8B on/off and 27B low). They require separate hosted configurations; the other 11 have no exact listed route in that snapshot. Historical local baselines do not authorize redundant local prompt runs.
- Thirty-one eligible complete pairs have an [audited comparison report](../results/prompt-comparison-v1-2026-09-24/paired-reports/thirty-one-eligible-comparisons.html). Further partial and native reports still require reconciliation.

Hosted accounting after sealing the original prompt lanes and both DeepSeek continuations: $0.66501041250 known reported charges across the project, plus $0.761937920 reserved as conservative bounds for unknown charges. This leaves $3.57305166750 under the approved $5 cap after those bounds, with no active allocation at this snapshot. Unknown charges are not asserted to be actual spending. The [master ledger](../results/openrouter-paid-budget.jsonl) is the source; TypeSafe's separate $1 approval is not included.

## Future larger run

The [harness research](HARNESS_RESEARCH.md) and [system specification](HARNESS_SPEC.md) are published. They should improve orchestration, recovery, evidence collection and reporting before hundreds of questions are run. They are not a prerequisite for publishing the initial MVP findings, and do not authorize generating the remaining records or raising spending caps.
