# Postapproval reservation audit, 6 October 2026

**Finding:** The $10 postapproval approval is an overall paid-work spending ceiling. The separate [authority ledger](../results/postapproval-paid-work-2026-10-02.jsonl) implements it as permanent maximum stage holds. Its 47 holds total **$9.948371024**, leaving **$0.051628976** at a locked read at 11:10 UTC (SHA-256 `4516e72a3fafd52da879655bb4923ff6ef8852532002cf7baefd2c55ed9c4423`). The proposed Jev P2 fresh2 DEV-019 through DEV-060 suffix needs **$0.056448000** in full-context reserves, a **$0.004819024** gap at that snapshot. This is a reservation-accounting gap, not proof that the user's $10 spending ceiling has been reached. [Current goals](CURRENT_GOALS.md) records that the postapproval cap covers new paid work across providers, while the separate OpenRouter approval is $12.38. Neither cap changes in this audit.

A versioned release of **$0.073788960** from the sealed Jev P2 fresh1 hold has a concrete proof path. That single release would raise shared-authority headroom to **$0.125417936**, enough for the suffix with **$0.068969936** left after a new $0.056448000 hold, if the head remains unchanged. The Jev P2 fresh1 [completion](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/completion.json) has 60 valid results and binds the attempts hash. Its [reconciliation](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/budget-reconciliation.json) records a closed $0.080640000 child, $0.006851040 known provider-reported cost, no unknown charge, and $0.073788960 unused allocation. The child hash matches the saved child, the OpenRouter [master ledger](../results/openrouter-paid-budget.jsonl) has the same reconciliation, and the authority hold matches the stage's reviewed receipt. The $0.006851040 remains counted; this is not a claim about an external invoice.

No release, cap amendment, allocation or inference happened in this audit. The existing [hold writer](../scripts/openrouter_native_variants_v2.py) and older [Cloudflare writer](../scripts/clef_native_full_p0.py) accept only `hold` events and sum every historical maximum. Appending a `release` to the current file without a versioned reader would make those writers reject the file. That failure is safe, but it would interrupt their work. A reviewed migration must fence or update every writer before using released capacity.

## Provenance of all 47 holds

The tables use these evidence roots: `C/` means [`results/clef-native-v1/`](../results/clef-native-v1/); `N-smoke/` means [`results/route-audits/native-variants-v2-20261006/`](../results/route-audits/native-variants-v2-20261006/); `N-Kev/` and `N-Jev/` mean the [Kev](../results/route-audits/native-variants-full-v1-20261006/) and [Jev](../results/route-audits/jev-native-full-v1-20261006/) full-pass roots. A stage path in a table points to its `completion.json` and, where present, `budget-reconciliation.json`. All amounts are USD. "Retain" is the conservative amount that would remain after a release. "Release" is a candidate, not a ledger event.

The 26 Cloudflare holds total **$7.656482**. The 24 completed entries retain their full holds because the saved app responses do not establish observed billable cost. Two stopped Flash P0 stages each attempted one position with a $0.005899 unknown-cost reserve. Their never-sent positions suggest at most **$0.690183** could be released, but this audit did not revalidate every raw connected-app event and grant needed for that change. Those two amounts are not part of the verified minimum release above.

