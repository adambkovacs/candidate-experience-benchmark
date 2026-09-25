# Legacy local prompt comparisons, v1

The [offline adapter](../../scripts/evaluate_legacy_local_prompt_pairs_v1.py) audits five saved P0/P1/P2 triples: Qwen 0.6B local HTTP; Qwen 0.6B SDK thinking on and off; and Qwen 1.7B SDK thinking on and off. It reads the existing 60 development records, frozen prompt additions, saved outputs, manifests, P1/P2 journals and terminal receipts, then scores against the provisional references offline. It sends no model requests.

Every result is labeled `descriptive_legacy_baseline` with `eligible_paired_comparison: false`. Historical P0 has 60 ordered saved rows and a manifest, but no per-attempt journal or terminal receipt. The adapter checks the source hashes, available P0 request or source-derived HTTP controls, input isolation, raw response status, visible model and runtime controls, exact P1/P2 prompt composition, and P1/P2 attempt and terminal links. It reports valid and invalid outcomes, per-field and all-four scores, and changed record labels for each pair over the full 60-record denominator. Visible equality does not establish a causal prompt effect or restore the earlier P0 timing and cache conditions.


| Configuration | P0 valid / all-four | P1 valid / all-four | P2 valid / all-four |
|---|---:|---:|---:|
| [Qwen 0.6B HTTP](qwen3-0.6b-q4km-nonthinking.json) | 60 / 0 | 60 / 0 | 60 / 0 |
| [Qwen 0.6B SDK thinking on](qwen3-0.6b-sdk-thinking-on.json) | 31 / 0 | 50 / 1 | 58 / 2 |
| [Qwen 0.6B SDK thinking off](qwen3-0.6b-sdk-thinking-off.json) | 0 / 0 | 4 / 0 | 2 / 0 |
| [Qwen 1.7B SDK thinking on](qwen3-1.7b-sdk-thinking-on.json) | 60 / 23 | 60 / 14 | 59 / 8 |
| [Qwen 1.7B SDK thinking off](qwen3-1.7b-sdk-thinking-off.json) | 60 / 28 | 59 / 24 | 53 / 29 |

Each figure uses the same 60 provisional development references. Invalid outputs remain in the denominator and are not repaired.

Read-only audit:

```bash
python3 scripts/evaluate_legacy_local_prompt_pairs_v1.py --config qwen3-1.7b-sdk-thinking-on
python3 -m unittest tests/test_legacy_local_prompt_pairs_v1.py
```

The five reports were written after independent review. Output files use exclusive creation and cannot overwrite an earlier report. The existing [strict SDK auditor](../../scripts/evaluate_local_prompt_pairs_v1.py) is unchanged; these legacy reports must not be presented as its strictly paired results.
