# LM Studio Qwen load controls: static investigation

**Finding:** The pinned LM Studio CLI has a supported load path that *requests* both one parallel session and the frozen GPU split. Its bundled load command maps `--parallel 1` to `llm.load.numParallelSessions=1`. Passing `--gpu max` explicitly also causes its bundled SDK to map `load.gpuSplitConfig` to `{strategy:"evenly", disabledGpus:[], priority:[], customRatio:[]}` and the GPU offload ratio to 1. This is a source-level finding, not a verified loaded-instance result. No model was loaded, unloaded, or queried during this investigation.

The [frozen six-Qwen plan](../results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json) includes five SDK Qwen configurations that require both fields. The [small-local plan](../results/repeatability-v1/small-local-v1/manifest.json) requires the same pair for Qwen 3.5 4B thinking-off. Both plans require seven exact load fields, including CPU thread pool 12, context 8192, flash attention true, direct I/O false, GPU offload ratio 1, the split object above, and parallel sessions 1. Their controllers attach to an already loaded model, check `lms ps` for one parallel session, and compare the complete reported load configuration against the frozen fields after a request. The comparison is exact, so a CLI invocation alone cannot admit a phase. See the [runtime check](../scripts/small_local_repeat_admission.cjs#L301-L334) and [load-field classifier](../scripts/local_prompt_execution_v1.cjs#L37-L70).

The pinned external SDK, version 1.5.0, can set the GPU split through `LLMLoadModelConfig.gpu`, but its [public load type](/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.d.ts#L4800-L4900) and [load schema](/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs#L5300-L5322) have no parallel-session property. Its [LLM conversion](/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs#L17574-L17597) maps GPU split but not parallel sessions. This matches the [preflight observation](LOCAL_RESUME_PREFLIGHT_2026-10-02.md#L31): the explicit-GPU SDK load produced four sessions, while the frozen plan requires one. Pinned SDK 1.5.0 alone therefore provides no supported way found here to set both fields at load time.

The installed CLI, commit `efce996`, has SHA-256 `8c5e3c497cf0705c7229d4b43c275a6622ea0d492156c7e499d9ffdd09399291` at [`/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms`](/Applications/LM%20Studio.app/Contents/Resources/app/.webpack/lms). Its read-only `load --help` shows `--gpu`, `--parallel`, `--context-length`, and `--identifier`. The following evidence comes from that exact executable's embedded JavaScript, with byte offsets measured from the start of the file:

| Byte offset | Installed-source behavior |
| --- | --- |
| 64,007,821 | `gpuOptionParser` turns `max` into numeric `1`. |
| 64,008,600 to 64,009,500 | The load command declares `--gpu` and `--parallel`; it also has hidden `--exact` and `--local` options. |
| 64,011,269 | The command places `parallel` in `maxParallelPredictions` and, only when `--gpu` is supplied, places `{ratio: gpu}` in `loadConfig.gpu`. |
| 62,931,702 | The bundled SDK load schema accepts `gpu` and `maxParallelPredictions`. |
| 62,941,128 | GPU conversion defaults to `strategy:"evenly"` and empty `disabledGpus`, `priority`, and `customRatio` arrays when GPU is explicit. |
| 63,060,685 and 63,060,927 | The bundled SDK maps the explicit GPU setting to `gpuSplitConfig` and `maxParallelPredictions` to `numParallelSessions`. |
| 64,021,600 | The CLI forwards that configuration to `namespace.load(modelKey, ...)`. |

The previous [Qwen 3.5 thinking-off smoke diagnosis](QWEN35_OFF_LOAD_CONFIG_DIAGNOSIS_2026-10-01.md#L3-L9) reports a CLI-loaded result with parallel 1 and the other five expected fields, but no `load.gpuSplitConfig`. It preserves DEV-001 as a control failure. That note does not record the exact CLI arguments, so it does not establish whether `--gpu` was explicit. The installed source indicates that omitting `--gpu` omits the split from the CLI's requested configuration; it does not prove why that earlier instance lacked the field.

For a later, separately reviewed *load-only* preflight, the candidate shape is:

```text
/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms load \
  --exact --local <frozen-artifact-path> \
  --gpu max --parallel 1 --context-length 8192 \
  --identifier <frozen-model-identifier>
```

`--exact` requires the downloaded model path to match exactly; `--local` excludes linked remote devices in the installed command source. Replace placeholders from the applicable frozen plan and verify the installed CLI hash before use. This command was **not run**. It requests four controls. The other frozen values, the full seven-field response, model identity, cache, backend preference, host readiness, and existing failed/unsent position accounting still require direct inspection under the project gates before any inference. Do not overwrite or replay the failed DEV-001. [LM Studio's SDK documentation](https://lmstudio.ai/docs/typescript/llm-prediction/parameters) says `.model()` ignores load configuration when an instance is already loaded; calling the pinned SDK after a CLI load cannot be assumed to repair a mismatch. If the full loaded configuration differs, stop and define a separately versioned configuration rather than changing the frozen controls.

The pinned SDK file inspected here has SHA-256 `9657d3c5f4e1e17316b810b8d0a99c93bf1bef75706390552d167db06913957c`. This investigation used only installed help, source inspection, and existing saved evidence. The active Qwen HTTP work was not disturbed.
