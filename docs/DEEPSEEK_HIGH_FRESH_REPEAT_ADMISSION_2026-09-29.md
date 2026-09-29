# DeepSeek high fresh repeat admission

The historical DeepSeek V4.1 Flash high run has 60 saved development positions for each of P0, P1, and P2. [The source-bound continuation audit](../results/prompt-comparison-v1-2026-09-24/paired-reports/hosted-remaining-audit-v1/openrouter-paid-deepseek-v41-flash-high.json) records four invalid P0 outputs; two invalid, one prompt-admission failure, and one service error in P1; and one invalid and one service error in P2. The suffix requests broke the original condition schedule. These outcomes remain historical observations and do not count as a pass in the new matched series.

The [offline planner](../scripts/deepseek_high_fresh_repeat_study.py) reconstructs each saved request from the exact input feedback, the saved condition instruction, and the historical strict JSON schema and provider controls. It checks all 180 development request bodies and all nine saved smoke requests, the 60 IDs per condition, the `open-inference/fp4` route, `high` reasoning, 300-second timeout, and the saved failure policy. The saved row hash is checked when present. P1 has 54 and P2 has 59 continuation rows without a saved request-hash field; their request digests are derived from their saved request bodies, whose source files are hash-bound. The missing fields are not presented as historical observations. Each new request contains only input feedback and the condition instruction, with no reference labels or old predictions.

The planner also binds the [dated public route observation](../results/repeatability-v1/deepseek-low-fresh3-v2/lower-price-endpoint-audit-v1.json). Historical requests used endpoint prompt metadata of `$0.0000001` per token. That public observation found `$0.00000003`, with the same selected route, `$0.0000005` completion price, and advertised high-reasoning support. The new request's provider `max_price` remains `$0.10` per million input tokens and `$0.50` per million output tokens. A fresh route and price check is required before any dispatch; the dated observation alone cannot admit a live request.

The three new passes rotate conditions as P0/P1/P2, P2/P0/P1, and P1/P2/P0. Each condition needs a separate three-record smoke, raw inspection, and 60-record development stage. No stage may retry an uncertain request. A separate execution controller, budget partition, stage review, and smoke inspection still need independent review. The planner and these manifests perform no inference, load no key, and allocate no budget.

The 189 historical development and smoke rows have `$0.04874595` in known charges. Two unknown charges retain `$0.2138112` in combined reserved upper bounds; they are not counted as observed spend. Tripling the historical known-charge proxy gives `$0.14623785`, while tripling the unknown-bound sensitivity gives `$0.6414336`. The proposed child partition is `$0.90` under the existing `$10` aggregate cap. This is a proposal, not funding or a completion guarantee. Every future call must reserve the full `$0.1069056` upper bound before the request.

Frozen offline manifests:

- [fresh1](../results/repeatability-v1/deepseek-high-fresh-matched3-v1/fresh1/manifest.json): `37efdc68eef639668e5821e52aa467e70417535e82947788228f40c4760569c2`
- [fresh2](../results/repeatability-v1/deepseek-high-fresh-matched3-v1/fresh2/manifest.json): `47bbd59f3a64578deff6b0e0c1b4e69c10e3f0c9726840c548e9e0ddcdf934df`
- [fresh3](../results/repeatability-v1/deepseek-high-fresh-matched3-v1/fresh3/manifest.json): `bbb39ccd5d163148c15af08392e2ef7f9c774eec4d6fc073d059f2a88e29dd2a`

Recheck source reconstruction and all three manifests with:

```sh
python3 -m unittest tests.test_deepseek_high_fresh_repeat_study -v
python3 scripts/deepseek_high_fresh_repeat_study.py verify --fresh-pass fresh1 --sha256 37efdc68eef639668e5821e52aa467e70417535e82947788228f40c4760569c2
python3 scripts/deepseek_high_fresh_repeat_study.py verify --fresh-pass fresh2 --sha256 47bbd59f3a64578deff6b0e0c1b4e69c10e3f0c9726840c548e9e0ddcdf934df
python3 scripts/deepseek_high_fresh_repeat_study.py verify --fresh-pass fresh3 --sha256 bbb39ccd5d163148c15af08392e2ef7f9c774eec4d6fc073d059f2a88e29dd2a
```

Independent offline verification passed all five tests and all three source-bound manifest checks. Root code review found no confirmed blocking issue in the offline planner. This does not approve a future execution controller or allocate the proposed budget.