| Authority hold | Hold | Stage under `C/` | Saved outcome | Retain | Candidate release |
| --- | ---: | --- | --- | ---: | ---: |
| `cloudflare-initial-smoke` | 0.064884 | `clef/fresh1/P0/smoke` and `clef-flash/fresh1/P0/smoke` | 3 + 3 valid | 0.064884 | 0 |
| `cloudflare-clef-fresh1-p0-development` | 0.943740 | `clef/fresh1/P0/development` | 60 valid | 0.943740 | 0 |
| `cloudflare-clef-flash-fresh1-p0-development` | 0.353940 | `clef-flash/fresh1/P0/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-fresh2-p0-smoke` | 0.047187 | `clef/fresh2/P0/smoke` | 3 valid | 0.047187 | 0 |
| `cloudflare-clef-flash-fresh2-p0-smoke` | 0.017697 | `clef-flash/fresh2/P0/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-fresh2-p0-development` | 0.943740 | `clef/fresh2/P0/development` | 60 valid | 0.943740 | 0 |
| `cloudflare-clef-flash-fresh2-p0-development` | 0.353940 | `clef-flash/fresh2/P0/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-fresh3-p0-smoke` | 0.047187 | `clef/fresh3/P0/smoke` | 3 valid | 0.047187 | 0 |
| `cloudflare-clef-flash-fresh3-p0-smoke` | 0.017697 | `clef-flash/fresh3/P0/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-fresh3-p0-development` | 0.943740 | `clef/fresh3/P0/development` | 60 valid | 0.943740 | 0 |
| `cloudflare-clef-flash-fresh3-p0-development` | 0.353940 | `clef-flash/fresh3/P0/development` | stopped, 1 unknown, 59 unsent | 0.005899 | 0.348041 |
| `cloudflare-clef-flash-fresh1-p1-smoke` | 0.017697 | `clef-flash/fresh1/P1/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh1-p1-development` | 0.353940 | `clef-flash/fresh1/P1/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-flash-fresh2-p1-smoke` | 0.017697 | `clef-flash/fresh2/P1/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh2-p1-development` | 0.353940 | `clef-flash/fresh2/P1/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-flash-fresh3-p1-smoke` | 0.017697 | `clef-flash/fresh3/P1/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh3-p1-development` | 0.353940 | `clef-flash/fresh3/P1/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-flash-fresh1-p2-smoke` | 0.017697 | `clef-flash/fresh1/P2/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh1-p2-development` | 0.353940 | `clef-flash/fresh1/P2/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-flash-fresh2-p2-smoke` | 0.017697 | `clef-flash/fresh2/P2/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh2-p2-development` | 0.353940 | `clef-flash/fresh2/P2/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-flash-fresh3-p2-smoke` | 0.017697 | `clef-flash/fresh3/P2/smoke` | 3 valid | 0.017697 | 0 |
| `cloudflare-clef-flash-fresh3-p2-development` | 0.353940 | `clef-flash/fresh3/P2/development` | 60 valid | 0.353940 | 0 |
| `cloudflare-clef-fresh1-p1-smoke` | 0.047187 | `clef/fresh1/P1/smoke` | 3 valid | 0.047187 | 0 |
| `cloudflare-clef-fresh1-p1-development` | 0.943740 | `clef/fresh1/P1/development` | 60 valid | 0.943740 | 0 |
| `cloudflare-clef-flash-fresh3-p0-development-suffix-v1` | 0.348041 | `clef-flash/fresh3/P0/development-suffix-v1` | stopped, 1 unknown, 58 unsent | 0.005899 | 0.342142 |

The seven earlier OpenRouter holds total **$1.835337600**. Every corresponding partition has one `budget_partition` and one `partition_reconciled` event in the [master ledger](../results/openrouter-paid-budget.jsonl); each recorded child SHA-256 matches the sealed child file. The table maps hold IDs to exact partition IDs. It preserves all three Mistral unknown-charge bounds and Gemma's one unknown bound. The **$1.632409655** unused sum is a candidate after individual hold-to-receipt source checks; this audit did not complete those seven mappings. The Gemma fifth [terminal reconciliation](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fifth-suffix-017-046-v1/terminal-reconciliation-after-dev046.json) explicitly says its authority carry was retained pending separate review.

| Authority hold | Hold | Master partition ID | Known | Unknown bound | Unused |
| --- | ---: | --- | ---: | ---: | ---: |
| `openrouter-gemma-fifth` | 0.600000000 | `gemma26-on-v2-fifth-suffix-017-046-v1` | 0.011092140 | 0 | 0.588907860 |
| `openrouter-gemma-final-047-060` | 0.300000000 | `gemma26-on-v2-final-suffix-047-060-v1` | 0.005757830 | 0 | 0.294242170 |
| `openrouter-gemma26-fresh3-p0-p1-v1` | 0.400000000 | `gemma26-fresh3-p0-p1-v1` | 0.039954970 | 0.019742720 | 0.340302310 |
| `openrouter-mistral119-none-third-suffix-054-060-v1` | 0.300000000 | `mistral119-none-v3-fresh1-p0-suffix-054-060-v1` | 0.000393795 | 0.041779200 | 0.257827005 |
| `openrouter-gemma26-fresh3-p1-dev060-v1` | 0.020000000 | `gemma26-fresh3-p1-dev060-v1` | 0.000410540 | 0 | 0.019589460 |
| `openrouter-mistral119-none-fourth-suffix-059-060-v1` | 0.090000000 | `mistral119-none-v5-fresh1-p0-suffix-059-060-v1` | 0.000238350 | 0.041779200 | 0.047982450 |
| `openrouter-mistral119-none-fresh1-p1-successor-smoke-v1` | 0.125337600 | `mistral119-none-fresh1-p1-successor-smoke-v1` | 0 | 0.041779200 | 0.083558400 |

The 14 Kev/Jev OpenRouter holds total **$0.456551424**. Their reviewed receipts bind each authority hold and source hash. All 14 child files match the child SHA-256 in both the stage reconciliation and master ledger. Thirteen stages closed successfully. Jev P2 fresh2 stopped on DEV-018; its **$0.001344000** unknown-charge bound remains counted. The group's unused sum is **$0.399864486**, subject to a reviewed release entry per stage.

