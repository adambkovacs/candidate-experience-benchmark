# Analysis refresh, 2 October 2026

The [machine-readable refresh](../public-site/analysis-refresh.json) recomputes the figures below from 66 SHA-256-bound files. It checks every public Sonnet 5.5 development record against the published score and the frozen [v0.2 reference key](../data/pilot/proposed_labels.jsonl). All figures describe the same 60 synthetic reviews. The project owner confirmed that people checked all 60 reference answers on 2 October; the key has not been changed, and [proposed revisions](REFERENCE_REVIEW_V1.md) remain separate. Agreement with this key is not a measure of hiring accuracy.

## What the new Sonnet series adds

[Sonnet 5.5's fresh v2 series](../public-site/sonnet55-fresh-matched3.json) has four efforts, three prompt conditions and three separately dispatched full passes: 36 complete cells, 60 valid classifications per cell. Each request grouped ten reviews. The [public evidence report](../public-site/sonnet55-fresh-matched3-evidence/report.json) binds sanitized records, usage and the original stopped smoke to the scored cells.

| Effort | P0 all-four / 60 | P1 all-four / 60 | P2 all-four / 60 | P1 minus P0 | P2 minus P0 |
| --- | --- | --- | --- | --- | --- |
| Low | 58, 56, 58 | 58, 57, 58 | 56, 57, 56 | 0, +1, 0 | −2, +1, −2 |
| Medium | 56, 57, 57 | 57, 57, 59 | 57, 57, 57 | +1, 0, +2 | +1, 0, 0 |
| High | 58, 58, 58 | 57, 58, 58 | 58, 58, 58 | −1, 0, 0 | 0, 0, 0 |
| Xhigh | 58, 58, 58 | 58, 58, 58 | 58, 58, 58 | 0, 0, 0 | 0, 0, 0 |

The paired prompt differences depend on effort. Medium P1 reaches 59/60 in its third pass, while high and xhigh do not gain from either added prompt in any pass. Low P2 changes sign across passes. The Sonnet series therefore supports the earlier finding that extra instructions do not consistently improve agreement; it supplies repeated, matched observations instead of relying on a single result. These deltas are descriptive. The visible prompt and batch controls are frozen, but serving revision, effective seed and hidden CLI behavior are unavailable. [Protocol and controls](SONNET55_MATCHED3_V2_CONTINUATION_2026-10-02.md).

Equal scores do not mean equal classifications. Across P0's three passes, the union of review IDs with at least one changed four-field answer is 3 at low effort, 3 at medium, 1 at high and 0 at xhigh. The corresponding P1 counts are 2, 4, 1 and 1; P2 counts are 1, 0, 2 and 1. Xhigh scored 58/60 in all nine cells, yet P1 changed `DEV-006` and P2 changed `DEV-030` between passes. The [feed](../public-site/analysis-refresh.json) contains the exact IDs and per-field scores. They are repeat observations on the same reviews, not new independent cases.

Class balance changes how a field score reads. The reference key contains nine `yes` testimonials and 50 `no` testimonials; an all-`no` rule would already agree on 50/60. In Sonnet P0, high and xhigh find all nine reference-positive testimonials in all three passes, while low finds 9, 8 and 9 and medium finds 8, 9 and 9. All four efforts match all 25 reference-positive serious-concern labels in every P0 pass. These class hits are useful diagnostics, but the reference labels remain provisional and the 36 cells reuse the same nine and 25 cases. [Reference distributions and record-level evidence](../public-site/analysis-refresh.json).

## How the Claude conclusion changed

The previous [Claude repeat synthesis](CLAUDE_REPEAT_SYNTHESIS_2026-09-28.md) covered 17 configurations: 15 historical roster series, the separate Opus 5.5 medium series and a fresh Haiku series. Adding the four Sonnet 5.5 efforts makes 21 visible configurations. In none of the 21 does P1 or P2 beat P0 on all-four agreement in **all three matched passes**. This is a count of distinct saved configurations, not a pooled success rate or 21 independent model samples. The [Claude roster feed](../public-site/claude-roster-repeats.json), [Opus medium feed](../public-site/claude-repeats.json), [Haiku feed](../public-site/haiku-fresh-matched3.json) and [Sonnet feed](../public-site/sonnet55-fresh-matched3.json) retain each score and pass identity.

The comparison is **within each series**. The historical series join first passes to later repeats, sometimes across a CLI patch; Haiku is a separate fresh series; Sonnet 5.5 uses its own model and a reviewed v2 CLI guard. Model, route, runtime, batch context and hidden serving behavior can differ between series. The earlier [39-configuration prompt audit](../public-site/findings.json) found P2 below P1 in 21, above in 4 and tied in 14 single-pass comparisons. Those single-pass configurations and the 21 repeat series answer related questions, but their counts must not be added as if they were independent evidence.

## Cost, token and timing interpretation

| Sonnet effort | Development output tokens, nine cells | Reported thinking tokens | Cache writes / reads | API-equivalent development estimate |
| --- | ---: | ---: | ---: | ---: |
| Low | 33,653 | 0 | 121,039 / 155,496 | $0.8520012 |
| Medium | 36,666 | 3,029 | 57,930 / 218,592 | $0.6423144 |
| High | 66,594 | 32,872 | 57,932 / 218,592 | $0.9416024 |
| Xhigh | 83,131 | 49,404 | 57,945 / 218,592 | $1.1070244 |

Medium has a lower estimate than low despite using more output tokens because their cache-write and cache-read mix differs. Xhigh used about 2.47 times low's output tokens, without a consistent all-four score gain. The estimates sum to **$3.5429424 for development**; the [Sonnet report](SONNET55_FRESH_MATCHED3_FINDINGS_2026-10-02.md) separately records $0.2625174 for smoke. Rates come from [Anthropic's Sonnet 5.5 pricing](https://platform.claude.com/docs/en/models/sonnet-5-5/overview). These are list-price API equivalents for subscription CLI requests, not observed charges, subscription quota use or a claim that higher effort always costs more. The [subscription price feed](../public-site/subscription-price-estimates.json) has comparable proxies for older Claude series, with missing phases marked; it does not create an actual subscription bill.

The refresh retains summed **client request wall time** and **CLI-reported API duration** by effort. Neither is pure model inference time, and request grouping differs from one-record hosted calls. Provider token categories can also differ: reported thinking tokens are a subset or diagnostic of output usage, never an extra charge added to output tokens. No cross-route speed or cost ranking follows from these figures. [Usage details](../public-site/analysis-refresh.json).

## Other saved cohorts remain visible

| Cohort and current saved boundary | Interpretation |
| --- | --- |
| [Qwen 27B medium and xhigh](../public-site/qwen27-final-descriptive-findings.json) | Two descriptive three-pass series; interrupted composite slots mean neither qualifies as a clean matched-three experiment. |
| [Legacy small Qwen](../public-site/legacy-qwen-repeats.json) | The fresh HTTP 0.6B repeat series and two exact SDK 0.6B settings each have nine of nine full cells. The SDK thinking-on final P2 cell has 58 valid, two invalid and 1/60 all-four agreement; thinking-off has five valid, 55 invalid and 0/60. At this dated checkpoint, the 1.7B thinking-on SDK setting has one of nine cells (fresh1/P0, 60 valid, 24/60); the 1.7B off and 3.5-4B on settings remain at zero. These local runs have their own controls and cannot be pooled with hosted Qwen 27B. |
| [Clef and Clef Flash native P0](../public-site/clef-findings.json) | Each has one complete fresh1/P0 pass, 60 valid responses, and 53/60 and 45/60 all-four agreement respectively. Vendor confidence and chosen-label probability remain distinct. The [first-pass report](CLEF_FINDINGS_2026-10-02.md) gives input-price estimates and conservative holds; provider-billed dollars are unavailable. No three-pass Clef claim follows from these cells. |
| [DeepSeek low](../public-site/deepseek-low-third-interruption-findings.json) | Two of nine planned full cells are complete. The latest P2 cutoff has 46 valid, one invalid, three service errors and ten never-sent positions; it has no full score. |
| [Gemma 26B thinking on](../public-site/gemma26-postabort-findings.json) | The [older second-continuation cutoff](../public-site/gemma26-second-continuation-findings.json) had six of nine full cells; the [DEV-006 terminal](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/third-interruption-continuation-v1/terminal-public-after-dev006.json) recorded 54 then-unsent positions. Separately dispatched suffixes now account for all 60 fresh3/P2 positions: 58 valid, the preserved DEV-005 and DEV-006 service errors, and **56/60** all-four agreement on the fixed denominator. That makes seven of nine scored cells. Fresh3/P0 and P1 remain never sent; the interrupted reconstruction is descriptive, not a clean matched-three pass. [Source-bound findings](GEMMA26_POSTABORT_FINDINGS_2026-10-02.md). |
| Mistral 119B none | The [original terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-development-none-v1/fresh1/P0/development.terminal-public.json) has 47 valid answers and an unknown `DEV-048` timeout. The [first suffix](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-remaining-none-v1/fresh1/P0-suffix-049-060/suffix.terminal-public.json) adds valid `DEV-049`, then an HTTP 429 at `DEV-050`. The [second suffix](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-second-suffix-none-v1/fresh1/P0/suffix.terminal-public.json) adds valid `DEV-051` and `DEV-052`, then a shared-pool HTTP 429 at `DEV-053`; `DEV-054` through `DEV-060` were never sent. The combined saved state is 50 valid, three failed or unknown, seven never sent, and no full score. The failed positions were not replayed. |

Each cohort retains its own prompt, model, runtime and completion status. Gemma's new fixed-60 composite includes both preserved failures; DeepSeek and Mistral still lack full-cell scores. Scores on just the successful subset would hide provider and interruption failures. The [refresh feed](../public-site/analysis-refresh.json) records exact source hashes and the current saved boundary for each cohort.

Gemma's 58 cost-bearing responses report **$0.02230691** across the 60-position composite; DEV-005 and DEV-006 have no observed charge. Reported token sums are 149,117 prompt, 34,908 completion and 184,025 total, each with 58 reported and two missing entries. The reported 35,331 reasoning tokens **exceed** reported completion tokens, so these provider categories conflict; reasoning is a diagnostic and must not be added to total or treated as a reliable subset. Summed client request time is 1,609.57 seconds; pure inference time and a provider invoice are unavailable. The final $0.30 child ledger covers only DEV-047–060 and reports $0.00575783 known charges within that wider composite. [Gemma usage and reconciliation](GEMMA26_POSTABORT_FINDINGS_2026-10-02.md).

## What is and is not measured

The bound evidence covers prompt version, reasoning effort, reported model and route, batch size, CLI version, visible seed policy, saved outcomes, per-field and all-four agreement, class balance, individual answer flips, reported token categories, API-equivalent estimates and client-side durations. Sonnet's manifest requires Claude Code 2.1.287, batch size ten, a 600-second timeout and unchanged CLI default seed; reference labels were applied after inference. The first low P0 smoke originally stopped under an earlier plugin guard and was admitted from its retained raw response offline under the v2 guard. Its original failure remains in the [source report](../public-site/sonnet55-fresh-matched3.json).

Actual subscription charges and quota use, pure inference time, effective provider seed, hidden retries, serving revision, built-in plugin prompt effects, statistical independence and performance on real candidate feedback cannot be recovered from the saved records. Cost and timing comparisons across routes must keep those missing variables visible. The 60 reference cases were checked by people according to the owner's 2 October confirmation, but their versioned key is still provisional and the development set is not a held-out test.

Run `python3 scripts/build_analysis_refresh.py --check` and `python3 -m unittest tests.test_analysis_refresh -q` to verify this snapshot without making model requests.
