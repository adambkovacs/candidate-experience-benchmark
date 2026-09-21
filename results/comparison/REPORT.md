# Development benchmark: observed configurations

All judgments are compared against provisional, same-assistant AI-reviewed labels on the same 60 synthetic development records. These are not human ground truth or held-out results. The remaining 340 records are ungenerated.

Each cell below is a count out of 60. Missing or failed outputs count as incorrect; partial configurations must not be ranked against complete ones. Retry-inclusive rows are separate views of the same configuration, not independent experiments.

| Configuration | Status | Valid | Sentiment | Follow-up | Serious concern | Testimonial | All four |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-0.6b-q4km-nonthinking | complete | 60 | 37 | 54 | 13 | 9 | 0 |
| rules-v1 | complete | 60 | 22 | 25 | 35 | 41 | 10 |
| qwen3-0.6b-sdk-thinking-on | complete | 31 | 16 | 25 | 14 | 7 | 0 |
| qwen3-0.6b-sdk-thinking-off | complete | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen3-1.7b-sdk-thinking-on | complete | 60 | 49 | 56 | 45 | 35 | 23 |
| qwen3-1.7b-sdk-thinking-off | complete | 60 | 51 | 55 | 44 | 43 | 28 |
| qwen3.5-4b-sdk-thinking-on | complete | 52 | 51 | 52 | 50 | 52 | 49 |
| qwen3.5-4b-sdk-thinking-off | complete | 60 | 48 | 58 | 51 | 57 | 41 |
| qwen3-8b-sdk-thinking-on | complete | 60 | 51 | 59 | 55 | 55 | 47 |
| qwen3-8b-sdk-thinking-off | complete | 60 | 48 | 58 | 51 | 57 | 41 |
| qwen3.8-27b-sdk-thinking-low | blocked_model_download_network | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-medium | blocked_model_download_network | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-xhigh | blocked_model_download_network | — | — | — | — | — | — |
| gemma4-e2b-sdk-thinking-on | pending | — | — | — | — | — | — |
| gemma4-e2b-sdk-thinking-off | pending | — | — | — | — | — | — |
| gemma4-e4b-sdk-thinking-on | blocked_model_download_network | — | — | — | — | — | — |
| gemma4-e4b-sdk-thinking-off | blocked_model_download_network | — | — | — | — | — | — |
| gemma4-26b-a4b-sdk-thinking-on | pending | — | — | — | — | — | — |
| gemma4-26b-a4b-sdk-thinking-off | pending | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-on | pending | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-off | pending | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-off | blocked_model_download_network | — | — | — | — | — | — |
| qwen36-35b-a3b-on | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| qwen36-35b-a3b-off | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| deepseek-r1-distill-qwen32b-native-reasoning | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| mistral-small32-24b-not-applicable | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| mistral-small4-119b-none | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| mistral-small4-119b-high | staged_capacity_and_runtime_unverified | — | — | — | — | — | — |
| sonnet5-low-first-pass | completed_with_service_failure | 59 | 59 | 58 | 58 | 56 | 54 |
| sonnet5-low-with-retry | completed | 60 | 59 | 59 | 59 | 57 | 54 |
| opus5-low | completed | 60 | 59 | 60 | 59 | 57 | 55 |
| haiku45-not_applicable | completed | 60 | 56 | 60 | 58 | 59 | 53 |
| sonnet5-medium | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| sonnet5-high | completed | 60 | 59 | 60 | 58 | 60 | 57 |
| sonnet5-xhigh | completed | 60 | 58 | 60 | 59 | 60 | 57 |
| sonnet5-max | completed | 60 | 59 | 60 | 60 | 60 | 59 |
| opus5-medium | completed | 60 | 58 | 60 | 59 | 60 | 57 |
| opus5-high | completed | 60 | 59 | 60 | 59 | 60 | 58 |
| opus5-xhigh | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| opus5-max | completed | 60 | 59 | 60 | 60 | 59 | 58 |
| fable51-low | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| fable51-medium | completed | 60 | 59 | 59 | 59 | 59 | 57 |
| fable51-high | completed | 60 | 59 | 60 | 59 | 59 | 57 |
| fable51-xhigh | completed | 60 | 59 | 60 | 59 | 60 | 58 |
| fable51-max | completed | 60 | 59 | 60 | 59 | 60 | 58 |
| typesafe-jev113-v2 | complete | 60 | 56 | 58 | 57 | 58 | 54 |
| openjev-fixed | blocked_model_download_network | — | — | — | — | — | — |
| openjev-adaptive | blocked_model_download_network | — | — | — | — | — | — |
| openjev-thinking | blocked_model_download_network | — | — | — | — | — | — |
| openjev-generated-off | blocked_model_download_network | — | — | — | — | — | — |
| openjev-generated-on | blocked_model_download_network | — | — | — | — | — | — |
| semif-direct | blocked_model_download_network | — | — | — | — | — | — |
| semif-serial | blocked_model_download_network | — | — | — | — | — | — |
| semif-shared | blocked_model_download_network | — | — | — | — | — | — |
| alex-openjev08 | blocked_model_download_network | — | — | — | — | — | — |
| laya-english | unsupported_length | — | — | — | — | — | — |
| laya-typed | unsupported_length | — | — | — | — | — | — |
| salesrlagent | task_incompatible | — | — | — | — | — | — |
| openrouter-qwen38-free | blocked_provider_429 | — | — | — | — | — | — |
| openrouter-deepseek-free | unavailable_no_free_model | — | — | — | — | — | — |
| laya-english-expanded-cpu | blocked_model_download_network | — | — | — | — | — | — |
| laya-typed-expanded-cpu | blocked_model_download_network | — | — | — | — | — | — |
| semif-generated-bf16 | blocked_model_download_network | — | — | — | — | — | — |
| laya-multilingual | blocked_model_download_network | — | — | — | — | — | — |
| laya-multilingual-expanded-cpu | blocked_model_download_network | — | — | — | — | — | — |
| codex-gpt-5.6-luna-low | continuation_running | — | — | — | — | — | — |
| codex-gpt-5.6-luna-medium | pending | — | — | — | — | — | — |
| codex-gpt-5.6-luna-high | pending | — | — | — | — | — | — |
| codex-gpt-5.6-luna-xhigh | pending | — | — | — | — | — | — |
| codex-gpt-5.6-luna-max | pending | — | — | — | — | — | — |
| codex-gpt-6-astra-low | continuation_running | — | — | — | — | — | — |
| codex-gpt-6-astra-medium | pending | — | — | — | — | — | — |
| codex-gpt-6-astra-high | pending | — | — | — | — | — | — |
| codex-gpt-6-astra-xhigh | pending | — | — | — | — | — | — |
| codex-gpt-6-astra-max | pending | — | — | — | — | — | — |
| codex-gpt-6-astra-ultra | pending | — | — | — | — | — | — |
| codex-gpt-5.6-sol-low | smoke_complete_development_held | — | — | — | — | — | — |
| codex-gpt-5.6-sol-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-max | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-ultra | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-low | smoke_complete_development_held | — | — | — | — | — | — |
| codex-gpt-5.6-terra-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-max | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-ultra | pending_batching_decision | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-high | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-medium | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-low | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-high | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-medium | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-low | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-high | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-medium | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-low | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.1-pro-high | pending_approval_and_isolation | — | — | — | — | — | — |
| antigravity-gemini-3.1-pro-low | pending_approval_and_isolation | — | — | — | — | — | — |

