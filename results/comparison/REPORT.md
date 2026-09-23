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
| qwen3.8-27b-sdk-thinking-low | development_running | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-medium | download_verified_smoke_pending | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-xhigh | download_verified_smoke_pending | — | — | — | — | — | — |
| gemma4-e2b-sdk-thinking-on | complete | 60 | 50 | 58 | 46 | 52 | 35 |
| gemma4-e2b-sdk-thinking-off | complete | 60 | 50 | 59 | 45 | 50 | 34 |
| gemma4-e4b-sdk-thinking-on | download_verified_smoke_pending | — | — | — | — | — | — |
| gemma4-e4b-sdk-thinking-off | download_verified_smoke_pending | — | — | — | — | — | — |
| gemma4-26b-a4b-sdk-thinking-on | pending | — | — | — | — | — | — |
| gemma4-26b-a4b-sdk-thinking-off | pending | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-on | pending | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-off | pending | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-off | download_verified_smoke_pending | — | — | — | — | — | — |
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
| opus55-low-batch10 | completed | 60 | 60 | 59 | 59 | 60 | 59 |
| opus55-medium-batch10 | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| opus55-high-batch10 | completed | 60 | 60 | 59 | 59 | 60 | 59 |
| opus55-xhigh-batch10 | completed | 60 | 59 | 59 | 59 | 60 | 58 |
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
| laya-english-expanded-cpu | running | — | — | — | — | — | — |
| laya-typed-expanded-cpu | ready_for_local_validation | — | — | — | — | — | — |
| semif-generated-bf16 | blocked_model_download_network | — | — | — | — | — | — |
| laya-multilingual | unsupported_length | — | — | — | — | — | — |
| laya-multilingual-expanded-cpu | ready_for_local_validation | — | — | — | — | — | — |
| alex-openjev4b | staged_disk_budget | — | — | — | — | — | — |
| openrouter-qwen38-free-low | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-medium | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-xhigh | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-off | pending_provider_recovery | — | — | — | — | — | — |
| anyjev-qwen06-raw | ready_for_gpu_smoke | — | — | — | — | — | — |
| anyjev-qwen06-l0 | ready_for_gpu_smoke | — | — | — | — | — | — |
| anyjev-qwen06-l1 | staged_separate_calibration_required | — | — | — | — | — | — |
| anyjev-qwen06-l2 | staged_separate_calibration_required | — | — | — | — | — | — |
| anyjev-qwen06-generated-control | ready_for_gpu_smoke | — | — | — | — | — | — |
| codex-gpt-5.6-luna-low | completed_with_initialization_retries | 60 | 57 | 60 | 57 | 60 | 56 |
| codex-gpt-5.6-luna-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-luna-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-luna-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-luna-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-astra-low | completed_with_initialization_retries | 60 | 57 | 60 | 59 | 60 | 56 |
| codex-gpt-6-astra-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-6-astra-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-6-astra-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-6-astra-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-astra-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-sol-low | smoke_complete_development_held | — | — | — | — | — | — |
| codex-gpt-5.6-sol-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-sol-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-sol-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-terra-low | smoke_complete_development_held | — | — | — | — | — | — |
| codex-gpt-5.6-terra-medium | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-high | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-xhigh | pending_batching_decision | — | — | — | — | — | — |
| codex-gpt-5.6-terra-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-terra-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-sol-low-batch10 | partial_timeout | — | — | — | — | — | — |
| codex-gpt-6-sol-medium-batch10 | smoke_complete_development_pending | — | — | — | — | — | — |
| codex-gpt-6-sol-high-batch10 | smoke_timeout | — | — | — | — | — | — |
| codex-gpt-6-sol-xhigh-batch10 | pending_after_service_recovery | — | — | — | — | — | — |
| codex-gpt-6-luna-low-batch10 | partial_repeated_timeout | — | — | — | — | — | — |
| codex-gpt-6-luna-medium-batch10 | smoke_complete_development_pending | — | — | — | — | — | — |
| codex-gpt-6-luna-high-batch10 | smoke_timeout | — | — | — | — | — | — |
| codex-gpt-6-luna-xhigh-batch10 | pending_after_service_recovery | — | — | — | — | — | — |
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

Pinned Q4_K_M hash verified. Three low-effort smoke responses inspected; 60-record development run active in results/qwen3.8-27b-2026-09-23. Shared-machine contended timing.

