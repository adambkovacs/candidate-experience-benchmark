# 04 Harness: classification-bench

Refreshed 2026-10-08 against `/Users/adamkovacs/Documents/codebuild/classification-bench`, commit `a1e9879` (HEAD, main). The first version of this note was written against `d53ea74`; five commits landed since. Read-only. Every claim below is either something I ran, or a status the repo's own docs state. Nothing here is marked live that the docs mark pending.

Caveat on the checkout: the working tree has uncommitted edits (`README.md`, `cli.py`, `report.py`, `report_findings.py`, three docs and two test files). That is another session's in-progress work. I ran everything from a clean `git archive` of `a1e9879`, not from the dirty tree, and deleted the copy afterwards.

## 1. Pitch

classification-bench is a local-first Python tool for running your own categorical classification task across several models and prompts, then measuring how often they agree with your reference labels and how often their answers change between repeats. You supply the inputs, the decision fields, the allowed labels, the rubric and optional reference labels. It is for people who need to compare models on their own judgment call before trusting one. It generalizes the candidate-experience benchmark, where four decisions about candidate-written reviews exposed the same needs every time: strict output validation, visible missing answers, versioned references, exact request identities, cost accounting, and repeat measurements. Those were rebuilt once as a reusable runner instead of one-off scripts per model. It is not a hiring tool, and a score does not show a model is fit for autonomous hiring decisions.

## 2. What works today (I ran these)

Environment: Python 3.14.6, macOS, standard library only, no API key, no network.

| Command | Real output |
|---|---|
| `python3 -m classification_bench --help` | 18 subcommands: init, import, validate, plan, evaluate, **sensitivity** (new), simulate, simulate-recover, simulate-export, preflight, preview, run, status, recover, export, report, catalog, budget-increase |
| README offline example: `plan` then `evaluate` on `examples/` | Same result as before: 6 requests; 9 planned positions, 0 missing, 1 invalid (`toy-b`, pass 3). Exact-match per pass: 3/3, 2/3, 2/3. Mean 0.778, range 0.667 to 1.0. Flip rate pass 1 vs 2: 1/3 (case `toy-b`). Passes 1 vs 3 and 2 vs 3: 2 comparable, 1 excluded (`toy-b`), rate 0. The same output now carries per-label precision, recall, F1, support, TP/FP/FN and a confusion table for every field and pass. |
| `python3 -m scripts.offline_demo --task product` | Exit 0, `live_model_calls: 0`, wrote `report.html`. I did not recount the request and status split at this commit. At `d53ea74` it was 24 requests, 12 valid and 12 invalid. |
| Same, `--task candidate` | Exit 0, `live_model_calls: 0`, wrote `report.html`. Same caveat on the counts. |
| `python3 -m unittest discover -s tests` | **433 tests, OK, 44 skipped** (32 s). All 44 skips are report DOM tests that need `jsdom`, which is not installed here (skip reasons read "jsdom unavailable"). IMPLEMENTATION_STATUS says "430 tests pass, no skips" at the last full record, so "no skips" holds only with jsdom present. The test count grew from 272 at `d53ea74`. |

The README's own caveat stands: the synthetic example tests the software, not model quality or nondeterminism. The "returns 1, 2/3, 2/3" line is a test of the analysis pipeline. No LLM ran.

Also verified from docs (not re-run by me): a custom support-routing task run offline produced 16 requests, 24 positions, 12 deliberate invalid outcomes, 0 missing.

## 3. Status by capability

### Live-verified, scoped and historical

| Capability | Exact status |
|---|---|
| OpenRouter, one route | Authorized smoke on 2026-09-28: `openai/gpt-4.1-nano` via the `openai` provider. 3 of 3 requests valid, 3 of 3 matched the fictional labels, $0.000174 rounded charge. Delayed generation metadata later confirmed the model identity. An earlier smoke had 2 HTTP 200 responses that both failed strict validation. Three fictional records say nothing about model quality. |
| Cloudflare Clef and Clef-Flash (native decision models) | 42 of 42 requests returned valid typed choices across smoke and full scopes. Exact dollar charges are unavailable. USD 0.454188 stays as a held reserve, not an invoice. Returned model name is an echo, not independent identity proof. |

### Works today, offline (new since `d53ea74`; passes in the 433-test run above)

These need no model and no network. Evidence is the named test, which passed in my run, plus the repo doc line. The parity matrix labels each "implementation/offline coverage exists" and keeps rendered acceptance open (see Not built yet).

