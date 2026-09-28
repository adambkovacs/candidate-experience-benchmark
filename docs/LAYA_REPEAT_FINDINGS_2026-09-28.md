# Laya native repeat findings, 28 September 2026

All three expanded-context Laya configurations returned valid classifications for all 60 reviews in each of three separately dispatched passes. None changed a classification between passes. Each configuration nevertheless matched all four provisional reference decisions on **zero of 60 reviews**, in every pass. Stable output did not imply agreement with this task's rubric.

| Native configuration | Sentiment | Follow-up | Serious concern | Testimonial suitability | All four |
| --- | ---: | ---: | ---: | ---: | ---: |
| English | 41 / 60 | 42 / 60 | 33 / 60 | 13 / 60 | 0 / 60 |
| Typed decisions | 39 / 60 | 47 / 60 | 32 / 60 | 10 / 60 | 0 / 60 |
| Multilingual | 33 / 60 | 37 / 60 | 24 / 60 | 10 / 60 | 0 / 60 |

The scores and classifications in this table were unchanged across the three passes. An all-four match requires every field to match on the same review; separate field scores do not establish that conjunction.

Testimonial suitability was the weakest field in all three setups. The provisional references mark 50 reviews as unsuitable and nine as suitable. English Laya predicted `insufficient_information` for 35 reviews and `yes` for 22. Typed Laya predicted only those two classes, with 34 `yes` answers. Multilingual Laya predicted `yes` for 59 reviews, and also predicted serious concern for 59 reviews, compared with 25 positive serious-concern references. These distributions show a mismatch between these exact native task mappings and the reference rubric. They do not establish performance on other tasks or prove a general limitation of the underlying model.

These are native P0 option-scoring procedures, not chat generation. Generative P1/P2 prompts are not equivalent operations for these configurations. The first pass and two new passes retain the same frozen checkpoint, native mapping, CPU FP32 runtime and full-input controls. The [admission plan](LAYA_NATIVE_P0_REPEAT_ADMISSION_2026-09-28.md) records those choices. Each new development pass followed a separately inspected three-record smoke; smoke outputs are not pooled into the 60-record development scores. DEV-001–003 are rerun within development.

There are still only 60 fictional reviews, with AI-reviewed provisional references. The repeated answers are not independent new test cases. Zero observed changes does not prove intrinsic determinism. Recorded request durations include client/runtime effects and uncontrolled host conditions; they are not model-only inference measurements. Token counts are native reported input counts, while electricity, hardware cost and pure inference time remain unavailable.

The [report builder](../scripts/build_laya_repeat_findings.py) reconstructs scores, class counts and flips from hash-bound raw outputs, intents, admissions and completion records. It checks repository evidence without claiming to rehash the private workstation's model files during public builds. The original results remain unchanged.
