# Larger-model roster reconciliation

Checked 2026-09-21 against README.md, PLAN.md, MODEL_RESEARCH.md and their available Git history through `1e8c66f`. This is a proposed execution roster, not completed inference. No weights were downloaded and no inference or paid API calls were made during this review. Keep the existing 60-record scope and three-record smoke gate.

## What was actually planned

| Family | Recorded scope | Reconciliation |
| --- | --- | --- |
| Qwen | Commit `c310feb` explicitly named Qwen3.8-27B as the larger local candidate and separately reserved a hosted Qwen slot. `617d220` added Qwen3-0.6B, Qwen3-1.7B, Qwen3.5-4B and Qwen3-8B. `5377703` records the user's expansion to every listed size. | Qwen3-8B and Qwen3.8-27B remain required wherever their runs are not yet complete. A 35B MoE is a new addition, not a recovered omission. |
| DeepSeek | `c310feb` reserved one pinned hosted model/provider but named no version. The current plan still has that unfilled slot. | A local R1 distill provides an executable family comparison, but does not fulfill a flagship hosted DeepSeek run or identify a previously selected model. |
| Mistral | No Mistral match in the checked README/PLAN/MODEL_RESEARCH history, including case-insensitive Git content searches. | Treat Mistral as an addition from the latest user direction. Do not describe it as an exact model omitted from the original plan. |

The evidence is reproducible with `git show c310feb:docs/PLAN.md` and `git log --all -i -G 'mistral|deepseek|qwen' -p -- README.md docs/PLAN.md docs/MODEL_RESEARCH.md`. Historical optional wording does not cancel the user's later expanded scope. Gemma and specialist candidates remain in the parent execution queue; this document does not replace them.

## Recommended local queue

Finish existing planned runs first. Then add the following in table order, with Mistral Small 4 staged after checking free disk and resident memory. All parameter counts describe model architecture; active MoE parameters do not describe weight storage. File sizes below are decimal GB computed from public Hub metadata, not runtime RAM measurements. None establishes speed or successful loading on the installed runtime.

