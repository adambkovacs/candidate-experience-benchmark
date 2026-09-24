# Terra medium P1 prelaunch provenance

Snapshot time: 2026-09-24T17:11:38.571080+00:00

The only saved old dispatch request was the supplied helper command:

```sh
python3 results/prompt-comparison-v1-2026-09-24/subscription-coordinator-handoff/recruitment_codex_phase.py --id codex-gpt-5.6-terra-medium --condition P1 --phase smoke
```

It was submitted in a shared `Promise.all` with Terra high P1 smoke. The saved controller transcript records the tool input at line 1227 and the failed outer tool result at line 1241. The result says `CreateProcess` was rejected because the automatic permission approval review did not finish before its deadline; it explicitly cautions against treating the timeout as evidence of unsafety and permits one retry or user guidance. This is a timeout, not a substantive rejection.

The frozen journal prefix contains no Terra medium P1 claim. Its P1 run directory does not exist, and a filtered live-process check found no matching helper/controller. Therefore the old request did not create a model inference request, scheduler reservation, output, or process lifecycle. The condition is recorded as unattempted. Root authorized one fresh smoke after this snapshot; that later attempt must be recorded separately.

The other four unattempted queue entries are legacy P0 configurations and remain explicitly excluded from reruns.
