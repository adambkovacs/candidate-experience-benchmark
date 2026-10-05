# Mistral 119B fresh1/P0 partial findings, 5 October 2026

The fresh1/P0 composite has 55 valid classifications, five failed requests with unknown charges, and no unsent positions. The failures are DEV-048, DEV-050, DEV-053, DEV-058, and DEV-060. DEV-048 ended in a timeout; the other four ended in HTTP 429 responses. Failed outputs remain unscored and retained in the accounting.

On the fixed 60-position denominator, 40 outputs match all four frozen `review_version` 0.2 labels (40/60). Among the 55 valid outputs, the conditional all-four match rate is 40/55. Field matches among valid outputs are sentiment 46/55, follow-up needed 52/55, serious concern 48/55, and testimonial potential 51/55. The labels remain marked provisional in v0.2. The project owner confirmed that a human checked all 60 labels on 2 October 2026. This report applies no label corrections, and the reference labels were not sent to the model.

The 55 valid outputs used 78,702 prompt tokens and 2,164 completion tokens. Their recorded known cost is $0.005084835. The five failed requests retain a combined unknown-charge upper bound of $0.20889600. For the 55 completed requests, journal timestamps give 79.517 seconds total elapsed wall time, with a 1.353 second median (range 0.859 to 3.370 seconds). Five failed requests have no `request_finished` event, so no completed-request latency is assigned to them. The first phase's terminal record notes host sleep overlapped the DEV-048 timeout; the measured wall times are not sleep-adjusted.

This is a descriptive partial pass, not a clean repeatability pass. Its result does not close any other condition or fresh pass in the planned matrix.

The [public JSON projection](../public-site/mistral119-fresh1-p0-findings.json) is regenerated offline by [the report builder](../scripts/build_mistral119_fresh1_p0_findings.py). Its source hashes bind the inputs, frozen proposed labels, parsed outputs, attempts, journals, phase terminals, and suffix reviews/reconciliations. The constituent evidence is linked below:

- [Initial DEV-001..048 terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-development-none-v1/fresh1/P0/development.terminal-public.json)
- [DEV-049..050 suffix terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-remaining-none-v1/fresh1/P0-suffix-049-060/suffix.terminal-public.json)
- [DEV-051..053 suffix terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-second-suffix-none-v1/fresh1/P0/suffix.terminal-public.json)
- [DEV-054..058 reviewed terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-third-suffix-none-v1/fresh1/P0/suffix.third-terminal-pending-review.json), [root review](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-third-suffix-none-v1/fresh1/P0/suffix.third-terminal-root-review.json), and [reconciliation](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-third-suffix-none-v1/fresh1/P0/suffix.third-budget-reconciliation.json)
- [DEV-059..060 terminal](../results/repeatability-v1/mistral119-fresh-matched3-v1/v5-fourth-suffix-none-v1/fresh1/P0/suffix.fourth-terminal-pending-review.json), [root review](../results/repeatability-v1/mistral119-fresh-matched3-v1/v5-fourth-suffix-none-v1/fresh1/P0/suffix.fourth-terminal-root-review.json), and [reconciliation](../results/repeatability-v1/mistral119-fresh-matched3-v1/v5-fourth-suffix-none-v1/fresh1/P0/suffix.fourth-budget-reconciliation.json)
- [Frozen proposed labels](../data/pilot/proposed_labels.jsonl)