**qwen3.8-27b-sdk-thinking-medium**

Pinned model download completed and SHA256 verified. Awaiting serialized GPU slot and three-record response inspection for this configuration.

**qwen3.8-27b-sdk-thinking-xhigh**

Pinned model download completed and SHA256 verified. Awaiting serialized GPU slot and three-record response inspection for this configuration.

**gemma4-e2b-sdk-thinking-on**

Exact artifact/runtime/request controls in results/gemma4-e2b-2026-09-21/thinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e2b-2026-09-21/thinking-development.jsonl`; SHA-256 `ed61b4e3822d35a8292745203cebb7cf4cf5d4987f71c0cb216fff5cde956602`.

**gemma4-e2b-sdk-thinking-off**

Exact artifact/runtime/request controls in results/gemma4-e2b-2026-09-21/nonthinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e2b-2026-09-21/nonthinking-development.jsonl`; SHA-256 `c52798fde9b7962a917c07459d8cd9fa93a2fa47c7efcbfd16e5dabde0dd8dd1`.

**gemma4-e4b-sdk-thinking-on**

Pinned model download completed and SHA256 verified. Awaiting serialized GPU slot and three-record response inspection for this configuration.

**gemma4-e4b-sdk-thinking-off**

Pinned model download completed and SHA256 verified. Awaiting serialized GPU slot and three-record response inspection for this configuration.

**gemma4-26b-a4b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-26b-a4b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-31b-sdk-thinking-on**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**gemma4-31b-sdk-thinking-off**

Authorized existing60 only. Artifact/runtime support and smoke review required before full run; no result yet.

**qwen3.8-27b-sdk-thinking-off**

Pinned model download completed and SHA256 verified. Awaiting serialized GPU slot and three-record response inspection for this configuration.

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

**opus55-low-batch10**

60/60 valid, six ordered batches of ten after inspected batch smoke of three. No controller retries. CLI 2.1.280 Claude Max; usage credits off, no overage. Batch timing amortized per row; usage once in batch audit. Historical single-record runs unchanged; future max/ultra excluded.

Evidence: `results/claude-subscription-2026-09-23/opus55-low-batch10-development.jsonl`; SHA-256 `9304bc1b5a589e9487679425c21066d825942660a933c44bef30426b7a68cdf8`.

**opus55-medium-batch10**

60/60 valid, six ordered batches of ten after inspected batch smoke of three. No controller retries. CLI 2.1.280 Claude Max; usage credits off, no overage. Batch timing amortized per row; usage once in batch audit. Historical single-record runs unchanged; future max/ultra excluded.

Evidence: `results/claude-subscription-2026-09-23/opus55-medium-batch10-development.jsonl`; SHA-256 `d33a9fe8fee6126d5c369226a26eab4f879619ff26e314343516fa818b2c7bbb`.

**opus55-high-batch10**

60/60 valid, six ordered batches of ten after inspected batch smoke of three. No controller retries. CLI 2.1.280 Claude Max; usage credits off, no overage. Batch timing amortized per row; usage once in batch audit. Historical single-record runs unchanged; future max/ultra excluded.

Evidence: `results/claude-subscription-2026-09-23/opus55-high-batch10-development.jsonl`; SHA-256 `75139c6df4632614ab216ed405871fd7f2efcf247e9c6e2ca51696c0bc7f40c5`.

**opus55-xhigh-batch10**

60/60 valid, six ordered batches of ten after inspected batch smoke of three. No controller retries. CLI 2.1.280 Claude Max; usage credits off, no overage. Batch timing amortized per row; usage once in batch audit. Historical single-record runs unchanged; future max/ultra excluded.

Evidence: `results/claude-subscription-2026-09-23/opus55-xhigh-batch10-development.jsonl`; SHA-256 `213308fcdfcce4edf847a19b3482548f136dcb2518265bc66435f6912920b704`.

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

Three separately logged bounded smoke attempts failed firstrequestHTTP429; nofull60. Zero-price model/provider verified eachrun. No paidfallback. Later metadata lists supported_efforts xhigh/medium/low, mandatory=false; original effort:none request is not a validated successful configuration. Future disabled-reasoning config should be explicit and verified separately.

**openrouter-deepseek-free**

Livecatalog rechecked2026-09-21; noDeepSeek :free variant. No paidsubstitution authorized.

