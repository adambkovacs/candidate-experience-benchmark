# Recruitment Feedback Demo — project plan

Status: planning only. No dataset generated, model calls made, application built, or results measured.
Repository: https://github.com/adambkovacs/recruitment-feedback-demo (private).
Owner: adambkovacs.

## Goal and scope

Build an interactive showcase of TypeSafe Jev classifying candidate feedback about the recruitment experience, separating sentiment from operational action. Demonstrate overlapping signals, uncertainty, human review, and measured performance on a small synthetic benchmark.

Version 1 covers candidate-experience feedback. Version 2 may check interviewer notes against hire/no-hire votes using a role rubric. Keep those datasets and evaluation tasks separate.

## Dataset size: 200

Start with 30 carefully written calibration examples, included in the final 200. Review the label definitions before generating the remaining 170. Two hundred is a practical demo budget, not a statistically established production validation sample. Expand to 500 only to fill observed coverage gaps or improve evaluation precision; use 1,000 later for throughput demonstrations.

Proposed primary scenario allocation (each record counted once here; output labels may overlap):

| Primary scenario | Count |
| --- | ---: |
| Ordinary positive experiences | 35 |
| Ordinary negative experiences | 35 |
| Mixed praise and criticism | 40 |
| Neutral, vague, or insufficient context | 25 |
| Specific praise with testimonial potential | 25 |
| Serious reported concerns requiring escalation review | 25 |
| Off-topic, empty, or instruction-like input | 15 |
| Total | 200 |

These proportions deliberately enrich difficult cases; they are not estimates of real candidate sentiment or complaint prevalence.

Vary interview stage, job family, seniority, writing length, formality, typos, indirectness, sarcasm, and explicit hiring outcome. Include courteous serious complaints, angry resolved complaints, rejected candidates with excellent experiences, hired candidates with bad experiences, and praise that also requests no public attribution. English first; multilingual evaluation is a separate expansion.

Reserve 20 of the 200 records for 10 paired tests: five same-meaning paraphrase pairs and five minimal-change pairs where a condition materially changes. Pairs remain in the same split. Avoid near-duplicate scenarios across splits.

Split by scenario family before tuning:
- Development: 100, including the initial 30.
- Validation: 40, for selecting routing thresholds.
- Held-out test: 60, untouched until questions and thresholds are frozen.

Stratify the scenario categories across splits where possible. A held-out set this small gives preliminary evidence; report denominators and uncertainty, especially for rare escalation cases. Once a test item informs tuning, it is no longer unseen for that revised version.

## Label contract

| Field | Meaning | Intended judgment |
| --- | --- | --- |
| sentiment | positive / negative / mixed / neutral / insufficient_information | Choice |
| topics | communication, scheduling, interviewer_conduct, assessment_burden, role_clarity, accessibility, other | Independent yes/no probabilities |
| unresolved_issue | Feedback explicitly describes a problem that remains unresolved | Noul |
| resolution_requested | Candidate asks for a response or remedy | Noul |
| serious_concern_reported | Describes conduct covered by the written escalation rubric | Noul |
| issue_severity | No problem / minor friction / substantial disruption / serious reported concern | Score with concrete anchors |
| testimonial_potential | Contains specific, self-contained praise useful for editorial review | Noul |
| publication_restriction_present | Explicitly asks not to publish or attribute the feedback | Noul |
| input_usable | Contains interpretable feedback relevant to recruitment experience | Noul |

The escalation rubric should list concrete reported events: threatening conduct, harassment allegations, discriminatory remarks, exposure of private information, and ignored agreed accessibility arrangements. Flag reported concerns for human review; do not declare allegations proven. Routine dissatisfaction is distinct from a serious concern.

Mixed sentiment is a content label, not model uncertainty. An uncertain answer routes to review regardless of whether sentiment is positive or negative. Noul is a yes probability, not an intensity score. Choice/Score confidence describes distribution concentration, not a guarantee of correctness.

## Routing rules

Keep judgment outputs reusable and routing policy in ordinary code. Multiple flags may coexist.

1. Serious reported concern: prioritize escalation review according to validated thresholds, even when the tone is positive.
2. Missing/uncertain information on an action-relevant question: human review. Ignore uncertainty on unused branches.
3. Unresolved ordinary issue or requested remedy: candidate-support follow-up queue.
4. Specific praise: testimonial editorial shortlist, with no publication implied.
5. Ordinary usable feedback without a required action: analytics queue.
6. Unusable/off-topic input: excluded or manual review, visibly distinguished from valid neutral feedback.

Publication consent is a separate explicit metadata field: unknown / granted / declined. Sentiment never grants consent. No emails, escalations, or career-site publication occur automatically in the demo; destinations are simulated queues.

