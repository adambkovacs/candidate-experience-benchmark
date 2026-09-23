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
| qwen3.8-27b-sdk-thinking-low | complete | 60 | 59 | 60 | 59 | 59 | 57 |
| qwen3.8-27b-sdk-thinking-medium | replaced_by_hosted_user_request | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-xhigh | replaced_by_hosted_user_request | — | — | — | — | — | — |
| gemma4-e2b-sdk-thinking-on | complete | 60 | 50 | 58 | 46 | 52 | 35 |
| gemma4-e2b-sdk-thinking-off | complete | 60 | 50 | 59 | 45 | 50 | 34 |
| gemma4-e4b-sdk-thinking-on | complete | 60 | 54 | 58 | 53 | 57 | 46 |
| gemma4-e4b-sdk-thinking-off | complete | 60 | 46 | 58 | 52 | 57 | 37 |
| gemma4-26b-a4b-sdk-thinking-on | replaced_by_hosted_user_request | — | — | — | — | — | — |
| gemma4-26b-a4b-sdk-thinking-off | replaced_by_hosted_user_request | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-on | replaced_by_hosted_user_request | — | — | — | — | — | — |
| gemma4-31b-sdk-thinking-off | replaced_by_hosted_user_request | — | — | — | — | — | — |
| qwen3.8-27b-sdk-thinking-off | replaced_by_hosted_user_request | — | — | — | — | — | — |
| qwen36-35b-a3b-on | replaced_by_hosted_user_request | — | — | — | — | — | — |
| qwen36-35b-a3b-off | replaced_by_hosted_user_request | — | — | — | — | — | — |
| deepseek-r1-distill-qwen32b-native-reasoning | downloading_runtime_unverified | — | — | — | — | — | — |
| mistral-small32-24b-not-applicable | replaced_by_hosted_user_request | — | — | — | — | — | — |
| mistral-small4-119b-none | replaced_by_hosted_user_request | — | — | — | — | — | — |
| mistral-small4-119b-high | replaced_by_hosted_user_request | — | — | — | — | — | — |
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
| openjev-fixed | complete | 60 | 57 | 59 | 56 | 58 | 52 |
| openjev-adaptive | complete | 60 | 56 | 59 | 56 | 58 | 51 |
| openjev-thinking | complete | 60 | 57 | 60 | 60 | 60 | 57 |
| openjev-generated-off | complete | 52 | 50 | 51 | 50 | 51 | 46 |
| openjev-generated-on | complete | 59 | 56 | 58 | 56 | 57 | 53 |
| semif-direct | complete | 60 | 50 | 56 | 50 | 54 | 36 |
| semif-serial | complete | 60 | 50 | 56 | 49 | 54 | 35 |
| semif-shared | complete | 60 | 50 | 56 | 49 | 54 | 35 |
| alex-openjev08 | complete | 60 | 39 | 37 | 20 | 9 | 3 |
| laya-english | unsupported_length | — | — | — | — | — | — |
| laya-typed | unsupported_length | — | — | — | — | — | — |
| salesrlagent | task_incompatible | — | — | — | — | — | — |
| openrouter-qwen38-free | blocked_provider_429 | — | — | — | — | — | — |
| openrouter-deepseek-free | unavailable_no_free_model | — | — | — | — | — | — |
| laya-english-expanded-cpu | complete | 60 | 41 | 42 | 33 | 13 | 0 |
| laya-typed-expanded-cpu | complete | 60 | 39 | 47 | 32 | 10 | 0 |
| semif-generated-bf16 | ready_for_local_validation | — | — | — | — | — | — |
| laya-multilingual | unsupported_length | — | — | — | — | — | — |
| laya-multilingual-expanded-cpu | ready_for_local_validation | — | — | — | — | — | — |
| alex-openjev4b | ready | — | — | — | — | — | — |
| openrouter-qwen38-free-low | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-medium | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-xhigh | pending_provider_recovery | — | — | — | — | — | — |
| openrouter-qwen38-free-off | blocked_rate_limit | — | — | — | — | — | — |
| anyjev-qwen06-raw | complete | 60 | 8 | 35 | 25 | 33 | 0 |
| anyjev-qwen06-l0 | complete | 60 | 37 | 13 | 34 | 44 | 4 |
| anyjev-qwen06-l1 | staged_separate_calibration_required | — | — | — | — | — | — |
| anyjev-qwen06-l2 | staged_separate_calibration_required | — | — | — | — | — | — |
| anyjev-qwen06-generated-control | complete | 0 | 0 | 0 | 0 | 0 | 0 |
| codex-gpt-5.6-luna-low | completed_with_initialization_retries | 60 | 57 | 60 | 57 | 60 | 56 |
| codex-gpt-5.6-luna-medium | completed | 60 | 58 | 60 | 58 | 58 | 54 |
| codex-gpt-5.6-luna-high | completed | 60 | 58 | 59 | 59 | 59 | 57 |
| codex-gpt-5.6-luna-xhigh | completed_after_infrastructure_recovery | 60 | 58 | 60 | 58 | 60 | 57 |
| codex-gpt-5.6-luna-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-astra-low | completed_with_initialization_retries | 60 | 57 | 60 | 59 | 60 | 56 |
| codex-gpt-6-astra-medium | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| codex-gpt-6-astra-high | completed | 60 | 59 | 60 | 59 | 60 | 58 |
| codex-gpt-6-astra-xhigh | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| codex-gpt-6-astra-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-astra-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-sol-low | completed | 60 | 58 | 60 | 60 | 60 | 58 |
| codex-gpt-5.6-sol-medium | completed | 60 | 58 | 60 | 58 | 60 | 57 |
| codex-gpt-5.6-sol-high | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| codex-gpt-5.6-sol-xhigh | completed | 60 | 58 | 60 | 59 | 60 | 57 |
| codex-gpt-5.6-sol-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-sol-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-terra-low | completed | 60 | 59 | 59 | 59 | 60 | 58 |
| codex-gpt-5.6-terra-medium | completed | 60 | 59 | 59 | 58 | 60 | 57 |
| codex-gpt-5.6-terra-high | completed | 60 | 58 | 60 | 58 | 60 | 57 |
| codex-gpt-5.6-terra-xhigh | completed | 60 | 59 | 59 | 58 | 60 | 57 |
| codex-gpt-5.6-terra-max | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-5.6-terra-ultra | excluded_by_user | — | — | — | — | — | — |
| codex-gpt-6-sol-low-batch10 | completed_after_transport_recovery | 60 | 59 | 60 | 58 | 60 | 58 |
| codex-gpt-6-sol-medium-batch10 | complete | 60 | 59 | 60 | 59 | 60 | 58 |
| codex-gpt-6-sol-high-batch10 | completed | 60 | 58 | 60 | 59 | 60 | 57 |
| codex-gpt-6-sol-xhigh-batch10 | completed | 60 | 58 | 60 | 59 | 60 | 57 |
| codex-gpt-6-luna-low-batch10 | completed_after_transport_recovery | 60 | 55 | 59 | 58 | 59 | 54 |
| codex-gpt-6-luna-medium-batch10 | complete | 60 | 55 | 59 | 58 | 57 | 50 |
| codex-gpt-6-luna-high-batch10 | completed | 60 | 58 | 59 | 58 | 60 | 56 |
| codex-gpt-6-luna-xhigh-batch10 | completed | 60 | 59 | 60 | 58 | 60 | 57 |
| antigravity-gemini-3.8-flash-high | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-medium | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-low | blocked_unverified_tool_restriction | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-high | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-medium | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.7-flash-low | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-high | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-medium | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.6-flash-low | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.1-pro-high | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.1-pro-low | pending_shared_runtime_verification | — | — | — | — | — | — |
| antigravity-gemini-3.8-flash-low-native-observed-batch10 | partial_service_error | — | — | — | — | — | — |
| openrouter-paid-qwen3.8-27b-medium | complete_with_service_failure | 59 | 58 | 59 | 58 | 58 | 56 |
| openrouter-paid-qwen3.8-27b-xhigh | complete_with_output_failure | 59 | 59 | 59 | 56 | 59 | 56 |
| openrouter-paid-qwen3.8-27b-off | complete | 60 | 58 | 60 | 59 | 57 | 54 |
| openrouter-paid-qwen36-35b-a3b-on | complete | 60 | 58 | 60 | 58 | 58 | 54 |
| openrouter-paid-qwen36-35b-a3b-off | complete | 60 | 56 | 59 | 57 | 56 | 51 |
| openrouter-paid-gemma4-26b-a4b-on | complete_with_output_failure | 59 | 59 | 59 | 59 | 59 | 59 |
| openrouter-paid-gemma4-26b-a4b-off | complete | 60 | 57 | 58 | 58 | 56 | 53 |
| openrouter-paid-gemma4-31b-on | complete | 60 | 57 | 60 | 58 | 60 | 56 |
| openrouter-paid-gemma4-31b-off | complete | 60 | 58 | 60 | 59 | 59 | 56 |
| openrouter-paid-mistral-small32-24b-not-applicable | partial_upstream_rate_limit | — | — | — | — | — | — |
| openrouter-paid-mistral-small4-119b-none | smoke_upstream_rate_limit | — | — | — | — | — | — |
| openrouter-paid-mistral-small4-119b-high | smoke_upstream_rate_limit | — | — | — | — | — | — |
| openrouter-paid-deepseek-v41-flash-off | complete | 60 | 57 | 59 | 59 | 56 | 54 |
| openrouter-paid-deepseek-v41-flash-low | complete_with_output_failure | 57 | 57 | 57 | 57 | 57 | 57 |
| openrouter-paid-deepseek-v41-flash-high | running_continuation | — | — | — | — | — | — |
| openrouter-paid-mistral-small32-24b-venice-not-applicable | complete | 60 | 54 | 57 | 55 | 57 | 48 |

