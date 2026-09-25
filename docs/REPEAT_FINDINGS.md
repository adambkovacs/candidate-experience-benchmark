# Prompt repeat findings

Each configuration is a separate series on the same 60 development records. Scores and pass counts are reported within each configuration.

## GPT-6 Luna · medium effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 50/60 | 55/60 | 59/60 | 58/60 | 57/60 | 973.9 | 61445 | 2034 |
| original | P1 | 60/60 | 52/60 | 55/60 | 60/60 | 59/60 | 58/60 | 117.2 | 62473 | 2032 |
| original | P2 | 60/60 | 51/60 | 55/60 | 60/60 | 59/60 | 56/60 | 146.7 | 67891 | 2028 |
| repeat2 | P0 | 60/60 | 54/60 | 57/60 | 59/60 | 58/60 | 59/60 | 133.4 | 62631 | 2028 |
| repeat2 | P1 | 60/60 | 52/60 | 55/60 | 59/60 | 60/60 | 58/60 | 117.7 | 63667 | 2032 |
| repeat2 | P2 | 60/60 | 53/60 | 57/60 | 60/60 | 59/60 | 56/60 | 119.5 | 69079 | 2028 |
| repeat3 | P0 | 60/60 | 51/60 | 53/60 | 60/60 | 60/60 | 58/60 | 128.1 | 62623 | 2030 |
| repeat3 | P1 | 60/60 | 53/60 | 56/60 | 60/60 | 60/60 | 57/60 | 116.8 | 63661 | 2030 |
| repeat3 | P2 | 60/60 | 51/60 | 55/60 | 59/60 | 60/60 | 57/60 | 113.9 | 69075 | 2032 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +2; sentiment +0, follow_up_needed +1, serious_concern_reported +1, testimonial_potential +1.
- original P2: all four +1; sentiment +0, follow_up_needed +1, serious_concern_reported +1, testimonial_potential -1.
- repeat2 P1: all four -2; sentiment -2, follow_up_needed +0, serious_concern_reported +2, testimonial_potential -1.
- repeat2 P2: all four -1; sentiment +0, follow_up_needed +1, serious_concern_reported +1, testimonial_potential -3.
- repeat3 P1: all four +2; sentiment +3, follow_up_needed +0, serious_concern_reported +0, testimonial_potential -1.
- repeat3 P2: all four +0; sentiment +2, follow_up_needed -1, serious_concern_reported +0, testimonial_potential -1.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 50, 54, 51 of 60; mean 51.67; range 50 to 54.
- P0 sentiment: 55, 57, 53 of 60; mean 55.00; range 53 to 57.
- P0 follow_up_needed: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P0 serious_concern_reported: 58, 58, 60 of 60; mean 58.67; range 58 to 60.
- P0 testimonial_potential: 57, 59, 58 of 60; mean 58.00; range 57 to 59.
- P1 all four: 52, 52, 53 of 60; mean 52.33; range 52 to 53.
- P1 sentiment: 55, 55, 56 of 60; mean 55.33; range 55 to 56.
- P1 follow_up_needed: 60, 59, 60 of 60; mean 59.67; range 59 to 60.
- P1 serious_concern_reported: 59, 60, 60 of 60; mean 59.67; range 59 to 60.
- P1 testimonial_potential: 58, 58, 57 of 60; mean 57.67; range 57 to 58.
- P2 all four: 51, 53, 51 of 60; mean 51.67; range 51 to 53.
- P2 sentiment: 55, 57, 55 of 60; mean 55.67; range 55 to 57.
- P2 follow_up_needed: 60, 60, 59 of 60; mean 59.67; range 59 to 60.
- P2 serious_concern_reported: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P2 testimonial_potential: 56, 56, 57 of 60; mean 56.33; range 56 to 57.

Paired P1/P2 minus P0 all-four spread:

- P1: +2, -2, +2; three-pair range -2 to +2.
- P2: +1, -1, +0; three-pair range -1 to +1.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 7/60 | 3/60 | 0/60 | 2/60 | 2/60 |
| P0 | original to repeat3 | 60/60 | 7/60 | 3/60 | 1/60 | 2/60 | 1/60 |
| P0 | repeat2 to repeat3 | 60/60 | 8/60 | 5/60 | 1/60 | 2/60 | 1/60 |
| P1 | original to repeat2 | 60/60 | 6/60 | 2/60 | 1/60 | 1/60 | 2/60 |
| P1 | original to repeat3 | 60/60 | 6/60 | 4/60 | 0/60 | 1/60 | 1/60 |
| P1 | repeat2 to repeat3 | 60/60 | 4/60 | 2/60 | 1/60 | 0/60 | 1/60 |
| P2 | original to repeat2 | 60/60 | 5/60 | 5/60 | 0/60 | 0/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 7/60 | 5/60 | 1/60 | 1/60 | 1/60 |
| P2 | repeat2 to repeat3 | 60/60 | 7/60 | 4/60 | 1/60 | 1/60 | 1/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 50 to 54 of 60 comments per pass; 10 comments changed at least one decision across the three passes.

P1 matched all four references on 52 to 53 of 60 comments per pass; 8 comments changed at least one decision across the three passes.

P2 matched all four references on 51 to 53 of 60 comments per pass; 9 comments changed at least one decision across the three passes.

P1 versus P0 changed direction across passes: changes were +2, -2, +2 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 changed direction across passes: changes were +1, -1, +0 matches out of 60. Three passes do not establish a reliable future effect.