| Capability (parity ID) | Evidence |
|---|---|
| **Per-label metrics (R8):** per-field and all-field agreement, support, TP/FP/FN, precision, recall, F1 and full confusion, with undefined ratios shown as unavailable, not zero | `tests/test_report_metrics.py`: `test_imbalanced_counts_precision_recall_f1_and_full_denominator`, `test_complete_confusion_rows_reconcile_support_including_unusable`, `test_zero_prediction_precision_and_zero_reference_recall_are_unavailable`. I also saw the figures in the `evaluate` output above. FEATURE_PARITY R8. |
| **Agree-or-defer rule (R13):** accept a case when two runs give identical answers on every field, defer otherwise. Accepted cases are split into correct, error and reference-unknown. Equal invalid outputs always defer. Every eligible run pair is enumerated, with case IDs. | `tests/test_report_analysis.py`: `test_all_unordered_eligible_pairs_use_full_denominator`, `test_equal_invalid_outputs_are_always_deferred`. FEATURE_PARITY R13 and R14 (pair drilldown, cost and source disclosure). Retrospective only: no claim about deployment or human-review savings. |
| **Reference sensitivity (R15):** re-score saved predictions against explicitly declared alternative references. Scores are marked hypothetical, saved references never change, and a missing reference cannot be filled in. | `sensitivity` subcommand. `tests/test_report_sensitivity.py`: `test_hand_calculated_single_alternative_gains_and_losses`, `test_scenarios_are_independent_and_combined_deltas_match_manual_counts`, `test_null_omitted_and_absent_reference_fields_cannot_be_filled`. `docs/REFERENCE_SENSITIVITY.md`. |
| **Unlabeled and partial-reference runs:** inputs without labels are classified and compared, with no accuracy invented. Partial references need an explicit opt-in. | `tests/test_unlabeled_evaluation.py`: `test_unlabeled_predictions_keep_full_denominator_and_have_no_accuracy`, `test_partial_references_require_explicit_boolean_opt_in`. IMPLEMENTATION_STATUS "Optional references" section. |
| **Report analysis:** paired prompt gains and losses with exact case IDs, repeat ranges and flips, declared cohorts, shareable local URL state for runs, cases and A/B picks, an 11-slide presentation mode, and allowlisted downloads (pseudonymous or private) with byte hashes | `tests/test_report_analysis.py`: `test_paired_prompt_gains_losses_and_validity_turnover_keep_exact_ids`, `test_cohort_denominators_distinguish_runs_configs_and_unusable_cases`. `tests/test_report_explorer.py`: `test_ab_url_reload_reset_and_independent_query_parameters`. `docs/PRESENTATION.md`, `docs/REPORT_EXPORTS.md`. |

### Wired and tested offline only, not live-verified

| Capability | Exact status |
|---|---|
| OpenRouter "any model" | Not a model allowlist: you give an exact model slug and provider tag, and the `catalog` command fetches the live endpoint snapshot (pricing, limits, supported parameters). The adapter rejects unsupported controls (effort, seed, tools, response repair) rather than guessing. Only the one route above has live evidence. So "any model that passes the catalog check", not "any model works". Reasoning-effort control is not supported by the adapter today. |
| Claude Code and Codex subscription adapters | Registered, with offline matrix, parser, isolation and request-count budget tests. Read-only preflight succeeded on this host on 8 Oct (Codex 0.156.1 with ChatGPT auth, Claude Code 2.1.293 with Claude.ai auth). **No model inference has been sent. Live acceptance is pending.** "Extra usage disabled" is an operator-declared assertion, not a provider billing query, and expires after 24 hours. macOS only, native executable only. Cost is counted in requests, never dollars. |
| Liquid d1, Solar Decide, Qwen decision-model-preview | Adapters and provider contracts exist, with offline tests. **No live provider call has been made.** Billing evidence and authorization are still pending. |
| Budgets and caps | Implemented and tested: atomic reserve-before-dispatch, settle-once, unresolved holds, smoke and full caps, `pause` or `stop` at exhaustion, audited cap increases. Exercised live on the OpenRouter and Clef scopes above. Limit: one accounting unit per run scope, so dollar-backed and request-backed routes cannot share one scope. |
| Task import (`init`, `import`, `validate`) | Implemented for JSON, JSONL and CSV with frozen source bytes and separated references. Offline evidence: two unrelated imported tasks ran end to end synthetically. |
| Report explorer | Implemented: model-group and adapter rails, one shared filter state across all views, case search, two-condition comparison, controlled configuration comparisons, agreement-vs-duration plot, hidden-case reveal. **The latest report has not had its rendered visual and keyboard acceptance.** Tests are DOM and source checks only. |

### Not built yet or still pending