Development-attempt costs only. Unknown-cost reservations are bounds, not observed charges; total cash remains unknown where charges are missing. This is not the shared ledger balance: that ledger also covers smoke and failed/incomplete configurations. Runs without explicit billing evidence are unavailable and omitted here. Overlapping first-pass/retry views must not be summed across rows.

| Configuration | Billing coverage | Known actual USD | Unknown-cost reserved upper bound USD | Sources |
| --- | --- | ---: | ---: | --- |
| typesafe-jev113-v2 | partial | unavailable | 0.002123688 | `results/openjev/typesafe-development-v2.jsonl`; `results/openjev/typesafe-development-v2-continuation.jsonl` |
| openrouter-paid-qwen3.8-27b-medium | reported | 0.065762400 | 0.047001600 | `results/openrouter-partition-qwen27-medium-2026-09-23/development.jsonl`; `results/openrouter-partition-qwen27-medium-2026-09-23/development-from049.jsonl` |
| openrouter-paid-qwen3.8-27b-xhigh | reported | 0.061920600 | 0 | `results/openrouter-partition-qwen27-xhigh-2026-09-23/development.jsonl`; `results/openrouter-partition-qwen27-xhigh-2026-09-23/development-from014.jsonl` |
| openrouter-paid-qwen3.8-27b-off | reported | 0.013049550 | 0 | `results/openrouter-partition-qwen27-off-2026-09-23/development.jsonl` |
| openrouter-paid-qwen36-35b-a3b-on | reported | 0.0636796 | 0 | `results/openrouter-qwen35-on-2026-09-23/development.jsonl` |
| openrouter-paid-qwen36-35b-a3b-off | reported | 0.0072576 | 0 | `results/openrouter-qwen35-off-2026-09-23/development.jsonl` |
| openrouter-paid-gemma4-26b-a4b-on | reported | 0.02114858 | 0 | `results/openrouter-gemma26-on-2026-09-23/development.jsonl`; `results/openrouter-gemma26-on-2026-09-23/development-from023.jsonl` |
| openrouter-paid-gemma4-26b-a4b-off | reported | 0.00687630 | 0 | `results/openrouter-gemma26-off-2026-09-23/development.jsonl` |
| openrouter-paid-gemma4-31b-on | reported | 0.01303944 | 0 | `results/openrouter-parallel-gemma31-on-2026-09-23/development.jsonl` |
| openrouter-paid-gemma4-31b-off | reported | 0.00555500 | 0 | `results/openrouter-parallel-gemma31-off-2026-09-23/development.jsonl` |
| openrouter-paid-deepseek-v41-flash-off | reported | 0.00268114 | 0 | `results/openrouter-parallel-deepseek-flash-off-2026-09-23/development.jsonl` |
| openrouter-paid-deepseek-v41-flash-low | reported | 0.01513539 | 0 | `results/openrouter-parallel-deepseek-flash-low-2026-09-23/development.jsonl`; `results/openrouter-parallel-deepseek-flash-low-2026-09-23/development-from007.jsonl` |
| openrouter-paid-mistral-small32-24b-venice-not-applicable | reported | 0.00873028125 | 0 | `results/openrouter-mistral24-venice-na-2026-09-23/development.jsonl` |


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

