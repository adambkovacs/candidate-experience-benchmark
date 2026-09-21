# Recruitment Feedback Comparison

A reproducible case study of candidate-experience feedback triage across TypeSafe Jev, Codex, Claude Code, hosted DeepSeek/Qwen, and local models.

**Status: planning. No dataset generated or benchmark results yet.**

## Agreed scope

- **400 synthetic records:** 60 development (including 30 pilot), 40 validation, 200 ordinary-case test, 100 challenge test.
- Four judgments: sentiment, follow-up needed, serious concern reported, and testimonial potential.
- Equivalent tasks with provider-appropriate structured output and isolated contexts.
- Codex and Claude Code subscription runs where supported; Jev/DeepSeek/Qwen API runs; two local model configurations on an M4 MacBook Pro with 128 GB unified memory.
- Separate ordinary-case quality, challenge failures, review workload, execution-surface latency, and actual cost/usage.
- No real candidate data or consent workflow. Invented testimonials are never presented as real endorsements.

Read [the full plan](docs/PLAN.md) for the roster, dataset design, evaluation protocol, Kaggle reconnaissance, and milestones.

## Next milestone

Finalize the labeling guide and create 30 development examples before generating the remaining 370. Build the evaluator before the showcase.

## Deliverables

1. Versioned dataset, reference labels, and rubric.
2. Reproducible runners and evaluation manifest.
3. Comparison tables with explicit configuration and execution-surface details.
4. Failure explorer and concise case study.
5. Optional cascade experiment after standalone comparisons.

Future study: interviewer evidence versus hire/no-hire vote, evaluated separately.
