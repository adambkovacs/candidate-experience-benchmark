# Reference review v1: frequent disputes and Jev cases

Date: 2026-09-25. Reviewer: a separate Codex AI review of the development key. This is not human adjudication or a blinded test. I read the [labeling guide](../docs/LABELING_GUIDE.md), [pilot audit](../docs/PILOT_AUDIT.md), [inputs](../data/pilot/inputs.jsonl), [proposed labels](../data/pilot/proposed_labels.jsonl), and [saved results](../public-site/data.json). The three frequent disputes were DEV-006, DEV-013, and DEV-030. I also checked the six [Jev disagreements](../docs/FINDINGS.md#jevs-six-disagreements-need-different-explanations). Source SHA-256 hashes and calculations are in [the review result](../results/reference-review-v1.json).

## Decision

Propose one reference correction: DEV-006 `serious_concern_reported: insufficient_information -> no`. The text establishes an open problem, but alleges no serious category. The current guide reserves `insufficient_information` for a specifically alleged but underspecified serious issue. This correction is a rubric decision, not an inference from model votes. It is recorded as a [separate proposed revision](../data/pilot/reference-revisions/v0.3.json); the v0.2 key and all run files stay intact.

DEV-013 and DEV-030 need human adjudication before a reference change. The current wording permits reasonable disagreement about their sentiment. Keep their saved labels for the present experiment. DEV-027, DEV-029, and DEV-059 have clear answers under the current guide, so their Jev disagreements remain model errors against this operational key.

## Field decisions

| Record | Field | Saved label | Review decision | Reason |
| --- | --- | --- | --- | --- |
| DEV-006 | sentiment | negative | Keep, definitive | "Again" and "still isn't sorted" express dissatisfaction with the experience. |
| DEV-006 | follow_up_needed | yes | Keep, definitive | The problem is explicitly unresolved. |
| DEV-006 | serious_concern_reported | insufficient_information | Propose `no`, definitive under current guide | "That thing" names no serious category or conduct. Missing detail about an ordinary open issue is not a serious allegation. |
| DEV-006 | testimonial_potential | no | Keep, definitive | The feedback is unfavorable and lacks an endorsement. |
| DEV-013 | sentiment | neutral | Keep pending human decision | "Straightforward" may be mild praise or a matter-of-fact account. "No complaint" establishes absence of criticism, not necessarily a favorable evaluation. `positive` is defensible, but the guide does not fix this boundary. |
| DEV-013 | follow_up_needed | no | Keep, definitive | The candidate reports no issue in their own interview and asks for nothing. |
| DEV-013 | serious_concern_reported | no | Keep, definitive | An unspecified rumor about other experiences does not meet the concrete report threshold. |
| DEV-013 | testimonial_potential | no | Keep, definitive | Even if sentiment becomes positive, the text lacks a specific favorable recruitment example and includes a rumor. |
| DEV-027 | sentiment | positive | Keep, definitive | "Really helpful" praises the interviewers' concrete response to the cancelled train. |
| DEV-027 | follow_up_needed | no | Keep, definitive | The video interview took place; no open request is reported. |
| DEV-027 | serious_concern_reported | no | Keep, definitive | No qualifying conduct is reported. |
| DEV-027 | testimonial_potential | yes | Keep, definitive | The praise and the concrete accommodation stand alone as a favorable recruitment account. The [paired case](../data/pilot/pairs.json) describes the same judgment in different wording. |
| DEV-029 | sentiment | insufficient_information | Keep, definitive | The restaurant review gives no recruitment experience to judge. |
| DEV-029 | follow_up_needed | insufficient_information | Keep, definitive | Its complaint concerns food, not a candidate-facing recruitment issue. |
| DEV-029 | serious_concern_reported | insufficient_information | Keep, definitive | The entire submission is off-topic; the guide assigns all four fields this value. |
| DEV-029 | testimonial_potential | insufficient_information | Keep, definitive | A food review cannot be assessed as recruitment feedback. |
| DEV-030 | sentiment | neutral | Keep pending human decision | "Accessibility issue" can imply an adverse experience, and uncertain reassessment can support `negative`. Yet the candidate says the issue may have been dealt with and gives no clear evaluation. The guide does not settle the implied-evaluation threshold here. |
| DEV-030 | follow_up_needed | yes | Keep, definitive | The candidate does not know whether they will get another assessment. Clarification is still needed. |
| DEV-030 | serious_concern_reported | insufficient_information | Keep, definitive under current guide | A specific accessibility issue is alleged, but the conduct is missing. The text does not say an arrangement was refused or ignored. |
| DEV-030 | testimonial_potential | no | Keep, definitive | The uncertainty and absent praise cannot form an endorsement. |
| DEV-059 | sentiment | mixed | Keep, definitive | "Nice staff" is praise alongside repeated unwanted advances. |
| DEV-059 | follow_up_needed | yes | Keep, definitive | The candidate has asked the recruiter to stop further contact; the request remains open. |
| DEV-059 | serious_concern_reported | yes | Keep, definitive | The manager repeatedly asked the candidate out after two refusals. The operational guide flags specific repeated unwanted conduct for review. |
| DEV-059 | testimonial_potential | no | Keep, definitive | The full submission includes a serious concern. |

DEV-013's sentiment and DEV-030's sentiment are `needs_human` in the companion JSON. A human reviewer should choose a consistent boundary, then recheck other affected development examples before any new key is adopted. The saved model votes are diagnostic evidence of disagreement, not votes that determine the reference.

## Proposed guide clarification

Add the following text to a versioned addendum. Do not alter the original v0.2 guide in place:

> For `serious_concern_reported`, an unspecified recurring or unresolved problem is `no` unless the feedback alleges a serious category, however vaguely. Missing incident details alone do not make this field `insufficient_information`. Use `insufficient_information` when a specific serious issue is alleged but the conduct is too underspecified to decide whether it meets the `yes` threshold. An "accessibility issue" names a serious category but does not, by itself, establish that an arrangement was refused or ignored.

For sentiment, human review should decide whether terms such as "straightforward" count as favorable evaluation and whether a named "issue" with uncertain resolution counts as criticism. A guide addendum should state those choices with examples and recheck all 60 development references affected by them.

## Counterfactual score effect of DEV-006 only

The [calculation file](../results/reference-review-v1.json) changes only DEV-006's serious-concern reference in memory. It reads the frozen public case export and the same 38 strict hosted/subscription P0 run IDs used in the [findings](../docs/FINDINGS.md#disagreements-cluster-around-three-ambiguous-reviews). Invalid responses remain in the denominator. No model was rerun.

| Cohort | All four, saved | All four, proposed | Serious-concern field, saved | Serious-concern field, proposed |
| --- | ---: | ---: | ---: | ---: |
| Jev P0, 60 reviews | 54/60 | 55/60 (+1) | 57/60 | 58/60 (+1) |
| 38 strict P0 configurations, 2,280 configuration-review outcomes | 2,143/2,280 | 2,139/2,280 (-4) | 2,233/2,280 | 2,239/2,280 (+6) |

On DEV-006, 22 of the 38 strict predictions say `no` and 16 say `insufficient_information` for serious concern. The full-record matches move from 13 to 9 because several `no` predictions disagree on another field. This is why the field-level improvement and all-four decline can coexist. These 38 configurations are correlated runs on the same synthetic cases, not independent adjudicators. The changed score would describe agreement with a revised AI reference, not measured real-world accuracy.
