# Historical comparison publication, 1 October 2026

The repeat explorer now includes separate snapshots for the first Qwen continuation, second Gemma continuation and third DeepSeek interruption. These preserve the evidence available at their declared archive cutoff, not the latest execution status. Partial phases have no scores. Existing selections remain available.

Independent review approved the integration. All 67 repeat UI tests passed, and an isolated browser check exercised the new selections without console errors. The three data files rebuild exactly from archive `6bdf6cc2c4a0a24dd4088c96460e750563fc2af4`.

The first deployment failed because three tests expected private local fixtures. Commit `0432b9d1` replaced that CI invocation with portable tests while retaining exact archive reconstruction and adding a tampered-projection rejection check. The changed CI block passed in a clean archive.

[Pages run 36821195110](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36821195110) succeeded. Root fetched the four published assets and verified exact equality with the tested checkout:

| Asset | SHA-256 |
| --- | --- |
| repeats.js | c2d76e720a47327203f8796cd4fc2abf7efdeda9fea12db3124eef650ad4b264 |
| qwen27-interrupted-continuation-findings.json | 1356548b1f5ffad8a09db2ce0f320d3bdeaddf64b47364e807a0789642c366fb |
| gemma26-second-continuation-findings.json | f23d805f23117d39da1e1229d2bc2516eb667e1d17c355bc7ab5223c9bbb8ee0 |
| deepseek-low-third-interruption-findings.json | d00e5100c085160e126956db8f4335a944859d6bf9b7a527cb84ebb7d2b9b60e |

The newer Qwen completions remain separate work for the final interrupted-series analysis. Publishing these snapshots does not complete the benchmark.
