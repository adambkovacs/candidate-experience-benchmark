# Sonnet 5.5 continuation after the first smoke guard failure

The first Sonnet 5.5 `low/pass1/P0` smoke was dispatched once on Claude Code 2.1.287. Its saved result has three valid structured predictions for DEV-001 through DEV-003, exact `claude-sonnet-5-5` model identity, a successful CLI exit, one StructuredOutput tool call, no MCP servers or skills, and no observed overage. The original controller marked the batch `service_error` and stopped because its two-plugin allowlist did not recognize the three built-in identities reported by this CLI version. The [original attempt, raw capture, and stopped journal](../results/repeatability-v1/claude-sonnet55-fresh-matched3/low/pass1/P0/) remain unchanged. The original smoke is not rerun or relabeled.

The [v2 controller](../scripts/claude_sonnet55_matched3_v2.py) accepts exactly `cc-plugin-agents-md@builtin`, `cc-plugin-telemetry@builtin`, and `cc-plugin-plugin-authoring@builtin`, each with `path=builtin`. It rejects any missing, extra, renamed, or non-built-in plugin, and still requires the exact model, StructuredOutput alone, empty MCP and skill lists, and no observed overage. This is a Sonnet-local check; the shared Claude parser and original controller are unchanged. [Claude Code's CLI reference](https://code.claude.com/docs/en/cli-reference) says safe mode disables customizations such as user plugins and skills, while `--system-prompt` replaces the default prompt and `--tools ""` disables tools. The saved envelope does not independently expose every hidden effect of built-in plugin-authoring, so that remains an experimental limit.

The [offline admission sidecar](../results/repeatability-v1/claude-sonnet55-fresh-matched3-v2/low/pass1/P0/offline-smoke-admission.json) rechecks the retained raw output with the v2 guard. It records both the original terminal `service_error` and the v2 `ok` parsing result, along with hashes of the original manifest, claim, attempt, records, journal, raw capture, and review. It contains no reference labels and makes no model call. The v2 controller refuses to dispatch `low/pass1/P0/smoke` again. Its development gate requires a new root review bound to the sidecar's SHA-256; a review of the original smoke cannot admit development.

The 12 new manifests under [the v2 series](../results/repeatability-v1/claude-sonnet55-fresh-matched3-v2/) use separate configuration IDs ending in `-v2`. Each binds its corresponding original manifest and compares all P0/P1/P2 requests, batch membership, order, model, effort, and CLI runtime to that frozen source. It also binds the shared input loader, schema, prompt files, and both Sonnet controllers. Future smokes and development phases use the v2 guard. The first original smoke counts as a retained attempted smoke with a separate offline admission, not as a new request. No development phase has begun in v2.

For `low/pass1/P0`, the v2 manifest SHA-256 is `112dba9e9ef7b7e6c5183f14483f768d058b3304a0046fbb25f85679217bbf42`; the offline sidecar SHA-256 is `3a2e307627ca351a6c878cd5094a3074802da40b91fdd6d49fbc86a1b5231f83`. Verify them without inference:

```sh
python3 scripts/claude_sonnet55_matched3_v2.py --effort low verify \
  --pass pass1 --manifest-sha256 112dba9e9ef7b7e6c5183f14483f768d058b3304a0046fbb25f85679217bbf42
python3 scripts/claude_sonnet55_matched3_v2.py --effort low report
python3 -m unittest tests.test_claude_sonnet55_matched3_v2 -v
```

The next inference candidate is `low/pass1/P0/development`, six ordered batches of ten. Before dispatch, root reviews the original raw smoke and v2 sidecar, records a fresh private subscription preflight outside this repository, and writes a separate `claude-sonnet55-fresh-matched3-v2-root-review-v1` receipt. That receipt must name only `[{"condition":"P0","phase":"development"}]` in `approved_phases` and set `smoke_evidence_sha256` to the sidecar hash above. It also binds the v2 manifest, v2 controller, shared mechanics and roster hashes, private preflight hash, exact CLI path and version, and a review note. The development command requires all of those paths and hashes:

```sh
python3 scripts/claude_sonnet55_matched3_v2.py --effort low development \
  --pass pass1 --condition P0 \
  --manifest-sha256 112dba9e9ef7b7e6c5183f14483f768d058b3304a0046fbb25f85679217bbf42 \
  --claude /Users/adamkovacs/.local/share/claude/versions/2.1.287 \
  --root-review ABSOLUTE_V2_REVIEW_PATH --root-review-sha256 REVIEW_SHA256 \
  --preflight-receipt ABSOLUTE_PRIVATE_PREFLIGHT_PATH --preflight-sha256 PREFLIGHT_SHA256
```

The controller rejects the command if source hashes, offline admission, root review, preflight, quota, auth, or CLI identity fail. Its `low/pass1/P0/smoke` action always rejects before any model call.
