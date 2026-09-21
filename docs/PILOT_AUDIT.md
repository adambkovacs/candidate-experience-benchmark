# Development audit — v0.2

Date: 2026-09-21. Reviewer: same OpenAI assistant that authored the pilot; exact model ID not exposed. User delegated this review. This is a critical self-review, not independent adjudication or evidence of model performance.

## Verdict

The original pilot was useful for discussion but too easy and internally inconsistent for a credible showcase. Broad industry labels alone do not make a rigorous benchmark. Keep four judgments and the 400-record ceiling; spend effort on realistic boundaries, paired cases and observable errors.

## Corrections to original labels

| ID | Field | Previous | Revised | Reason |
| --- | --- | --- | --- | --- |
| DEV-006 | sentiment | insufficient_information | negative | Missing incident details do not erase expressed dissatisfaction. |
| DEV-008 | sentiment | negative | mixed | Explicit satisfaction with resolution is meaningful praise alongside criticism. |
| DEV-018 | sentiment | insufficient_information | negative | Tentative discomfort still has a direction. |
| DEV-018 | serious_concern_reported | insufficient_information | no | Generic unease alone is not a specifically alleged serious issue. |
| DEV-022 | serious_concern_reported | no | insufficient_information | Humiliating treatment needs clarification rather than dismissal. |
| DEV-030 | follow_up_needed | insufficient_information | yes | Not knowing whether reassessment will happen is itself an unresolved clarification need. |

Original text and labels are preserved in Git history. The machine-readable review log records before/after values for every original record. Unchanged records were also checked against the revised rules.

## High-impact policy changes

- Include reported retaliation and concrete intrusive selection questions.
- Do not require prior approval before a refused accessibility request can trigger review.
- Distinguish vague criticism from insufficient evidence of a specific serious category.
- Keep ordinary candidate contact separate from internal escalation.
- Do not let positive tone, apology, withdrawal or a no-contact request suppress a serious report.
- Apply one operational policy consistently across identity substitutions; do not infer legal status.

## Coverage added

DEV-031–060 fill the remaining 30 development slots, not extra held-out records. Total authored: 60 of 400; remaining: 340.
Coverage includes age stereotypes; irrelevant religion disclosures; sexual harassment; retaliation; accommodation denial/support; intrusive health inquiries versus participation-adjustment questions; national-origin/accent stereotypes versus work samples; sex, sexual-orientation, gender-identity and race-related reports; vague versus explicit culture-fit exclusion; informal versus formal complaints; no-contact requests; policy mentions; pregnancy questions; optional monitoring; specific second-hand reports; work-schedule requirements; resolved privacy exposure; and unsupported discrimination suspicion.

The development set is deliberately enriched for concerns. It cannot estimate their prevalence in real recruitment or support demographic fairness claims. DEV-031/032 are illustrative age cases, not a controlled pair (other text and role differ). Controlled pairs are explicitly listed in pairs.json.

## What we can test now

A standard-library Python runner sends one feedback record per fresh LM Studio request and validates the four-field response. The evaluator retains missing/invalid outputs in the denominator, reports per-label precision/recall/F1, separates serious misses from review/abstention, and checks six controlled pairs. It records raw responses, configuration notes and prompt/input hashes. Model distributions, calibration, hosted billing, full latency analysis and subscription adapters remain future work.

Development transport errors are recorded without retries; this is a smoke-test protocol, distinct from the final planned retry policy. Exact model artifact, quantization and runtime must be supplied in the config note. No silent schema repair. No reference labels are read by the run command.

## Highest-ROI next step

Run three configurations on this development set: Jev, one small local generator, and one larger model. First establish that the task works and the failure categories are informative. Add other adapters after this smoke test.
Freeze rubric and prompts only after development review. Then author 40 validation + 200 ordinary + 100 challenge records from new scenario families.

Reserve at least 40 of the planned 100 challenge records for bias/concern probes, overlapping existing challenge families rather than expanding the dataset: concrete reports, benign identity mentions, ambiguous proxies, and controlled identity/style changes. Include counterexamples that should NOT escalate as well as cases that should. Preserve the existing 20-pair total; allocate at least eight pairs to identity/style invariance and four to meaningful concern-evidence changes. These are design commitments, not generated test cases.

## Evidence limitations

This assistant has seen and written the answer key. It cannot be counted as a blinded benchmark contestant in this conversation. Subsequent evaluated models must receive only the permitted input and policy in a fresh inference context.
Proceed with clearly labeled AI-reference development results under the user's delegation. Human or independent expert checking would improve a published reference set, but is not falsely claimed and does not block development.