Exact artifact/runtime/request controls in results/qwen3.8-27b-2026-09-23/low-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/qwen3.8-27b-2026-09-23/low-development.jsonl`; SHA-256 `efcafb03b706b70999c84a367aa7cf2635e3a6b2014ce8085bfd7a0c20cbe056`.

**qwen3.8-27b-sdk-thinking-medium**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**qwen3.8-27b-sdk-thinking-xhigh**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**gemma4-e2b-sdk-thinking-on**

Exact artifact/runtime/request controls in results/gemma4-e2b-2026-09-21/thinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e2b-2026-09-21/thinking-development.jsonl`; SHA-256 `ed61b4e3822d35a8292745203cebb7cf4cf5d4987f71c0cb216fff5cde956602`.

**gemma4-e2b-sdk-thinking-off**

Exact artifact/runtime/request controls in results/gemma4-e2b-2026-09-21/nonthinking-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e2b-2026-09-21/nonthinking-development.jsonl`; SHA-256 `c52798fde9b7962a917c07459d8cd9fa93a2fa47c7efcbfd16e5dabde0dd8dd1`.

**gemma4-e4b-sdk-thinking-on**

Exact artifact/runtime/request controls in results/gemma4-e4b-2026-09-23/on-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e4b-2026-09-23/on-development.jsonl`; SHA-256 `c222b2aad7be007e5b080a23a70cc785429cefd2b0623341dba4abbdd2d8d0e7`.

**gemma4-e4b-sdk-thinking-off**

Exact artifact/runtime/request controls in results/gemma4-e4b-2026-09-23/off-manifest.json. Strict raw JSON, no repair. Shared-machine warm latency; model loading excluded.

Evidence: `results/gemma4-e4b-2026-09-23/off-development.jsonl`; SHA-256 `8aaba576e896639e3ba2a203913d07baf4c258fa89b6bb8e34177a2b168f9bc6`.

**gemma4-26b-a4b-sdk-thinking-on**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**gemma4-26b-a4b-sdk-thinking-off**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**gemma4-31b-sdk-thinking-on**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**gemma4-31b-sdk-thinking-off**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**qwen3.8-27b-sdk-thinking-off**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**qwen36-35b-a3b-on**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**qwen36-35b-a3b-off**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**deepseek-r1-distill-qwen32b-native-reasoning**

September23 DeepSeek-only downloader confirmed active; pinned32B GGUF27/592 chunks at verification. No completeartifact/hash or runtime smoke yet. Separate from hostedDeepSeekV4.1Flash.12GiB reserve; no duplicate downloads.

**mistral-small32-24b-not-applicable**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**mistral-small4-119b-none**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

**mistral-small4-119b-high**

September23 user requested reasonably priced OpenRouter routes instead of matching local downloads. Hosted variants are separate in openrouter-paid-run-registry.json; no claim of equivalent local quantization/runtime. Existing local results and partial downloads preserved.

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

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. September23 all13 artifact files independently hashverified; no local inference yet. Prepared nativeMLX runtime and loopback-only launch commands; waiting serialized model slot. LocalnativeMLX server ready; fixed smoke3 inspected and valid,4.9–7.3srecord; fixed60 development active. Actualreadcountnotexposed; configuredsamples1. Completed60 valid outputs in original7 plus resumed53. One interruption has unknown in-flight attempt/duration; recorded timings exclude this unknown amount. Server restart resets warmup/cache; native16384-token exact-prompt prefill cache means warm-service timings. Actual API read count unknown; configured samples1. See reconciliation.

Evidence: `results/openjev-local-fixed-2026-09-23/development-reconciled.jsonl`; SHA-256 `60ff59a5933fd9a926f921eafe5209cedfa0f13b05d3422f8a6bfb8a2962b396`.

**openjev-adaptive**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. September23 all13 artifact files independently hashverified; no local inference yet. Prepared nativeMLX runtime and loopback-only launch commands; waiting serialized model slot. September23 adaptive smoke3 inspected; full60 running with samples omitted, auto_max4 threshold0.1. Actual rereads not exposed; input token usage excludes adaptive extras. Warm server16384-token exact-prompt cache retained. Completed60 ordered unique development responses after inspected smoke3. Native MLX on Apple M4 Max128GB, default4bit group64 with236 layers at8bits. Warm-service cache retained; actual reread counts unknown. See reconciliation.

Evidence: `results/openjev-local-adaptive-2026-09-23/development.jsonl`; SHA-256 `b0ac1655ca76f617926147487ad67525208848e3590297e274493c2a8cb17bba`.

**openjev-thinking**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. September23 all13 artifact files independently hashverified; no local inference yet. Prepared nativeMLX runtime and loopback-only launch commands; waiting serialized model slot. September23 smoke3 valid and inspected; full60 running. Native think512 budget with samples1/steps1; smoke output-token counts363/512/406. Warm-server cache retained; actual rereads unknown. Completed60 ordered unique development responses after inspected smoke3. Native MLX on Apple M4 Max128GB, default4bit group64 with236 layers at8bits. Warm-service cache retained; actual reread counts unknown. See reconciliation.

Evidence: `results/openjev-local-thinking-2026-09-23/development.jsonl`; SHA-256 `65b8d36c2931e40098ca63955409b04ca8d7eb323408bc146eb2b7b8210f0e58`.

**openjev-generated-off**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. September23 all13 artifact files independently hashverified; no local inference yet. Prepared nativeMLX runtime and loopback-only launch commands; waiting serialized model slot. September23 smoke3 inspected valid; full60 active. Native generated JSON includes upstream schema-as-instruction/first-object extraction and MLX thought stripping, recorded explicitly. Single local benchmark; hosted HTTP jobs concurrent. Completed60 ordered unique development responses after inspected smoke3. Native MLX on Apple M4 Max128GB, default4bit group64 with236 layers at8bits. Server remained loaded; generated path does not reuse native read-prefill LRU. Reread count not applicable. See reconciliation. All60 attempted once; malformedJSON preserved without repair. See valid-output count in reconciliation.

