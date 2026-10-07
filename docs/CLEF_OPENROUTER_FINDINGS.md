# OpenRouter Clef decision runs: first pass

The first P0, P1 and P2 development runs are closed for both OpenRouter Clef routes. Each row below scores 60 saved four-question responses against the [frozen development labels](../data/pilot/proposed_labels.jsonl). The labels are provisional v0.2; the owner confirmed human review on 2 October 2026, with no versioned correction. These runs use the [OpenRouter native Decisions plan](../results/clef-openrouter-v1/plan.json), which is separate from the direct Cloudflare runs.

| Route | Prompt | All four correct | Sentiment | Follow-up | Serious concern | Testimonial | Observed development cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clef | P0 | 54/60 | 56/60 | 59/60 | 56/60 | 58/60 | $0.03184656 |
| Clef | P1 | 51/60 | 57/60 | 58/60 | 55/60 | 57/60 | $0.03472656 |
| Clef | P2 | 49/60 | 55/60 | 58/60 | 55/60 | 56/60 | $0.03718896 |
| Clef Flash | P0 | 45/60 | 50/60 | 57/60 | 56/60 | 57/60 | $0.01194246 |
| Clef Flash | P1 | 47/60 | 52/60 | 57/60 | 56/60 | 57/60 | $0.01302246 |
| Clef Flash | P2 | 46/60 | 50/60 | 57/60 | 56/60 | 58/60 | $0.01394586 |

Adding prompt instructions did not improve both models consistently. Clef's P0 to P2 all-four score fell from 54 to 49; among the same 60 records, six predictions changed, none gained all-four correctness and five lost it. Clef Flash rose from 45 to 46; three predictions changed, two gained all-four correctness and one lost it. These are paired observations for this first pass, not an estimate of future performance. Repeat passes are excluded until their own 60-record phases close.

The [deterministic report](../results/clef-openrouter-v1/findings-v1/findings.json) contains each field's reference-by-prediction counts, all prompt-pair changes, and IDs of wrong answers with high provider-reported confidence or high chosen-label probability. Those two numbers are kept separate. Sixty development records cannot establish probability calibration. The reported token totals are observed usage; cost is the sum of observed development response costs, excluding smoke and allocation. Client elapsed time is measured around requests, not provider processing time or whole-stage wall time.

The [report builder](../scripts/build_clef_openrouter_findings.py) strictly decodes each selected raw response and checks its request hash, saved parse, cost and ordered completion journal. Its [projection receipt](../results/clef-openrouter-v1/findings-v1/public-projection.receipt.json) records the SHA-256 hashes of that private evidence. A clean checkout can verify the public projection and the archived hashes but cannot decode private responses that are absent there. The [focused tests](../tests/test_build_clef_openrouter_findings.py) cover the published totals, projection tampering, present-source drift, an incomplete journal, and paired comparison counts.