| Authority hold | Hold | Stage under evidence root | Known | Unknown bound | Unused |
| --- | ---: | --- | ---: | ---: | ---: |
| `kev-openrouter-native-p1-choice-v1-smoke-v2` | 0.001032192 | `N-smoke/kev-openrouter-native-p1-choice-v1/smoke` | 0.000260064 | 0 | 0.000772128 |
| `kev-openrouter-native-p2-choice-v1-smoke-v2` | 0.001032192 | `N-smoke/kev-openrouter-native-p2-choice-v1/smoke` | 0.000281610 | 0 | 0.000750582 |
| `jev-openrouter-native-p1-choice-v1-smoke-v2` | 0.004032000 | `N-smoke/jev-openrouter-native-p1-choice-v1/smoke` | 0.000319998 | 0 | 0.003712002 |
| `jev-openrouter-native-p2-choice-v1-smoke-v2` | 0.004032000 | `N-smoke/jev-openrouter-native-p2-choice-v1/smoke` | 0.000342300 | 0 | 0.003689700 |
| `kev-openrouter-native-p1-choice-v1-fresh1-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p1-choice-v1/fresh1` | 0.005207412 | 0 | 0.015436428 |
| `kev-openrouter-native-p2-choice-v1-fresh1-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p2-choice-v1/fresh1` | 0.005638332 | 0 | 0.015005508 |
| `kev-openrouter-native-p1-choice-v1-fresh2-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p1-choice-v1/fresh2` | 0.005207412 | 0 | 0.015436428 |
| `kev-openrouter-native-p2-choice-v1-fresh2-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p2-choice-v1/fresh2` | 0.005638332 | 0 | 0.015005508 |
| `kev-openrouter-native-p1-choice-v1-fresh3-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p1-choice-v1/fresh3` | 0.005207412 | 0 | 0.015436428 |
| `kev-openrouter-native-p2-choice-v1-fresh3-full-v1` | 0.020643840 | `N-Kev/kev-openrouter-native-p2-choice-v1/fresh3` | 0.005638332 | 0 | 0.015005508 |
| `jev-openrouter-native-p1-choice-v1-fresh1-full-v1` | 0.080640000 | `N-Jev/jev-openrouter-native-p1-choice-v1/fresh1` | 0.006405000 | 0 | 0.074235000 |
| `jev-openrouter-native-p2-choice-v1-fresh1-full-v1` | 0.080640000 | `N-Jev/jev-openrouter-native-p2-choice-v1/fresh1` | 0.006851040 | 0 | 0.073788960 |
| `jev-openrouter-native-p1-choice-v1-fresh2-full-v1` | 0.080640000 | `N-Jev/jev-openrouter-native-p1-choice-v1/fresh2` | 0.006405000 | 0 | 0.074235000 |
| `jev-openrouter-native-p2-choice-v1-fresh2-full-v1` | 0.080640000 | `N-Jev/jev-openrouter-native-p2-choice-v1/fresh2` | 0.001940694 | 0.001344000 | 0.077355306 |

The OpenRouter [master ledger](../results/openrouter-paid-budget.jsonl) had **$0.42372567950** unallocated under its separate $12.38 cap, no pending master reservation, and no active child at this read. That amount can cover a $0.056448000 child at this snapshot; a locked recheck is still required. All 26 Cloudflare holds map to saved `complete` or `stopped` stage evidence, and a process-name check found no matching runner at this instant. Saved terminal files and a process snapshot do not replace a locked admission check.

## Required versioned release protocol

1. Review the exact hold, its stage receipt and immutable terminal files. For OpenRouter, require a closed child ledger plus the matching `partition_reconciled` event in the master, and verify `hold = known provider-reported charge + retained unknown upper bound + release`. For Cloudflare, keep the full per-attempt upper bound wherever actual charges are unavailable; release only positions proven never sent by sealed evidence.
2. Under an exclusive lock on the same authority file, verify its current head, original $10 provenance, every historical hold and all prior releases. Append a source-bound, uniquely identified `release` event. Never edit or delete a historical hold. Reject duplicate or excessive releases, open stages, unknown-cost reductions, and any net total above $10. A corresponding reviewed receipt must bind the hold ID, terminal and child/master hashes, old head, exact release amount and new ledger head.
3. Fence historical hold-only writers before the first new event. They reject a `release` event by schema, which fails closed, but their fixed-head receipts and legacy work will then stop. Every future paid-work path must use a reviewed v2 reader that counts each hold minus its reviewed releases under the same file lock. Test mixed-provider concurrent admissions, duplicate release, changed source, active stage, unknown cost, old-reader rejection, crash recovery and no replay.
4. Recheck the authority and OpenRouter master under their locks before any new child allocation or inference. Keep the Jev DEV-018 unknown charge and its failed outcome in the original pass. Any DEV-019 through DEV-060 continuation needs its own reviewed controller and receipt; recovering an unused hold does not approve that execution.

The decisive remaining work is a reviewed v2 accounting implementation and a root-approved release receipt for one sealed stage. The available evidence supports that work within the existing ceiling. This document does not authorize a release by itself.
