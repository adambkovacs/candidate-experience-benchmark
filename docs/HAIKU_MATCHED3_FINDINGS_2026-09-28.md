# Claude Haiku 4.5: fresh matched-three findings

The new Haiku series is complete: all nine condition/pass combinations have six completed development requests and 60 valid predictions. Each condition also has a separately inspected three-record smoke request. The [source-bound report](../public-site/haiku-fresh-matched3.json) verifies the frozen request manifests, phase admissions, claims, journals, smoke inspections, raw captures, model identity, and parsed records before scoring against the provisional v0.2 references.

| New pass, in execution order | P0 all-four match reference | P1 all-four match reference | P2 all-four match reference |
| --- | ---: | ---: | ---: |
| Pass 1: P0, P1, P2 | 55/60 | 53/60 | 54/60 |
| Pass 2: P1, P2, P0 | 55/60 | 56/60 | 55/60 |
| Pass 3: P2, P0, P1 | 57/60 | 59/60 | 56/60 |

Across the three passes, all-four agreement counts range from 55–57 for P0, 53–59 for P1, and 54–56 for P2. The within-pass P1 minus P0 difference ranges from −2 to +2 reviews matching the reference; P2 minus P0 ranges from −1 to 0. Exact four-field predictions change at least once across passes for 6 P0 reviews, 7 P1 reviews, and 4 P2 reviews. The report includes each pairwise flip, per-field score, and per-record changed ID. These are repeated responses to the same 60 reviews, not independent new observations; provider caching and serving revisions are unknown.

The [historical Haiku P1 reconciliation](../results/prompt-comparison-v1-2026-09-24/subscription-suffix-continuation-v2-haiku/reconciliation-v1/haiku45-not_applicable-phase2-batch10-p0-P1.json) remains separate. It contains 50 valid predictions and ten attempted DEV-011–020 transport failures. Its P1 timing straddled P2, and the saved CLI error had internal retry events. None of those ten failures was retried or relabeled as a prediction in the new series. New pass one is a fresh 60-review run, not a repair of the historical pass.

The 54 development requests took 2,443.888 seconds of client wall-clock time in total. The CLI supplied 124,000 input tokens, 81,613 cache-creation input tokens, 235,296 output tokens (including 181,715 reported thinking tokens), and no cache-read input tokens. Its summed API-equivalent list-price estimate is $1.463706 for development; including nine smoke requests gives 63 requests and $1.584761. Those figures are not subscription charges or pure model inference time. Actual billed cost and subscription quota consumed are unavailable. The runtime was Claude Code CLI 2.1.282 with `claude-haiku-4-5-20251001`, effort `not_applicable`, batch size ten, one fresh CLI context per request, and no controller retries. Hidden rendering, effective seed, serving revision, and CLI-internal retry behavior are not fully controlled or observed.

The reference set is AI-reviewed provisional v0.2, not independently adjudicated ground truth. Agreement with it measures consistency with that rubric; a repeated model answer is not evidence that the reference is correct. The [controller and admission contract](CLAUDE_HAIKU_MATCHED3.md) gives the exact scope and recovery boundary.
