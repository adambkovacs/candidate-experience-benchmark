# Gemini repeat findings, 28 September 2026

Repeating the same prompts exposed two different effects: small classification changes and occasional failure to finish a batch. Treating both as ordinary score variation would hide the main weakness of Gemini 3.8 medium in this experiment.

Each configuration has three passes for each prompt condition on the same 60 synthetic reviews. P0 uses the original prompt, P1 adds classifier instructions, and P2 adds the procedure and decision tree. Scores below count reviews matching all four provisional reference labels, out of 60. These are development-set observations, not estimates of production accuracy.

| Model and effort | P0 score range | P1 score range | P2 score range | Validity |
| --- | --- | --- | --- | --- |
| Gemini 3.1 Pro, low | 56–57 | 56–57 | 57 | 60/60 in all nine combinations |
| Gemini 3.6 Flash, medium | 55–56 | 55–57 | 56–57 | 60/60 in all nine combinations |
| Gemini 3.7 Flash, medium | 56 | 56–58 | 56–57 | 60/60 in all nine combinations |
| Gemini 3.8 Flash, medium | 47–56 | 47–55 | 47–56 | Five combinations at 50/60; four at 60/60 |

## Findings

Gemini 3.1 Pro's P2 predictions were identical across all three passes. P0 and P1 each changed on two reviews. Its P1 advantage over P0 ranged from one additional matching review to one fewer, so the single-pass improvement did not persist consistently.

Gemini 3.6 Flash's P1 difference also ranged from one fewer matching review to one more. P2 matched between zero and two more reviews than P0. These small differences sit alongside within-condition changes and do not establish a general benefit from longer instructions.

Gemini 3.7 Flash scored 56/60 in every P0 pass, yet its predictions changed on three reviews. An unchanged aggregate score can conceal changed classifications. Across three passes, the number of reviews with a changed four-field prediction was three for P0, two for P1 and four for P2.

Gemini 3.8 Flash hit the frozen output-token limit in the DEV-011–020 batch in five combinations: all three original conditions, repeat2 P1 and repeat3 P0. The provider returned `length` as the finish reason and incomplete JSON. The strict batch parser retained all ten positions as invalid; no partial answer was repaired or retried. This accounts for much of its apparent score movement. Raising the token limit would be a different configuration, not a correction to these saved runs.

Among the 50 reviews with valid outputs in all three Gemini 3.8 passes, P0 classifications did not change; P1 and P2 each changed on one review. That narrower denominator excludes the ten affected batch positions and must not be confused with 60/60 reliability.

## Cost and measurement

The four new repeat waves, including their smoke calls, incurred $1.928587 in returned OpenRouter charges: $0.555784 for Pro 3.1 low, $0.456366 for Flash 3.6 medium, $0.38012850 for Flash 3.7 medium and $0.53630850 for Flash 3.8 medium. These amounts cover the two added passes per condition, not the historical first passes.

Request duration is client-observed time, not pure inference time. Missing provider inference measurements remain unavailable. All series use the same 60 reviews, so repeated predictions are not additional independent cases. Reference labels are AI-reviewed provisional version 0.2, with unresolved human adjudication noted separately.

## Evidence

The [machine-readable report](../public-site/gemini-repeats.json) contains scores, validity, per-field changes, token usage, costs and hashes linking each result to its saved requests and raw responses. The [budget reconciliation receipts](../results/repeatability-v1/gemini-roster-wave-v1/) bind the four closed allocations. The [controller](../scripts/gemini_repeat_roster.py) preserves exact prompts, ordered batches and controls. All 23 Gemini planner, controller and report tests passed in a clean export of the staged sources.

## Gemini 3.7 Flash high: completed follow-up

The high-effort series now has nine closed condition/pass combinations. Repeat two produced 60 valid outputs for each prompt. Repeat three produced 50 valid and ten invalid outputs in each condition; DEV-011 through DEV-020 reached `length` / `MAX_TOKENS` in all three batches. The reported reasoning-token counts were 7,865, 7,863 and 7,860 for P0, P1 and P2. These are output-generation limits, not account-credit failures. The historical P0 and P1 also contain ten invalid outputs each.

All-four-field agreement scores were P0: 47, 57, 47; P1: 47, 56, 47; P2: 56, 56, 47, always with a denominator of 60. These differences combine classification agreement and output validity. They must not be interpreted entirely as changes in classification decisions. The report separately compares predictions among reviews that were valid in every compared pass.

The six new development phases and six smoke requests returned $0.709266 in provider charges. The $1 allocation is closed and its unused $0.290734 released. Master accounted spending and retained unknown-charge bounds total $9.36508848150, leaving $0.63491151850 under the $10 cap. Gemini 3.1 Pro high remains unallocated; the requested budget increase is pending. See the [reconciliation](../results/repeatability-v1/gemini37-high-wave-v1/reconciliation.json) and [updated report](../public-site/gemini-repeats.json).
