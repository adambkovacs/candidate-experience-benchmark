# Reproduce the development MVP

Status snapshot: 2026-09-24. Execution is continuing; the linked run registries are the current source for active and completed configurations. This guide covers the existing 60 synthetic development records; the remaining 340 records have not been generated. References are provisional labels reviewed by the same assistant that authored the examples. These runs do not establish held-out performance.

## Recorded status

This checkpoint includes the completed DeepSeek and all four SemIf runs. The linked registries retain every configuration, raw attempt and later status change. A completed 60-record attempt does not imply 60 valid or correct outputs.

| Configuration | Development status | Evidence |
| --- | --- | --- |
| Fixed keyword rules v1 | 60 records completed; development-informed baseline | [Rules artifacts](../results/rules-v1-2026-09-21/) |
| Local Qwen 0.6B HTTP and 0.6B/1.7B/4B/8B SDK on/off | All configurations attempted 60; output validity varies | [Local registry](../results/local-run-registry.json) |
| Local Qwen3.8-27B low; Gemma4 E2B/E4B on/off | Each attempted all 60 records | [Local registry](../results/local-run-registry.json) |
| Claude Sonnet 5, Opus 5, Fable 5.1 and Haiku 4.5 | Supported efforts completed with 60 valid outputs each; historical retries and max runs preserved | [Claude registry](../results/claude-subscription-2026-09-21/run-registry.json) |
| Claude Opus 5.5 low/medium/high/xhigh | All four completed with 60 valid outputs each, in batches of ten | [Claude registry](../results/claude-subscription-2026-09-21/run-registry.json) |
| Codex GPT-5.6 Luna/Sol/Terra and GPT-6 Astra/Sol/Luna | All 24 low/medium/high/xhigh configurations completed with 60 valid outputs each; original single-record and later batch10 workflows remain distinct | [Codex registry](../results/codex-run-registry.json) |
| Hosted Qwen3.6-35B-A3B on/off, AkashML FP8 | Both completed with 60 valid outputs | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Hosted Qwen3.8-27B off/medium/xhigh, DeepInfra BF16 | All attempted 60; off has 60 valid, medium and xhigh have 59 valid each with failures retained | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Hosted Gemma4 26B A4B and 31B on/off | All attempted 60; 26B on retains one invalid output | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Hosted DeepSeek V4.1 Flash off/low/high | All three attempted 60: off has 60 valid, low 57, high 56; every failure is retained | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Hosted Mistral Small 3.2 24B | Venice FP8 completed with 60 valid; earlier DeepInfra FP8 partial run remains separate | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Hosted Mistral Small 4 119B none/high | Smoke requests blocked by provider shared-pool HTTP 429; a bounded cooldown recovery also failed. Await provider recovery | [Paid registry](../results/openrouter-paid-run-registry.json) |
| Free Qwen3.8 route / free DeepSeek slot | Qwen smoke attempts rate-limited; no free DeepSeek route established. Paid configurations are separate, explicitly authorized alternatives | [Specialist registry](../results/specialist-run-registry.json) |
| Gemini through Antigravity CLI 1.2.9 | Pro3.1 low/high each completed60 valid after one batch05 HTTP503 recovery. Each retains seven development attempts across six unique batches. Flash sweep continues; prior Flash3.8-low failures remain separate | [Gemini registry](../results/gemini-run-registry.json) |
| Local OpenJev, DiffusionGemma 26B A4B | All five variants attempted 60; generated off/on retain eight/one invalid outputs. Requested-on uses an empty-thought scaffold, so effective thinking is unverified | [Specialist registry](../results/specialist-run-registry.json) |
| Hosted TypeSafe Jev 1.13.0 | 60 valid outputs under the separate aggregate $1 authorization; transport retry and unknown-cost reserve retained | [Specialist registry](../results/specialist-run-registry.json) |
| SemIf direct/serial/shared and generated BF16 | Three decision modes completed with 60 valid each; generated control has 52 valid of 60. Legacy generated request hashes describe decision intent, not actual generated messages | [Specialist registry](../results/specialist-run-registry.json) |
| Laya English/typed expanded CPU; AlexWortega 0.8B NLI; AnyJev raw/L0 | Completed 60 valid records each; native limits and expanded variants remain distinct | [Specialist registry](../results/specialist-run-registry.json) |
| AnyJev matched generated control | All 60 responses failed strict output validity because of Markdown fences; no repair | [Format audit](../results/anyjev-qwen06-generated-mps-2026-09-23/format-audit.json) |
| Remaining local baselines | Laya multilingual expanded and AlexWortega 4B use the serial local queue; exact DeepSeek R1-Distill-Qwen-32B download is cancelled; its hosted route is unavailable | [Local](../results/local-run-registry.json) and [specialist](../results/specialist-run-registry.json) registries |
| AnyJev L1/L2 | Require separate calibration evidence; no fitting and evaluating on the same 60 labels, and no generation of the remaining 340 | [Specialist registry](../results/specialist-run-registry.json) |

