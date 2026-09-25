# Gemma 26 repeat study

Three complete passes now exist for each prompt condition on the same 60 synthetic development reviews. The original pass met the frozen protocol; the two new passes used the same request bytes and controls. All nine condition/pass combinations have 60 valid categorical outputs.

| Prompt | Pass 1 all-four agreement | Pass 2 | Pass 3 | Reviews with a changed decision |
| --- | ---: | ---: | ---: | ---: |
| P0 | 53/60 | 52/60 | 52/60 | 2/60 |
| P1 | 52/60 | 52/60 | 52/60 | 2/60 |
| P2 | 52/60 | 51/60 | 53/60 | 3/60 |

Agreement uses the unchanged provisional v0.2 references. These are AI-reviewed development labels, not independently adjudicated ground truth. Changes are measured per review across the three passes; repeated responses do not increase the sample beyond 60 reviews.

The new passes made 360 development requests and 18 separate smoke requests. The closed budget partition reports $0.05468064 in total charges and no unknown charges. It released $0.14531936 of its $0.20 allocation. See the [budget reconciliation](budget-reconciliation-v1.json).

Model: `google/gemma-4-26b-a4b-it`; provider endpoint: `deepinfra/fp8`; quantization: FP8; reasoning: off. Runtime: OpenRouter HTTP v1; remote hardware undisclosed. Temperature 0, maximum output tokens 4,096, strict schema, no fallback or retries. [Repeat 2](repeat2/manifest.json) and [repeat 3](repeat3/manifest.json) bind the exact requests, settings and original evidence. Reference labels were excluded from all inference requests.

Pure inference time is unavailable. Saved durations are client request times and include transport and service overhead. Token counts and reported charges are retained per attempt. Charges have not been reconciled to an invoice. The wider requested repeat matrix remains unfinished.
