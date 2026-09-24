# Qwen3 0.6B SDK thinking-off-P2 development

Completed 60/60 distinct records; 2 valid outputs and 58 preserved invalid outputs. The exact four-field match was 0/60 against provisional development references.

| Judgment | Correct / 60 |
|---|---:|
| `sentiment` | 1/60 |
| `follow_up_needed` | 1/60 |
| `serious_concern_reported` | 0/60 |
| `testimonial_potential` | 0/60 |

Invalid output IDs: DEV-001, DEV-002, DEV-003, DEV-004, DEV-005, DEV-006, DEV-007, DEV-008, DEV-009, DEV-010, DEV-012, DEV-013, DEV-014, DEV-015, DEV-016, DEV-017, DEV-018, DEV-019, DEV-020, DEV-021, DEV-022, DEV-023, DEV-024, DEV-025, DEV-026, DEV-027, DEV-028, DEV-029, DEV-030, DEV-031, DEV-032, DEV-033, DEV-034, DEV-035, DEV-037, DEV-038, DEV-039, DEV-040, DEV-041, DEV-042, DEV-043, DEV-044, DEV-045, DEV-046, DEV-047, DEV-048, DEV-049, DEV-050, DEV-051, DEV-052, DEV-053, DEV-054, DEV-055, DEV-056, DEV-057, DEV-058, DEV-059, DEV-060.

Token use: 158010 prompt and 2736 generated tokens; summed per-record elapsed time 20.4 seconds.

Full metrics and source hashes: [development-evaluation.json](development-evaluation.json). Raw requests, responses, decisions, attempts and terminal remain in the adjacent saved files.

Provisional AI-reviewed development references were used only in offline evaluation. Fenced JSON was not unwrapped or repaired; invalid outputs were not retried.
