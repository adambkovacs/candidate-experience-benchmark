# Benchmark execution system specification

Status: design proposal, 2026-09-24. This document authorizes no inference, downloads, dataset generation or spending. It applies to repeatable tasks with fixed inputs and measurable outputs, including the current recruitment-feedback comparison.

Build a small durable coordinator around an existing evaluation framework. Reuse this repository's request builders, strict parsers, scorers and evidence checks. Select the framework through a bounded adapter test before replacing live runners. The next benchmark should require one experiment file and one execution command, with an explicit queue and automatic progress reporting.

The current scope remains 60 development records. The additional 340 records require separate authorization and the review and split-freeze steps in [PLAN.md](PLAN.md). A better runner does not turn provisional development references into held-out evidence.

## Problem and requirements

The current scripts protect useful properties: exact request bindings, separate reference evaluation, inspected smoke runs, preserved failures and spending limits. Their coordination has become expensive. Different adapters duplicate launch, admission and result handling; global journal updates can contend; each stopped condition needs manual reconciliation; local and hosted work compete for attention despite different resource needs.

In the latest hosted prompt phase, all 13 lanes reached a terminal state, but only five had complete P1/P2 pairs. Other lanes stopped on output length, provider 429/504 responses or DNS timeouts. A terminal lane is therefore not a completed comparison. The dashboard and command output must make that distinction visible.

The system must:

1. Expand and validate an experiment matrix before execution, including explicit unsupported or blocked configurations.
2. Resume untouched work without repeating completed requests or hiding previous attempts.
3. Run independent hosted lanes concurrently while respecting provider limits, account quotas, a shared money cap and local device locks.
4. Record the exact observable request, response, model identity, runtime and control settings. Unknown provider internals remain unknown.
5. Keep reference labels, metadata and previous predictions outside inference workers and their workspaces.
6. Treat output invalidity as a measured outcome. Separate it from transport failures, policy violations and unattempted work.
7. Produce quality, reliability, latency, cost and prompt-comparison reports offline from immutable evidence.
8. Preserve current results and allow gradual migration without changing a running experiment's protocol.

Relevant existing implementations are [admission](../scripts/prompt_admission.py), [controller guards](../scripts/prompt_controller.py), [schedule journal](../scripts/prompt_schedule.py), [paid runner](../scripts/openrouter_paid_benchmark.py), [budget partitions](../scripts/paid_budget_partitions.py), [offline protocol audit](../scripts/audit_prompt_protocol.py) and [paired evaluation](../scripts/evaluate_prompt_variants.py). These are migration inputs, not evidence that the proposed system already exists. The separate remaining-record amendment is still a draft and is not an adopted execution path.

## Adaptation decision

Evaluate Inspect AI and promptfoo first. Inspect's Python model extension is a plausible home for our adapters; promptfoo is a useful challenger for declarative prompt/configuration matrices and review. The companion [framework research](HARNESS_RESEARCH.md) owns the broader candidate and license review. Its recommendations must be checked against pinned versions during the implementation spike.

