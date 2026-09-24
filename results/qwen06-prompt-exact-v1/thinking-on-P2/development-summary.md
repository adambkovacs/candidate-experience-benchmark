# Qwen3 0.6B SDK thinking-on-P2 development

Completed 60/60 distinct records; 58 valid outputs and 2 preserved invalid outputs. The exact four-field match was 2/60 against provisional development references.

| Judgment | Correct / 60 |
|---|---:|
| `sentiment` | 31/60 |
| `follow_up_needed` | 42/60 |
| `serious_concern_reported` | 19/60 |
| `testimonial_potential` | 10/60 |

Invalid output IDs: DEV-026, DEV-042.

Token use: 157770 prompt and 19945 generated tokens; summed per-record elapsed time 201.3 seconds.

Full metrics and source hashes: [development-evaluation.json](development-evaluation.json). Raw requests, responses, decisions, attempts and terminal remain in the adjacent saved files.

Provisional AI-reviewed development references are used only in this offline evaluation; they were not supplied to the model. Invalid outputs were not repaired or retried.
