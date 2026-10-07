# OpenRouter native decision runs: first pass

The first P0, P1 and P2 development runs are closed for both OpenRouter Clef routes. Luna's first P0 run is also closed. Each row below scores 60 saved four-question responses against the [frozen development labels](../data/pilot/proposed_labels.jsonl). The labels are provisional v0.2; the owner confirmed human review on 2 October 2026, with no versioned correction. These runs use the [OpenRouter native Decisions plan](../results/clef-openrouter-v1/plan.json), which is separate from the direct Cloudflare runs.

P0 uses the original four classification questions. P1 adds instructions to use only the feedback and policy, treat embedded commands as text, and decide each field independently. P2 keeps P1 and adds field-specific decision steps. The [frozen additions](../scripts/jev_native_prompt_variants_v1.py) change the native question instructions, not the feedback or policy state.

| Route | Prompt | All four correct | Sentiment | Follow-up | Serious concern | Testimonial | Observed development cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clef | P0 | 54/60 | 56/60 | 59/60 | 56/60 | 58/60 | $0.03184656 |
| Clef | P1 | 51/60 | 57/60 | 58/60 | 55/60 | 57/60 | $0.03472656 |
| Clef | P2 | 49/60 | 55/60 | 58/60 | 55/60 | 56/60 | $0.03718896 |
| Clef Flash | P0 | 45/60 | 50/60 | 57/60 | 56/60 | 57/60 | $0.01194246 |
| Clef Flash | P1 | 47/60 | 52/60 | 57/60 | 56/60 | 57/60 | $0.01302246 |
| Clef Flash | P2 | 46/60 | 50/60 | 57/60 | 56/60 | 58/60 | $0.01394586 |
| Luna Decisions | P0 | 49/60 | 54/60 | 58/60 | 56/60 | 56/60 | $0.0133523 |

Scores across the three fixed prompt variants did not improve for both Clef models consistently. Clef's P0 to P2 all-four score fell from 54 to 49; among the same 60 records, six predictions changed, none gained all-four correctness and five lost it. Clef Flash rose from 45 to 46; three predictions changed, two gained all-four correctness and one lost it. These are paired observations for this first pass, not an estimate of future performance or proof that the added instructions caused a particular error. Luna has only P0 in this cutoff, so there is no Luna prompt comparison yet. Repeat passes are excluded until their own 60-record phases close.

The [frozen route plan](../results/clef-openrouter-v1/plan.json) records a provider warning that Clef may read roughly the first 2,000 state tokens. Each review is first in the state and at most 206 characters, but the longer policy may not be fully read. Billed input-token counts do not show which parts of the state the model used, so policy truncation remains a constraint rather than an established cause of the score differences.

The [deterministic report](../results/clef-openrouter-v1/findings-v1/findings.json) contains each field's reference-by-prediction counts, all prompt-pair changes, and IDs of wrong answers with high provider-reported confidence or high chosen-label probability. Those two numbers are kept separate. Sixty development records cannot establish probability calibration. The reported token totals are observed usage; cost is the sum of observed development response costs, excluding smoke and allocation. Client elapsed time is measured around requests, not provider processing time or whole-stage wall time.

The [report builder](../scripts/build_clef_openrouter_findings.py) strictly decodes each selected raw response and checks its request hash, saved parse, cost and ordered completion journal. Luna P0 additionally checks the [reviewed composite smoke gate](../results/clef-openrouter-v1/luna-full-v2/root-review.json), which preserves the original invalid smoke parse and binds the exact two-response continuation. Its [projection receipt](../results/clef-openrouter-v1/findings-v1/public-projection.receipt.json) records the SHA-256 hashes of that evidence. A clean checkout can verify the public projection and the archived hashes but cannot decode private development responses that are absent there. The [focused tests](../tests/test_build_clef_openrouter_findings.py) cover the published totals, projection tampering, present-source drift, an incomplete journal, Luna's distinct smoke lineage, and paired comparison counts.