Evidence: `results/openjev-local-generated-off-2026-09-23/development.jsonl`; SHA-256 `e29f4f0ef76ec8d62bbd5efe0791b0e536e38b8d50bbfd0623a72fbf7572d46f`.

**openjev-generated-on**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. September23 all13 artifact files independently hashverified; no local inference yet. Prepared nativeMLX runtime and loopback-only launch commands; waiting serialized model slot. Valid3smoke inspected. Pinned MlxGenerator passes enable_thinking true then always appends empty thought scaffold; outputthoughtmarkers skipped. This is native requested-flag behavior, not verified thinking or isolated reasoning contrast. Full60 launched unchanged. Completed60 ordered unique development responses after inspected smoke3. Native MLX on Apple M4 Max128GB, default4bit group64 with236 layers at8bits. Server remained loaded; generated path does not reuse native read-prefill LRU. Reread count not applicable. See reconciliation. All60 attempted once; malformedJSON preserved without repair. See valid-output count in reconciliation.

Evidence: `results/openjev-local-generated-on-2026-09-23/development.jsonl`; SHA-256 `08ea1e5b3efa7551dcfc588c1524a00c1a20f08e922a04d732c8ebe6f867b05e`.

**semif-direct**

Pinned artifact download/runtime preparation in progress; localGPU coordinated with parent. Download stopped after shared Hugging Face/network timeout outage; resumable partials preserved; no local inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. Latest pool stopped after5boundedURLError attempts with lastshardpartial; controlled resume session29090 started, partials retained. September23 all10 pinned artifact files independently hashverified; downloader terminalexit0; nativeMLX smoke pending serialized queue. September23 all10 pinnedartifactfiles reverified; smoke3 valid/normalized fullinput1594–1658tokens. Actual MLXparameterdtypes BF16+FP32, noquantization, MetalGPU required bynativebackend. Full60 active, hostedHTTP jobs parallel; nootherlocalinference. Completed60records (60 valid) after inspectedsmoke3. NativeMetalGPU, actualBF16+FP32 parameters,noquantization; fullinputhashes/scoremapping checked. HostedHTTPcalls concurrent, no otherlocalinference. See reconciliation.

Evidence: `results/semif-direct-bf16-2026-09-23/development.jsonl`; SHA-256 `beca52b5c0380b32a118cbf8fb1ae65c7e59324d15eb025ded36331d403fbe20`.

**semif-serial**

Completed 60 valid outputs after inspected smoke3. Native MLX Metal GPU, BF16 and FP32 parameters, no quantization. All 240 full-prompt token hashes match direct mode; predictions differ on DEV-038, so arithmetic equivalence is not claimed. A fresh serial-prefix scorer is created per feedback; cache reuse stays within its four questions. Concurrent hosted HTTP requests, no competing local inference. Exact source/artifact/runtime evidence is in reconciliation.json.

Evidence: `results/semif-serial-bf16-2026-09-23/development.jsonl`; SHA-256 `e8c6d4d3486de2083d3168a2b1001c9876996b5e8a3450252ea01493d02f1e51`.

**semif-shared**

Completed 60 valid outputs after inspected smoke3. Native MLX Metal GPU, BF16 and FP32 parameters, no quantization. All 240 full-prompt token hashes match direct and serial modes. Predictions match serial mode and differ from direct on DEV-038; no claim of arithmetic identity. Prefix sharing stays within each feedback record. Concurrent hosted requests, no competing local inference. Exact runtime/artifact and timing evidence is in reconciliation.json.

Evidence: `results/semif-shared-bf16-2026-09-23/development.jsonl`; SHA-256 `923b36ba111cba7b5eeaa8243b5ac3d70154955969b9f7b367820155da8f96b1`.

**alex-openjev08**

Pinned0.8B NLI artifact verified; MPS FP32 no quantization. Three-record smoke inspected then60 unique valid development outputs; all14 NLI triples finite/normalized and predictions independently reconstructed by maximum entailment. Full rubric+feedback1463–1514tokens, no truncation. Native reference PyTorch convolution/gated-delta kernels used; optional optimized kernels unavailable. No concurrent benchmark inference. Earlier incomplete-weight load failure remains historical. Provisional evaluation saved alongside raw responses.

Evidence: `results/alex-openjev08-mps-2026-09-23/development.jsonl`; SHA-256 `8a85a1070e073dbea00c165ca7995de93949bcd01d2e8f2da4cb615d0302d14a`.

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

Pinned artifact verified; expanded4096/head512 preserves full rubric and feedback. Three-record smoke inspected, then60 unique valid development outputs. CPU FP32,4 threads, no quantization; concurrent Qwen27B GPU inference and downloads caused severe variable contention. Native512 variant remains unsupported_length. Evaluation and reconciliation saved alongside predictions; references provisional.

Evidence: `results/laya-english-expanded-cpu-2026-09-23/development.jsonl`; SHA-256 `a5999c03f1537670e2007764fa61fe47c4ccb35149d52b42c5e942e257addc30`.

**laya-typed-expanded-cpu**

All pinned files verified; smoke3 inspected then60 unique valid development outputs. CPU FP32 no quantization,4threads, expanded4096/head512 exactfullinput coverage. No other benchmark inference. Native1024 configuration remains unsupported_length. Upstream choice11+ temperature clamp warning does not affect3/5optionquestions; confidence not treated as correctness. Provisional evaluation and reconciliation saved.

Evidence: `results/laya-typed-expanded-cpu-2026-09-23/development.jsonl`; SHA-256 `d0c5f85c1f3f942971d3edf5b99b1431dba6d043815554859bdea9591bcba678`.

**semif-generated-bf16**

Matched source revision851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a and precision with direct BF16 scoring. Adapter implemented; weights incomplete; no inference completed. September23 current-state reconciliation: downloads resumed, active downloader PID88683 confirmed. OpenJev12/13 files complete (one weight shard partial); SemIf8/10 complete (two weight shards partial). Prior network failure is historical, not current terminal status. Latest pool stopped after5boundedURLError attempts with lastshardpartial; controlled resume session29090 started, partials retained. September23 all10 pinned artifact files independently hashverified; downloader terminalexit0; nativeMLX smoke pending serialized queue.

**laya-multilingual**

Pinned multilingual weights fully SHA256verified. Native1024/head256 fails exact fullinput coverage60/60; no inference. Audit results/laya-coverage-audit-2026-09-23/multilingual.json.

**laya-multilingual-expanded-cpu**

Pinned multilingual weights fully SHA256verified. Expanded4096/head512 preserves60/60 complete inputs; encoder8192 capacity confirmed. Separate expanded variant; awaiting serial CPU smoke then60.

**alex-openjev4b**

Pinned AlexWortega/openjev revision f004f37e52695d6ddfb914a64dbf93942839ba1e, qwen3.5-4b-nli-v2 artifact9,098,638,502bytes. September23 disk space available; queued after existing OpenJev/SemIf downloads with12GiB reserve. Configuration matches sequence-classification architecture and NLI label ordering; actual runtime compatibility and inference remain unverified. Existing prerequisite downloads complete; queuedAlex4B downloader active session48709, weight5.10/9.08GB at latest snapshot. No inference yet. September23 resumed downloader18444 terminal exit0; independent second verification passed all6 files (LFS SHA256 plus Git blobSHA1 for metadata), total9,098,638,502bytes. Artifact ready; actual4B runtime compatibility remains untested. No inference yet.

**openrouter-qwen38-free-low**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-medium**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-xhigh**

Public model metadata explicitly lists this supported effort; single zero-priced ModelRun endpoint lists reasoning and reasoning_effort. No inference attempt at this effort. Existing baseline requests failed429; offline-tested adapter controls implemented; smoke required before development. See results/openrouter/reasoning-options-audit.json.

**openrouter-qwen38-free-off**

September23 live catalog verified Qwen3.8-27B:free ModelRun/fp4 explicit zero pricing and reasoning disabled. One smoke invocation stopped at DEV-001 HTTP429 after1.005s; no predictions or usage; no retry or development run. Older none attempts do not demonstrate reasoning-off support.

**anyjev-qwen06-raw**

AnyJev source3cd8c6fcd9e90fc04214575ade6779da1e3f3704; official causal artifactc1899de289a04d12100db370d81485cdf75e47ca. Full rubric per question, fourChoice fields, fresh Decider per record. Raw/L0 probabilities uncalibrated; nativeBF16 checkpoint differs from priorGGUF quantization. Offline-tested adapter; no real inference yet. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect. Three-record smoke inspected, then60 unique valid development outputs; actual MPS BF16 no quantization, no other benchmark inference. Full input and policy hashes verified; evaluation uses provisional references only after inference.

Evidence: `results/anyjev-qwen06-raw-mps-2026-09-23/development.jsonl`; SHA-256 `b1a1291e315dfd34312363fb5198d64b4f248f13f979a32240ac3ba19327d528`.

**anyjev-qwen06-l0**

AnyJev source3cd8c6fcd9e90fc04214575ade6779da1e3f3704; official causal artifactc1899de289a04d12100db370d81485cdf75e47ca. Full rubric per question, fourChoice fields, fresh Decider per record. Raw/L0 probabilities uncalibrated; nativeBF16 checkpoint differs from priorGGUF quantization. Offline-tested adapter; no real inference yet. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect. September23 MPS BF16 smoke3 inspected;56 full prompt evaluations perrecord,64.8–81.7s smoke latency. Full60 running serially; no other benchmark inference. Three-record smoke inspected, then60 unique valid development outputs; actual MPS BF16 no quantization, no other benchmark inference. Full input and policy hashes verified; evaluation uses provisional references only after inference.

Evidence: `results/anyjev-qwen06-l0-mps-2026-09-23/development.jsonl`; SHA-256 `fba96b08c10f8d85b2ab7e510902689dee302369f33e4f91baf152102cb524a1`.

**anyjev-qwen06-l1**

Requires per-question labeled calibration data and disjoint evaluation. Cannot fit and score on the same60 development records. No fitting, shipped unrelated heads, or extra340 records used.

**anyjev-qwen06-l2**

Requires per-question labeled calibration data and disjoint evaluation. Cannot fit and score on the same60 development records. No fitting, shipped unrelated heads, or extra340 records used.

**anyjev-qwen06-generated-control**

Use same pinned causal artifact/device/precision as AnyJev raw/L0. Separate generative control, never mislabeled as AnyJev decision mode. No real inference yet; primary raw/L0 and Laya execution prioritized. Weights downloaded and SHA256verified; adapters offline-tested and reviewed. Waiting for serializedGPU slot. Raw/L0 scores uncalibrated; generation prompt placement differs, so comparison is workflows rather than isolated decoding effect. Three-record smoke inspected, then60 unique development outputs (0 strict-valid); actual MPS BF16 no quantization, no other benchmark inference. Full input and policy hashes verified; evaluation uses provisional references only after inference. No output repair.

Evidence: `results/anyjev-qwen06-generated-mps-2026-09-23/development.jsonl`; SHA-256 `0018a1e2f7db62f2d65af1fdb59ff8194f11d6af57b5d164801dcd425fe18d14`.

**codex-gpt-5.6-luna-low**

60 unique valid outputs, no observed tools/delegation or eventparseerrors. Four pre-inference initialization failures retained in timing (64 attempts), no smoke included. Reclassified original responses counted once, not repeated. Perrecord ephemeral CLI wrapper; requested model pinned, served revision unavailable. Fresh scoped continuation review approved; no paidcredits/reset. Sol/Terra fullsweeps held for batchingdecision.

Evidence: `results/codex-gpt-5.6-luna-low-2026-09-21/development-reconciled.jsonl`; SHA-256 `18572c21f941687485254449df44f53f9d685cd3450deaede387214676999f6f`.

**codex-gpt-5.6-luna-medium**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-luna-medium-batch10-2026-09-23/development.jsonl`; SHA-256 `3f5bf38701e85c1f097a38feb40230b8065840f1c1cdd38423177dd873f78831`.

**codex-gpt-5.6-luna-high**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-luna-high-batch10-2026-09-23/development.jsonl`; SHA-256 `d4ef884d488c2715721795882da9484e14bf469c95aaeb69011424dcb94310fa`.

**codex-gpt-5.6-luna-xhigh**

Completed60valid via one explicitly authorized recovery after original batch01 DNSfailure600.015s. First recovered request/schema hashes and membership exactly match original. Original10failed rows and rawattempt preserved; finalpredictions use60recovery rows. Timingincludes7requests, with infrastructurefailure duration separated in evaluation. No tools/parser errors/warnings or furtherretries. NativeChatGPTsubscription only,no paidAPI/credits.

Evidence: `results/codex-gpt-5.6-luna-xhigh-recovery-2026-09-23/development.jsonl`; SHA-256 `2fdad3354a0f63032c0b55ed8c7ff255210d9b4d48293cbc1b435f7945f8c768`.

**codex-gpt-5.6-luna-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-astra-low**

60 unique valid outputs, no observed tools/delegation or eventparseerrors. Four pre-inference initialization failures retained in timing (64 attempts), no smoke included. Reclassified original responses counted once, not repeated. Perrecord ephemeral CLI wrapper; requested model pinned, served revision unavailable. Fresh scoped continuation review approved; no paidcredits/reset. Other fullsweeps held for batchingdecision.

Evidence: `results/codex-gpt-6-astra-low-2026-09-21/development-reconciled.jsonl`; SHA-256 `a1526015cfbcc8badbded93d29a16cec1f4bbfb06217040d224d79bedd63cd14`.

**codex-gpt-6-astra-medium**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-6-astra-medium-batch10-2026-09-23/development.jsonl`; SHA-256 `3931aa5605a8d1a9c490bb91c36e39f0331837776c330ee34362952566e77d14`.

**codex-gpt-6-astra-high**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-6-astra-high-batch10-2026-09-23/development.jsonl`; SHA-256 `541a21a2208ca791c083d716666b094379ca9209a11c8761085634d09e7589cd`.

**codex-gpt-6-astra-xhigh**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-6-astra-xhigh-batch10-2026-09-23/development.jsonl`; SHA-256 `72a6fe6129e3925ec6709a68c116020912cfb547d5e6de95a6f72fcadb423c04`.

**codex-gpt-6-astra-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-astra-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-sol-low**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing; historical individual smoke preserved. No paid API/credits.

Evidence: `results/codex-gpt-5.6-sol-low-batch10-2026-09-23/development.jsonl`; SHA-256 `3e9f7c87d7c3c844381002ac474abb829fe98e7cfee3c33b5800b783bb7cebdd`.

**codex-gpt-5.6-sol-medium**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-sol-medium-batch10-2026-09-23/development.jsonl`; SHA-256 `b2133c998266c36a8851e8e5563421ca958b4fef47560cf5482dd3c32dbad926`.

**codex-gpt-5.6-sol-high**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-sol-high-batch10-2026-09-23/development.jsonl`; SHA-256 `3455dcd06de2d502e6ae25c8248445c1cd70a7f58d184336dae00233271fed5b`.

**codex-gpt-5.6-sol-xhigh**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-sol-xhigh-batch10-2026-09-23/development.jsonl`; SHA-256 `bb43657b1103c48c3f6a2ca605f36298f256a43e14bbcf7d6ab3ef1e57388585`.

**codex-gpt-5.6-sol-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-sol-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-terra-low**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout, no retries, tools, parser errors or metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing; historical individual smoke preserved. Request latency varied substantially; no paid API/credits.

Evidence: `results/codex-gpt-5.6-terra-low-batch10-2026-09-23/development.jsonl`; SHA-256 `32fd2f4053d75dd538eccfa84696043ee03688fa03542b935537bf8121fc4138`.

**codex-gpt-5.6-terra-medium**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout, no retries, tools or parser errors. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-terra-medium-batch10-2026-09-23/development.jsonl`; SHA-256 `ed369f1190da98c7bccef827a0e102b90b4c5c73df4af2be6a5ef09ee745dabb`.

**codex-gpt-5.6-terra-high**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout, no retries, tools, parser errors or metadata warnings. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-terra-high-batch10-2026-09-23/development.jsonl`; SHA-256 `4b74bcbe04ff75d3bd59129178b05be0c7e98d4ae1800e3c849bff188949faa9`.

**codex-gpt-5.6-terra-xhigh**

Completed60 unique valid records in6 sequential batch10 requests,600s timeout,no inference retries/tools/parser errors/metadata warnings. Initial permissionreview timedout before execution; one allowed approvalretry succeeded, no duplicate inference. CLI0.155.0-alpha.16 ChatGPT subscription; served revision not exposed. Smoke excluded from development scoring/timing. No paid API/credits.

Evidence: `results/codex-gpt-5.6-terra-xhigh-batch10-2026-09-23/development.jsonl`; SHA-256 `19f40816c5ce7d4c1c8cd6253431aa304bb22e94b7579de514f5e951673816b5`.

**codex-gpt-5.6-terra-max**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-5.6-terra-ultra**

September23 user excluded max and ultra from future runs. Historical artifacts preserved.

**codex-gpt-6-sol-low-batch10**

Completed 60 unique valid records after the second authorized transport recovery. Original successful records were reused, never rerun. Both historical development timeouts remain in total attempt timing; smoke is preserved separately and excluded. CLI 0.155.0-alpha.16 ChatGPT subscription, no tools/parser errors/metadata warnings in successful attempts, no paid credits. Served revision not exposed.

Evidence: `results/codex-gpt-6-sol-low-2026-09-23/development-batch-completed.jsonl`; SHA-256 `32fceb0506e4fd35af4791700557d787d235990234654c0eebbba842d1931123`.

**codex-gpt-6-sol-medium-batch10**

All 60 records returned valid outputs in six batches of ten. Raw prompts, schemas, order and predictions were checked offline. Exact served revision and quantization are not exposed by the CLI. Full audit and timing are in results/codex-gpt-6-sol-medium-2026-09-23/manifest.json.

Evidence: `results/codex-gpt-6-sol-medium-2026-09-23/development-batch.jsonl`; SHA-256 `e58e3f21125b0b6502a8a6ffdfbdf81db03e4c123a7cde638e96d304dcd68681`.

**codex-gpt-6-sol-high-batch10**

Completed 60 unique valid records in six batch10 requests after the inspected successful smoke. Historical failed smoke attempts remain preserved separately and are excluded from development timing. CLI 0.155.0-alpha.16 ChatGPT subscription; no observed tools, parser errors or runtime metadata warnings. Served model revision not exposed. No paid API or credits.

Evidence: `results/codex-gpt-6-sol-high-batch10-resumed-2026-09-23/development.jsonl`; SHA-256 `9ee13c2dacb86e059df7480ed8d8e13e5f48b695b6d170579557fd79669dad03`.