Timing includes process/runtime and transport overhead as applicable. Cached prompts, local power mode, and CLI wrappers differ. Do not interpret a cross-surface latency ranking as model-only speed.

**qwen3-0.6b-q4km-nonthinking**

LM Studio0.4.16+2 / llama.cpp2.22.0 Metal, Q4_K_M on M4Max128GB. Temperature0, 512outputtokens, context8192. Shared machine, low power on, warm cache. See local manifest for exact artifact and request audit.

Evidence: `results/qwen3-0.6b-q4_k_m-2026-09-21/development.jsonl`; SHA-256 `557e5f3759f5fede68e16a6c22c3df230a2283d05d2844c560cf1efa3824c7e9`.

**rules-v1**

Deterministic rubric-derived baseline; no model inference. Author had seen development labels; not blinded. No tuning after this run.

Evidence: `results/rules-v1-2026-09-21/development.jsonl`; SHA-256 `76e4d032ae199f79352663715d4707923d7f37c961caf429002bdf46c84bb50b`.

**qwen3-0.6b-sdk-thinking-on**

LM Studio SDK1.5.0, explicit thinking on, raw JSON prompt, temperature0.6, top_k20, top_p0.95,4096token budget. Formatting errors count as failures. Matched on/off settings; differs from constrained HTTP baseline. See manifest.