## GPT-6 Sol · high effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 495.8 | 62529 | 3574 |
| original | P1 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 163.0 | 63557 | 3678 |
| original | P2 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 188.7 | 68961 | 3857 |
| repeat2 | P0 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 145.1 | 63699 | 3567 |
| repeat2 | P1 | 60/60 | 58/60 | 59/60 | 59/60 | 59/60 | 60/60 | 147.0 | 64743 | 3729 |
| repeat2 | P2 | 60/60 | 57/60 | 58/60 | 60/60 | 58/60 | 60/60 | 139.2 | 70153 | 3155 |
| repeat3 | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 58/60 | 60/60 | 148.0 | 63695 | 3553 |
| repeat3 | P1 | 60/60 | 58/60 | 59/60 | 60/60 | 58/60 | 60/60 | 159.1 | 64733 | 3556 |
| repeat3 | P2 | 60/60 | 58/60 | 59/60 | 59/60 | 59/60 | 60/60 | 149.7 | 70155 | 3632 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +0; sentiment +0, follow_up_needed -1, serious_concern_reported +0, testimonial_potential +0.
- original P2: all four +0; sentiment +0, follow_up_needed -1, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P1: all four +1; sentiment +1, follow_up_needed -1, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +0.
- repeat3 P1: all four +1; sentiment +1, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +0.
- repeat3 P2: all four +1; sentiment +1, follow_up_needed +0, serious_concern_reported +1, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 57, 57, 57 of 60; mean 57.00; range 57 to 57.
- P0 sentiment: 58, 58, 58 of 60; mean 58.00; range 58 to 58.
- P0 follow_up_needed: 60, 60, 59 of 60; mean 59.67; range 59 to 60.
- P0 serious_concern_reported: 59, 59, 58 of 60; mean 58.67; range 58 to 59.
- P0 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 all four: 57, 58, 58 of 60; mean 57.67; range 57 to 58.
- P1 sentiment: 58, 59, 59 of 60; mean 58.67; range 58 to 59.
- P1 follow_up_needed: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P1 serious_concern_reported: 59, 59, 58 of 60; mean 58.67; range 58 to 59.
- P1 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P2 all four: 57, 57, 58 of 60; mean 57.33; range 57 to 58.
- P2 sentiment: 58, 58, 59 of 60; mean 58.33; range 58 to 59.
- P2 follow_up_needed: 59, 60, 59 of 60; mean 59.33; range 59 to 60.
- P2 serious_concern_reported: 59, 58, 59 of 60; mean 58.67; range 58 to 59.
- P2 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: +0, +1, +1; three-pair range +0 to +1.
- P2: +0, +0, +1; three-pair range +0 to +1.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 0/60 | 0/60 | 0/60 | 0/60 | 0/60 |
| P0 | original to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |
| P0 | repeat2 to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |
| P1 | original to repeat2 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P1 | original to repeat3 | 60/60 | 3/60 | 1/60 | 1/60 | 1/60 | 0/60 |
| P1 | repeat2 to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 3/60 | 1/60 | 1/60 | 1/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 57 to 57 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P1 matched all four references on 57 to 58 of 60 comments per pass; 3 comments changed at least one decision across the three passes.

P2 matched all four references on 57 to 58 of 60 comments per pass; 3 comments changed at least one decision across the three passes.

P1 versus P0 did not improve agreement in every pass: changes were +0, +1, +1 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 did not improve agreement in every pass: changes were +0, +0, +1 matches out of 60. Three passes do not establish a reliable future effect.

## GPT-6 Sol · medium effort

Completed conditions: 6/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 58/60 | 59/60 | 60/60 | 59/60 | 60/60 | 1267.0 | 62523 | 3118 |
| original | P1 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 136.6 | 63565 | 3070 |
| original | P2 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 136.4 | 68967 | 3218 |
| repeat2 | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 289.9 | 63709 | 3216 |
| repeat2 | P1 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 197.8 | 64735 | 3036 |
| repeat2 | P2 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 221.3 | 70149 | 3053 |
| repeat3 | P0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| repeat3 | P1 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| repeat3 | P2 | missing | missing | missing | missing | missing | missing | missing | missing | missing |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four -1; sentiment -1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- original P2: all four -1; sentiment -1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P1: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 58, 57 of 60; mean pending; range pending.
- P0 sentiment: 59, 58 of 60; mean pending; range pending.
- P0 follow_up_needed: 60, 59 of 60; mean pending; range pending.
- P0 serious_concern_reported: 59, 59 of 60; mean pending; range pending.
- P0 testimonial_potential: 60, 60 of 60; mean pending; range pending.
- P1 all four: 57, 57 of 60; mean pending; range pending.
- P1 sentiment: 58, 58 of 60; mean pending; range pending.
- P1 follow_up_needed: 60, 59 of 60; mean pending; range pending.
- P1 serious_concern_reported: 59, 59 of 60; mean pending; range pending.
- P1 testimonial_potential: 60, 60 of 60; mean pending; range pending.
- P2 all four: 57, 57 of 60; mean pending; range pending.
- P2 sentiment: 58, 58 of 60; mean pending; range pending.
- P2 follow_up_needed: 60, 59 of 60; mean pending; range pending.
- P2 serious_concern_reported: 59, 59 of 60; mean pending; range pending.
- P2 testimonial_potential: 60, 60 of 60; mean pending; range pending.

Paired P1/P2 minus P0 all-four spread:

- P1: -1, +0; three-pair range pending.
- P2: -1, +0; three-pair range pending.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 2/60 | 1/60 | 1/60 | 0/60 | 0/60 |
| P1 | original to repeat2 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:


