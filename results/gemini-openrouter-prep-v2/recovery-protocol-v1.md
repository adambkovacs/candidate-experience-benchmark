# Gemini v2 smoke recovery

The original Gemini 3.8 Flash low P0 smoke stopped because the immediate OpenRouter generation-metadata GET returned an HTTP error. Its completion and $0.001704 charge remain in the original v2 attempt. Do not repeat the smoke inference request.

`smoke-recovery-proof-v1.json` binds the original manifest, smoke attempts, smoke records, smoke journal, and recovered metadata sidecar by SHA-256. It checks the generation ID, Google AI Studio provider, allowed model revision, exact reported cost, token counts, absence of tool/search use, and the three parsed judgments. The original v2 files remain unchanged.

To authorize the six frozen development batches, create a reviewed JSON receipt with exactly these fields:

```json
{
  "schema": "gemini-openrouter-continuation-approval-v1",
  "approved": true,
  "manifest_sha256": "546b42fd2ffb8634b3c4f89cd5fb0c00044b0d551880efe79efa071fbca1b066",
  "smoke_recovery_proof_sha256": "11e45d0463286fb61f454e344a1c7e9caaf8cf9c8f94792bbe2e26f790745271",
  "controller_sha256": "5b422b159290033521d10baba25df75c49e402a61094aaf77604788cc7120e20",
  "budget_manifest_sha256": "a994b6f4a673f35e409f9c2f6f2a393ee14f181a8481cf74b9f64880678a3f68",
  "partition_id": "gemini-v2-38-low",
  "phase": "development"
}
```

After creating that receipt, run from the repository root:

```sh
python3 scripts/gemini_openrouter_metadata_recovery_v1.py run-development \
  --manifest results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0/manifest.json \
  --manifest-sha256 546b42fd2ffb8634b3c4f89cd5fb0c00044b0d551880efe79efa071fbca1b066 \
  --budget-manifest results/gemini-openrouter-prep-v2/probe-budget-v2.json \
  --partition-id gemini-v2-38-low \
  --approval PATH_TO_REVIEWED_RECEIPT \
  --env-file .env
```

The controller makes at most six chat-completion POSTs, one per frozen batch of ten. It does not replay the smoke or retry a POST. After each completion, generation metadata GET can retry twice, with one second between attempts. If identity or billing cannot be verified, the controller stops and records the paid response and terminal reason.

OpenRouter documents that [generation metadata can take a few seconds to appear](https://openrouter.ai/blog/tutorials/choose-best-ai-model/) and defines the [generation lookup API](https://openrouter.ai/docs/api/api-reference/generations/get-generation).
