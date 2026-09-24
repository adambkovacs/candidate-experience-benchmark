# Recruitment Feedback Comparison

A reproducible case study of candidate-experience feedback triage across TypeSafe Jev, Codex, Claude Code, Gemini, OpenRouter-hosted Qwen/Gemma/DeepSeek/Mistral, and local models.

**Status: development comparison in progress on the existing 60 fictional records only. Completed runs include Claude and Codex effort sweeps, Gemini Pro and some Flash efforts, hosted Jev/Qwen/Gemma/DeepSeek/Mistral24, local Qwen/Gemma, OpenJev, SemIf, Laya English/typed, AlexWortega NLI and AnyJev configurations. Other baseline configurations and the prompt experiments remain open. The remaining 340 records are ungenerated.**

The latest [prompt-comparison report](results/prompt-comparison-v1-2026-09-24/paired-reports/thirty-six-eligible-comparisons.html) covers 36 audited configurations. See [MVP status](docs/MVP_STATUS.md) for remaining work and [harness research](docs/HARNESS_RESEARCH.md) for the proposed larger-run tooling.

See the [current comparison](results/comparison/REPORT.md), [failure explorer](results/comparison/explorer.html), and [MVP run notes](docs/RUN_MVP.md). Labels remain provisional AI references; this is not a held-out ranking.

## Agreed scope

- **400 synthetic records:** 60 development (including 30 pilot), 40 validation, 200 ordinary-case test, 100 challenge test.
- Four judgments: sentiment, follow-up needed, serious concern reported, and testimonial potential.
- Equivalent tasks with provider-appropriate structured output and isolated contexts.
- ChatGPT Pro, Claude Max, and Google AI Pro subscription workflows where supported; Jev/DeepSeek/Qwen API runs; LM Studio and specialist local runners on an M4 MacBook Pro with 128 GB unified memory.
- Separate ordinary-case quality, challenge failures, review workload, execution-surface latency, and actual cost/usage.
- No real candidate data or consent workflow. Invented testimonials are never presented as real endorsements.

Read [the full plan](docs/PLAN.md) for the roster, dataset design, evaluation protocol, Kaggle reconnaissance, and milestones.

See the [first local results](docs/LOCAL_DEVELOPMENT_RESULTS.md) and [initial preflight](docs/LOCAL_PREFLIGHT.md) for evidence and reproducibility details.

## Next milestone

Read [the critical audit](docs/PILOT_AUDIT.md), [v0.2 labeling guide](docs/LABELING_GUIDE.md), and [60 feedback examples](docs/PILOT_REVIEW.md). The [proposed labels](docs/PILOT_PROPOSED_LABELS.md) were reviewed by the same assistant, not a human or independent reviewer. Follow the [local development smoke test](docs/RUN_DEVELOPMENT.md) for each new configuration. Generation of the remaining 340 remains on hold.

Machine-readable [inputs](data/pilot/inputs.jsonl), [provisional labels](data/pilot/proposed_labels.jsonl), and [output schema](schemas/judgments.schema.json) are included. Keep the labels and metadata out of model contexts. All examples are fictional and development-only.

## Deliverables

1. Versioned dataset, reference labels, and rubric.
2. Reproducible runners and evaluation manifest.
3. Comparison tables with explicit configuration and execution-surface details.
4. Failure explorer and concise case study.
5. Optional cascade experiment after standalone comparisons.

Future study: interviewer evidence versus hire/no-hire vote, evaluated separately.

## Expanded candidate research

[Model research](docs/MODEL_RESEARCH.md) covers Gemma dense versus MoE, smaller Qwen models, SemIf (formerly OpenJev), AlexWortega/OpenJev, and Laya. Run three-record smoke checks, inspect responses, then benchmark the existing 60 development records for supported configurations. The user expanded the listed sizes and specialist variations into scope, then prioritized available OpenRouter routes over further local runs. Hosted replacements are separately identified; they do not claim the local quantization or runtime. Local specialist procedures and exact models without a hosted route remain local. See the [route and cost review](docs/OPENROUTER_COST_REVIEW.md).

## Offline verification

`python3 scripts/development_benchmark.py validate`

`python3 -m unittest discover -s tests -q`

`node --test tests/*.cjs`

The development set includes reported bias, harassment, retaliation, privacy and accommodation concerns, benign counterexamples, and six controlled pairs. This evaluates feedback routing; it does not rank candidates or certify hiring compliance. Results measure agreement with provisional development references, not general model quality.

## Planned follow-up

After the current runs, [compare two prompt variations](docs/PROMPT_VARIANTS.md): classifier framing, and classifier framing plus an SOP and decision tree. The existing rubric-and-schema prompt remains the baseline. This phase has not run. The [fifteen necessary batch-context P0 preparations](results/subscription-batch-p0-run-registry.json) are complete and remain separate from historical single-record baselines. [Execution readiness](docs/PROMPT_EXECUTION_READINESS.md) tracks the remaining evidence and scheduling work, including the limits of opaque hosted prompt rendering.
