# Claude Sonnet 5.5 matched-three admission

Sonnet 5.5 is a new Claude subscription configuration. It has no historical pass in this benchmark. Each of `low`, `medium`, `high`, and `xhigh` therefore needs three separately dispatched 60-record passes for P0, P1, and P2. This is 36 development phases, 216 ordered batches of ten, and 36 separate three-record smokes. Failed, invalid, and ambiguous attempts remain in the denominator. No completed Sonnet 5 pass is relabeled as Sonnet 5.5.

The exact requested model is `claude-sonnet-5-5`. [Anthropic's model page](https://platform.claude.com/docs/en/models/sonnet-5-5/overview) lists that ID. [Anthropic's effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort) says Sonnet 5.5 supports low, medium, high, xhigh, and max; the user's current scope excludes max and ultra. Anthropic also says these effort levels were recalibrated from Sonnet 5, so comparisons between equal named levels across the two models need that caveat.

The [dedicated controller](../scripts/claude_sonnet55_matched3.py) pins Claude Code `2.1.287 (Claude Code)` at `/Users/adamkovacs/.local/share/claude/versions/2.1.287`. On 2 October, the local CLI reported that version, and `--safe-mode auth status` returned `loggedIn=true`, `authMethod=claude.ai`, and `apiProvider=firstParty`. These checks establish CLI and account identity. They do not establish current quota, credits-off status, extra-usage status, or a successful Sonnet 5.5 inference. [Claude Code CLI documentation](https://code.claude.com/docs/en/cli-reference) describes the model, effort, safe-mode, and print controls.

The controller binds the existing [P0/P1/P2 instruction files](../results/prompt-comparison-v1-2026-09-24/subscription-preparation-v2/sonnet5-low-first-pass-phase2-batch10-p0/), the 60 ordered `{id, feedback}` inputs, the schema, and each shared source file used to build or check a request, including `scripts/development_benchmark.py`, by SHA-256. The instruction bytes are the same as those in the prior Haiku batch lane. Every request has a fresh temporary workspace and CLI process, a fixed ten-record batch except for a separate three-record smoke, a structured schema, no controller retry, and a stop after the first non-OK or ambiguous batch. The CLI uses safe mode, empty settings sources, no external tools or MCP servers, no session persistence, and no fallback model. The parser requires exactly the requested IDs and model identity. References and prior predictions stay outside inference.

Pass orders rotate by condition: pass1 P0/P1/P2, pass2 P1/P2/P0, pass3 P2/P0/P1. Each pass is a distinct manifest. For each effort, the controller requires the previous pass to close before the next and requires the preceding condition to close before a later condition. Each smoke needs inspection before development. A claimed phase cannot be replayed. The CLI's effective seed, serving revision, hidden rendering, and internal retries remain unobservable. Client elapsed time includes CLI startup and is not pure inference time; reported API-equivalent cost is not a subscription charge.

Before the first smoke, root must record a fresh private preflight **outside this repository**. It must identify the root operator, exact CLI version, Claude.ai first-party authentication, credits off, extra usage disabled, current session and weekly usage below 95%, and a UTC check within 30 minutes. The controller rechecks live auth and version before inference. Root then supplies a hash-bound review receipt naming the manifest, controller, shared mechanics, private preflight, CLI path and version, and **one** admitted condition and phase. A smoke review has `smoke_inspection_sha256: null`. A development review is a separate receipt written after smoke inspection and must contain the exact SHA-256 of that inspection file. One review cannot admit both phases. The review file contains hashes and controls only. Root should inspect the first Sonnet 5.5 smoke's raw capture, model identity, plugin/tool isolation, usage event, output validity, and quota state before admitting any 60-record development phase.

Offline preparation and verification:

```sh
for effort in low medium high xhigh; do
  python3 scripts/claude_sonnet55_matched3.py --effort "$effort" prepare
done
python3 -m unittest tests.test_claude_sonnet55_matched3 -v
```

All 12 manifests were refrozen and verified after adding the shared input-loader binding and the separate development review gate. The `low/pass1` manifest is `a2be0656aa4fb117bf8821cdef4e68059d56eab17532cdb2db7f3bccd5377dc2`. To check it without inference:

```sh
python3 scripts/claude_sonnet55_matched3.py --effort low verify \
  --pass pass1 --manifest-sha256 a2be0656aa4fb117bf8821cdef4e68059d56eab17532cdb2db7f3bccd5377dc2
```

The first possible model call is `low/pass1/P0/smoke`, after the private preflight and root review exist. Its command shape is:

```json
{
  "schema": "claude-sonnet55-fresh-matched3-root-review-v2",
  "approved": true,
  "configuration_id": "sonnet55-low-fresh-matched3-batch10",
  "pass": "pass1",
  "manifest_sha256": "a2be0656aa4fb117bf8821cdef4e68059d56eab17532cdb2db7f3bccd5377dc2",
  "controller_sha256": "90059a4c264f9003ce78a8233a390bb947a46b17c44c12b9579150026f2d2080",
  "mechanics_sha256": "7ef992b3312dbaa83f3e94827a7bd95025130f316a0949b6d9230648bb1783c0",
  "roster_sha256": "103d8a919eac33d264c7e44eb22af688061559effc16c0e05084381d66ee488a",
  "private_preflight_sha256": "PREFLIGHT_SHA256",
  "cli_path": "/Users/adamkovacs/.local/share/claude/versions/2.1.287",
  "cli_version": "2.1.287 (Claude Code)",
  "approved_phases": [{"condition": "P0", "phase": "smoke"}],
  "smoke_inspection_sha256": null,
  "review_note": "Root inspection note explaining this smoke admission"
}
```

Save the actual reviewed JSON as `results/repeatability-v1/claude-sonnet55-fresh-matched3/low/pass1/P0/smoke.root-review.json`, then hash that file. Replace the private preflight hash and review note with observed values. The controller checks the preflight hash and rejects stale preflights.

```sh
python3 scripts/claude_sonnet55_matched3.py --effort low smoke \
  --pass pass1 --condition P0 \
  --manifest-sha256 a2be0656aa4fb117bf8821cdef4e68059d56eab17532cdb2db7f3bccd5377dc2 \
  --claude /Users/adamkovacs/.local/share/claude/versions/2.1.287 \
  --root-review ABSOLUTE_REVIEW_PATH --root-review-sha256 REVIEW_SHA256 \
  --preflight-receipt ABSOLUTE_PRIVATE_PREFLIGHT_PATH --preflight-sha256 PREFLIGHT_SHA256
```

After a successful smoke, `inspect` records an evidence-bound inspection note. Root can then write a new `claude-sonnet55-fresh-matched3-root-review-v2` review with `approved_phases: [{"condition":"P0","phase":"development"}]` and `smoke_inspection_sha256` set to the inspection file's SHA-256. Development requires that new review and a fresh private preflight. No model request or full pass was dispatched during offline preparation.

## First smoke outcome

The low/P0 smoke returned three structured outputs from `claude-sonnet-5-5`, then the controller stopped with `IsolationIdentityOrBillingGuard`. The CLI reports three built-in plugins with names absent from the older shared guard. Original evidence retains `service_error`; no development phase was admitted. The [public capture](../public-evidence/claude-20261002/sonnet55-first-smoke/manifest.json) removes private account and quota diagnostics while retaining model output and usage. A separately versioned guard assessment is required; this attempt must not be replayed or silently repaired.
