# Qwen3 0.6B SDK thinking-on-P1 development

Completed 60/60 distinct records; 50 valid outputs and 10 preserved invalid outputs. The exact four-field match was 1/60 against provisional development references.

| Judgment | Correct / 60 |
|---|---:|
| `sentiment` | 30/60 |
| `follow_up_needed` | 41/60 |
| `serious_concern_reported` | 24/60 |
| `testimonial_potential` | 9/60 |

Invalid output IDs: DEV-011, DEV-012, DEV-018, DEV-034, DEV-039, DEV-040, DEV-041, DEV-054, DEV-055, DEV-057.

Token use: 103470 prompt and 16818 generated tokens; summed per-record elapsed time 136.5 seconds.

Full metrics and source hashes: [development-evaluation.json](development-evaluation.json). Raw requests, responses, decisions, attempts and terminal remain in the adjacent saved files.

Provisional AI-reviewed development references are used only in this offline evaluation; they were not supplied to the model. Invalid outputs were not repaired or retried.