- **OpenAI Decisions API:** announced, limited preview, no verified public endpoint or schema. Explicitly unsupported. Codex support does not substitute for it.
- **Rendered acceptance of the report and presentation (R19):** the new report features above are code and tests only. Nobody has opened the latest report in a browser to check layout, narrow widths, focus, reduced motion, print or evidence links. The docs mark this pending and record a browser-tool rejection of local files. A feature that works in a DOM test is not a feature that looks right.
- **Live acceptance of the goal's routes:** Claude Code and Codex inference, Liquid, Solar and Qwen, and actual extra-usage-off verification. IMPLEMENTATION_STATUS still lists operator and live route acceptance as required, and its newest entries record no additional provider calls.
- **No adapter for Jev or other specialist direct interfaces.** FEATURE_PARITY lists them as needing new access, protocol and billing contracts. Nothing in the package supports them.
- **Not in the core at all:** multi-label sets, numeric scores, rankings, multimodal inputs, free-text rationale scoring. The docs say these need separate contracts.
- **Not included:** public release, deployment, migration of the source benchmark into this tool. The goal doc (commit `a1e9879`) records that Adam intends to open-source the finished tool. It sets a public-release milestone after the acceptance gates pass, names Apache-2.0 as the provisional license with MIT as the alternative, and says the license is not settled. It also requires a redistribution-rights check and a scan of files and Git history for credentials, private data and raw responses first. The repo stays private until then.

## 4. Bring your own use case

You supply up to three data files plus a prompt, then plan, run and read the report.

**`task.json`: names, inputs and vocabulary.** There is no rubric field in this file. The rubric is prompt text (or separate rubric and SOP files when you use `import`).

```json
{
  "name": "fictional-product-fit",
  "input_keys": ["description", "audience"],
  "fields": [
    {"name": "segment", "labels": ["teams", "solo"]},
    {"name": "urgency", "labels": ["now", "later"]}
  ]
}
```

Each field needs at least two distinct string labels. Include your own "unknown" label if the task needs abstention. An invalid model answer is a separate state, not that label. Input values must be strings.

**`inputs.json`: records with stable IDs.** Input keys must exactly match `input_keys`. A stray `labels` key is rejected.

```json
{"records": [
  {"id": "toy-a", "input": {"description": "A shared planning board", "audience": "Small creative studio"}},
  {"id": "toy-b", "input": {"description": "A personal idea notebook", "audience": "Independent hobbyist"}}
]}
```

**`labels.json`: optional reference answers, kept separate.** They never enter planning or the inference capsule. Only offline `evaluate` and `report` open them. A correction means a new file and a new evaluation, not an overwrite.

```json
{"records": [
  {"id": "toy-a", "labels": {"segment": "teams", "urgency": "now"}},
  {"id": "toy-b", "labels": {"segment": "solo", "urgency": "later"}}
]}
```

**`experiment.json`: the matrix.** Configs times prompts times repeats, with fixed batch size. The rubric lives in `prompts[].text`.

```json
{
  "configs": [{"id": "synthetic-replay", "model": "fixture-only", "settings": {"reasoning": "low"}}],
  "prompts": [{"id": "baseline", "text": "Classify the fictional product description."}],
  "repeats": 3,
  "batch_size": 2
}
```

For a live OpenRouter config, `settings` carries `adapter: "openrouter"`, the provider tag, token limits and a `catalog`-generated `endpoint_snapshot`. For Claude Code or Codex, `adapter` is `claude_code` or `codex`, plus exact model ID, CLI path and version, effort, and the extra-usage declaration. Optional `model_type` (`llm`, `fine_tuned_llm`, `decision`) groups the report.

**Flow.**

1. **Bring data.** Either write the files above, or run `init`, `import`, `validate` on JSON, JSONL or CSV. Import freezes the exact source bytes and rubric, SOP and prompt files, and keeps references separate.
2. **Plan.** `plan` (or `preview` for a run) expands the matrix into requests. Each request ID is a SHA-256 of the full task, config, prompt and membership, so any change gives a new ID. The preview shows exact request identities and spending bounds before anything is sent.
3. **Execute.** `run` against a run config. OpenRouter and native routes need an explicit run-bound authorization file and a cap. Subscription routes need preflight and a request cap. Ambiguous dispatches are never resent. `status` and `recover` show and reconcile state. `simulate` runs the whole thing offline with a synthetic transport.
4. **Evaluate.** `export` writes label-free predictions. `evaluate` scores them against the references offline.
5. **Report.** `report` writes one private, self-contained local HTML file (mode 0600). It contains your inputs and reference labels, so it is not for publishing as is.

**What the report shows.** Exact agreement over the full planned denominator, per-field and all-field. Missing and invalid counts. Per-label precision, recall and F1 with support, macro-F1 over every declared label, confusion counts. Mean and range across repeat passes. Flip rates between repeat pairs, with the changed and excluded IDs. Paired prompt effects. Token counts, client request duration, and cost where the provider reports one. Cost comes with coverage, and unknown charges stay as holds rather than becoming zero. Three passes over three inputs is a diagnostic, not nine independent cases.

## 5. Lessons from the candidate-experience benchmark, and where each lives

