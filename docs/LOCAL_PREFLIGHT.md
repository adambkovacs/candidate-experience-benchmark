# Local preflight, 2026-09-21

This is the initial inventory snapshot. The user subsequently authorized a download and the [first local run completed](LOCAL_DEVELOPMENT_RESULTS.md).

Offline checks passed on the requested Mac checkout. Live inference is blocked: all six artifacts in the LM Studio inventory are embedding or reranking models. None is a suitable instruction model for the four-judgment task. A model appearing under the CLI's LLM category does not establish task suitability.

## Verified setup

See the [machine-readable inventory](../results/preflight-2026-09-21/manifest.json) for exact artifact paths, quantization, sizes, runtime identifiers and evidence commands.

- MacBook Pro Mac16,5: Apple M4 Max, 16 CPU cores (12 performance, four efficiency), 40 GPU cores, 128 GB unified memory.
- macOS 26.6, build 25G5028f; Python 3.14.6.
- LM Studio 0.4.16+2; CLI commit efce996. CLI is installed at `~/.lmstudio/bin/lms` but is absent from this shell's PATH.
- Selected runtimes: llama.cpp 2.22.0 and MLX 1.8.5. These are inventory observations, not proof of a benchmark runtime in use.
- Existing local server is running on port 1234. Three specialized models were loaded and idle at inspection; no model was loaded or unloaded for this audit.
- Low Power Mode is enabled. The power snapshot reported AC Power and a 17% battery that was discharging. Record power again before inference and disclose competing workloads for any timing result.

## Verification

`python3 scripts/development_benchmark.py validate` passed: 60 records, six controlled pairs.

`python3 tests/test_development_benchmark.py` passed all three tests. Printed fixture statuses include invalid output and a service error by design; those are mocked cases, not live inference failures.

Reviewed README.md, PLAN.md, PILOT_AUDIT.md and RUN_DEVELOPMENT.md. No AGENTS.md or CLAUDE.md exists inside this checkout. The parent codebuild instructions describe a separate AEA/Fulcrum project; this repository retains its own benchmark workflow.

Source inspection confirms that `run` reads inputs, the judgment portion of the rubric and the output schema. Reference labels enter only validation and evaluation. The mocked transport test checks fresh two-message requests and feedback-only user payloads. No inference request was sent during this preflight.

## Next step

Obtain a suitable small instruction model, either from a user-specified existing location or through an authorized download. Record its exact artifact, quantization, active runtime and context. Run three records, inspect raw responses and schema validity, then decide whether to run all 60 to a new output file. Keep the provisional reference labels outside every inference request.

The remaining 340 records are ungenerated. No hosted API was called, no model was downloaded, and no model-quality or speed result is claimed.
