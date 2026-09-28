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

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 58/60 | 59/60 | 60/60 | 59/60 | 60/60 | 1267.0 | 62523 | 3118 |
| original | P1 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 136.6 | 63565 | 3070 |
| original | P2 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 136.4 | 68967 | 3218 |
| repeat2 | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 289.9 | 63709 | 3216 |
| repeat2 | P1 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 197.8 | 64735 | 3036 |
| repeat2 | P2 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 221.3 | 70149 | 3053 |
| repeat3 | P0 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 186.0 | 63709 | 3108 |
| repeat3 | P1 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 398.4 | 64745 | 3273 |
| repeat3 | P2 | 60/60 | 57/60 | 58/60 | 60/60 | 58/60 | 60/60 | 468.2 | 70234 | 2914 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four -1; sentiment -1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- original P2: all four -1; sentiment -1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P1: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat3 P1: all four +0; sentiment +0, follow_up_needed -1, serious_concern_reported +0, testimonial_potential +0.
- repeat3 P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 58, 57, 57 of 60; mean 57.33; range 57 to 58.
- P0 sentiment: 59, 58, 58 of 60; mean 58.33; range 58 to 59.
- P0 follow_up_needed: 60, 59, 60 of 60; mean 59.67; range 59 to 60.
- P0 serious_concern_reported: 59, 59, 59 of 60; mean 59.00; range 59 to 59.
- P0 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 all four: 57, 57, 57 of 60; mean 57.00; range 57 to 57.
- P1 sentiment: 58, 58, 58 of 60; mean 58.00; range 58 to 58.
- P1 follow_up_needed: 60, 59, 59 of 60; mean 59.33; range 59 to 60.
- P1 serious_concern_reported: 59, 59, 59 of 60; mean 59.00; range 59 to 59.
- P1 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P2 all four: 57, 57, 57 of 60; mean 57.00; range 57 to 57.
- P2 sentiment: 58, 58, 58 of 60; mean 58.00; range 58 to 58.
- P2 follow_up_needed: 60, 59, 60 of 60; mean 59.67; range 59 to 60.
- P2 serious_concern_reported: 59, 59, 58 of 60; mean 58.67; range 58 to 59.
- P2 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: -1, +0, +0; three-pair range -1 to +0.
- P2: -1, +0, +0; three-pair range -1 to +0.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 2/60 | 1/60 | 1/60 | 0/60 | 0/60 |
| P0 | original to repeat3 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P0 | repeat2 to repeat3 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P1 | original to repeat2 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P1 | original to repeat3 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P1 | repeat2 to repeat3 | 60/60 | 0/60 | 0/60 | 0/60 | 0/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 1/60 | 0/60 | 0/60 | 1/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 57 to 58 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P1 matched all four references on 57 to 57 of 60 comments per pass; 1 comments changed at least one decision across the three passes.

