# Qwen on/P2 never-sent episodes

This controller covers one existing configuration: `openrouter-paid-qwen36-35b-a3b-on`, condition P2. It preserves the 42 first attempts and their original timing. DEV-033, 039, 040, 041 and 042 remain HTTP 429 service errors with unknown actual charges. Their five child ledgers retain $0.0299008 each as an upper bound. The first episode may send only DEV-043 through DEV-060. Even if all 18 return valid outputs, the composite has 55 valid positions and five service errors out of 60. It does not become an all-valid paired pass.

[The frozen v4 reconciliation](../results/qwen36-on-p2-final19-v4/reconciliation.json) and [plan](../results/qwen36-on-p2-final19-v4/plan.json) are pinned by SHA-256 in the controller. The initial manifest reconstructs every saved request against the frozen execution source, all 42 started and finished journal entries, their raw attempt rows, and their known or full-bound unknown ledger events. The five failed IDs are never eligible for another request.

The exact AkashML `akashml/fp8` endpoint currently appears in [OpenRouter's public endpoint listing](https://openrouter.ai/api/v1/models/qwen/qwen3.6-35b-a3b/endpoints) with $0.10 per million input tokens and $0.90 per million output tokens, 262,144 context tokens, and the required structured-output and reasoning controls. A catalog listing does not establish request capacity. Five saved 429s are direct evidence of prior capacity failure. The worker checks the public model and endpoint catalogs again before loading a key; a price, route, identity, capability, or request difference stops admission.

At the frozen per-call reservation of $0.0299008, all 18 calls require **$0.5382144** of partition capacity. Allocation remains a separate reviewed action against the live $10 master ledger. The controller does not allocate a partition or raise that cap. It requires a fresh, unused child partition with the exact model, provider and reasoning identity, and a cap at least equal to the episode's full call bound. The `root-review.json` in the episode directory must have schema `qwen36-on-p2-episode-root-review-v1`, `approved: true`, the exact manifest, controller and budget-manifest SHA-256 hashes, partition ID, request IDs, retained failed IDs and a nonempty cooldown note. This file is reviewed before dispatch; the program cannot independently prove who supplied its `approved` field.

Offline preparation is one command:

```sh
python3 scripts/qwen36_on_p2_episodes.py prepare --episode 1
```

It exclusively creates `results/qwen36-on-p2-never-sent-episodes-v1/episode-001/manifest.json` and prints its hash. Preparation makes no provider request, loads no key and creates no budget allocation. After external review and allocation, `execute` requires `--manifest`, `--sha256`, `--review`, `--budget-manifest` and `--partition-id`; an optional `--env-file` supplies the existing OpenRouter credential at dispatch time. The timeout is frozen at 300 seconds. There is no retry flag.

Execution exclusively creates a claim and append-only journal, response sidecar and attempt files. Each request first reserves its full bound in the child ledger, then writes a durable `request_started` event. The HTTP response or HTTP error body is captured at a 16 MiB limit, redacted for the credential bytes and saved with ID, attempt ID and request digest before parsing or charge settlement. Incomplete reads and content-length mismatches are recorded. An unknown charge keeps its reservation pending and stops the episode. A known charge above the bound is recorded in full by the reviewed ledger, blocks further calls and needs explicit investigation. Route or returned identity differences also stop the episode.

After a terminal episode, an operator must account any unknown charge at its full bound with the existing reviewed ledger API, reconcile and close the child partition to the master ledger, then run:

```sh
python3 scripts/qwen36_on_p2_episodes.py reconcile --episode 1 --budget-manifest PATH
```

Reconciliation checks each started request against exactly one durable response, attempt, finish event and reserve plus settlement or full-bound unknown event. It binds the closed child ledger and the master's partition reconciliation. A valid model output with missing cost still stops the episode; after explicit full-bound accounting, the output remains valid but the stopped episode can reconcile. A saved HTTP 200 body with malformed JSON remains a service error and can reconcile after the same accounting. Missing raw evidence, an unfinished journal, or a pending charge blocks reconciliation. A later episode can be prepared only after this explicit reconciliation; it derives the remaining suffix from the immutable attempted prefix and cannot resend an attempted ID. New review and budget admission are required for each later episode. The old episode stays intact.

The response sidecar proves what bytes this client saved, subject to credential redaction. It cannot prove whether an interrupted request reached the provider when no response was saved. Such a request stays ambiguous and is never automatically retried. `elapsed_seconds` is client request elapsed time, including transport and local accounting; it is not server inference time. Actual provider charges remain unknown where OpenRouter supplied no cost. The source reference labels are used only by later offline scoring and never enter these requests.