| Lesson | Where it lives |
|---|---|
| Strict output validation | `classification_bench/core.py` `_validated_predictions`: extra fields, missing fields and unknown labels are invalid outcomes. Rules in `docs/FORMATS.md`. Provider adapters reject malformed JSON without repair or retry (`docs/OPENROUTER.md`). |
| Visible missing answers | `core.py` `evaluate`: missing and invalid predictions keep their slot in the scheduled denominator. Per-label recall counts them as misses. Flip rates exclude them by ID and print null, not zero, when nothing is comparable (README "Reading the metrics"). |
| Versioned references | Reference file is separate and digest-bound (`FORMATS.md`, `core.py` `validate_reference_labels`). Corrections create a new imported directory and evaluation (`docs/TASK_SETUP.md`). |
| Request identities | `core.py` `build_plan`: `request_id` is a SHA-256 of canonical JSON over task, config, prompt, repeat and membership. `docs/EVIDENCE_CONTRACTS.md` adds byte-level hashes for raw request and response artifacts. |
| Cost accounting | `classification_bench/budget.py` `reserve` and `settle` (atomic SQLite ledger, `docs/BUDGET_API.md`). Observed charge, estimate, unknown hold and request count are separate fields in the report (`report.py`). |
| Repeat passes | Matrix expansion in `core.py` and `benchmark.py`. Pass means, ranges and flip rates in `core.py` `evaluate`. Recovery and replay never count as fresh repeats (README). |
| Raw evidence before parsing, no automatic resend | `evidence.py`, `verified_execution.py`, `coordinator.py` `claim` and `reconcile`. See `docs/VERIFIED_EXECUTION.md`, `docs/BENCHMARK_LESSONS.md`. |

## 6. Repo visibility

`AI-Enablement-Academy/classification-bench` is **private** (re-confirmed with `gh repo view` on 2026-10-08: `visibility: PRIVATE`). AGENTS.md forbids making it public without explicit authorization. The slide should not show its URL as a clickable link.

Suggested slide badge: "being open-sourced". Adam has said the harness will be open-sourced. The repo is not public yet, no release date is set, and the license is undecided, so do not say "released", "open source" or name a license.

The source case study is public and can carry a URL: `https://github.com/adambkovacs/candidate-experience-benchmark`. The harness is a generalization of that repo, per `docs/PROVENANCE.md`.

## 7. Slide and script

### Slide (5 bullets)

- **classification-bench:** a local tool to compare models on your own categorical decisions, with your own labels.
- **Built from this benchmark's lessons:** strict validation, missing answers stay visible, versioned references, request identities, cost holds, repeat passes.
- **Working today:** offline end to end (433 tests), including per-label scores, agree-or-defer and reference sensitivity. OpenRouter and Cloudflare Clef on small live smokes.
- **Wired, not yet run live:** Claude Code and Codex subscriptions, Liquid, Solar and Qwen. OpenAI Decisions waits on a public API.
- **Being open-sourced.** Not public yet. Report visual checks and live Claude Code and Codex runs are still pending.

### 60-second spoken version (first person, about 150 words)

"This benchmark taught me what a harness has to do. Count missing answers. Reject answers that break the format. Keep your reference labels away from the model. Know exactly which request you sent. Know what it cost. Run it more than once.

So I pulled those lessons out of this one dataset and built a tool. It's called classification-bench. You bring your own inputs, your own decision fields, your own labels and your own rubric. It runs the models and prompts you pick, and reports agreement, per-label scores, and how often an answer flips between repeats.

Here's where it honestly stands. The whole pipeline runs offline, with more than 400 tests. It has made small, real calls through OpenRouter and Cloudflare's Clef. The Claude Code and Codex routes are built, but I haven't sent them a real request yet. It isn't public yet, but it's being open-sourced. When it is, I'll say so."

Word count is about 153, which reads in about 60 seconds at a normal pace.

## Sources checked

README.md, AGENTS.md, docs/RUNNER.md, REFERENCE_SENSITIVITY.md, FINDINGS_ANALYSIS.md, PRESENTATION.md, REPORT_EXPORTS.md, CONTROLLED_COMPARISONS.md, the commit range `d53ea74..a1e9879`, the test files named in section 3, FORMATS.md, TASK_SETUP.md, SUBSCRIPTION_RUNNER.md, OPENROUTER.md, NATIVE_DECISIONS.md, OPENAI_DECISIONS_STATUS.md, IMPLEMENTATION_STATUS.md, FEATURE_PARITY.md, REPORT_EXPLORER.md, BENCHMARK_LESSONS.md, PROVENANCE.md, HANDOFF.md, NEXT_TASK_GOAL.md, CLEF_LIVE_ACCEPTANCE_20261002.md, LIVE_IDENTITY_SMOKE_RESULT.md, CUSTOM_TASK_WALKTHROUGH.md, EVIDENCE_CONTRACTS.md, and `examples/` (root, `candidate/`, `product/`).
