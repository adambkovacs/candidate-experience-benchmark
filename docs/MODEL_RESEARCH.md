# Model research and candidate roster

Research date: 2026-09-21. No local compatibility or performance tests performed.

## Confirmed setup

ChatGPT Pro, Claude Max, Google AI Pro; LM Studio on M4 MacBook Pro with 128 GB unified memory. Exact chip variant and runtime version remain to be logged.

## Gemma dense versus MoE

Gemma 4 31B is dense. Gemma 4 26B A4B routes each token through a subset of experts: the official card lists 25.2B total and 3.8B active parameters, with eight of 128 experts active plus one shared. Inactive expert weights still require storage/residency; active count is not the memory footprint. Lower active computation suggests faster execution, but runtime and workload decide measured speed. Do not assume a 4B dense model's latency or 31B dense quality.

Recommendation: prioritize 26B A4B as the efficient large local candidate. Treat 31B as an optional comparison if larger-local quality remains an open question. Qwen3.8-27B remains an alternative large dense candidate. A cross-model comparison cannot isolate architecture as the cause of a quality difference.

Sources:
- https://ai.google.dev/gemma/docs/core/model_card_4
- https://ai.google.dev/gemma/docs/core

## User-specified OpenJev: razorback16/openjev

Primary candidate: https://github.com/razorback16/openjev (explicitly identified by the user). Independent Jev-compatible server, not official Jev weights. It uses DiffusionGemma 26B A4B with MLX on Apple Silicon. README documents roughly 16 GB for the 4-bit Mac weights. No local verification yet.

Add to priority screening. Log defaults and adaptive re-reads; compare a fixed single-read configuration with the default policy separately. Optional thinking must be explicitly labeled and timed. Test its generated-label endpoint against direct decisions using the same weights, precision, and backend. This is an inference-method comparison; DiffusionGemma text generation is diffusion-based, not ordinary autoregressive decoding.

The documentation says its chat endpoint treats requested JSON schemas as instructions rather than hard schema constraints. Validate results and count failures. Question chunking/sequential options can affect independence; freeze question order and settings, then test perturbations separately. Verify wire/SDK compatibility rather than assuming identical semantics.

Source: https://github.com/razorback16/openjev/blob/main/README.md

## Other projects with similar names

SemIf (formerly TheoLeeCJ/openjev) is independent of TypeSafe and reads declared-option logits from frozen open models. It is not Jev's released weights or training. It documents an Apple Silicon MLX backend. Candidate: frozen Qwen3.5-4B direct scoring, paired with generated structured labels from the same base revision and precision where feasible. Different runtimes must be disclosed.

AlexWortega/openjev is a separate NLI classifier project with trained Qwen3.5-based checkpoints. Its model card lists 0.8B and 4B versions, predicting contradiction/entailment/neutral. Test the 0.8B checkpoint first as a compact specialist. This requires a custom classifier adapter; neutral is not automatically our task's insufficient-information label. No assumption of LM Studio compatibility.

Sources:
- https://github.com/TheoLeeCJ/SemIf
- https://huggingface.co/AlexWortega/openjev

## Laya

The identified project is NandhaKishorM/laya / convaiinnovations/laya. The English and typed-decision checkpoints are listed as 421M parameters; the multilingual checkpoint as 322M. Its documentation describes narrow token budgets and weak base zero-shot performance on its typed-decisions benchmark. Its Jev comparisons use external published figures rather than identical live runs.

Include one pinned English typed-decisions checkpoint as a research candidate, with no recruitment fine-tuning in the primary comparison. Report token-budget failures or truncation explicitly. Test CPU/Apple backend support separately; published NVIDIA timings are not Mac timings. The user's March 2025 date was not verified, and this may not be the exact referenced project.

Sources:
- https://github.com/NandhaKishorM/laya
- https://huggingface.co/convaiinnovations/laya

## Small models

Useful candidates:
- Qwen3-0.6B: sub-billion generative baseline.
- Qwen3-1.7B: optional intermediate size.
- Qwen3.5-4B: compact generative model and matched SemIf baseline.
- Qwen3-8B: optional intermediate if 4B is inadequate and larger models are slower.
- Gemma 4 E2B/E4B: alternatives; effective parameter naming does not equal full stored parameter count.

Do not add every size to the final benchmark. Prioritize a tiny generator, a compact generator, a compact specialist, and a larger local model. Same-family scaling claims need an actual same-family ladder; unrelated models/sizes do not establish a clean scaling law.

Sources:
- https://huggingface.co/Qwen/Qwen3-0.6B
- https://huggingface.co/Qwen/Qwen3-1.7B
- https://huggingface.co/Qwen/Qwen3-8B
- https://ai.google.dev/gemma/docs/core

## Gemini

Include Gemini alongside OpenAI and Anthropic, targeting a Pro-class and a Flash-class configuration if both are exposed and pinnable. Google AI Pro is confirmed by the user; actual model access and subscription-backed noninteractive behavior require a local check.

Google's Gemini CLI documentation describes Google AI Pro sign-in; Antigravity's official plans also document Google AI Pro and CLI access. Choose the currently functioning, supported client for this account and record it. Do not equate subscription access with paid Gemini API credits. Fail or separately label automatic fallback: never aggregate Flash responses into a Pro result.

Sources:
- https://geminicli.com/docs/get-started/authentication/
- https://antigravity.google/docs/plans

## Execution strategy

Candidate reconnaissance is not a commitment to a full run for every candidate. Screen candidates on the same 30 development records, recording setup time, errors, memory, speed, and rough quality. Select and freeze the final roster before either held-out set, retaining provider diversity and meaningful failure baselines. Publish all screening outcomes and exclusion reasons.

Suggested priority additions: Gemini, razorback16/OpenJev with MLX, Laya 421M, and Qwen3-0.6B. AlexWortega/OpenJev 0.8B, SemIf/Qwen3.5-4B, 1.7B, 8B, and a second large Gemma are optional diagnostics. They are distinct projects, not interchangeable OpenJev implementations.

LM Studio remains the default for supported generative models. Specialized classification/logit readers use separate supported local runners when required. Do not substitute ordinary chat completions while claiming to evaluate their specialized mechanism.

Long inputs: preserve the original evidence for every system, count unsupported length as a coverage failure, and report any shortened/chunked workflow separately. Do not silently truncate all inputs to suit the shortest-context model.