| Exact upstream model | Total / active parameters | Proposed artifact | Weight size | Supported thinking conditions |
| --- | --- | --- | ---: | --- |
| [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | 27B language model, dense; vision components are additional | [ggml-org Q4_K_M](https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF) | 18.974 GB | off; on with low, medium, xhigh |
| [deepseek-ai/DeepSeek-R1-Distill-Qwen-32B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B) | 32B class, dense; Qwen2.5-derived distill, not R1's 671B MoE | [lmstudio-community Q4_K_M](https://huggingface.co/lmstudio-community/DeepSeek-R1-Distill-Qwen-32B-GGUF) | 19.851 GB | Reasoning-native; no documented off or named effort control |
| [mistralai/Mistral-Small-3.2-24B-Instruct-2506](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) | 24B class, dense | [lmstudio-community Q4_K_M](https://huggingface.co/lmstudio-community/Mistral-Small-3.2-24B-Instruct-2506-GGUF) | 14.334 GB | No documented thinking toggle; effort not applicable |
| [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 35B language model / 3B active; vision components additional | [Unsloth UD-Q4_K_M](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | 22.135 GB | on/off via enable_thinking; no named effort roster established by this card |
| [mistralai/Mistral-Small-4-119B-2603](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | 119B / 6.5B active | [mradermacher Q4_K_M](https://huggingface.co/mradermacher/Mistral-Small-4-119B-2603-GGUF) | 72.159 GB | reasoning_effort none/high |

The first four artifacts are comfortably below 128 GB in weight-file size. Small 4 leaves less room for macOS, KV cache and runtime buffers; a short-context fit test must establish actual residency. Stage downloads and serialize local inference. Do not lower precision or change checkpoints silently if an artifact cannot load.

The quantized repositories are converter publications, not official weight releases by the original model authors. Their own metadata is primary evidence for their files. `UD-Q4_K_M` is a dynamic quantization recipe and must not be reported as numerically identical to ordinary Q4_K_M. The ggml-org Qwen3.8 file is intentionally selected here rather than assuming another publisher's smaller file with a similar quantization name is interchangeable.

## Runtime and adapter requirements

Use LM Studio's llama.cpp Metal backend for these GGUF candidates. Converter repositories expose llama.cpp/LM Studio integration. Mistral Small 4's official card explicitly lists both runtimes. That establishes an available software path, not support proven on the installed Metal 2.22.0 build. Record the actual runtime used and any required update; do not claim a local measurement until smoke succeeds.

Qwen3.8's official template supports `enable_thinking` plus `reasoning_effort` low/medium/xhigh, defaulting to xhigh. The local runner now requires explicit effort for that template. Qwen3.6 uses on/off control. Pin and inspect each converted template before trusting it. [Qwen3.8 template](https://huggingface.co/Qwen/Qwen3.8-27B/blob/main/chat_template.jinja), [Qwen3.6 card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B).

DeepSeek R1 Distill has no equivalent enable_thinking switch. Its publisher recommends a thinking prefix and user-message instructions rather than a system message. The SDK runner now has an explicit artifact-pinned reasoning-native path, with offline tests; runtime support still requires smoke verification. Preserve the same rubric/schema content, log role placement, and disclose that difference. Do not fabricate an off run by deleting a reasoning prefix. [DeepSeek recommendations](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B#usage-recommendations).

The SDK runner now implements artifact-pinned Mistral Small 3.2 effort-not-applicable handling and Small 4 none/high control with `[THINK]` / `[/THINK]` parsing. Focused offline tests pass. Actual runtime and converted-template compatibility still require smoke verification; see [runner controls](RUN_MVP.md#native-deepseek-and-mistral-paths). [Mistral Small 3.2](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506), [Small 4 settings](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603#recommended-settings).

Continue the existing common sampling profile only as a deliberate comparison condition. It is not uniformly publisher-recommended. Keep output/context budgets and timeout accounting explicit; a thinking budget failure remains a failure in the 60-record denominator.

## Exact artifact metadata

Public `https://huggingface.co/api/models/REPOSITORY?blobs=true` responses supplied the following revisions, filenames, byte sizes and expected LFS SHA-256 values. These hashes are expected values from the publisher, not claims of a completed local hash check. Download only the pinned file, then verify bytes and GGUF metadata before inference.

| Repository | Revision | File | Bytes | Expected SHA-256 |
| --- | --- | --- | ---: | --- |
| ggml-org/Qwen3.8-27B-GGUF | `efbb3b1f70a21d97fd4495240648405f7228554f` | `Qwen3.8-27B-Q4_K_M.gguf` | 18973870528 | `c600de0300ae8a0eb3a6c0b8b5561b8b96f16bd2c863c2a66c42de29d391a747` |
| lmstudio-community/DeepSeek-R1-Distill-Qwen-32B-GGUF | `2c8db776f8037c44c2af1fa197699a0d0c6c4b7a` | `DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf` | 19851335552 | `d0f0b016bb20e4e9f4978ef82123240a7f31750f675154e469664b8f292a0f1a` |
| lmstudio-community/Mistral-Small-3.2-24B-Instruct-2506-GGUF | `36798e8b853bcf0ce899aeba9f8a7530ff1991fe` | `Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf` | 14333909728 | `9829cc54f2105c79499b783e81fbb476b610e91ee9373cc68334c267e49f6bbc` |
| unsloth/Qwen3.6-35B-A3B-GGUF | `a483e9e6cbd595906af30beda3187c2663a1118c` | `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` | 22134528992 | `ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61` |
| mradermacher/Mistral-Small-4-119B-2603-GGUF | `232efe1aa36380f84dadc8633b3218bd96bf60c6` | `Mistral-Small-4-119B-2603.Q4_K_M.gguf` | 72158719520 | `c83250ae5b88eb5d0e8702d02b495c6f0c305527dfc9ad915b89f800f49f13b0` |

## Free hosted routes and larger exclusions

The live [OpenRouter catalog](https://openrouter.ai/api/v1/models) returned only `qwen/qwen3.8-27b:free` among `qwen/`, `deepseek/` and `mistralai/` free-suffixed models. Its [endpoint metadata](https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b:free/endpoints) listed ModelRun, tag `modelrun/fp4`, quantization FP4, zero prompt/completion prices, and provider name `qwen/qwen3.8-27b-20260814:free`. This is the already-attempted route, not a newly successful run. Recheck current pricing and availability before a controlled retry; catalog presence does not remove the recorded HTTP 429 blocker. No free DeepSeek or Mistral route was verified. Their paid catalog entries are not authorized fallbacks.

Do not label the proposed R1 distill as the newest DeepSeek. The current [DeepSeek-V4.1-Flash card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) describes 552B backbone plus 196B Engram parameters, with 8B active in prefill and 16B in decode. Even a hypothetical uniform 4-bit representation of 748B parameters is about 374 GB before overhead. This is not a practical ordinary single-Mac candidate here. [V4-Flash](https://api-docs.deepseek.com/news/news260424/) is 284B total/13B active, about 142 GB at idealized four-bit weight storage alone. Aggressive lower-bit/custom offload experiments are separate from this initial supported-4-bit roster.

[Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) is a newer experimental architecture: 125B/6B active plus 51B n-gram embeddings and 4B MTP. A compatible pinned Mac artifact and runtime were not established in this review. Keep it explicitly deferred rather than substituting its active count for its storage footprint. Qwen3.6-35B-A3B offers a smaller, documented MoE candidate without claiming to be the newest Qwen release.
