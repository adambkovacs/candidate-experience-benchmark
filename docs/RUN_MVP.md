# Reproduce the development MVP

Status snapshot: 2026-09-21. Execution is continuing. This guide covers the existing 60 synthetic development records; the remaining 340 records have not been generated. References are provisional labels reviewed by the same assistant that authored the examples. These runs do not establish held-out performance.

## Recorded status

| Configuration | Development status | Evidence |
| --- | --- | --- |
| Fixed keyword rules v1 | 60 records completed; development-informed baseline | [Rules artifacts](../results/rules-v1-2026-09-21/) |
| Qwen3-0.6B, Q4_K_M, temperature 0 | 60/60 valid outputs; weak semantic results | [Local manifest](../results/qwen3-0.6b-q4_k_m-2026-09-21/manifest.json) |
| Claude Sonnet 5, all five efforts | 60/60 valid per effort; low required one timeout retry | [Claude registry](../results/claude-subscription-2026-09-21/run-registry.json) |
| Claude Opus 5 and Fable 5.1, all five efforts | 60/60 valid per configuration | [Claude registry](../results/claude-subscription-2026-09-21/run-registry.json) |
| Claude Haiku 4.5, effort not applicable | 60/60 valid | [Haiku evaluation](../results/claude-subscription-2026-09-21/haiku45-not_applicable-evaluation.json) |
| Codex gpt-5.6-luna, low effort | Incomplete: 17 valid development outputs after parser reclassification | [Retained outputs](../results/codex-gpt-5.6-luna-low-2026-09-21/development-reclassified.jsonl) |
| Codex gpt-6-astra, low effort | Incomplete: 11 valid development outputs after parser reclassification | [Retained outputs](../results/codex-gpt-6-astra-low-2026-09-21/development-reclassified.jsonl) |
| OpenRouter qwen/qwen3.8-27b:free, modelrun/fp4 | Two smoke attempts received HTTP 429; no successful benchmark response | [Attempt artifacts](../results/openrouter/) |
| Gemini through Antigravity CLI 1.2.7 | Login and supported context/tool isolation pending; no inference | [Preflight](../results/gemini-preflight-2026-09-21/preflight.json) |
| Local razorback16/OpenJev, DiffusionGemma 26B A4B | Model download and dependencies underway; no inference | [Setup audit](../results/openjev/setup-audit.json) |
| Hosted TypeSafe Jev 1.13.0 | API key and user-approved spending cap pending; no inference | [Adapter](../scripts/jev_benchmark.py) |

## Common procedure

Run from the repository root with Python 3.10 or later. The benchmark controllers use the standard library. External CLIs and the OpenJev server have their own dependencies.

```bash
python3 scripts/development_benchmark.py validate
python3 -m unittest discover -s tests -p 'test_*.py'
```

Use a new output filename for every invocation. Run three records, inspect the actual responses and isolation metadata, then start the 60-record run with unchanged settings. The common evaluator deliberately scores smoke or incomplete files against all 60 references, so unattempted records appear as missing:

```bash
python3 scripts/development_benchmark.py evaluate --predictions PATH_TO_PREDICTIONS.jsonl
```

Inference reads feedback, the judgment section of the rubric and output constraints. Reference labels are read only by evaluation. CLI inference starts in a fresh temporary directory. Built-in CLI instructions and structured-output machinery remain part of the measured execution surface. Do not copy this repository, labels or previous outputs into an inference workspace.

## Local LM Studio and rules

The completed local run used LM Studio 0.4.16+2, llama.cpp Apple Metal runtime 2.22.0, an M4 Max with 128 GB memory and an 8,192-token model context. Its pinned artifact hash, GPU settings, template metadata and power conditions are in the manifest.

```bash
python3 scripts/development_benchmark.py run --model recruitment-qwen3-0.6b-q4km --limit 3 --output smoke-local-new.jsonl --config-note 'Record current hardware, runtime, artifact hash, quantization, context and power mode'
python3 scripts/rules_baseline.py --output rules-new.jsonl
```

