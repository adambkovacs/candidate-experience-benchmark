# Native generated-output coverage

This table counts saved outcomes against all 60 provisional development references. It does not claim that the central paired-protocol audit has passed. The [source-bound summary](summary.json) preserves those limitations and exact input files.

| Configuration | Prompt | Saved /60 | Valid /60 | All four match /60 | Missing |
| --- | --- | ---: | ---: | ---: | --- |
| anyjev-qwen06-generated-control | P0 | 60 | 0 | 0 | none |
| anyjev-qwen06-generated-control | P1 | 60 | 0 | 0 | none |
| anyjev-qwen06-generated-control | P2 | 60 | 30 | 1 | none |
| semif-generated-bf16 | P0 | 60 | 52 | 35 | none |
| semif-generated-bf16 | P1 | 60 | 38 | 26 | none |
| semif-generated-bf16 | P2 | 59 | 57 | 42 | DEV-033 |
| openjev-generated-off | P0 | 60 | 52 | 46 | none |
| openjev-generated-off | P1 | 60 | 54 | 49 | none |
| openjev-generated-off | P2 | 60 | 56 | 51 | none |
| openjev-generated-on | P0 | 60 | 59 | 53 | none |
| openjev-generated-on | P1 | 60 | 50 | 46 | none |
| openjev-generated-on | P2 | 60 | 53 | 47 | none |

SemIf P2 combines two separately preserved runs and leaves DEV-033 unresolved. No missing output is treated as a correct prediction. Malformed outputs remain invalid; this report does not strip Markdown fences, repair JSON, or replay requests.

OpenJev requested-on is an observed flag condition with unverified effective reasoning. SemIf baseline request hashes cover decision intent rather than the actual generated messages. AnyJev generated output is a separate HF generation control, not its native decision method. These differences remain explicit when the native paired auditors are implemented.

## Public comparison and evidence limits

All 12 rows above are already included in the public explorer through the source-bound native export. They are descriptive comparisons against the same 60 provisional references. The central strict paired auditor has no native response extractor, so its eligibility checks have not passed for these configurations. This is an evidence limitation, not an unrun prompt condition.

- AnyJev P1/P2 have reconciled native controls. Its P0 controller can reconstruct messages and check the saved request hashes, but the rendered prompt was not saved. Strict eligibility would require an offline audit proving that reconstruction and the full protocol.
- SemIf P0 hashes record decision intent rather than the generated messages. P2 also retains the unresolved DEV-033. The saved evidence does not support a strict, complete three-way comparison.
- OpenJev off/on P1/P2 have reconciled evidence, but historical P0 wire messages and rendered token IDs were not saved. Effective reasoning remains unverified for requested-on. Both triples remain descriptive.

See the [public export adapter](../../../scripts/build_public_explorer.py), [central paired evaluator](../../../scripts/evaluate_prompt_variants.py), and [protocol auditor](../../../scripts/audit_prompt_protocol.py). Future offline native adapters may establish additional claims where the saved evidence permits them. They must not fabricate historical inputs, repair outputs, or turn an unknown outcome into a scored prediction.
