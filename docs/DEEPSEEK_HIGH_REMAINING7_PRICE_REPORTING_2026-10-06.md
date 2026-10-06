# DeepSeek high price-v1 reporting gate, 6 October 2026

The [price-v1 proposal](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-manifest.json) changes the request price ceilings and therefore declares a separate configuration. The earlier [current-price P0/P1 report](../public-site/additional-hosted-fresh-repeats.json) remains separate. Its two closed phases do not count as repeats under the new controls.

The [offline reporter](../scripts/build_deepseek_high_remaining7_price_findings.py) publishes a price-v1 phase only after its `closure.review.json` exists and matches the exact frozen plan, approved adapter and stage reviews, inspected smoke, 60 ordered development attempts, raw HTTP bodies, and an immutable child-ledger snapshot. It uses the [repaired phase verifier](../scripts/deepseek_high_remaining7_execution_v1.py), checks every cumulative reserve and settlement by attempt ID, and scores all 60 positions against the provisional references offline. A billed intrinsic invalid stays invalid and remains in the denominator. The live child ledger is never a report source.

For publication from a clean checkout, the reporter reconstructs the frozen request plan from its hashed source files and verifies the archived reconciliation receipt against the archived child ledger. The receipt records an absolute ledger path from the execution machine; that path is not followed during offline publication. The runtime admission gate remains unchanged.

The receipt schema is `deepseek-high-remaining7-price-v1-phase-closure-v1`. Its sibling snapshot is `closure-ledger-snapshot.jsonl` under `execution-adapter-v1/<fresh pass>/<condition>/`. Phases must close in the [declared order](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/manifest.json); a later receipt cannot bypass an unclosed predecessor. The reporter's `close-phase` action writes those two review artifacts only after the terminal phase and full offline verification. Root controls execution and admission.

The first [fresh1/P2 closure](../results/repeatability-v1/deepseek-high-remaining7-price-v1/execution-adapter-v1/fresh1/P2/closure.review.json) is verified: all 60 development answers are valid and 58/60 match all four provisional references. Development cost is $0.03250234680; the three-call smoke cost is $0.001118700. The immutable child snapshot accounts for all 63 reservations and settlements at $0.03362104680. The [hosted feed](../public-site/additional-hosted-fresh-repeats.json) and [combined analysis](../public-site/analysis-refresh.json) publish this one closed phase under the revised-price configuration. No old P0/P1 phase receives credit under these controls.

For each later terminal phase, audit it with:

```sh
python3 scripts/build_deepseek_high_remaining7_price_findings.py close-phase --fresh-pass fresh2 --condition P2
```

Then regenerate the hosted report with the same script's `build --output public-site/additional-hosted-fresh-repeats.json` action and run `check` with the same output path. Publication and any combined-analysis update need a separate review of the newly closed result.
