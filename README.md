# Recruitment Feedback Demo

An interactive candidate-experience feedback triage showcase using TypeSafe Jev.

**Status: planning.** No dataset, model results, or application yet.

## First demo

Classify candidate feedback across sentiment, topics, unresolved issues, serious reported concerns, and testimonial potential. Combine independent judgments into simulated action queues, with uncertainty routed to human review.

Start with **30 reviewed pilot examples**, then expand to **200 synthetic records**: 100 development, 40 validation, and 60 held-out test records. Showcase 8–12 development examples and report measured results separately.

Read [the full project plan](docs/PLAN.md) for dataset composition, labels, routing, evaluation, and the five-minute demo flow.

## Build checklist

- [x] Create private repository and planning documents.
- [ ] Finalize label definitions and escalation rubric.
- [ ] Create and review 30 calibration examples.
- [ ] Expand to 200; review labels and freeze splits.
- [ ] Configure server-side TypeSafe access and versioned questions.
- [ ] Implement evaluation runner and record actual latency/usage.
- [ ] Tune on development/validation; evaluate held-out data.
- [ ] Build feedback inbox, judgment cards, simulated queues, and threshold controls.
- [ ] Add labeled playback, error handling, and presentation script.

Version 2: interviewer evidence versus hire/no-hire vote, using a separate rubric and benchmark.

All initial records will be synthetic. This demo evaluates feedback routing, not candidate suitability. No automatic messages or career-site publication.
