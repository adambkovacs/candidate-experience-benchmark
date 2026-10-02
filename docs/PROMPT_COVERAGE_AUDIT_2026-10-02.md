# Public prompt coverage audit, 2026-10-02

This is a read-only reconciliation of the local [public explorer feed](../public-site/data.json), its 163-entry roster, and the published repeat reports. It counts saved public condition views by **experiment ID**. A later run with different controls does not fill a missing condition in an earlier configuration. This audit does not establish the state of the live website or authorize inference.

| Public experiment coverage | Count |
| --- | ---: |
| Experiment IDs in the feed | 126 |
| IDs with P0, P1 and P2 views | 82 |
| IDs with only a P0 view | 44 |
| Roster entries marked `scheduled` | 76 |
| Scheduled IDs with all three views | 69 |
| Scheduled IDs with only P0 | 7 |

The **seven scheduled P0-only IDs** are the native-observed Antigravity Gemini batch-of-10 configurations: 3.1 Pro low and high, 3.6 Flash low and medium, and 3.7 Flash low, medium and high. Their 14 P1/P2 condition cells have no completed public view. The [roster accounting](MVP_ROSTER_ACCOUNTING.md) calls each route *blocked after P0* and says to use OpenRouter for current Gemini work; an OpenRouter result is a separate configuration. The public feed still labels all seven `scheduled`, so its disposition does not convey that operational block. The 3.1 Pro low P1 [partial report](../results/prompt-comparison-v1-2026-09-24/gemini-exact-v2/billing-default-continuation-v1/partial-report.md) retains 40 valid responses, 10 saved service errors and 10 unattempted records. It is not a full public P1 run.

Of the other 37 P0-only IDs, 16 are older single-record views with a **separate, completed batch or fresh matched series**. Thirteen older Claude IDs map to 12 distinct Fable 5.1, Opus 5 and Sonnet 5 batch-of-10 configurations with nine closed condition/pass combinations each in the [Claude roster repeat report](../public-site/claude-roster-repeats.json); both older Sonnet 5 low variants point to the same later low batch configuration. The older Haiku ID has its own completed [fresh matched-three series](../public-site/haiku-fresh-matched3.json), separate from the historical batch P1 transport failure. Two older Codex low IDs have separate batch-of-10 configurations with nine closed combinations each in the [Codex repeat report](../public-site/repeats.json). These 15 later series do not turn the 16 earlier P0-only configurations into matched P0/P1/P2 experiments.

The remaining 21 P0-only IDs are excluded under the current roster: 15 native or specialist methods without applicable chat prompt variants, three superseded local Qwen routes, and three max-effort Claude routes. Their empty P1/P2 cells are recorded exclusions, not missing scheduled work. The [roster accounting](MVP_ROSTER_ACCOUNTING.md) records those route decisions and preserves their original P0 evidence.

The immediate public-feed reconciliation is to label the seven Antigravity rows consistently with their blocked operational status while retaining their P0 and partial P1 evidence. The wider [current goals](CURRENT_GOALS.md) still require completion of the broader repeat matrix. The new [Sonnet 5.5 admission plan](SONNET55_MATCHED3_ADMISSION_2026-10-02.md) is outside this public-feed count: its 36 development phases are planned separately, with no closed phase counted here.
