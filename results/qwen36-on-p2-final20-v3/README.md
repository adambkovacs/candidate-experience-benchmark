# Qwen 3.6 on/P2 final-20 continuation, v3

The reviewed continuation is terminal. It attempted DEV-041 once, received HTTP 429, and stopped. DEV-042–060 were never sent. The [offline reconciliation](../hosted-final-suffix-reconciled-v3/qwen36-on-p2.json) records 41 total attempts, 37 valid outputs, four preserved service errors (DEV-033, DEV-039, DEV-040, DEV-041), and 19 never-sent records. This evidence is descriptive and remains ineligible for strict paired comparison.

The [input-only plan](plan.json) selected exactly DEV-041–060 and bound the original, v1, and v2 terminal sources. Its SHA-256 is `79a383c8725e4e111c51e992df1b8c8e359f9a4c0549f897b30f718d405b52cf`. The [versioned controller](../../scripts/qwen36_on_p2_suffix_v3.py) reconstructed the frozen on/P2 requests, checked the exact AkashML fp8 route and controls, opened exclusive output files, and stopped on the first service failure. It did not retry DEV-033, DEV-039, DEV-040, or DEV-041.

The [output](development.jsonl), [attempt journal](development.jsonl.attempts.jsonl), [root review](root-review.json), [budget manifest](budget-manifest.json), and [sealed child ledger](budget-manifest-qwen36-on-p2-final20-v3.jsonl) remain available for audit. The DEV-041 reserve of $0.0299008 is an unknown-charge upper bound, not observed spend. The unused $0.6100992 allocation was released. The [offline reconciler](../../scripts/build_qwen36_on_p2_v3_reconciliation.py) requires the terminal journal, saved request and attempt links, reviewed plan/controller/budget hashes, and sealed partition before writing an immutable report. The original counterbalanced timing cannot be recovered from this suffix.

The completed report was generated with:

```bash
python3 scripts/build_qwen36_on_p2_v3_reconciliation.py \\
  --budget-manifest results/qwen36-on-p2-final20-v3/budget-manifest.json \\
  --partition-id qwen36-on-p2-final20-v3 \\
  --review results/qwen36-on-p2-final20-v3/root-review.json
```

The report path is exclusive. Do not rerun this command against the existing report or replay the stopped requests.