**codex-gpt-6-sol-xhigh-batch10**

Completed 60 unique valid records in six batch10 requests after the inspected successful smoke. Historical failed smoke attempts remain preserved separately and are excluded from development timing. CLI 0.155.0-alpha.16 ChatGPT subscription; no observed tools, parser errors or runtime metadata warnings. Served model revision not exposed. No paid API or credits.

Evidence: `results/codex-gpt-6-sol-xhigh-batch10-resumed-2026-09-23/development.jsonl`; SHA-256 `e886d9a7559499ee2b14b50adf1b46139f5c88bead8f9afadd5ee3f1d28d8261`.

**codex-gpt-6-luna-low-batch10**

Completed 60 unique valid records after the second authorized transport recovery. Original successful records were reused, never rerun. Both historical development timeouts remain in total attempt timing; smoke is preserved separately and excluded. CLI 0.155.0-alpha.16 ChatGPT subscription, no tools/parser errors/metadata warnings in successful attempts, no paid credits. Served revision not exposed.

Evidence: `results/codex-gpt-6-luna-low-2026-09-23/development-batch-completed.jsonl`; SHA-256 `ba319b4af1a61523ad2528f0dafac66066c13fc79e02820d64be73a751dca52a`.

**codex-gpt-6-luna-medium-batch10**

All 60 outputs valid. Six raw batch prompts, schemas, input order and predictions checked offline; no observed tools, parser errors or runtime metadata warnings. Served revision and quantization are not exposed. Audit and timing: results/codex-gpt-6-luna-medium-2026-09-23/manifest.json

Evidence: `results/codex-gpt-6-luna-medium-2026-09-23/development-batch.jsonl`; SHA-256 `1a129010a05d4fb62542cab917a6ff84e59d8396a14a5b63918d3a8d5c144a2c`.

**codex-gpt-6-luna-high-batch10**

Completed 60 unique valid records in six batch10 requests after the inspected successful smoke. Historical failed smoke attempts remain preserved separately and are excluded from development timing. CLI 0.155.0-alpha.16 ChatGPT subscription; no observed tools, parser errors or runtime metadata warnings. Served model revision not exposed. No paid API or credits.

Evidence: `results/codex-gpt-6-luna-high-batch10-resumed-2026-09-23/development.jsonl`; SHA-256 `d26489775508b4c7047a7a8921f64f595e5e77edcaea8c7cbe6c7374f0d91541`.

**codex-gpt-6-luna-xhigh-batch10**

Completed 60 unique valid records in six batch10 requests after the inspected successful smoke. Historical failed smoke attempts remain preserved separately and are excluded from development timing. CLI 0.155.0-alpha.16 ChatGPT subscription; no observed tools, parser errors or runtime metadata warnings. Served model revision not exposed. No paid API or credits.

Evidence: `results/codex-gpt-6-luna-xhigh-batch10-resumed-2026-09-23/development.jsonl`; SHA-256 `27f5307c67981e2b4933c6cfdd894093e2030ba27200050e73f1df7e04a8122f`.

**antigravity-gemini-3.8-flash-high**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.8-flash-medium**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.8-flash-low**

The existing native Antigravity login and model catalogue work. Three smoke attempts were preserved: an eligibility HTTP 503 with zero reported tokens; a model response with 57 tools listed and a plan-mode warning; and a corrected configuration that returned three valid classifications without warnings or tool calls but still listed 57 tools. No external tool use was observed. Whether initialization lists static inventory or effective model access remains unverified, so the strict tool-scope gate failed and no development requests were sent. Aggregate reported usage: 26,965 input tokens, 1,314 output tokens, 990 thinking tokens and 28,279 total tokens. The three request durations sum to 113.24463 seconds. The first runtime log was privately quarantined with an explicit source-hash redaction audit. No relogin, hosted Gemini API or paid credits were used.

**antigravity-gemini-3.7-flash-high**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.7-flash-medium**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.7-flash-low**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.6-flash-high**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.6-flash-medium**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.6-flash-low**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.1-pro-high**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.1-pro-low**

The user authorized the existing logged-in native Antigravity CLI. This model and effort remain in the requested catalogue. Further smoke requests are pending verification of the shared runtime tool restrictions: Flash 3.8 low returned valid classifications but initialization still listed 57 tools after documented controls were applied. No external tool use was observed. See results/antigravity-gemini38-flash-low-2026-09-23/README.md. This row has no benchmark inference and does not require renewed user approval.

**antigravity-gemini-3.8-flash-low-native-observed-batch10**

Distinct native agent workflow, CLI and language server 1.2.9; smoke3 passed with 57 advertised tools, no observed tool calls, restrictions unverified. Initial development batch failed before inference on an idle-connection closure. One authorized recovery of the exact same batch failed on eligibility UNAVAILABLE503. Both report zero tokens; combined request wall time 77.3929815 seconds. Zero valid development records, ten unique failed records and fifty unattempted. All attempts preserved; no further retry, credits, API-key billing or relogin. Smoke excluded from development timing.

**openrouter-paid-qwen3.8-27b-medium**

All 60 records attempted once; 59 valid outputs. DEV-048 transport failure retained with full $0.047001600 unknown charge bound; continuation covered only DEV-049–060. No output repair, retry or tuning. All development attempts remain included in timing and cost; child budget sealed.

Evidence: `results/openrouter-partition-qwen27-medium-2026-09-23/development-reconciled.jsonl`; SHA-256 `5704234c79b3952e5545cb27fd08426da390068c01e645e99392bf918a3a9a14`.

**openrouter-paid-qwen3.8-27b-xhigh**

All 60 records attempted once; 59 valid outputs. DEV-013 length/content-null failure retained at the unchanged 4096-token limit; continuation covered only DEV-014–060. No output repair, retry or tuning. All development attempts remain included in timing and cost; child budget sealed.

Evidence: `results/openrouter-partition-qwen27-xhigh-2026-09-23/development-reconciled.jsonl`; SHA-256 `dc129d32aed007ddcaf7041ff179ee6458f924c5569bd77948e8ac784f353d8d`.

**openrouter-paid-qwen3.8-27b-off**

60 valid, known billing; sealed partition.

Evidence: `results/openrouter-partition-qwen27-off-2026-09-23/development.jsonl`; SHA-256 `b702a3d2129075d31fef2249f105a72f61da2fcf38a05e9fd85be3051bcd6d40`.