**laya-english-expanded-cpu**

Pinned tokenizers preserve60/60 complete inputs (1614–1662 tokens perquestion); encoder capacity8192. Separate runtime-expanded variant, weights pending verification. CPU inference planned; shared-machine contention recorded. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. Sept23 allartifact hashes verified;3smoke inspected,60development runningCPU with concurrentQwen27B GPU contention.

**laya-typed-expanded-cpu**

Pinned tokenizers preserve60/60 complete inputs (1614–1662 tokens perquestion); encoder capacity8192. Separate runtime-expanded variant, weights pending verification. CPU inference planned; shared-machine contention recorded. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. Sept23 all15Laya artifact files verified against pinned SHA256; weights complete.

**semif-generated-bf16**

Matched source revision851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a and precision with direct BF16 scoring. Adapter implemented; weights incomplete; no inference completed.

**laya-multilingual**

Pinned multilingual weights fully SHA256verified. Native1024/head256 fails exact fullinput coverage60/60; no inference. Audit results/laya-coverage-audit-2026-09-23/multilingual.json.

**laya-multilingual-expanded-cpu**

Pinned multilingual weights fully SHA256verified. Expanded4096/head512 preserves60/60 complete inputs; encoder8192 capacity confirmed. Separate expanded variant; awaiting serial CPU smoke then60.

**alex-openjev4b**

Pinned revisionf004f37e52695d6ddfb914a64dbf93942839ba1e qwen3.5-4b-nli-v2/ verified via metadata:6files9098638502bytes. Config Qwen3_5ForSequenceClassification, labels0contradiction/1entailment/2neutral and same NLI template. Adapter architecture matches0.8B, actual load compatibility untested. No4B weights downloaded; staged within disk budget.

**openrouter-qwen38-free-low**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-medium**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-xhigh**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-off**

Future request uses reasoning.enabled=false; public metadata mandatory=false. No inference at this configuration. Original effort:none429attempts are preserved separately and do not validate reasoning-off behavior.

**anyjev-qwen06-raw**

AnyJev source3cd8c6fcd9e90fc04214575ade6779da1e3f3704; official causal artifactc1899de289a04d12100db370d81485cdf75e47ca. Full rubric per question, fourChoice fields, fresh Decider per record. Raw/L0 probabilities uncalibrated; nativeBF16 checkpoint differs from priorGGUF quantization. Offline-tested adapter; no real inference yet. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect.

**anyjev-qwen06-l0**

AnyJev source3cd8c6fcd9e90fc04214575ade6779da1e3f3704; official causal artifactc1899de289a04d12100db370d81485cdf75e47ca. Full rubric per question, fourChoice fields, fresh Decider per record. Raw/L0 probabilities uncalibrated; nativeBF16 checkpoint differs from priorGGUF quantization. Offline-tested adapter; no real inference yet. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect.

**anyjev-qwen06-l1**

Requires per-question labeled calibration data and disjoint evaluation. Cannot fit and score on the same60 development records. No fitting, shipped unrelated heads, or extra340 records used.

**anyjev-qwen06-l2**

Requires per-question labeled calibration data and disjoint evaluation. Cannot fit and score on the same60 development records. No fitting, shipped unrelated heads, or extra340 records used.

**anyjev-qwen06-generated-control**

Use same pinned causal artifact/device/precision as AnyJev raw/L0. Separate generative control, never mislabeled as AnyJev decision mode. No real inference yet; primary raw/L0 and Laya execution prioritized. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect.

**codex-gpt-5.6-luna-low**

60 unique valid outputs, no observed tools/delegation or eventparseerrors. Four pre-inference initialization failures retained in timing (64 attempts), no smoke included. Reclassified original responses counted once, not repeated. Perrecord ephemeral CLI wrapper; requested model pinned, served revision unavailable. Fresh scoped continuation review approved; no paidcredits/reset. Sol/Terra fullsweeps held for batchingdecision. September23: historical5.6 result retained; future successor is gpt-6-luna.

Evidence: `results/codex-gpt-5.6-luna-low-2026-09-21/development-reconciled.jsonl`; SHA-256 `18572c21f941687485254449df44f53f9d685cd3450deaede387214676999f6f`.

**codex-gpt-5.6-luna-medium**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-luna.