Evidence: `results/qwen3-0.6b-sdk-thinking-2026-09-21/development.jsonl`; SHA-256 `bddb791db2755571c6bf8a9993afc41121f1ba3237d3ff8e29d7d9d13235ac0e`.

**qwen3-0.6b-sdk-thinking-off**

LM Studio SDK1.5.0, explicit thinking off, raw JSON prompt, temperature0.6, top_k20, top_p0.95,4096token budget. Formatting errors count as failures. Matched on/off settings; differs from constrained HTTP baseline. See manifest.

Evidence: `results/qwen3-0.6b-sdk-nonthinking-2026-09-21/development.jsonl`; SHA-256 `09c1aeb4b42eab4f2e4ead55067dd17eae8136010a4cb977630564dfe422dd9b`.

**qwen3-1.7b-sdk-thinking-on**

LM Studio SDK1.5.0, llama.cpp2.22.0 Metal, M4 Max128GB. Matched raw JSON prompt, temperature0.6, top_k20, top_p0.95,4096 tokens,8192 context. See per-mode manifest. Thinking enabled does not ensure nonempty reasoning on every record.

Evidence: `results/qwen3-1.7b-2026-09-21/thinking-development.jsonl`; SHA-256 `a0925265784b70045c47e8d71c7f3bb01fb6f1682b164a8dafbff54387ee5b42`.

**qwen3-1.7b-sdk-thinking-off**

LM Studio SDK1.5.0, llama.cpp2.22.0 Metal, M4 Max128GB. Matched raw JSON prompt, temperature0.6, top_k20, top_p0.95,4096 tokens,8192 context. See per-mode manifest. Thinking enabled does not ensure nonempty reasoning on every record.

Evidence: `results/qwen3-1.7b-2026-09-21/nonthinking-development.jsonl`; SHA-256 `a445f4dd46e8d472bc43c92e958200238487a97eb1b37574c3c3f195273d80d1`.

**qwen3.5-4b-sdk-thinking-on**

Exact artifact/runtime/request controls in results/qwen3.5-4b-2026-09-21/thinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/qwen3.5-4b-2026-09-21/thinking-development.jsonl`; SHA-256 `4c588165b2980c8cb089e4c1574b65ccec8916135206e457a235863990f955e9`.

**qwen3.5-4b-sdk-thinking-off**

Exact artifact/runtime/request controls in results/qwen3.5-4b-2026-09-21/nonthinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/qwen3.5-4b-2026-09-21/nonthinking-development.jsonl`; SHA-256 `3704162ff632311c4595497595f3463debb0be2df7e9b7270d3be41b381efae4`.

**qwen3-8b-sdk-thinking-on**

Exact artifact/runtime/request controls in results/qwen3-8b-2026-09-21/thinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/qwen3-8b-2026-09-21/thinking-development.jsonl`; SHA-256 `a3420a642d88b0154d203f2fdc3b1a06b1e67f606a43ab3d6ab1f349216c60dc`.

**qwen3-8b-sdk-thinking-off**

Exact artifact/runtime/request controls in results/qwen3-8b-2026-09-21/nonthinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/qwen3-8b-2026-09-21/nonthinking-development.jsonl`; SHA-256 `adb637d71341d3c4013d0b4dc37b0eb90f3998c70f59ea797c53bffdb7524bf2`.