**openrouter-paid-qwen36-35b-a3b-on**

60 records finalized. Exact request/provider/billing evidence in results/openrouter-qwen35-on-2026-09-23/manifest.json. Separate hosted configuration, no local equivalence claim.

Evidence: `results/openrouter-qwen35-on-2026-09-23/development.jsonl`; SHA-256 `8817b970a43fd788524467f50de5413923ea504e15b67e068d52ec6c0917e321`.

**openrouter-paid-qwen36-35b-a3b-off**

60 records finalized. Exact request/provider/billing evidence in results/openrouter-qwen35-off-2026-09-23/manifest.json. Separate hosted configuration, no local equivalence claim.

Evidence: `results/openrouter-qwen35-off-2026-09-23/development.jsonl`; SHA-256 `456c9dca63122c62fce0a9daf9cf7abb2f4b8fa42560fa16fcdc73d446bd876b`.

**openrouter-paid-gemma4-26b-a4b-on**

All 60 IDs were attempted once: 59 valid outputs; DEV-022 exhausted the output budget and returned no JSON. Only unattempted DEV-023 through DEV-060 were continued, with the same 4096-token budget, provider and controls. No failed output was retried or repaired. Both raw files are retained for timing and cost accounting. Development cost $0.02114858; smoke cost $0.00086731. The provider reasoning-token anomaly is preserved.

Evidence: `results/openrouter-gemma26-on-2026-09-23/development-reconciled.jsonl`; SHA-256 `a7af4591db655915ce23952c1f3bcfbfa4c5b955fcfcd4cf3755fe269b1f5016`.

**openrouter-paid-gemma4-26b-a4b-off**

60 records finalized. Exact request/provider/billing evidence in results/openrouter-gemma26-off-2026-09-23/manifest.json. Separate hosted configuration, no local equivalence claim.

Evidence: `results/openrouter-gemma26-off-2026-09-23/development.jsonl`; SHA-256 `3a4e74a1787aa4595c5fade367755edc23869045ffc683beddf1f424a53bb9fb`.

**openrouter-paid-gemma4-31b-on**

All 60 development records returned valid JSON after the inspected smoke. Exact DeepInfra turbo FP4 route with requested thinking enabled. Sixteen development responses report reasoning-token counts greater than completion-token counts; raw values are preserved without correction. All reported costs are known, and the child budget is sealed and reconciled. Other hosted runs and one local MLX benchmark overlapped.

Evidence: `results/openrouter-parallel-gemma31-on-2026-09-23/development-reconciled.jsonl`; SHA-256 `b31b2eb1e6633790daf27018c3621759694e52faef51c12aa91506a494bd0411`.

**openrouter-paid-gemma4-31b-off**

Three smoke responses were inspected before all 60 development responses passed validation. Exact DeepInfra turbo FP4 route, reasoning disabled, 4096-token output budget, no provider fallback or retries. All reported charges are known. Other hosted configurations and one local MLX run overlapped. Provider cache usage is retained. The initial smoke command was rejected before execution; evidence-based resubmission of the same command was accepted. The child budget is sealed and reconciled.

Evidence: `results/openrouter-parallel-gemma31-off-2026-09-23/development-reconciled.jsonl`; SHA-256 `886b4fda9b09f8173ef4c73c86e1afb2585bc98d782020b3366c31dfa8fd21e7`.

**openrouter-paid-mistral-small32-24b-not-applicable**

Paused after repeated upstream HTTP 429 responses. Across four source files: 23 attempts, 21 unique records attempted, 19 valid outputs, 2 retained failures, and 39 unattempted records. All historical attempts and unknown billing bounds are preserved. Recovery child budget sealed; no additional calls scheduled on this route.

**openrouter-paid-mistral-small4-119b-none**

Original and bounded cooldown recovery smoke attempts both failed at the first request with HTTP 429 from the upstream provider shared pool. Each attempt retains its full reserved unknown-cost bound; no development requests. Next step: provider shared-pool recovery or a separately verified equivalent provider. No credit purchase or provider-key setup performed.

**openrouter-paid-mistral-small4-119b-high**

First smoke HTTP429, no retry; full reserved $0.04177920 retained as unknown bound, not observed cost; partition sealed.

**openrouter-paid-deepseek-v41-flash-off**

Inspected3smoke then60valid, exact OpenInferenceFP4 route, reasoning disabled,4096tokenbudget, nofallback/retry. Allreportedcostsknown. Parallel hosted configs and single local MLX benchmark; raw providercache usage retained. Child/master reconciliation controller-owned.

Evidence: `results/openrouter-parallel-deepseek-flash-off-2026-09-23/development-reconciled.jsonl`; SHA-256 `ac3168657f2fecc06adb40b8541de79ed7bcf0e920466bb1ce3342a98607ee63`.

**openrouter-paid-deepseek-v41-flash-low**

All 60 records attempted once; 57 valid outputs. DEV-006, DEV-013 and DEV-030 output failures retained without repair or retry. Continuation sent only previously unattempted records with unchanged model, provider, prompt and 4096-token limit. All costs known and child budget sealed. Concurrent hosted configurations; provider cache usage retained.

Evidence: `results/openrouter-parallel-deepseek-flash-low-2026-09-23/development-complete.jsonl`; SHA-256 `aee3f15a4ed678d1b9b2d8a8afe5684eba0ec009d1d8481b4abd00345a4f41db`.

**openrouter-paid-deepseek-v41-flash-high**

Concurrent hosted execution under a reserved child budget. Existing completed records and all failures are preserved; only the declared continuation range is sent. Terminal reconciliation is pending. The existing model, provider and generation controls are unchanged.

**openrouter-paid-mistral-small32-24b-venice-not-applicable**

All 60 records valid after inspected smoke3. Venice FP8 is a separate provider configuration for the same approved Mistral model; no pooling with partial DeepInfra results. Temperature0, max_tokens4096, timeout600, no retries or repairs. Costs known; exact serving weights and hardware undisclosed. Concurrent hosted runs and one independent local GPU benchmark.

Evidence: `results/openrouter-mistral24-venice-na-2026-09-23/development-reconciled.jsonl`; SHA-256 `ad8caac9b6db0df5f3e0e5b761f3bdb49e4aa7420eb184097bc29614ad7ab153`.

