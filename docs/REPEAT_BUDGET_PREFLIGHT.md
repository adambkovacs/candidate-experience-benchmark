# Repeat study budget preflight

Checked 2026-09-25 without inference calls. This is a planning estimate, not an invoice or a new spending authorization.

The current comparison inventory contains 53 configuration groups: 38 audited hosted/subscription setups, five local historical-baseline setups, nine observational Gemini setups and one native Jev setup. Two additional passes over P0/P1/P2 would mean 318 full condition runs, or 19,080 record outputs, before smoke tests and retries. Comparison eligibility does not establish repeat eligibility: inspect the saved protocol for each configuration before counting an old pass. Use a declared fresh three-pass series where necessary, increasing these counts and costs. A previously accepted CLI patch-version change alone is not grounds for a new baseline.

## OpenRouter

The [completed reconciliation](../results/gemini-openrouter-prep-v3/completed-budget-reconciliation-v1.json) accounts for $6.01078369650 of the $10 aggregate cap, leaving $3.98921630350. Accounted usage includes conservative unknown-charge bounds; it is not the observed bill. Recheck the authoritative `results/openrouter-paid-budget.jsonl` and child ledgers before dispatch.

Using development-only known charges from the [saved export](../public-site/data.json):

| Scope | Prior cost for one P0/P1/P2 pass | Two additional passes |
| --- | ---: | ---: |
| Nine Gemini configurations | $2.16512925 | $4.33025850 |
| Five paid OpenRouter configurations within the audited cohort | $0.16255040875 | $0.32510081750 |
| Combined | $2.32767965875 | $4.65535931750 |

This exceeds remaining headroom by $0.666143014 before smoke tests, retries, changed token usage, unknown-charge reservations or fresh baseline passes. Full paid dispatch therefore cannot be admitted under the current cap. Do not silently shrink the requested roster. Produce the exact eligible schedule and conservative bound before requesting an increased cap.

## Other routes

TypeSafe retains its separate $1 cap. The [Jev planning audit](JEV_PROMPT_AND_TIMING_AUDIT.md) gives a combined P1/P2 ceiling of $0.299859840 per pass including smoke calls, or $0.599719680 for two additional passes. This does not cover a newly required P0 series and is not a current ledger balance; reconcile all TypeSafe journals before admission.

Subscription fees have no allocated per-run price and must not be displayed as zero cost. Check subscription quota before launching. The five local historical configurations have no hosted price in this estimate; a hosted replacement changes the configuration and cannot count as an identical repeat of the local run.

No repeat inference was launched for this preflight. See the [repeat protocol](REPEATABILITY_PLAN.md) and [current goals](CURRENT_GOALS.md).
