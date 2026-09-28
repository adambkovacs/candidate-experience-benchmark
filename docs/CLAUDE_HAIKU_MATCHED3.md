# Haiku fresh matched-three lane

This lane is separate from `haiku45-not_applicable-phase2-batch10-p0`. The [historical P1 reconciliation](../results/prompt-comparison-v1-2026-09-24/subscription-suffix-continuation-v2-haiku/reconciliation-v1/haiku45-not_applicable-phase2-batch10-p0-P1.json) retains DEV-011–020 as attempted transport failures with no predictions. Its original P1 started before P2 but the P1 suffix completed after P2. The saved CLI result says ENOTFOUND and contains internal retry events; it does not establish whether a provider processed those requests. The old evidence remains intact and is not a first pass in this matched series.

The [controller](../scripts/claude_haiku_matched3.py) plans three new passes over the same 60 synthetic development reviews. Pass one runs `P0,P1,P2`; pass two runs `P1,P2,P0`; pass three runs `P2,P0,P1`. Every condition has one three-review smoke batch and six ten-review development batches. A phase stops on the first non-`ok` or ambiguous result; no batch is replayed. A stopped phase remains visible in `report`, and later conditions or passes cannot proceed through its order gate. All three passes use `claude-haiku-4-5-20251001`, effort `not_applicable`, Claude.ai subscription authentication, Claude Code CLI `2.1.282`, 600-second request timeout, a fresh isolated CLI directory per batch, structured batch output, and zero controller retries. CLI-internal retry behavior is observable only when the CLI emits events and is not controlled here. Serving revision, seed, and hidden rendering are unavailable. Client elapsed time divided across batch members is not pure inference latency. Estimated API-equivalent cost is not a subscription invoice.

`plan_data` reconstructs each development request from the frozen input-only [development records](../data/pilot/inputs.jsonl), saved historical request envelopes, and byte-bound P0/P1/P2 instructions. P1's original failed request and its later four successful suffix requests are bound as source evidence, but no prior prediction or reference label enters a new request. The manifest also binds the historical reconciliation, schema, controller, parser, and Claude mechanics. A changed source hash or changed request reconstruction fails verification. The new manifests and live evidence would live only under `results/repeatability-v1/claude-haiku-fresh-matched3/`.

The offline preparation command is:

```sh
python3 scripts/claude_haiku_matched3.py prepare
```

It exclusively creates `pass1`, `pass2`, and `pass3` manifests and prints their SHA-256 hashes. Preparation was completed on 2026-09-28 after independent review and seven passing controller tests. The three manifests are frozen under the directory above. Before any live phase, an operator must review those exact manifests and provide a fresh private subscription preflight receipt outside the repository. The receipt must satisfy the reviewed Claude preflight: `operator=root`, pinned CLI version, `claude.ai`/`firstParty`, credits and extra usage off, both quota percentages below 95, and timestamp no older than 30 minutes. The public phase review contains only hashes and the exact admitted condition/phase; it must not include private quota values. Its required shape is:

```json
{
  "schema": "claude-haiku-fresh-matched3-root-review-v1",
  "approved": true,
  "configuration_id": "haiku45-fresh-matched3-batch10",
  "pass": "pass1",
  "manifest_sha256": "<exact pass manifest SHA-256>",
  "controller_sha256": "<controller SHA-256>",
  "mechanics_sha256": "<claude_repeat_study.py SHA-256>",
  "roster_sha256": "<claude_repeat_roster.py SHA-256>",
  "private_preflight_sha256": "<private receipt SHA-256>",
  "cli_path": "/Users/adamkovacs/.local/share/claude/versions/2.1.282",
  "cli_version": "2.1.282 (Claude Code)",
  "approved_phases": [{"condition": "P0", "phase": "smoke"}],
  "review_note": "<specific reviewed admission>"
}
```

For each condition in frozen order, the operator runs `smoke` with `--pass`, `--condition`, `--manifest-sha256`, `--claude`, `--root-review`, `--root-review-sha256`, `--preflight-receipt`, and `--preflight-sha256`. After checking its saved raw capture, identity, one attempt, three records, and journal, `inspect` adds `--note` and writes an immutable smoke inspection. A separately admitted `development` phase then uses the same arguments as smoke and checks that the inspected smoke files are unchanged. Each phase claims an exclusive path, durably journals dispatch intent before the CLI call, and saves sanitized raw CLI output before parsing. A started request without a saved result is ambiguous and cannot be automatically sent again. The controller rejects API-key login, overage, unexpected model/tool use, a changed CLI binary path or version, stale private preflight, and any unreviewed phase.

`python3 scripts/claude_haiku_matched3.py report` is read-only. It records smoke and development states separately, counts `ok`, `invalid_output`, and `service_error` records, and verifies saved raw hashes. It does not score labels or turn missing predictions into valid ones. A later scoring report must distinguish 60 attempted positions from valid-prediction intersections, preserve every failed batch, and keep the historical attempt-outcome analysis separate from this new matched series.

The initial implementation checkpoint was offline. On 2026-09-28 the root task reviewed the controller, froze and independently verified all three manifests, and admitted this separate study through the existing Claude subscription. Execution remains subject to a fresh private quota receipt and smoke inspection for every condition. Admission is not completion; terminal journals and raw evidence establish each finished phase.
