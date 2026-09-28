# Qwen thinking-on P2: final never-sent suffix

Episode 002 dispatched only DEV-044 through DEV-060 under the frozen AkashML FP8 route and reasoning-on payload. All 17 returned valid classifications. The episode is terminal and its budget partition is reconciled; no prior failed request was retried.

Together with the preserved prefix, all 60 reviews now have an attempted outcome: 54 valid classifications and six retained service errors (DEV-033, DEV-039, DEV-040, DEV-041, DEV-042 and DEV-043). No reviews remain never sent. This interrupted series is not promoted into the clean paired-prompt cohort. The earlier failures and conservative unknown-charge bounds remain part of the evidence.

The new episode reported $0.0211142 in charges, 43,032 input tokens and 20,030 output tokens (63,062 total). Its $0.5083136 allocation released $0.4871994 after reconciliation. Master accounted charges and retained bounds are $9.38620268150; remaining headroom is $0.61379731850 under the unchanged $10 cap. These balances are a dated checkpoint, not a new authorization or a provider invoice.

The response capture preserves each body before parsing. All 17 terminal bodies were decoded and checked for account/profile, credential and quota field names; none of the audited keys occurred. The saved requests contain no authorization header, reference labels or previous predictions. Response bodies contain generation IDs and provider usage, which are retained as evidence. The raw capture hash below refers to the unchanged published bytes; no redaction was required for this successful episode. This audit does not undo the older episode's account-identifier disclosure boundary.

Episode 001 keeps its original response private and provides an explicitly redacted [public response](../episode-001/responses.public.jsonl) with the [original/public hash boundary](../episode-001/PUBLICATION.md). Public consumers must not require that unavailable private original merely to read this composite. Its documented error, frozen request, ledger and reconciliation preserve the failed position; the redacted copy does not authenticate the private original bytes.

## Evidence

- [manifest.json](manifest.json): SHA-256 `006a6e66caf93211aa455924be1fbde75eac97ee2bd114864a82c89e5f96e8f6`.
- [root-review.json](root-review.json): SHA-256 `28fd373acecb77121a33d01886a914d838fd523e06938e0cd891ea357bb41381`.
- [claim.json](claim.json): SHA-256 `940572b48884fd7694cd3115f8d14bd8eecfd6801549624975702a5122496196`.
- [journal.jsonl](journal.jsonl): SHA-256 `9e9464547bc9569c7f3ca1ebbc33e256cbfd78506f005c82173c4c787743825f`.
- [attempts.jsonl](attempts.jsonl): SHA-256 `77948bc38d6b8b0213da4b6993dfb22b69acb32ac701ad177e114159c015ddad`.
- [responses.jsonl](responses.jsonl): SHA-256 `a98e0f373e90f1d47dca8a87e6cb5d5af39475d266b08220ec260ec8427b97fb`.
- [reconciliation.json](reconciliation.json): SHA-256 `29734d065a3aa2c27527d8eb263c01d17e648c9b8b7d1fd98a68789259ca58a3`.
- [budget-partitions.json](budget-partitions.json): SHA-256 `ccd54dacd34b23f1a41a5d3f0c1ab5129a8bbea2f9a28e56e2dfe44fd039a3af`.
- [budget-partitions-qwen-on-p2-episode-002.jsonl](budget-partitions-qwen-on-p2-episode-002.jsonl): SHA-256 `bafb74480570587eba0e73db52ea2eacd007affec0c27769fba3b1dd2ca62032`.