**qwen3.8-27b-sdk-thinking-low**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet. Resumable download stopped during Hugging Face timeout outage.

**qwen3.8-27b-sdk-thinking-medium**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet. Resumable download stopped during Hugging Face timeout outage.

**qwen3.8-27b-sdk-thinking-xhigh**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet. Resumable download stopped during Hugging Face timeout outage.

**gemma4-e2b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-e2b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-e4b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet. Resumable download stopped during Hugging Face timeout outage.

**gemma4-e4b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet. Resumable download stopped during Hugging Face timeout outage.

**gemma4-26b-a4b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-26b-a4b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-31b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-31b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**qwen3.8-27b-sdk-thinking-off**

Supported nonthinking mode; checksum-pinned artifact remains incomplete during Hugging Face timeout outage.

**qwen36-35b-a3b-on**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**qwen36-35b-a3b-off**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**deepseek-r1-distill-qwen32b-native-reasoning**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**mistral-small32-24b-not-applicable**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**mistral-small4-119b-none**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**mistral-small4-119b-high**

User-requested family expansion; exact pinned artifact and sources in docs/ROSTER_RECONCILIATION.md. Storage staging choice pending; runtime smoke required. No inference yet.

**sonnet5-low-first-pass**

59/60 valid; DEV030 timeout180s.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-first-pass.jsonl`; SHA-256 `1d4af9f59f82edf2f725e6d73884e34fd9f0b584783c28a3e56927a10414f58f`.

**sonnet5-low-with-retry**

60/60 valid; timing must include failed DEV030 attempt.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-with-retry.jsonl`; SHA-256 `4995f7066fd71dbc54b5099dea368ed72d9ec17107e79369256a3baf78ae5454`.

**opus5-low**

60/60 valid first pass.

Evidence: `results/claude-subscription-2026-09-21/opus5-development.jsonl`; SHA-256 `2f394a4b2439ffde0f2dcdc7c8d8e25d31154108284fc4593c630cc0dbee1c31`.

**haiku45-not_applicable**

Smoke3 inspected; primary model exact, no overage. Initial detached controllers left empty logs and no prediction file; no inference completion evidenced. Full run uses managed exec session. Parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/haiku45-not_applicable-development-session.jsonl`; SHA-256 `2793372cf0490069f63805f2102791355ee01c2384896d854fd502d7d4b05e93`.

**sonnet5-medium**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-medium-development.jsonl`; SHA-256 `b16ad84ca3934c85213eb5db614256930fa7ddb767a35dd8703980e76d417ce2`.

**sonnet5-high**

Smoke3 inspected; primary model exact, no overage. Initial detached controllers left empty logs and no prediction file; no inference completion evidenced. Full run uses managed exec session. Parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-high-development-session.jsonl`; SHA-256 `39d1640ef792fad3a4d55fa0fbb8a7cb5810d4ef36761e20ab05c0084d814d17`.

**sonnet5-xhigh**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-xhigh-development.jsonl`; SHA-256 `42d86d86fe625a7779dc31efc1c1e941657f03e84360b8568a11f7f435fe95e3`.

**sonnet5-max**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/sonnet5-max-development.jsonl`; SHA-256 `63c9c2d131d342ac20aab6a5b17c9d9125a67a48d85c459ab4aceb52f785cb1c`.

**opus5-medium**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/opus5-medium-development.jsonl`; SHA-256 `f59ad04f5113cceee3a591b9f95e4127778b4457b2a0ab9fb25fa666b0c11151`.

**opus5-high**