Historical max-effort rows remain evidence; max and ultra are excluded from new runs. Paid non-GPT/Claude OpenRouter requests have explicit approval under the $5 aggregate cap in the [cost review](OPENROUTER_COST_REVIEW.md). Failed or incomplete provider runs remain visible and are not pooled with successful alternate providers. The classifier-framing and SOP experiment has frozen candidate text and offline preview adapters, but no phase-two inference has run; see [execution readiness](PROMPT_EXECUTION_READINESS.md).

## Common procedure

Run from the repository root with Python 3.11 or later. The benchmark controllers use the standard library. External CLIs and the OpenJev server have their own dependencies.

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

## Local reasoning runner controls

The JavaScript SDK runner deliberately freezes a common sampling profile across local artifacts: prompt-format runs use temperature 0.6, top-p 0.95, top-k 20 and min-p disabled; constrained-format runs use temperature 0. Other effective settings are retained in each response's prediction configuration. This is an experimental control, not a claim that these are publisher-recommended settings. [Google recommends](https://huggingface.co/google/gemma-4-E2B-it) temperature 1.0, top-p 0.95 and top-k 64 for Gemma 4. [Qwen3.8 recommends](https://huggingface.co/Qwen/Qwen3.8-27B) different thinking and non-thinking profiles. Comparisons between prompt and constrained formats also change sampling and must not be interpreted as isolated effects of JSON constraints.

Thinking controls are taken from the verified artifact template. Gemma uses thought-channel delimiters; Qwen uses think tags. Qwen3.8 thinking runs require explicit `--effort low`, `medium` or `xhigh`; off-mode runs omit effort. Inspect each smoke response to confirm the final answer is separated from reasoning. The GGUF inspector and runner reject split artifacts because verifying one shard does not establish the identity of every loaded weight file. The inspector uses Python 3.11's `hashlib.file_digest`.

The local SDK runner accepts `--start N` as a one-based input position and `--limit N` as the number of rows. Defaults are start 1 and limit 3. For example, `--start 31 --limit 30` selects records 31 through 60. Out-of-bounds ranges and duplicate input IDs are rejected. Continue into a new exclusive output file; no append or automatic retry occurs. Reconcile IDs and sidecar events across separate files before combining results, and preserve failed or uncertain attempts explicitly.

