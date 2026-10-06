# DeepSeek low: final first-pass P2 suffix

The final DEV-051 through DEV-060 continuation returned ten valid judgments, all ten matching the provisional references on all four fields. Its [closed review](../results/repeatability-v1/deepseek-low-fresh3-v2/current-price-authority-v3-051-060/prompt-ceiling-v4/closure.root-review.json) binds the saved request, raw response and scoring evidence. The new [public findings feed](../public-site/deepseek-low-final-suffix-findings.json) combines those ten results with the [earlier public 50-position projection](../results/repeatability-v1/deepseek-low-fresh3-v2/second-interruption-continuation-v1/phase-03-suffix.public.json). It does not change either historical source.

The resulting P2 composite has **56 valid, one invalid and three service-error outcomes** across the fixed 60 reviews. Its all-four score is **53/60**. DEV-039 remains invalid; DEV-040, DEV-049 and DEV-050 remain service errors. The ten new answers close the unsent suffix, but the composite still crosses interruptions and separate continuations. It is a descriptive first pass, not a clean matched repeat.

| First-pass condition | Valid | All four correct / 60 | Difference from P0 |
| --- | ---: | ---: | ---: |
| P0 | 59 | 58 | 0 |
| P1 | 60 | 57 | -1 |
| P2 composite | 56 | 53 | -5 |

These fixed-denominator differences mix classification and output availability. On reviews valid in both compared conditions, four-field vectors changed on 2/55 for P0 versus P2 and 4/56 for P1 versus P2. The feed retains each field's confusion counts, predicted and reference class counts, and case IDs for shared-valid changes. The [earlier interruption findings](../public-site/deepseek-low-third-interruption-findings.json) remain available for the original failure sequence.

The final ten requests recorded **$0.004464008007** in observed charges, 25,205 prompt tokens, 3,125 completion tokens and 147.78 seconds of cumulative client request time. Across the 60-position P2 composite, 57 positions have observed prompt and completion token counts and known charges; three service errors have unknown charges. The observed known charge total is **$0.017093728007**. The earlier public projection lacks total-token and reasoning-token fields for its first 50 positions, so the feed marks those fields missing instead of treating their sums as zero. Client time includes transport and local capture; it does not measure pure provider inference.

The [reconstruction script](../scripts/build_deepseek_low_final_suffix_findings.py) uses relative archive paths and hashes, with no live budget ledger. Its [tests](../tests/test_build_deepseek_low_final_suffix_findings.py) verify source integrity, scoring, the 60-position denominator, public-field limits and relocation. The remaining second and third P0/P1/P2 repeat phases are still open in this report.