P2 matched all four references on 57 to 57 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P1 versus P0 did not improve agreement in every pass: changes were -1, +0, +0 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 did not improve agreement in every pass: changes were -1, +0, +0 matches out of 60. Three passes do not establish a reliable future effect.
## GPT-5.6 Luna · high effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 59/60 | 685.5 | 49401 | 5339 |
| original | P1 | 60/60 | 59/60 | 59/60 | 60/60 | 59/60 | 60/60 | 167.7 | 50431 | 4962 |
| original | P2 | 60/60 | 58/60 | 60/60 | 59/60 | 58/60 | 60/60 | 224.8 | 55849 | 4650 |
| repeat2 | P0 | 60/60 | 59/60 | 59/60 | 60/60 | 60/60 | 60/60 | 189.5 | 50579 | 5574 |
| repeat2 | P1 | 60/60 | 59/60 | 59/60 | 60/60 | 60/60 | 60/60 | 168.3 | 51617 | 4656 |
| repeat2 | P2 | 60/60 | 57/60 | 59/60 | 59/60 | 57/60 | 60/60 | 200.2 | 57025 | 5743 |
| repeat3 | P0 | 60/60 | 57/60 | 59/60 | 59/60 | 59/60 | 60/60 | 226.8 | 50587 | 6259 |
| repeat3 | P1 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 183.9 | 51621 | 5400 |
| repeat3 | P2 | 60/60 | 57/60 | 59/60 | 59/60 | 58/60 | 60/60 | 187.6 | 57027 | 5124 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +2; sentiment +1, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +1.
- original P2: all four +1; sentiment +2, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +1.
- repeat2 P1: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat2 P2: all four -2; sentiment +0, follow_up_needed -1, serious_concern_reported -3, testimonial_potential +0.
- repeat3 P1: all four +3; sentiment +1, follow_up_needed +1, serious_concern_reported +1, testimonial_potential +0.
- repeat3 P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 57, 59, 57 of 60; mean 57.67; range 57 to 59.
- P0 sentiment: 58, 59, 59 of 60; mean 58.67; range 58 to 59.
- P0 follow_up_needed: 59, 60, 59 of 60; mean 59.33; range 59 to 60.
- P0 serious_concern_reported: 59, 60, 59 of 60; mean 59.33; range 59 to 60.
- P0 testimonial_potential: 59, 60, 60 of 60; mean 59.67; range 59 to 60.
- P1 all four: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P1 sentiment: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P1 follow_up_needed: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 serious_concern_reported: 59, 60, 60 of 60; mean 59.67; range 59 to 60.
- P1 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P2 all four: 58, 57, 57 of 60; mean 57.33; range 57 to 58.
- P2 sentiment: 60, 59, 59 of 60; mean 59.33; range 59 to 60.
- P2 follow_up_needed: 59, 59, 59 of 60; mean 59.00; range 59 to 59.
- P2 serious_concern_reported: 58, 57, 58 of 60; mean 57.67; range 57 to 58.
- P2 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: +2, +0, +3; three-pair range +0 to +3.
- P2: +1, -2, +0; three-pair range -2 to +1.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 2/60 | 1/60 | 1/60 | 1/60 | 1/60 |
| P0 | original to repeat3 | 60/60 | 3/60 | 1/60 | 0/60 | 2/60 | 1/60 |
| P0 | repeat2 to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |
| P1 | original to repeat2 | 60/60 | 2/60 | 2/60 | 0/60 | 1/60 | 0/60 |
| P1 | original to repeat3 | 60/60 | 1/60 | 1/60 | 0/60 | 1/60 | 0/60 |
| P1 | repeat2 to repeat3 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 2/60 | 1/60 | 0/60 | 1/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 3/60 | 2/60 | 0/60 | 1/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 57 to 59 of 60 comments per pass; 3 comments changed at least one decision across the three passes.

P1 matched all four references on 59 to 60 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P2 matched all four references on 57 to 58 of 60 comments per pass; 3 comments changed at least one decision across the three passes.

