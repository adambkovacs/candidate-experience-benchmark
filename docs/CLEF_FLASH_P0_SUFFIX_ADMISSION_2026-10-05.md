# Clef Flash P0 unsent suffix admission

This note records an offline-only admission for the 59 Clef Flash fresh3/P0
development requests that remained unsent after the frozen parent stopped at
DEV-001. It does not allocate money, call Cloudflare, modify the shared
authority ledger, or replay DEV-001.

The suffix is exactly DEV-002 through DEV-060. Its preparation binds the
parent completion, the parent `external-error-audit.json`, the completed
three-record smoke review, the frozen request set, the native bridge, the
Clef Flash billing source, and the authority snapshot. The suffix has its own
stage identity and child directory and reserves exactly `$0.348041` (59 ×
`$0.005899`). The earlier `$0.35394` parent hold remains untouched.

Preparation is deterministic and writes only the requested immutable
manifest:

```sh
python3 scripts/clef_flash_p0_suffix.py prepare \
  --output results/clef-native-v1/clef-flash/fresh3/P0/development-suffix-manifest-v1.json
python3 scripts/clef_flash_p0_suffix.py check \
  --manifest results/clef-native-v1/clef-flash/fresh3/P0/development-suffix-manifest-v1.json
```

Before any execution, root must independently review that manifest and create
a suffix grant binding its SHA-256, the account hash, the current authority
ledger head, the native bridge, the smoke review, the parent completion and
external error audit, the exact `$0.348041` hold, and the catalogue/billing
source. The catalogue recheck is evidence for model route and price only; it
is not quota or inference-success proof. The grant and root review are outside
this offline preparation step.

After that review, root may run the one-shot native handoff with:

```sh
python3 scripts/clef_flash_p0_suffix.py run --execute \
  --manifest results/clef-native-v1/clef-flash/fresh3/P0/development-suffix-manifest-v1.json \
  --grant /path/to/root-reviewed-clef-flash-p0-suffix-grant.json \
  --env-file /path/to/private/cloudflare.env
```

The controller claims its separate child directory atomically, reserves one
request at a time, writes the native bridge request, and accepts the exact
app-result submission protocol described below. Any unknown transport result, malformed
bridge/provider envelope, service error, or strict invalid output stops the
stage; all later IDs remain in `never_sent`, with the corresponding unknown
charge bound preserved. No retry is permitted.

The operator must save `<attempt>.dispatch.json` before calling the connected
app. It contains the ready request's `request_sha256` and the operator name.
After the call, save both the complete MCP tool result and its inner app
response without alteration. Submit them with:

```sh
python3 scripts/clef_flash_p0_suffix.py submit \
  --request /path/to/attempt.request.json \
  --app-result-file /path/to/saved-app-result.json \
  --tool-result-file /path/to/saved-tool-result.json
```

Submission verifies the dispatch marker and matching outer and inner results,
then saves the evidence beside the ready request before releasing the response
to the waiting runner. A tool error has no verified provider response: preserve
it and let the runner stop as an unknown outcome. Do not resend the request.
The parent audit's request hash identifies the full bridge file; the terminal
record's request hash identifies the model payload. The controller checks both
against their respective saved bytes.

Sources: [current goals](CURRENT_GOALS.md), [native remaining controller](../scripts/clef_native_remaining.py), [native preparation](../scripts/clef_native_preparation.py), [connected-app bridge](../scripts/clef_connected_app_bridge.py), [catalogue recheck](../results/clef-native-v1/catalogue-recheck-2026-10-05.json), and the frozen [parent completion](../results/clef-native-v1/clef-flash/fresh3/P0/development/completion.json).