Load the matching artifact before invoking the local command. Omit `--limit` for all 60 local records. The runner refuses redirects, checks the returned model and requires a normal stop. The recorded Qwen configuration used strict JSON schema, no observed reasoning tokens and temperature 0. All responses finished normally in 41 to 43 tokens. Do not attribute its errors to model size alone: conversion, quantization, template, decoding and task design were not independently controlled. The publisher recommends different non-thinking sampling settings. Local timing was warm and cache-enabled, with Low Power Mode on and other models resident.

## Expanded effort roster

The user expanded the development sweep to every supported effort level. [The live run registry](../results/claude-subscription-2026-09-21/run-registry.json) records all 16 completed configurations in 17 views, keeping Sonnet low first-pass and retry-inclusive results separate. The earlier Sonnet/Opus low runs were reused. Each of the 14 added configurations passed an inspected three-record smoke test and then produced 60 valid development outputs without controller retries.

| Exact Claude model | Supported effort levels |
| --- | --- |
| `claude-sonnet-5` | low, medium, high, xhigh, max |
| `claude-opus-5` | low, medium, high, xhigh, max |
| `claude-fable-5-1` | low, medium, high, xhigh, max |
| `claude-haiku-4-5-20251001` | Not applicable; omit the effort flag |

Official model documentation and the native account picker confirmed the families. Returned primary model identity is checked during smoke. Unsupported effort settings can silently clamp in Claude, so they are not separate experimental configurations. `ultracode` is workflow orchestration rather than another model effort level and is excluded from this tool-free task. At sweep start, native `/usage` showed usage credits off, 14% session use, 83% weekly use and 69% Fable weekly use. These are account-wide snapshots, not attributable benchmark costs.

## Claude Max subscription

Use the supported `claude auth login --claudeai` flow. Verify Claude.ai authentication with `claude auth status`, then verify usage credits are off in `/usage`. The acknowledgement below records that verification; it does not turn credits off.

```bash
python3 scripts/claude_benchmark.py --model claude-sonnet-5 --effort low --limit 3 --output sonnet-smoke-new.jsonl --extra-usage-disabled --config-note 'Current Claude Max and usage-credits-off verification'
```

Choose a model and effort from the roster above. For Haiku use `--effort not_applicable`, which omits the CLI effort flag. Use `--limit 60` after inspecting the smoke output. Claude Code 2.1.274 ran these configurations in safe mode with tools, MCP, skills and session persistence disabled. Do not substitute `--bare`: it disables subscription OAuth. The adapter removes only the unsupported `$schema` draft annotation and retains the judgment constraints, recording both schema hashes.

Sonnet provenance: `sonnet5-development.jsonl` contains DEV-001 through DEV-030, including a 180-second timeout on DEV-030; `sonnet5-development-part2.jsonl` contains DEV-031 through DEV-060. `sonnet5-first-pass.jsonl` combines those first attempts. The separate `sonnet5-dev030-retry1.jsonl` succeeded; `sonnet5-with-retry.jsonl` identifies both attempts. The retry-inclusive timing summary includes the failed timeout. Do not silently replace the first-pass result.

Primary assistant model IDs matched the requested models. Claude also reported auxiliary Haiku usage. Earlier smoke/Sonnet artifacts retain predictions and selected metadata rather than complete wrapper envelopes; later logging preserves safe result and error text. Hosted runs overlapped, with up to 11 record processes active, so end-to-end timing includes shared client contention. Effort is the requested CLI setting; responses do not expose an independently verified applied effort. Initial detached launch attempts left empty controller logs and no prediction artifacts; those logs remain, and no completion is inferred from them. The subsequent managed runs supply the recorded results. The latest observed account-wide quota event reported 85% weekly usage and no overage; quota changes cannot be attributed solely to this benchmark.

## Codex subscription

Verify `codex login status` reports ChatGPT authentication. The controller excludes API credentials, forces ChatGPT sign-in and disables configured tools, project instructions, skills and memory. Observed tool use invalidates a record.

```bash
python3 scripts/codex_benchmark.py --model gpt-5.6-luna --effort low --limit 3 --output luna-smoke-new.jsonl
```