Smoke3 inspected; primary model exact, no overage. Initial detached controllers left empty logs and no prediction file; no inference completion evidenced. Full run uses managed exec session. Parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/opus5-high-development-session.jsonl`; SHA-256 `d9d53f0b7fba031fd064c914f52c0d91ab10426f508a1bd7596f05def39f044f`.

**opus5-xhigh**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/opus5-xhigh-development.jsonl`; SHA-256 `2f9ce23e27c9f0f891285dd9c0c16cdf170af886bf00ad12188e511f89a6be7f`.

**opus5-max**

Smoke3 inspected12/12 judgments correct, exact model identity; parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/opus5-max-development.jsonl`; SHA-256 `5af375a01f2ecd7bbb0ed4d3be40c9c9c56ba769ae99aa7940cac43f06b8b94d`.

**fable51-low**

Smoke3 inspected; primary model exact, no overage. Initial detached controllers left empty logs and no prediction file; no inference completion evidenced. Full run uses managed exec session. Parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/fable51-low-development-session.jsonl`; SHA-256 `c4c906701cdb91a1d7630e6412282119f7507e5bbc0cb9a2552d0b7b75a4af89`.

**fable51-medium**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/fable51-medium-development.jsonl`; SHA-256 `32c1350dd1183b32ff882177323ebf023e46298788db6bf09a4eecc57646c54f`.

**fable51-high**

Smoke3 manually inspected,12/12 judgments aligned. Queued to4-worker hosted batch; verify file progress for running state.

Evidence: `results/claude-subscription-2026-09-21/fable51-high-development.jsonl`; SHA-256 `8b940a5da86ae029733811bbd12e3a704d3d41ca22ad4c8c4b6ed3f824939a49`.

**fable51-xhigh**

Smoke3 inspected12/12 judgments correct, exact model identity; parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/fable51-xhigh-development.jsonl`; SHA-256 `17c927214a48fc0007be02549c934e36436a859091d83a493a2d925892823871`.

**fable51-max**

Smoke3 inspected12/12 judgments correct, exact model identity; parallel hosted execution.

Evidence: `results/claude-subscription-2026-09-21/fable51-max-development.jsonl`; SHA-256 `56d558466693ec477db476fd5f1de0471191d18e67636d2cdb4282d8093d5705`.

**typesafe-jev113-v2**

60 valid after one explicitly retained transport retry atDEV046; first-pass45valid then RemoteDisconnected. Shared1USD ledger includes unknown-cost reserve. Provisional development references only.

Evidence: `results/openjev/typesafe-development-v2-reconciled.jsonl`; SHA-256 `5bb3186a23e884fddeeccd9051ec77cc2e3079b6698148b9cdb44c40b602bab4`.

**openjev-fixed**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**openjev-adaptive**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**openjev-thinking**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**openjev-generated-off**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**openjev-generated-on**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**semif-direct**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**semif-serial**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**semif-shared**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**alex-openjev08**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**laya-english**

Native512-token context truncates60/60 full rubric+feedback inputs; no inference performed. Exact native sequence audit: results/laya-coverage-audit-2026-09-21/coverage.json. Never shorten policy or feedback to fit.

**laya-typed**

Native1024-token context truncates60/60 full rubric+feedback inputs; no inference performed. Exact native sequence audit: results/laya-coverage-audit-2026-09-21/coverage.json. Never shorten policy or feedback to fit.

**salesrlagent**

Predicts sales conversion via learned feature/PPO pipeline, not four user-defined recruitment judgments. No valid zero-shot categorical mapping; adapting or retraining changes task.

**openrouter-qwen38-free**

Three separately logged bounded smoke attempts failed firstrequestHTTP429; nofull60. Zero-price model/provider verified eachrun. No paidfallback.

**openrouter-deepseek-free**

Livecatalog rechecked2026-09-21; noDeepSeek :free variant. No paidsubstitution authorized.

**laya-english-expanded-cpu**

Pinned tokenizers preserve60/60 complete inputs (1614–1662 tokens perquestion); encoder capacity8192. Separate runtime-expanded variant, weights pending verification. CPU inference planned; shared-machine contention recorded. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**laya-typed-expanded-cpu**

