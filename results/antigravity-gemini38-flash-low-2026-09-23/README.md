# Native Antigravity smoke audit

The existing Antigravity login works. CLI 1.2.7 advertises and reports `gemini-3.8-flash-low`; no new login was needed. Personal AI-credit overage was explicitly disabled. This is a native agent workflow, not a bare-model benchmark.

Three smoke requests were made, each containing the same three fictional feedback records without reference labels:

1. Eligibility check returned HTTP 503 before initialization, with zero reported tokens.
2. The native model returned three valid classifications, but initialization listed 57 tools. The native `finish` output tool was observed; no external tool use was observed. A warning said plan mode had no effect with slash expansion disabled.
3. A corrected custom agent added the documented `excludeDefaultComponents: true`, `inheritCustomizations: false` and `inheritMcp: false` controls and removed the conflicting plan flag. It returned three valid classifications without warnings or observed tool calls, but initialization still listed 57 tools.

The CLI initialization list may be inventory rather than effective model exposure; that distinction remains unverified. The strict tool-scope gate therefore failed. No 60-record development run was started, and no further native inference is running. This does not establish actual external tool use or a need to sign in again.

`attempt-summary.json` retains all three request durations and token usage, including rejected configurations. Exact requests, schemas, streams and journals are preserved. The first runtime log was quarantined privately because it could contain session metadata; the explicitly redacted artifact includes its original SHA-256. Later attempts retain only log size/hash. Stream and stderr credential-pattern screening is recorded in `evidence-audit.json`.

Sources: [Antigravity changelog](https://www.antigravity.google/changelog), [custom agents](https://antigravity.google/docs/subagents/), [headless output](https://antigravity.google/docs/cli/headless/), [credits setting](https://antigravity.google/docs/settings/).