Use `--model gpt-6-astra` for the other configuration and `--limit 60` after smoke inspection. The recorded CLI version is 0.154.0. Returned model revisions are not exposed. Both development runs remain incomplete. Some valid responses were initially classified as errors because of CLI warnings or recovered transport events; reclassified artifacts use retained responses, not new inference. Keep original attempts and parser provenance.

Claude and Codex accept `--offset N` for explicit continuation into a new artifact. It skips N input rows, not N successful rows. Reconcile IDs before continuing; the evaluator rejects duplicate IDs. Keep retries separate and resolve them explicitly for any retry-inclusive report.

## Pending hosted and specialist runs

OpenRouter restricts requests to an explicit `:free` model, verifies zero-priced catalog and provider metadata, disables fallback and sets zero price limits. It checks returned provider/model identity and stops on service errors or unexpected cost. Recheck availability before retrying the recorded endpoint:

```bash
python3 scripts/openrouter_benchmark.py --model qwen/qwen3.8-27b:free --provider modelrun/fp4 --limit 3 --output openrouter-smoke-new.jsonl
```

Provide `OPENROUTER_API_KEY` through the environment or an untracked `--env-file`. Never print or commit credentials. HTTP 429 attempts are service failures, not model judgments. No paid endpoint is authorized by this command.

Gemini's adapter currently refuses inference. Its `preflight --agy PATH_TO_OFFICIAL_CLI` command checks inventory and overage settings; successful login alone does not satisfy the remaining isolation requirement.

Local OpenJev is an independent server, not TypeSafe Jev weights. The selected artifact is `mlx-community/diffusiongemma-26B-A4B-it-4bit`, revision `a7a81407613811e8ba63af92ac0d852b809e191f`, using MLX. After download and server verification, use `jev_benchmark.py --surface openjev --base-url http://localhost:PORT --model openjev-0.1 --mode fixed --limit 3 --output NEW.jsonl --config-note 'Verified server and artifact configuration'`. Fixed mode requests one read. Adaptive mode may reread; the wire API does not expose actual read counts, and reported input tokens exclude adaptive rereads.

Hosted Jev requires `TYPESAFE_API_KEY`, `--surface typesafe`, `--base-url https://api.typesafe.ai`, `--model jev-1.13.0`, `--mode official`, `--authorize-hosted-inference` and an explicitly approved `--max-usd`. Do not run it before obtaining the key and cap. The adapter's reserve is a client stop rule, not a provider-enforced billing limit. Recorded token-price estimates exclude unknown fees or price changes.

## Cost and interpretation

Subscription usage is not API billing. Claude usage credits were verified off and no overage was observed; exact attributable quota and billed charges were not exposed. Codex likewise does not expose an attributable charge for these records. CLI API-equivalent dollar estimates must not be presented as actual subscription charges. Hosted hardware and quantization are undisclosed unless an endpoint documents them. Local energy was not measured.

All reported accuracies use 60-record denominators, including failures and missing predictions. Serious concerns predicted `no`, predicted `insufficient_information` and missing/failed outputs remain separate. Schema validity does not establish correct judgment. Generating the remaining 340 records, paid fallback, quota bypass and label-informed repair are outside this MVP run.

## Official references

- [LM Studio chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
- [Qwen3-0.6B model card and sampling guidance](https://huggingface.co/Qwen/Qwen3-0.6B)
- [Claude programmatic mode](https://code.claude.com/docs/en/headless), [model settings](https://code.claude.com/docs/en/model-config), [subscription authentication and billing](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)
- [Codex authentication](https://learn.chatgpt.com/docs/auth), [noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [OpenRouter provider routing](https://openrouter.ai/docs/features/provider-routing), [API limits](https://openrouter.ai/docs/api-reference/limits)
- [OpenJev pinned source](https://github.com/razorback16/openjev/tree/e04794ab36e4f7e6040c2547baecdb2737ce2e79), [TypeSafe API](https://docs.typesafe.ai/api), [TypeSafe models](https://docs.typesafe.ai/models)