Pinned tokenizers preserve60/60 complete inputs (1614–1662 tokens perquestion); encoder capacity8192. Separate runtime-expanded variant, weights pending verification. CPU inference planned; shared-machine contention recorded. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed.

**semif-generated-bf16**

Matched source revision851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a and precision with direct BF16 scoring. Adapter implemented; weights incomplete; no inference completed.

**laya-multilingual**

Pinned public artifact metadata verified: convaiinnovations/laya revision1c5edc17a7acd8701df6fc341c0d179f1c62c982 multilingual/ contains5files totaling678201636bytes, weights643835514bytes. Queued after network/CDN recovery. Tokenizer coverage and actual encoder capacity still require local verification; no inference completed.

**laya-multilingual-expanded-cpu**

Pinned public artifact metadata verified: convaiinnovations/laya revision1c5edc17a7acd8701df6fc341c0d179f1c62c982 multilingual/ contains5files totaling678201636bytes, weights643835514bytes. Queued after network/CDN recovery. Tokenizer coverage and actual encoder capacity still require local verification; no inference completed.

**codex-gpt-5.6-luna-low**

Fresh scoped subscription continuation approved after explicit user request. Prior successes reused; tools disabled and fresh perrecord runtime; stop onservice/isolation/quotafailure. No paidcredits. Weekly11%remaining at the latest quota check; newfullsweeps held pending batchingdecision.

**codex-gpt-5.6-luna-medium**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-5.6-luna-high**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-5.6-luna-xhigh**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-5.6-luna-max**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-6-astra-low**

Fresh scoped subscription continuation approved after explicit user request. Prior successes reused; tools disabled and fresh perrecord runtime; stop onservice/isolation/quotafailure. No paidcredits. Weekly11%remaining at the latest quota check; newfullsweeps held pending batchingdecision.

**codex-gpt-6-astra-medium**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-6-astra-high**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-6-astra-xhigh**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-6-astra-max**

Cached account catalog lists this effort; live configuration not yet tested. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-6-astra-ultra**

Cached account catalog lists this effort; live configuration not yet tested. Ultra auto-delegation requires live isolation verification; separate agent-workflow result if tool isolation cannot hold. Network grant unavailable in resumed agent turn; hosted subscription continuation rejected by automatic approval review despite later user authorization.

**codex-gpt-5.6-sol-low**

Three independent smoke records valid; raw responses inspected, no tools/delegation or eventparseerrors. No development run; held pending user batchingdecision and weeklyquota11%remaining. Smoke never included in developmenttiming. CLI0.154.0 vs catalogue0.155.0; serverrevision unavailable.

**codex-gpt-5.6-sol-medium**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-sol-high**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-sol-xhigh**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-sol-max**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-sol-ultra**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-terra-low**

Three independent smoke records valid; raw responses inspected, no tools/delegation or eventparseerrors. No development run; held pending user batchingdecision and weeklyquota11%remaining. Smoke never included in developmenttiming. CLI0.154.0 vs catalogue0.155.0; serverrevision unavailable.

**codex-gpt-5.6-terra-medium**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-terra-high**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-terra-xhigh**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-terra-max**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**codex-gpt-5.6-terra-ultra**

New explicit user request for Sol/Terra. Installed catalogue verified; subscription smoke review pending. Ultra advertises automatic task delegation, so any observed tool/delegation use invalidates primary isolated results.

**antigravity-gemini-3.8-flash-high**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.8-flash-medium**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.8-flash-low**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.7-flash-high**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.7-flash-medium**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.7-flash-low**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.6-flash-high**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.6-flash-medium**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.6-flash-low**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.1-pro-high**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

**antigravity-gemini-3.1-pro-low**

NativeCLI1.2.7 signed-in catalogue verified; exact model/effort ID advertised. No inference. Benchmark approval remains pending; tool/memory isolation and zero-credit setting must be verified before smoke. Evidence: results/gemini-preflight-2026-09-21/catalogue-preflight.json.