**codex-gpt-5.6-luna-high**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-luna.

**codex-gpt-5.6-luna-xhigh**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-luna.

**codex-gpt-5.6-luna-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-astra-low**

60 unique valid outputs, no observed tools/delegation or eventparseerrors. Four pre-inference initialization failures retained in timing (64 attempts), no smoke included. Reclassified original responses counted once, not repeated. Perrecord ephemeral CLI wrapper; requested model pinned, served revision unavailable. Fresh scoped continuation review approved; no paidcredits/reset. Other fullsweeps held for batchingdecision.

Evidence: `results/codex-gpt-6-astra-low-2026-09-21/development-reconciled.jsonl`; SHA-256 `a1526015cfbcc8badbded93d29a16cec1f4bbfb06217040d224d79bedd63cd14`.

**codex-gpt-6-astra-medium**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-6-astra-high**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-6-astra-xhigh**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-6-astra-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-astra-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-sol-low**

Three independent smoke records valid; raw responses inspected, no tools/delegation or eventparseerrors. No development run; held pending user batchingdecision and weeklyquota11%remaining. Smoke never included in developmenttiming. CLI0.154.0 vs catalogue0.155.0; serverrevision unavailable. September23: historical5.6 result retained; future successor is gpt-6-sol.

**codex-gpt-5.6-sol-medium**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-sol.

**codex-gpt-5.6-sol-high**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-sol.

**codex-gpt-5.6-sol-xhigh**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results. September23: historical5.6 result retained; future successor is gpt-6-sol.

**codex-gpt-5.6-sol-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-sol-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-terra-low**

Three independent smoke records valid; raw responses inspected, no tools/delegation or eventparseerrors. No development run; held pending user batchingdecision and weeklyquota11%remaining. Smoke never included in developmenttiming. CLI0.154.0 vs catalogue0.155.0; serverrevision unavailable.

**codex-gpt-5.6-terra-medium**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-5.6-terra-high**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-5.6-terra-xhigh**

Installed account catalogue advertises this effort. Additional full sweeps held pending user batching decision; no credit redemption or paid API fallback. Ultra advertises automatic delegation; any observed tool use invalidates isolated primary results.

**codex-gpt-5.6-terra-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-terra-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-sol-low-batch10**

Batch10 CLI155 partial run stopped at300s timeout with no captured events/stderr. Luna20valid/Sol10valid before failedbatch. Failure is runtime/transport unknown, not observed model quality. Failedbatch and missing IDs remain in60denominator; rawbatchtime countedonce. Fullcontinuation pending inspection; no max/ultra or paidcredits. Approvedboundedcontinuation uses concurrency1 and600s transporttimeout (initial300s), same inferencepayload/batchmembership. Timing protocol change explicit.

**codex-gpt-6-sol-medium-batch10**

Three valid batchsmoke outputs inspected; no observedtools/parsererrors. Full60 notstarted: laterlow/high requests hit repeated emptytimeoutevents. Holdnewinference pending service recovery. Batch10 workflow, no max/ultra.

**codex-gpt-6-sol-high-batch10**

Three-record high smoke hit300s TimeoutExpired, no fullrun. Rawfailure retained; xhigh notstarted afterstop.

**codex-gpt-6-sol-xhigh-batch10**

Notattempted; smoke sequence stopped on precedinghigh timeout. Hold untilservice recovery. No max/ultra.

**codex-gpt-6-luna-low-batch10**

20valid; batch03 timedout twice at300s then600s, secondwithconcurrency1. Failed30-recordcoverage snapshot plus30unattempted remain60denominator. Bothrawdurations retained; request payload reconstruction verified againstoriginalhash. No furthercalls untilservice recovery, no max/ultra/credits.

**codex-gpt-6-luna-medium-batch10**

Three valid batchsmoke outputs inspected; no observedtools/parsererrors. Full60 notstarted: laterlow/high requests hit repeated emptytimeoutevents. Holdnewinference pending service recovery. Batch10 workflow, no max/ultra.

**codex-gpt-6-luna-high-batch10**

Three-record high smoke hit300s TimeoutExpired, no fullrun. Rawfailure retained; xhigh notstarted afterstop.

**codex-gpt-6-luna-xhigh-batch10**

Notattempted; smoke sequence stopped on precedinghigh timeout. Hold untilservice recovery. No max/ultra.

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