P1 versus P0 did not improve agreement in every pass: changes were +2, +0, +3 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 changed direction across passes: changes were +1, -2, +0 matches out of 60. Three passes do not establish a reliable future effect.
## GPT-5.6 Luna · low effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 56/60 | 56/60 | 60/60 | 60/60 | 60/60 | 208.4 | 49409 | 3705 |
| original | P1 | 60/60 | 57/60 | 58/60 | 59/60 | 60/60 | 59/60 | 241.1 | 51633 | 3497 |
| original | P2 | 60/60 | 56/60 | 56/60 | 60/60 | 59/60 | 60/60 | 158.1 | 57037 | 3511 |
| repeat2 | P0 | 60/60 | 54/60 | 56/60 | 59/60 | 60/60 | 59/60 | 157.8 | 50583 | 3463 |
| repeat2 | P1 | 60/60 | 58/60 | 58/60 | 60/60 | 60/60 | 60/60 | 153.4 | 51615 | 3678 |
| repeat2 | P2 | 60/60 | 54/60 | 58/60 | 60/60 | 58/60 | 57/60 | 150.5 | 57035 | 3307 |
| repeat3 | P0 | 60/60 | 55/60 | 57/60 | 59/60 | 58/60 | 60/60 | 150.6 | 50583 | 3578 |
| repeat3 | P1 | 60/60 | 57/60 | 57/60 | 60/60 | 60/60 | 60/60 | 149.6 | 51619 | 3496 |
| repeat3 | P2 | 60/60 | 56/60 | 58/60 | 59/60 | 58/60 | 60/60 | 163.0 | 57037 | 3318 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +1; sentiment +2, follow_up_needed -1, serious_concern_reported +0, testimonial_potential -1.
- original P2: all four +0; sentiment +0, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +0.
- repeat2 P1: all four +4; sentiment +2, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +1.
- repeat2 P2: all four +0; sentiment +2, follow_up_needed +1, serious_concern_reported -2, testimonial_potential -2.
- repeat3 P1: all four +2; sentiment +0, follow_up_needed +1, serious_concern_reported +2, testimonial_potential +0.
- repeat3 P2: all four +1; sentiment +1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 56, 54, 55 of 60; mean 55.00; range 54 to 56.
- P0 sentiment: 56, 56, 57 of 60; mean 56.33; range 56 to 57.
- P0 follow_up_needed: 60, 59, 59 of 60; mean 59.33; range 59 to 60.
- P0 serious_concern_reported: 60, 60, 58 of 60; mean 59.33; range 58 to 60.
- P0 testimonial_potential: 60, 59, 60 of 60; mean 59.67; range 59 to 60.
- P1 all four: 57, 58, 57 of 60; mean 57.33; range 57 to 58.
- P1 sentiment: 58, 58, 57 of 60; mean 57.67; range 57 to 58.
- P1 follow_up_needed: 59, 60, 60 of 60; mean 59.67; range 59 to 60.
- P1 serious_concern_reported: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 testimonial_potential: 59, 60, 60 of 60; mean 59.67; range 59 to 60.
- P2 all four: 56, 54, 56 of 60; mean 55.33; range 54 to 56.
- P2 sentiment: 56, 58, 58 of 60; mean 57.33; range 56 to 58.
- P2 follow_up_needed: 60, 60, 59 of 60; mean 59.67; range 59 to 60.
- P2 serious_concern_reported: 59, 58, 58 of 60; mean 58.33; range 58 to 59.
- P2 testimonial_potential: 60, 57, 60 of 60; mean 59.00; range 57 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: +1, +4, +2; three-pair range +1 to +4.
- P2: +0, +0, +1; three-pair range +0 to +1.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 2/60 | 0/60 | 1/60 | 0/60 | 1/60 |
| P0 | original to repeat3 | 60/60 | 4/60 | 3/60 | 1/60 | 2/60 | 0/60 |
| P0 | repeat2 to repeat3 | 60/60 | 5/60 | 3/60 | 0/60 | 2/60 | 1/60 |
| P1 | original to repeat2 | 60/60 | 3/60 | 2/60 | 1/60 | 0/60 | 1/60 |
| P1 | original to repeat3 | 60/60 | 4/60 | 3/60 | 1/60 | 0/60 | 1/60 |
| P1 | repeat2 to repeat3 | 60/60 | 2/60 | 2/60 | 0/60 | 0/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 6/60 | 2/60 | 0/60 | 1/60 | 3/60 |
| P2 | original to repeat3 | 60/60 | 4/60 | 4/60 | 1/60 | 1/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 5/60 | 2/60 | 1/60 | 0/60 | 3/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 54 to 56 of 60 comments per pass; 5 comments changed at least one decision across the three passes.

P1 matched all four references on 57 to 58 of 60 comments per pass; 4 comments changed at least one decision across the three passes.

P2 matched all four references on 54 to 56 of 60 comments per pass; 7 comments changed at least one decision across the three passes.

