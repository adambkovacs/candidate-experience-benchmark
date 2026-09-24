# Subscription stopped-condition inventory v1

Captured 2026-09-24T17:28:00Z from the raw saved attempts and outputs. This inventory covers seven stopped development conditions: **160 valid outputs, 70 ambiguous records in failed attempted batches, and 190 never-sent records**. Every original development ID is classified once per condition. Failed attempted IDs are not continuation candidates. Runtime, provider, and guard failures remain distinct from model invalidity.

The machine-readable evidence inventory is [inventory.json](inventory.json). Each condition includes exact ID arrays, ordered attempted batches, failure details, manifest binding, and SHA-256 hashes for its source evidence.

Never-sent suffixes are the only continuation candidates. Existing frozen tooling cannot execute these suffixes unchanged: the Codex raw controller accepts offsets but the shared prompt guard rejects nonzero offsets and requires all 60 development records; the Claude controller has no offset support. Each suffix therefore needs a separately reviewed continuation manifest and continuation-aware guard/controller with unique schedule and output bindings before execution. Do not use the existing frozen phase helper as-is.

No inference was run and no existing run file or shared execution journal was changed. The source journal hash and line count are recorded in `inventory.json`.
