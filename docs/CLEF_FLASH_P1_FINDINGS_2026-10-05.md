# Clef Flash P1 findings

Three separately dispatched P1 development passes completed 60 of 60 responses each. Against the same frozen reference set, each scored 47/60 on all four fields. The three passes produced identical parsed prediction vectors, native probability distributions, and provider confidence values across all 60 records. The project owner confirmed human checking of all 60 reference answers on 2 October 2026. The provisional v0.2 labels and scores remain frozen; the human check did not silently replace or revise them. These passes complete the declared three-pass P1 checkpoint; they do not establish performance on a broader population.

The P1 prompt-condition comparison is matched to fresh1/P0 on the model route, ordered inputs, references, record cohort, native Choice interface, and connected-app transport. P1 changed the request payload as planned. All 60 records remained valid in both conditions. The all-four score rose from 45/60 in P0 to 47/60 in P1: DEV-027 and DEV-044 became correct on all four fields, and no previously all-four-correct record became incorrect. Native probability distributions changed on all 60 records, as did provider confidence on all 60; the predictions changed only on those two records. This is a descriptive comparison of one prompt-condition contrast, not a causal or population-level estimate.

| Field | Correct / 60 | Multiclass Brier | Mean negative log true-class probability | Five-bin chosen-label ECE |
| --- | ---: | ---: | ---: | ---: |
| Sentiment | 52 | 0.292119 | 0.596398 | 0.224538 |
| Follow-up needed | 57 | 0.140407 | 0.297115 | 0.108258 |
| Serious concern reported | 56 | 0.139218 | 0.323770 | 0.115415 |
| Testimonial potential | 57 | 0.099398 | 0.223160 | 0.105575 |

Against the frozen provisional labels, two incorrect follow-up predictions assigned at least 0.90 probability to the chosen label: DEV-029 (0.9153) and DEV-059 (0.9043). For serious concern, DEV-029 was also incorrect with provider confidence 0.9566 and chosen-label probability 0.9854. These are disagreements with the frozen reference labels; they are not claims about errors against an independently adjudicated ground truth. Provider confidence and the model's native Choice probabilities are distinct reported quantities.

Each pass recorded 144,694 input tokens and zero output tokens. At the saved published input rate of $0.09 per million tokens, the estimated input charge is $0.01302246 per pass. Provider-billed cost is unavailable; the $0.35394 full-context hold is a reservation bound, not a bill. Client elapsed times were 184.664354, 182.385577, and 147.342118 seconds for fresh1, fresh2, and fresh3. They include connected-app operator handoff and are not inference-latency measurements.

The machine-readable [public projection](../results/clef-native-v1/clef-flash-p1-findings-public.json) is built from terminal run records and checked against stage grants, completion receipts, connected-app request/response evidence, the frozen manifests, and reference hashes. It contains no account identifier or quota data. The offline builder is [scripts/build_clef_flash_p1_findings.py](../scripts/build_clef_flash_p1_findings.py), with focused coverage in [tests/test_build_clef_flash_p1_findings.py](../tests/test_build_clef_flash_p1_findings.py). The [frozen P0 findings](../public-site/clef-findings.json) and [P0 manifest](../results/clef-native-v1/full-p0-manifest-v1.json) provide the matched baseline. The saved pricing source is [Clef Flash billing source](../results/clef-native-v1/clef-flash-billing-source.md); Cloudflare's [Clef Flash model page](https://developers.cloudflare.com/workers-ai/models/clef-flash/) is the vendor reference.

To regenerate and verify the projection:

```sh
python3 scripts/build_clef_flash_p1_findings.py
python3 scripts/build_clef_flash_p1_findings.py --check
python3 -m unittest tests.test_build_clef_flash_p1_findings -v
```
