# Host sleep during interrupted runs, 1 October 2026

The Mac slept during both timed-out E4B requests. Their elapsed times cannot establish how long the model spent computing. The failed requests remain unknown outcomes; neither was retried.

Root read the local macOS power log with `pmset -g log` on 1 October. The relevant entries, converted from local UTC+02:00 to UTC, are:

| UTC | Recorded host event |
| --- | --- |
| 01:23:50 | Entering Sleep state due to `Clamshell Sleep`, on AC power |
| 01:39:59 | DarkWake from Deep Idle |
| 02:14:09 | Entering Sleep state due to `Dark Wake Thermal Emergency`, on AC power |
| 02:30:50 | DarkWake from Deep Idle |

The [original E4B journal](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on/fresh2/P2/development.journal.jsonl) records DEV-039 starting at 01:23:47.026 UTC and stopping with an unknown outcome at 01:39:59.035 UTC. The [continuation journal](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on/interruption-continuation-v1/fresh2/P2/suffix.journal.jsonl) records DEV-052 starting at 02:13:52.305 UTC and stopping at 02:30:50.086 UTC. Both intervals overlap a recorded sleep period and end at the subsequent wake. This supports reporting a host interruption; it does not reveal pure inference time or prove how much computation happened before sleep.

The two hosted Qwen fresh3/P0 requests also ended with `TimeoutError` at 02:35:47 UTC. The saved records do not establish whether host sleep, networking, the provider, or a combination caused those failures. Their charges remain unknown and their full reserved bounds are retained.

No power or thermal safeguard was disabled. Root requested that the user open the lid and keep the Mac awake on a ventilated surface before further inference. Offline review and reconciliation continue. The machine can be locked without granting permission to ignore sleep or thermal interruptions.

This note contains the relevant power-event observations, not the full system log, which includes unrelated process and calendar details. Recorded outputs, original timings and frozen controls remain unchanged.
