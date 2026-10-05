# Clef Flash fresh1/P2 findings

The three separately dispatched P2 development passes each completed 60 valid responses out of 60 and scored 46/60 on all four fields against the frozen provisional v0.2 labels. Their parsed prediction vectors, native probability distributions, and provider confidence values were identical across all 60 records in every pairwise comparison. This completes the declared three-pass P2 checkpoint. The project owner confirmed human checking of all 60 reference answers on 2 October 2026. Those checked provisional labels and the existing P0/P1 scores remain frozen; this report does not silently revise them.

| Field | Correct / 60 | Multiclass Brier | Mean negative log true-class probability | Five-bin chosen-label ECE |
| --- | ---: | ---: | ---: | ---: |
| Sentiment | 50 | 0.296078 | 0.597217 | 0.183802 |
| Follow-up needed | 57 | 0.154066 | 0.324764 | 0.123190 |
| Serious concern reported | 56 | 0.143270 | 0.328777 | 0.118152 |
| Testimonial potential | 58 | 0.089543 | 0.206616 | 0.114093 |

The comparison is matched on the same model route, 60 ordered inputs, reference set, native Choice interface, and connected-app transport. Compared with fresh1/P0, the all-four score rose by one, from 45/60 to 46/60. DEV-044 and DEV-058 became all-four correct; DEV-032 changed from all-four correct to incorrect. Compared with fresh1/P1, the score fell by one, from 47/60 to 46/60: DEV-058 became all-four correct, while DEV-027 and DEV-032 became incorrect. Among the incorrect P2 predictions, follow-up DEV-029 and DEV-059 received chosen-label probabilities 0.9053 and 0.9222. Serious-concern DEV-029 received provider confidence 0.9503 and chosen-label probability 0.9832. These are disagreements with the frozen reference labels. The comparisons are descriptive for this fixed cohort, not estimates of population performance or proof that the prompt alone caused the changes.

Each P2 pass recorded 154,954 input tokens and zero output tokens. At the saved published input rate of $0.09 per million tokens, the input-price estimate is $0.01394586 per pass. Provider-billed cost is unavailable; the $0.35394 full-context hold is a reservation bound, not a bill. Client elapsed times were 180.080418, 157.980623, and 164.435086 seconds for fresh1, fresh2, and fresh3. They include connected-app operator handoff and are not pure inference-latency measurements.

The machine-readable [public projection](../results/clef-native-v1/clef-flash-p2-findings-public.json) validates all three P2 passes' specific smoke and development grants, completion receipts, connected-app requests and responses, reservation journals, frozen manifests, and the reference hash. It also revalidates the saved P0 and three-pass P1 source-bound projections before comparing conditions. The report contains no account identifier or quota data. The [offline builder](../scripts/build_clef_flash_p2_findings.py) has focused tests in [tests/test_build_clef_flash_p2_findings.py](../tests/test_build_clef_flash_p2_findings.py). For context see the separate [P1 findings](CLEF_FLASH_P1_FINDINGS_2026-10-05.md), [frozen P0 findings](../public-site/clef-findings.json), and Cloudflare's [Clef Flash model page](https://developers.cloudflare.com/workers-ai/models/clef-flash/).

To regenerate and verify the projection:

```sh
python3 scripts/build_clef_flash_p2_findings.py
python3 scripts/build_clef_flash_p2_findings.py --check
python3 -m unittest tests.test_build_clef_flash_p2_findings -v
```