New SDK runs write `OUTPUT.attempts.jsonl` beside the predictions. Each `started` event is flushed before calling the model, and each `finished` event follows a flushed prediction row. An unmatched start means the outcome is unknown; reconcile it before retrying. `--timeout-seconds` defaults to 600 per record. On timeout the runner calls the [SDK cancellation API](https://lmstudio.ai/docs/typescript/llm-prediction/cancelling-predictions), waits up to five seconds for acknowledgement, saves any partial result and stops the batch. A timeout is never a valid judgment. Cancellation not acknowledged means server completion remains uncertain. Previously completed local outputs and the Qwen3.5-4B process already running when this change was introduced have no sidecar journal; their saved completed responses remain usable, but absence of a saved row cannot prove no request occurred.

## Native DeepSeek and Mistral paths

The SDK runner accepts three explicit families only for the exact converted weight hashes recorded in [roster reconciliation](ROSTER_RECONCILIATION.md). It still verifies the local file hash and loaded model identity. Alternate artifacts require review; a family name alone is insufficient. Runtime support remains pending a three-record smoke test on downloaded, verified weights.

| Family flag | Required controls | Prompt placement and parsing |
| --- | --- | --- |
| `--family deepseek-r1-distill-qwen32b` | `--thinking native`; omit effort | Preserve the native think prefix. Put the unchanged rubric/schema instructions and quoted feedback in one user message, following [DeepSeek's recommendation](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B#usage-recommendations). Parse think tags. No invented off condition. |
| `--family mistral-small3.2` | `--thinking not_applicable`; omit effort | Preserve the instruction template and system/user placement; disable reasoning parsing. No documented thinking toggle. [Model card](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506). |
| `--family mistral-small4` | `--thinking on --effort high` or `--thinking off --effort none` | Require the artifact's model-settings control and THINK delimiters; prepend only the selected effort variable. Preserve system/user placement. [Official template](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603/blob/a11f36bebf709121056b1dbcc943d1c6afbe494d/chat_template.jinja). |

Every result records `artifact_family`, `instruction_role` and the complete request. DeepSeek's role change is specific to that family and is an execution difference in comparisons. Existing Qwen/Gemma invocations omit the family flag and retain their previous request messages, template controls and sampling. Template mismatches fail before inference; do not silently replace a converted template or remove a control to make it pass.

## Expanded effort roster

September 23 update: future Claude efforts exclude max and ultra; completed historical runs remain unchanged. Opus 5.5 is added with low, medium, high and xhigh in a distinct batch-of-10 workflow. See [current Claude procedure](CLAUDE_SUBSCRIPTION.md) and the registry for execution status.

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

Use `--model gpt-6-astra` for the other configuration and `--limit 60` after smoke inspection. The recorded CLI version is 0.154.0. Returned model revisions are not exposed. Luna low and Astra low each have 60 valid outputs. Each reconciled timing view retains four initialization failures alongside the 60 completed requests; see the [Codex registry](../results/codex-run-registry.json). All 24 supported model/effort configurations are now complete with 60 valid outputs each, as reconciled in [the coverage audit](../results/codex-coverage-audit-2026-09-23.json). Earlier single-record runs remain distinct from subsequent batch10 preparations. Some valid responses were initially classified as errors because of CLI warnings or recovered transport events; reclassified artifacts use retained responses, not new inference. Keep original attempts and parser provenance.

Claude and Codex accept `--offset N` for explicit continuation into a new artifact. It skips N input rows, not N successful rows. Reconcile IDs before continuing; the evaluator rejects duplicate IDs. Keep retries separate and resolve them explicitly for any retry-inclusive report.

## Pending hosted and specialist runs

OpenRouter restricts requests to an explicit `:free` model, verifies zero-priced catalog and provider metadata, disables fallback and sets zero price limits. It checks returned provider/model identity and stops on service errors or unexpected cost. Recheck availability before retrying the recorded endpoint:

```bash
python3 scripts/openrouter_benchmark.py --model qwen/qwen3.8-27b:free --provider modelrun/fp4 --limit 3 --output openrouter-smoke-new.jsonl
```

Provide `OPENROUTER_API_KEY` through the environment or an untracked `--env-file`. Never print or commit credentials. HTTP 429 attempts are service failures, not model judgments. No paid endpoint is authorized by this command.

The initial September21 Gemini preflight did not run inference; its [historical audit](../results/gemini-preflight-2026-09-21/agent-workflow-audit.json) predates the user's explicit Antigravity authorization and subsequent native-agent runs. The current [Gemini registry](../results/gemini-run-registry.json) records completed, partial and blocked configurations. Credits stay disabled, each new condition requires an inspected smoke, and every observed external tool call is a failed isolation check. The CLI advertises tools, so these runs do not establish effective tool disablement or bare-model isolation.

Local OpenJev is an independent server, not TypeSafe Jev weights. The selected artifact is `mlx-community/diffusiongemma-26B-A4B-it-4bit`, revision `a7a81407613811e8ba63af92ac0d852b809e191f`, using MLX. After download and server verification, use `jev_benchmark.py --surface openjev --base-url http://localhost:PORT --model openjev-0.1 --mode fixed --limit 3 --output NEW.jsonl --config-note 'Verified server and artifact configuration'`. Fixed mode requests one read. Adaptive mode may reread; the wire API does not expose actual read counts, and reported input tokens exclude adaptive rereads.

Hosted Jev requires `TYPESAFE_API_KEY`, `--surface typesafe`, `--base-url https://api.typesafe.ai`, `--model jev-1.13.0`, `--mode official`, `--authorize-hosted-inference` and an explicitly approved `--max-usd`. The existing run used an authorized key and a $1 aggregate cap covering all TypeSafe configurations and retries. Reuse its artifacts and reconcile consumed cost before any additional run. The adapter's reserve is a client stop rule, not a provider-enforced billing limit. Recorded token-price estimates exclude unknown fees or price changes.

## Hugging Face access

Hugging Face is used to discover public artifacts, inspect model cards and metadata, pin revisions and hashes, and download weights. It is not used for hosted inference in this benchmark. Feedback and reference labels are not sent to Hugging Face. Downloaded weights run in LM Studio or a local specialist runtime; separate hosted runs use their explicitly recorded providers.

## Cost and interpretation

Subscription usage is not API billing. Claude usage credits were verified off and no overage was observed; exact attributable quota and billed charges were not exposed. Codex likewise does not expose an attributable charge for these records. CLI API-equivalent dollar estimates must not be presented as actual subscription charges. Hosted hardware and quantization are undisclosed unless an endpoint documents them. Local energy was not measured.

All reported accuracies use 60-record denominators, including failures and missing predictions. Serious concerns predicted `no`, predicted `insufficient_information` and missing/failed outputs remain separate. Schema validity does not establish correct judgment. Generating the remaining 340 records, unapproved paid fallback, quota bypass and label-informed repair are outside this MVP run. Paid non-GPT/Claude OpenRouter inference has a separately approved aggregate $5 cap; TypeSafe retains its separate $1 cap.

## Official references

- [LM Studio chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
- [Qwen3-0.6B model card and sampling guidance](https://huggingface.co/Qwen/Qwen3-0.6B)
- [Claude programmatic mode](https://code.claude.com/docs/en/headless), [model settings](https://code.claude.com/docs/en/model-config), [subscription authentication and billing](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)
- [Codex authentication](https://learn.chatgpt.com/docs/auth), [noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [OpenRouter provider routing](https://openrouter.ai/docs/features/provider-routing), [API limits](https://openrouter.ai/docs/api-reference/limits)
- [OpenJev pinned source](https://github.com/razorback16/openjev/tree/e04794ab36e4f7e6040c2547baecdb2737ce2e79), [TypeSafe API](https://docs.typesafe.ai/api), [TypeSafe models](https://docs.typesafe.ai/models)

## Later prompt comparison

The user requested a follow-up with classifier framing and a second condition adding an SOP and decision tree. Follow [PROMPT_VARIANTS.md](PROMPT_VARIANTS.md) after the current comparison is finished. Keep these future conditions separate from active baseline runs; no prompt changes are applied retroactively.

## Interrupted local continuation, September 24

Alex4B saved DEV-001 through DEV-045 before interruption. No worker remained alive at resumption. The specialist runner now accepts a zero-based `--offset` with bounded, input-only selection, so DEV-046 through DEV-060 can continue into a new exclusive file without replaying saved outputs. The [interruption record](../results/alex-openjev4b-mps-2026-09-23/interruption-2026-09-24.json) preserves the possibility of an unsaved DEV-046 attempt; total attempt timing remains unknown. The absence of a saved row is not proof that no inference occurred.

Gemini3.8 Flash medium stopped after an attempted external command in its second development batch. The runtime denied that command. Its failed batch and raw event are retained as an isolation violation, with no retry or relaxation of permissions. Native-agent results elsewhere remain labeled with their effective-tool-restriction uncertainty.

## Hosted routing correction, September 24

The DeepSeek R1 Distill Qwen32B download was stopped at the user's direction. Its partial artifacts remain on disk, but the final artifact is unverified and no inference ran. The [cancellation record](../results/deepseek-r1-download-cancelled-2026-09-24.json) records the terminated process and 528 of 592 completed chunk receipts. The [exact endpoint check](../results/openrouter-r1-distill-qwen32-availability-2026-09-23.json) found no serving OpenRouter endpoint; this configuration is blocked, not a reason to resume downloading. Completed hosted DeepSeek V4.1 Flash results are a separate checkpoint.

Gemini3.8 Flash low and high also stopped on denied external command attempts in batch02. Each saved ten valid records before the failure; all three3.8 efforts now have explicit isolation blockers. No command was permitted, no failed batch was repaired, and no permission setting was relaxed. The [Gemini registry](../results/gemini-run-registry.json) links each retained raw attempt.