## Record format and reference labels

Each record includes: id, feedback_text, interview_stage, job_family, synthetic=true, scenario_family_id, pair_id if applicable, split, and publication_consent.

Store reference labels separately from model inputs: expected_labels, expected_routes, supporting_source_spans, short human rationale, reviewer_status, disagreement_notes, and rubric_version. Do not pass generation instructions, scenario category, expected answers, or rationales into inference.

Generation produces draft labels only. A human reviewer validates all 200. Ideally a second reviewer independently labels the held-out 60 and all serious-concern examples without seeing model predictions. Preserve disagreement; adjudicate or mark genuinely ambiguous examples. Do not manufacture a single definite answer where the input cannot support one.

## Model integration plan

Use the TypeSafe skill and recheck live API/SDK/model documentation when implementation begins. Server-side API key only. Choose and record the exact Jev version at that point; do not assume today's model name remains current.

Send independent questions over one feedback record together. Use narrow questions with explicit definitions and no-match outcomes where needed. The application owns thresholding, routing, counts, and display. Jev supplies structured judgments; it does not generate explanatory paragraphs. Evidence highlighting can later select exact source spans; initially show the original feedback beside field definitions and stored reference rationales, clearly attributed.

Persist dataset version, question version, model version, thresholds, timestamps, latency, usage, errors, and outputs for each run. API failure is not ambiguity. Live results and recorded playback must be visibly distinguished. Never silently substitute invented outputs for an unavailable API.

## Evaluation

Measure sentiment macro-F1 and confusion matrix; per-flag precision and recall; serious-concern misses; unnecessary escalations; human-review share; accuracy among automatically routed records; paired-test consistency/sensitivity; and median/p95 end-to-end latency. Report usage and cost only from actual usage and verified pricing.

Compare with a simple keyword/sentiment baseline on the same held-out set. A general-purpose LLM baseline is optional for a later comparison. Measure correctness and latency separately from presentation animation.

Provisional readiness checks:
- All 200 records reviewed, deduplicated, and assigned to fixed splits.
- Questions and thresholds frozen before held-out evaluation.
- Every missed serious concern and false escalation inspected and reported.
- Routing trade-offs visible; no single aggregate accuracy hides failure cases.
- Secret handling, error display, and playback labeling verified.
- Claims limited to this synthetic benchmark; no invented target accuracy or production-readiness claim.

Set numerical accuracy goals after reviewing the pilot and human agreement, before evaluating the held-out test. Do not tune goals retrospectively to make results look good.

## Showcase interface

A feedback inbox with filters, a selected feedback card, structured judgments, topic tags, and simulated action queues. Show probability/confidence using accurate field-specific terminology. Include a human-review panel with editable labels, a threshold control, an evaluation panel, and clearly labeled live/playback modes.

Proposed five-minute presentation:
1. Let the audience route three contrasting examples.
2. Reveal Jev outputs and reference labels, including disagreement.
3. Show a positive comment that still warrants follow-up.
4. Run the 200-record set or replay a labeled recorded run with original measured timings.
5. Adjust review thresholds to show workload versus errors on validation data.
6. Show the frozen held-out result separately and invite a fresh audience example.

Select 8–12 memorable showcase records from development data. Keep the held-out test out of interactive prompt tuning. Audience-entered examples are exploratory, not benchmark results.

## Implementation backlog

1. Create private GitHub repository and commit this plan and README.
2. Finalize label definitions, escalation rubric, and routing examples.
3. Produce and review 30 calibration records.
4. Generate the remaining 170; deduplicate, split, and validate reference labels.
5. Implement versioned questions, server-side evaluation runner, and result persistence.
6. Tune using development/validation data, then run frozen held-out evaluation.
7. Build inbox, judgment cards, simulated queues, and threshold controls.
8. Add playback, error handling, presentation script, and documented limitations.

Suggested repository structure: README.md; docs/PLAN.md; docs/LABELING_GUIDE.md; docs/DEMO_SCRIPT.md; data/inputs/; data/reference/; questions/; evaluation/; app/. Decide framework when building starts; no ATS or database integration is required for the first 200-record demo.

## Inputs needed before implementation

- GitHub repository created; commit the planning documents before implementation.
- TypeSafe API access configured securely, never pasted into source control.
- A reviewer familiar with recruitment to validate the pilot and reference labels.
- Intended audience and presentation length; default assumption is a five-minute recruiter-facing showcase.
- Hosting choice only when the interface is ready to build or share.

## Reference patterns

- https://docs.typesafe.ai/primitives
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/concepts/how-to-build-with-system-one

These establish the intended programming approach; this plan reports no measured Jev recruitment performance.
