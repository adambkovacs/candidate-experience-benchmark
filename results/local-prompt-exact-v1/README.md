# Remaining local prompt comparison: prepared execution

This directory prepares the nine local-only configurations left after the Qwen3 0.6B SDK pairs. It contains no P1/P2 inference output yet. The first condition is the original Qwen3 0.6B **local HTTP** configuration, followed by eight **LM Studio SDK** configurations in the frozen schedule's order. These are separate transport surfaces; the HTTP configuration is not replaced by the completed Qwen3 0.6B SDK runs.

The manifest binds the exact P0 model artifacts, baseline request controls, canonical input-only records, prompt composer, schema, roster, schedule, CLI, SDK, engine and hardware. The 18 P1/P2 conditions each require a three-record smoke run, raw-response inspection, then a separate 60-record development run. The controller refuses replay and stops on control or service failures or a timeout. Invalid model output remains an observed result.

The input-only preflight counted all 1,620 rendered P0/P1/P2 prompts using the public SDK. All fit the 8,192-token context with the saved output reserves. The 540 P0 comparisons agree with saved native counts for Qwen3 0.6B, Qwen3 1.7B and Qwen3.5 4B. Gemma 4 E2B and E4B each have an observed constant native count of public rendered-string count plus one across their 120 saved P0 records; the preflight includes that offset. This count agreement does not establish token-sequence equivalence. Every live response must still match its expected native prompt count.

`smoke-plan.json` lists all 18 conditions. Both `manifest.json` and `smoke-plan.json` are preparation evidence, not execution approval. A separate root review receipt bound to frozen hashes is required before any request.