Framework defaults must not become experimental policy. Inspect documents indefinite recoverable API retries and separate eval-set retry and cleanup behavior. Promptfoo documents enabled caching and exposes test context to custom scripts. Disable or replace these behaviors where they conflict with a frozen run; prove the effective settings through integration tests. [Inspect concurrency](https://inspect.aisi.org.uk/models-concurrency.html), [Inspect eval sets](https://inspect.aisi.org.uk/eval-sets.html), [Inspect model extensions](https://inspect.aisi.org.uk/extensions-model-api.html), [promptfoo configuration](https://www.promptfoo.dev/docs/configuration/reference/), [promptfoo script providers](https://www.promptfoo.dev/docs/providers/custom-script/).

Preserve attempts outside any framework view that removes prior errors after success. Promptfoo documents that behavior for `--retry-errors`. EvalScope's `--ignore-errors` can reduce the evaluated denominator, which conflicts with our full-denominator reports. Inspect's generate-boundary cost checks are useful but do not establish an atomic aggregate reservation across concurrent workers and unknown charges. [promptfoo CLI](https://www.promptfoo.dev/docs/usage/command-line/), [EvalScope basic usage](https://evalscope.readthedocs.io/en/latest/get_started/basic_usage.html), [Inspect limits](https://inspect.aisi.org.uk/setting-limits.html).

Use the following selection gates, with passing evidence in a short architecture decision record:

| Gate | Required demonstration |
| --- | --- |
| Request fidelity | A real adapter receives exactly the frozen prompt, schema and controls, without extra instructions or hidden retries introduced by the framework. |
| Reference isolation | The inference process cannot read reference files, scorer context, prior predictions or unapproved framework caches. |
| Evidence export | Original raw responses and attempts survive errors, cancellation, resume and export. Native specialist results remain representable. |
| Scheduling | We can own admission, request claims, resource limits and retry decisions without patching many framework internals. |
| Accounting | Every billable attempt requires our reservation before dispatch; usage settles once at the request unit. |
| Portability | A clean checkout can reproduce parsing and scoring offline. No hosted dashboard subscription is required. |
| Maintenance | Pinned permissive license and dependency review pass; adapter changes are small enough to test after upgrades. |

Reject a candidate that cannot meet a hard gate. Prefer a thin integration over a fork. If neither fits execution safely, use their report or evaluation layer while keeping the existing runners behind the coordinator. Do not build a new agent framework, model server, authentication service or distributed cluster scheduler for this project.

## Architecture and ownership

Use one coordinator process on the Mac initially. It owns a SQLite database on local disk, a short transaction for each claim or accounting mutation, and a content-addressed artifact directory. Workers run in separate processes and communicate through a narrow local interface. No database transaction or journal lock spans inference.

The database holds mutable scheduling projections and append-only event and money records. Artifacts hold immutable request and response bytes. Each committed terminal event refers to artifact hashes; durable writes and atomic rename happen before the event is committed. A crash may leave an unreferenced artifact, which recovery can inspect. It must never create a terminal record pointing to bytes that were not durably saved.

A framework adapter consumes the compiled execution plan and returns events to this coordinator. It does not independently decide retries, spending or sample selection. If the selected framework already meets a component's requirements, use that implementation and its tests instead of duplicating it.

Logical boundaries:

- The planner validates inputs, expands configurations and freezes the request schedule.
- The scheduler claims admitted requests and acquires account, provider and device capacity.
- The worker receives a label-free execution capsule and runs one request.
- The evidence recorder saves raw bytes, observable controls and stream events.
- The parser produces typed predictions or explicit invalid-output reasons.
- The scorer reads references in a separate offline process.
- The report builder reads stable snapshots, never mutates run state, and exposes incomplete work.

SQLite is the proposed single-host starting point, not a requirement for future multi-host execution. Do not put its live database on a shared network filesystem. Move coordination to a transactional service only when there is a demonstrated need for multiple hosts. Keep the artifact and adapter contracts stable across that change.

## Data contracts and identities

Use schema-versioned JSON contracts with canonical serialization and SHA-256 for content identity. Store UTC wall-clock times for chronology and monotonic elapsed times within a process. Never infer duration by subtracting wall-clock values across hosts.

| Entity | Required identity and content |
| --- | --- |
| Dataset snapshot | Dataset ID, input hash, ordered record IDs, split assignment and task-input schema. Reference binding is held only in evaluation metadata. Scenario-family metadata stays out of worker capsules. |
| Task specification | Task ID/version; instruction and policy hashes; output schema; deterministic parser/scorer versions; permitted input fields; metric definitions. Recruitment is one task implementation. |
| Configuration | Exact requested model and resolved identity when exposed; provider/route; workflow class; artifact revision and quantization where known; reasoning, sampling, schema mode, context and output limits; runtime and adapter build; retry/cache policy. Explicit nulls need an evidence reason. |
| Experiment | Human ID plus plan hash; dataset/task/configuration bindings; conditions; repeats; seed policy; context unit; record order; smoke gate; money/quota authority; schedules and exclusions. |
| Request unit | Stable logical ID from experiment, configuration, condition, phase, repeat and exact ordered membership. References a rendered request artifact and binding digest. Smoke and full-run requests are distinct. |
| Attempt | Unique ID, request ID, attempt ordinal, parent retry/recovery event, lease generation, timestamps, process/host identity, raw artifacts, reported model, finish/error reason, usage and charge evidence. |
| Prediction | Record ID, request/attempt ID, parser version, strict status, typed output or diagnostic. Does not contain a silently repaired output. |
| Evaluation | Reference and scorer hashes, immutable selected-attempt map, denominator, all metrics and limitations. Re-scoring creates a new evaluation ID without inference. |
| Artifact | Hash, media type, byte count, relative storage location, producing attempt and confidentiality class. Credentials are never an artifact. |

Keep human aliases separate from exact identities. A hosted model with undisclosed weights is not an exact local checkpoint, and a changed provider route is a new configuration. Config IDs must include effective execution controls; a display-name change alone must not cause a new request.

Record adapter source/dependency digests per frozen build. A reporting-only update should not invalidate an unrelated live request. Compile reusable prompt, schema and configuration artifacts once; generate request bindings rather than maintaining hand-written per-configuration manifests.

## Worker adapter interface

The interface is conceptual; names are proposed rather than existing commands or APIs.

```python
capabilities() -> CapabilitySnapshot
prepare(config, input_capsule) -> PreparedRequest
preflight(prepared) -> AdmissionEvidence
execute(prepared, attempt_context) -> RawAttempt
inspect(raw_attempt) -> ObservedDiagnostics
cancel(attempt_context) -> CancellationEvidence
reconcile(attempt_context) -> RecoveryEvidence
```

`execute` receives an attempt ID, scoped credentials from the normal runtime, a time budget and a reservation permit. It cannot load references or choose another model. `prepare` is deterministic and does not perform inference. `inspect` checks identity, tools, finish status and limits, independently of task correctness. Parsers and scorers remain separate.

The capability snapshot must distinguish supported, unsupported and unknown controls: native system role, structured output, exact tokenizer, provider batch API, cancellation, idempotency, usage/cost fields, exposed reasoning controls, controllable tools, cache settings and internal retries. Unknown support cannot silently become a claimed guarantee.

| Adapter | Required treatment |
| --- | --- |
| Claude/Codex subscription CLI | Use supported subscription authentication in an isolated workspace. Record binary/version, exact arguments, input, stdout/stderr and event stream; expose only configured tools. Check paid overage state. Observe CLI retries where possible; unexposed retry counts stay unknown. Never extract subscription credentials into an API client. |
| Gemini/Antigravity CLI | Preserve its native-agent workflow class when bare-model isolation is unavailable. Audit advertised and observed tool events separately. A denied external tool attempt is still an isolation violation; a configured empty list alone is not proof of enforcement. |
| OpenRouter API | Pin model and approved provider routing, disable fallbacks where required, retain pricing snapshot and raw usage. Reserve before each dispatch. Catalog and endpoint availability checks are distinct from billable inference. |
| LM Studio | Verify exact artifact, quantization, runtime/backend, context and supported template rendering. Acquire the local GPU lock before load. Use rendered token IDs when available; otherwise label the admission evidence limitation. |
| Native specialist | Preserve original direct-decision, NLI, choice/probability, diffusion or generated-label method. Record artifacts, tensor precision, tokenization and native parameters. Multiple calls per record are explicit child requests. No conversion into chat merely to fit a framework interface. |

Add cancellation and finalizer tests for each adapter. Worker cleanup may remove its isolated temporary workspace after evidence has been captured; it cannot delete historical raw attempts or references.

## Reference isolation and caches

An inference capsule contains only permitted task inputs, required policy, output contract, mapping IDs where required, and effective execution controls. Reject unknown input fields. The scheduler keeps evaluation metadata and references in a separate store that is never mounted into a worker sandbox. A clean current directory alone does not prove isolation if the CLI can access the repository, home instructions, memories or shared caches.

Test each subscription adapter with labeled sentinel files outside the capsule, discovery of default context sources, and captured launch/runtime evidence. Disable supported memory, tool and plugin paths. If stronger isolation is unavailable, label the workflow limitation explicitly and stop on observed forbidden access. Do not claim an OS boundary that was not enforced.

Disable framework response caching for measured inference by default. Importing an existing attempt is an explicit reuse event, not a new execution. If a future experiment studies caching, declare cache namespace, key, eligibility and hit/miss status; include all request controls in the key. Provider-side cache usage may be observable only through telemetry. Do not equate unknown cache state with a cold request.

Raw CLI cache files can contain unrelated conversations or credentials. Save only the minimal scoped response/events needed for this attempt, and never copy whole account caches into the repository. Preserve exact application payload bytes where safe; exclude authorization headers and redact secrets in transport diagnostics before storage, recording that boundary.

## Planning, context units and admission

The planner produces a cost and request-count preview without loading references or invoking models. It rejects duplicate configuration identities, unsupported efforts, missing artifacts and unauthorized routes before smoke. It records an explicit disposition for every roster entry.

Multi-record prompts and provider asynchronous batches are different axes:

- `records_per_context: 10` means ten records share one model context. This can affect predictions and is an experimental control.
- `transport: provider_async_batch` means the provider schedules many independent requests. Each may still contain one record or ten, according to the frozen plan.

Hold record membership, order and boundaries fixed across paired prompt conditions. Switching either axis requires a new configuration or declared comparison. Count tokens, cost and duration once per actual request; per-record shares are labeled amortized. An asynchronous batch must save its provider job ID, per-item custom IDs, results and partial failures, and reserve the approved liability before submission.

For local tokenizers, verify the complete rendered prompt plus output reserve against the actual effective capacity. Include native canvas/overhang behavior where relevant. For opaque wrappers, retain full client bytes, advertised limits and observed usage; prospective token counts may remain unknown. Never call bytes a token bound or silently truncate the policy or feedback.

A new configuration/condition needs three smoke records, recorded raw-response inspection and a bound admission decision before full execution. Smoke inspection checks protocol and output behavior, not agreement against secret answers. Intrinsic schema failures can be admitted as an expected measured limitation under the frozen policy. Identity mismatch, tool violations or proven context overflow block admission.

## State and safe recovery

Maintain separate state for experiment eligibility, logical requests and actual attempts. Sample outcome does not double as scheduler state.

```text
configuration: planned -> preflight_passed -> smoke_running
               -> inspection_required -> admitted -> active -> terminal
               -> blocked (reason and evidence required)

request: pending -> leased -> dispatch_intent -> running -> response_saved
         -> parsed -> terminal

recovery: lease_expired -> reconciliation_required
          -> restored_result | safe_to_dispatch | unresolved_submission
```

Terminal request outcomes include valid output, invalid output, exhausted permitted transport attempts, policy violation and canceled-before-dispatch. Unattempted records remain pending, deferred or blocked and visible in coverage. A configuration can be terminal-incomplete; only complete coverage plus required audits means completed.

Leases include owner, heartbeat time, expiry and a monotonically increasing fencing token. A stale worker cannot update current state, settle a second charge or take a new request. A dispatch permit is validated immediately before the external call. Once a call may have crossed the network, lease expiry cannot prove that the provider did not execute it.

Exactly-once inference is not promised for interfaces without provider idempotency. Persist dispatch intent before sending. On restart, inspect durable response files, provider IDs/status and surviving child processes. Import a saved result before considering another attempt. Reuse provider idempotency keys only where their semantics are verified. Otherwise mark ambiguous submissions unresolved, keep the charge hold, and require a recorded recovery decision. Do not automatically resend on lease expiry.

Heartbeat timeouts signal a need to reconcile, not permission to kill a slow model. Cancellation records whether execution stopped locally, whether provider cancellation was confirmed, and whether billing remains uncertain. Recovery may process untouched records after an explicit policy decision while keeping the original ambiguous attempt unresolved.

## Failure policy and concurrency

Freeze policy before execution. A future default can permit at most two retries for demonstrated transient infrastructure failures with capped exponential backoff and jitter, consistent with the intended final protocol in [PLAN.md](PLAN.md). Current imported no-retry runs retain their original policy. Framework and adapter retry layers must not multiply this budget invisibly.

| Observation | Proposed frozen-policy action |
| --- | --- |
| Valid structured answer, including an incorrect judgment | Save and score; continue untouched requests. |
| Fenced JSON, wrong enum, extra field, refusal or malformed output | Preserve strict invalidity; no repair or content retry. Continue unrelated requests if protocol integrity remains intact. |
| Output budget exhausted | Save invalid/truncated outcome. Continue untouched requests with the same budget if the experiment permits it; never enlarge only the failing condition. A repair or larger-budget study has a new ID. |
| Proven input/context overflow or identity/control drift | Stop affected configuration; record blocker. Do not shorten inputs or silently substitute. |
| DNS/connect failure demonstrably before submission | Record attempt; retry within frozen infrastructure budget without a charge settlement claim. Shared-network breaker may pause other affected lanes. |
| Timeout/504 after possible submission | Hold unknown charge. Query status if supported; no automatic duplicate without verified idempotency or a declared ambiguous-retry policy and budget. |
| Provider 429 | Honor exposed retry timing; apply account/provider/model pool limits. Bounded retry or defer without spinning more workers into the same pool. |
| Forbidden tool/delegation event | Preserve violation and stop configuration. Other isolated lanes can proceed. |
| Local OOM/runtime crash | Stop or reconcile the affected device lane; release its lock only after process/device state is verified. |

Use separate concurrency limits for subscription accounts, OpenRouter provider pools, model endpoints, network and local hardware. A provider can share capacity across models, so per-model counters alone are insufficient. Start conservatively and increase concurrency only from observed successful throughput and rate-limit evidence. Provider failures should not cancel independent successful lanes.

Persist circuit-breaker state, failure reason, cooldown and next eligible probe time. A probe that performs inference is an attempt with a reservation and provenance. Require bounded recovery attempts; no endless retry loop. Locks and bookkeeping contention use short bounded retries that are recorded separately from model attempts.

Serialize local GPU inference and model loads. Route planning checks hosted availability before scheduling local downloads; a missing hosted route is an explicit fact to review, not automatic download authorization. Download jobs have their own disk budget, cancellation receipt, checksum and resumable state. Preserve partial files when canceled unless deletion is separately authorized.

## Money and quota accounting

Keep one atomic budget per authorization scope. The current OpenRouter $5 and TypeSafe $1 are separate lifetime caps for the authorized work, including previous spending. Subscription access is a separate policy with paid overage disabled. No part of this proposal raises those limits.

Before sending, a transaction checks:

```text
known_charges + unresolved_charge_holds + in_flight_reservations
    + proposed_reservation <= authorized_cap
```

These buckets must be disjoint. Use decimal amounts or integer monetary subunits, never binary floats. A worker reservation covers a defensible upper bound using the approved price ceiling, maximum chargeable input/output and any known request fees. If the provider cannot supply a finite defensible bound, hard-cap mode rejects execution or requires a separate explicitly bounded provider-side spend control. Byte counts are not substituted for unknown billable token bounds.

Store authorization ID, price source/date, currency and conversion assumptions where relevant. Price drift, unsupported pricing tiers or actual cost above the reserve stop new dispatches for that budget and remain visible. Reserving conservatively prevents ordinary overspend; no software ledger can guarantee against a provider charging beyond its quoted bound.

Settlement replaces the in-flight reserve once. A timeout or missing usage does not settle to zero. Move the full reserve to an unresolved hold until reconciled; a later observed charge releases only the proven unused amount. A conservative upper-bound accounting event is separate from actual billed cost. Repeated settlement callbacks must be idempotent.

Prefer a shared transaction over permanently dividing the $5 into many tiny lane caps. Optional lane envelopes can prevent starvation, but are allocations, not charges, and unused capacity returns safely. Track subscriptions through observable quota and cooldown fields, without inventing dollar cost. API-equivalent cost can appear only as a separately labeled estimate, never as actual subscription spending.

## Versioning, evaluation and reports

Freeze task, prompt, schema, split, model controls, parser, failure policy and request order before a run. Store exact P0/P1/P2 additions and role placement. Reject accidental drift before dispatch. A user-approved runtime change, such as the accepted Codex CLI patch transition, becomes a signed-off amendment with historical and current controls, scope and comparison limitation. Approval does not prove runtime equivalence.

Attempt selection is explicit and deterministic. Reports show the primary attempt, every permitted retry, final selected prediction and total cost/time. A resumed untouched record does not replace a prior failed record. Retry-success and first-attempt quality can be reported separately. Do not select the best answer after comparing with references.

Keep all authorized records in the headline denominator, with valid, invalid, service-failed and unattempted counts. Report per-label metrics, all-field agreement, concern misses, false escalation, pair consistency and uncertainty grouped by scenario family. Preserve ordinary/challenge split separation and repeat identities when future data is authorized. Calibration and evaluation labels need separate splits; specialist L1/L2 fitting cannot consume its evaluation references.

Paired reports verify same input membership/context boundaries and visible controls, show label transitions, wrong-to-correct and correct-to-wrong cases, and distinguish complete, partial, amended and unmatched comparisons. Historical-baseline reuse and hidden provider rendering remain limitations. A versioned partial report is useful; it must not claim complete experimental control.

Exports should include JSONL predictions, request/attempt tables, CSV/Parquet metrics where useful, a manifest with artifact hashes and standalone HTML. A read-only dashboard shows queue counts, active leases, recent heartbeats, blockers and next action, money buckets, quota availability and estimated remaining work. It must say whether an estimate uses observed throughput or assumptions. Include a machine-readable status command so agents can coordinate without scraping terminal output.

## Proposed operator interface

These commands illustrate the intended interface. They are not implemented and must not be copied as current run instructions.

```bash
bench plan experiments/recruitment-dev.yaml --offline
bench verify PLAN_ID --offline
bench import-legacy results/ --read-only --output imported-catalog.json
bench smoke PLAN_ID --eligible
bench inspect PLAN_ID --smoke --record-decision
bench run PLAN_ID --admitted --resume-untouched
bench status PLAN_ID --json
bench reconcile PLAN_ID --attempt ATTEMPT_ID --evidence recovery.json
bench evaluate PLAN_ID --references references.jsonl --offline
bench report PLAN_ID --snapshot --output report.html
```

The experiment file should declare task, input binding, configuration groups, prompt conditions, batch size, retry policy and authorization references. Adapter capabilities prune unsupported combinations into explicit roster dispositions. Defaults are resolved into the frozen plan so later changes to a library default cannot alter execution. Resume and evaluation are separate commands; neither silently generates missing data or purchases credits.

## Acceptance tests

The implementation is ready for a larger authorized run only after these checks pass:

| Test | Passing result |
| --- | --- |
| Concurrent claims | Many workers race for the same request; only one obtains a valid dispatch permit. Short transaction contention does not create model retries. |
| Shared spending | Parallel workers approach the cap; reservations never exceed it. Duplicate settlements have no effect. Missing usage retains a full hold. |
| Crash boundaries | Kill before dispatch, after possible submission, after durable response, and before settlement. Recovery never blindly repeats a possibly submitted request and restores saved responses. |
| Stale worker | Lease expires and owner changes; old worker cannot dispatch more work or mutate the new owner's state. Ambiguous in-flight inference remains visible. |
| Reference sentinel | Task metadata, reference canaries and prior predictions cannot enter prepared requests or framework provider context. Sandbox evidence matches the stated isolation level. |
| Failure isolation | Inject length, invalid JSON, 429, DNS, 504, forbidden tools and model drift. Only the scope required by the frozen policy pauses; untouched independent work continues. |
| Context and batch identity | Oversized exact-token input is rejected. Opaque counts remain unknown. P1/P2 preserve exact P0 record order and context boundaries. |
| Strict evaluation | Fences and repaired JSON remain invalid in primary scoring. Missing rows remain in denominators. Batch usage is counted once. |
| Import fidelity | Current artifacts remain byte-identical; historical missing data stay null. Rebuilt baseline and paired metrics match existing checked reports exactly. |
| Framework upgrade | A pinned integration fixture detects retry, cache, request or parser changes before the new version is used live. |
| Offline reproducibility | A clean checkout with the exported artifact set reproduces parsing, scoring, audit and HTML without credentials or network. |
| Scale rehearsal | At least 10,000 fake request units exercise claims, restarts, budgets and export with no model calls or new authored questions. Completion and failure counts reconcile exactly. |

Use synthetic transport fixtures for stress tests. They do not enlarge the research dataset. A live acceptance pilot uses a separately approved small subset of the existing 60, with a reserved budget; already completed results are not rerun merely to demonstrate the new dashboard.

## Delivery and migration

1. Inventory and choose: produce the read-only legacy importer and a framework decision record. Run the two-candidate adapter spike with mocked transport, crash injection and exported evidence. Select one execution integration or document why a report-only integration fits better. Exit gate: hard selection gates pass.
2. Durable core: implement contracts, local coordinator, budget transactions, lease/recovery logic and artifact writer. Keep current runners callable as legacy adapters. Exit gate: accounting, crash and concurrency tests pass without inference.
3. Adapter parity: add OpenRouter and one subscription adapter first, then remaining subscription, LM Studio and native specialist adapters. Compare prepared requests and parsed historical outputs against frozen fixtures. Exit gate: request fidelity and offline metric parity for each adapter.
4. Operational pilot: after explicit authorization, run a bounded live smoke in coexistence with the old system. Exercise stop/resume and a deliberately simulated transport failure without retrying completed requests. Exit gate: evidence and billing reconcile, with no protocol drift.
5. Reporting and cutover: publish a stable status view and export, import current immutable evidence, and declare the new coordinator authoritative only for new experiment IDs. Exit gate: clean-checkout reproduction and the fake scale rehearsal pass.

Import current JSONL ledgers, registries, journals, manifests, predictions and raw attempts by hash. Retain source paths and import-tool version. Never rewrite an original record to make it fit a new schema. Missing historical request bytes or runtime fields are explicit import limitations. Keep the original report and a reconciliation file showing metric agreement or explained differences.

During coexistence, exactly one coordinator owns each experiment and budget scope. Do not let a legacy paid process and a new scheduler spend against disconnected copies of the same cap. Cutover occurs after live legacy attempts are terminal and their known and unknown liabilities are reconciled. A rollback stops new dispatch and returns to the previous runner for newly planned work; it does not replay completed requests.

Defer distributed workers, hosted dashboards, automatic prompt search, model-as-judge scoring and provider migration until a concrete experiment needs them. Before the future 340-record generation begins, approve its dataset/review protocol, selected model roster and spending limits separately. The immediate design work can proceed entirely offline.