P1 versus P0 improved agreement in all three observed passes: changes were +1, +4, +2 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 did not improve agreement in every pass: changes were +0, +0, +1 matches out of 60. Three passes do not establish a reliable future effect.
## GPT-5.6 Luna · medium effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 54/60 | 58/60 | 60/60 | 58/60 | 58/60 | 512.1 | 49395 | 4339 |
| original | P1 | 60/60 | 57/60 | 57/60 | 60/60 | 60/60 | 60/60 | 199.9 | 50435 | 4022 |
| original | P2 | 60/60 | 55/60 | 57/60 | 59/60 | 59/60 | 60/60 | 148.4 | 55841 | 4030 |
| repeat2 | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 60/60 | 59/60 | 162.9 | 50587 | 4048 |
| repeat2 | P1 | 60/60 | 57/60 | 57/60 | 60/60 | 60/60 | 60/60 | 157.0 | 51619 | 3755 |
| repeat2 | P2 | 60/60 | 56/60 | 59/60 | 59/60 | 58/60 | 60/60 | 159.2 | 57031 | 3936 |
| repeat3 | P0 | 60/60 | 55/60 | 56/60 | 58/60 | 60/60 | 58/60 | 166.8 | 52261 | 4283 |
| repeat3 | P1 | 60/60 | 55/60 | 56/60 | 59/60 | 60/60 | 60/60 | 159.3 | 53297 | 4112 |
| repeat3 | P2 | 60/60 | 56/60 | 58/60 | 59/60 | 58/60 | 60/60 | 162.7 | 58145 | 4112 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +3; sentiment -1, follow_up_needed +0, serious_concern_reported +2, testimonial_potential +2.
- original P2: all four +1; sentiment -1, follow_up_needed -1, serious_concern_reported +1, testimonial_potential +2.
- repeat2 P1: all four +0; sentiment -1, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +1.
- repeat2 P2: all four -1; sentiment +1, follow_up_needed +0, serious_concern_reported -2, testimonial_potential +1.
- repeat3 P1: all four +0; sentiment +0, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +2.
- repeat3 P2: all four +1; sentiment +2, follow_up_needed +1, serious_concern_reported -2, testimonial_potential +2.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 54, 57, 55 of 60; mean 55.33; range 54 to 57.
- P0 sentiment: 58, 58, 56 of 60; mean 57.33; range 56 to 58.
- P0 follow_up_needed: 60, 59, 58 of 60; mean 59.00; range 58 to 60.
- P0 serious_concern_reported: 58, 60, 60 of 60; mean 59.33; range 58 to 60.
- P0 testimonial_potential: 58, 59, 58 of 60; mean 58.33; range 58 to 59.
- P1 all four: 57, 57, 55 of 60; mean 56.33; range 55 to 57.
- P1 sentiment: 57, 57, 56 of 60; mean 56.67; range 56 to 57.
- P1 follow_up_needed: 60, 60, 59 of 60; mean 59.67; range 59 to 60.
- P1 serious_concern_reported: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P2 all four: 55, 56, 56 of 60; mean 55.67; range 55 to 56.
- P2 sentiment: 57, 59, 58 of 60; mean 58.00; range 57 to 59.
- P2 follow_up_needed: 59, 59, 59 of 60; mean 59.00; range 59 to 59.
- P2 serious_concern_reported: 59, 58, 58 of 60; mean 58.33; range 58 to 59.
- P2 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: +3, +0, +0; three-pair range +0 to +3.
- P2: +1, -1, +1; three-pair range -1 to +1.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 5/60 | 2/60 | 1/60 | 2/60 | 1/60 |
| P0 | original to repeat3 | 60/60 | 6/60 | 2/60 | 2/60 | 2/60 | 4/60 |
| P0 | repeat2 to repeat3 | 60/60 | 5/60 | 2/60 | 1/60 | 0/60 | 3/60 |
| P1 | original to repeat2 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P1 | original to repeat3 | 60/60 | 2/60 | 1/60 | 1/60 | 0/60 | 0/60 |
| P1 | repeat2 to repeat3 | 60/60 | 3/60 | 2/60 | 1/60 | 0/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 3/60 | 2/60 | 0/60 | 1/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 4/60 | 3/60 | 0/60 | 1/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 3/60 | 1/60 | 0/60 | 2/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 54 to 57 of 60 comments per pass; 7 comments changed at least one decision across the three passes.

P1 matched all four references on 55 to 57 of 60 comments per pass; 3 comments changed at least one decision across the three passes.

P2 matched all four references on 55 to 56 of 60 comments per pass; 5 comments changed at least one decision across the three passes.

P1 versus P0 did not improve agreement in every pass: changes were +3, +0, +0 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 changed direction across passes: changes were +1, -1, +1 matches out of 60. Three passes do not establish a reliable future effect.
## GPT-5.6 Sol · high effort

Completed conditions: 9/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.

| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | P0 | 60/60 | 58/60 | 59/60 | 59/60 | 59/60 | 60/60 | 290.1 | 58453 | 3914 |
| original | P1 | 60/60 | 58/60 | 59/60 | 60/60 | 59/60 | 60/60 | 336.0 | 59491 | 3834 |
| original | P2 | 60/60 | 57/60 | 58/60 | 59/60 | 58/60 | 60/60 | 534.1 | 64913 | 4056 |
| repeat2 | P0 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 162.4 | 59643 | 4071 |
| repeat2 | P1 | 60/60 | 58/60 | 58/60 | 60/60 | 60/60 | 60/60 | 159.8 | 60679 | 3944 |
| repeat2 | P2 | 60/60 | 57/60 | 58/60 | 60/60 | 58/60 | 60/60 | 162.6 | 66093 | 3794 |
| repeat3 | P0 | 60/60 | 57/60 | 58/60 | 60/60 | 59/60 | 60/60 | 164.2 | 61315 | 4071 |
| repeat3 | P1 | 60/60 | 58/60 | 59/60 | 60/60 | 59/60 | 60/60 | 158.9 | 62349 | 3846 |
| repeat3 | P2 | 60/60 | 57/60 | 58/60 | 59/60 | 59/60 | 60/60 | 157.5 | 67755 | 3756 |

Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):

