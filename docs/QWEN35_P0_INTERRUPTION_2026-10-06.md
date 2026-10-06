# Qwen3.5 4B thinking-on: first P0 pass interrupted

The first fresh P0 development pass stopped before all 60 reviews were sent. It has **no full-pass score** and counts as **zero of nine completed conditions** for this configuration. The [terminal receipt](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/development.completion.json) records 52 attempted requests and 51 saved responses. Rechecking the saved [raw responses](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/development.raw.jsonl), [parsed records](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/development.records.jsonl) and [journal](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/development.journal.jsonl) gives this fixed 60-position accounting:

| Outcome | Reviews | Count |
| --- | --- | ---: |
| Valid saved response | DEV-001 to DEV-051, excluding the seven invalid responses | 44 |
| Invalid saved response | Within DEV-001 to DEV-051 | 7 |
| Stopped with unknown outcome | DEV-052 | 1 |
| Never sent | DEV-053 to DEV-060 | 8 |

The [root interruption review](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/interruption.root-review.json) binds the terminal and [host audit](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/interruption.host-audit.json) by SHA-256. The host audit confirms sleep and hibernation during DEV-052. It supports that timing caveat, but does not establish the model's internal state or a pure inference duration. DEV-052 remains unknown even though cancellation was requested.

The [source-bound repeat feed](../public-site/legacy-qwen-repeats.json) keeps this phase in `missingPasses` and `partialPasses`; it does not add a `passes.fresh1.P0` score. The other eight phases remain uncompleted in this cutoff. Reference labels were used only for offline analysis, and invalid responses were kept without repair. Any later suffix needs its own admission and evidence; this report makes no claim that one has run.