- original P1: all four +0; sentiment +0, follow_up_needed +1, serious_concern_reported +0, testimonial_potential +0.
- original P2: all four -1; sentiment -1, follow_up_needed +0, serious_concern_reported -1, testimonial_potential +0.
- repeat2 P1: all four +1; sentiment +0, follow_up_needed +1, serious_concern_reported +1, testimonial_potential +0.
- repeat2 P2: all four +0; sentiment +0, follow_up_needed +1, serious_concern_reported -1, testimonial_potential +0.
- repeat3 P1: all four +1; sentiment +1, follow_up_needed +0, serious_concern_reported +0, testimonial_potential +0.
- repeat3 P2: all four +0; sentiment +0, follow_up_needed -1, serious_concern_reported +0, testimonial_potential +0.

Three-pass scores (mean and range appear when all three passes are complete):

- P0 all four: 58, 57, 57 of 60; mean 57.33; range 57 to 58.
- P0 sentiment: 59, 58, 58 of 60; mean 58.33; range 58 to 59.
- P0 follow_up_needed: 59, 59, 60 of 60; mean 59.33; range 59 to 60.
- P0 serious_concern_reported: 59, 59, 59 of 60; mean 59.00; range 59 to 59.
- P0 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 all four: 58, 58, 58 of 60; mean 58.00; range 58 to 58.
- P1 sentiment: 59, 58, 59 of 60; mean 58.67; range 58 to 59.
- P1 follow_up_needed: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P1 serious_concern_reported: 59, 60, 59 of 60; mean 59.33; range 59 to 60.
- P1 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.
- P2 all four: 57, 57, 57 of 60; mean 57.00; range 57 to 57.
- P2 sentiment: 58, 58, 58 of 60; mean 58.00; range 58 to 58.
- P2 follow_up_needed: 59, 60, 59 of 60; mean 59.33; range 59 to 60.
- P2 serious_concern_reported: 58, 58, 59 of 60; mean 58.33; range 58 to 59.
- P2 testimonial_potential: 60, 60, 60 of 60; mean 60.00; range 60 to 60.

Paired P1/P2 minus P0 all-four spread:

- P1: +0, +1, +1; three-pair range +0 to +1.
- P2: -1, +0, +0; three-pair range -1 to +0.

Reference class counts (60 records):

- sentiment: insufficient_information 2, mixed 8, negative 31, neutral 8, positive 11
- follow_up_needed: insufficient_information 1, no 24, yes 35
- serious_concern_reported: insufficient_information 6, no 29, yes 25
- testimonial_potential: insufficient_information 1, no 50, yes 9

Completed pass comparisons, changed labels among records valid in both passes:

| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P0 | original to repeat2 | 60/60 | 1/60 | 1/60 | 0/60 | 0/60 | 0/60 |
| P0 | original to repeat3 | 60/60 | 2/60 | 1/60 | 1/60 | 0/60 | 0/60 |
| P0 | repeat2 to repeat3 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P1 | original to repeat2 | 60/60 | 2/60 | 1/60 | 0/60 | 1/60 | 0/60 |
| P1 | original to repeat3 | 60/60 | 0/60 | 0/60 | 0/60 | 0/60 | 0/60 |
| P1 | repeat2 to repeat3 | 60/60 | 2/60 | 1/60 | 0/60 | 1/60 | 0/60 |
| P2 | original to repeat2 | 60/60 | 1/60 | 0/60 | 1/60 | 0/60 | 0/60 |
| P2 | original to repeat3 | 60/60 | 1/60 | 0/60 | 0/60 | 1/60 | 0/60 |
| P2 | repeat2 to repeat3 | 60/60 | 2/60 | 0/60 | 1/60 | 1/60 | 0/60 |

The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.

Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.

The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.

Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).

Observed patterns:

P0 matched all four references on 57 to 58 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P1 matched all four references on 58 to 58 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P2 matched all four references on 57 to 57 of 60 comments per pass; 2 comments changed at least one decision across the three passes.

P1 versus P0 did not improve agreement in every pass: changes were +0, +1, +1 matches out of 60. Three passes do not establish a reliable future effect.

P2 versus P0 did not improve agreement in every pass: changes were -1, +0, +0 matches out of 60. Three passes do not establish a reliable future effect.
