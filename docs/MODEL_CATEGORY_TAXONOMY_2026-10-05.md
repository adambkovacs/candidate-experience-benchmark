# Model categories and verified training lineage

The public report has separate filters for a model's task and its verified training history. These labels describe model setups in this report; they do not change scores, run data, or the benchmark rubric.

## Purpose categories

- **General-purpose LLM**: a broadly useful language model, including one prompted to classify or used through a decision interface.
- **Task-fine-tuned LLM**: an LLM checkpoint with source evidence that its weights were trained for a specific downstream task.
- **Dedicated classification / decision model**: a model presented as built for typed classification or decisions. It may still use an LLM backbone, so this category can overlap with the general-purpose LLM category.
- **Rules baseline**: deterministic rules without learned model weights.
- **Classification pending source**: the available source does not establish the model's role.

The model's purpose and training history are separate. Fine-tuning and fitted adapters change weights; instructions in a prompt do not. The training filter therefore means *verified task-specific* weight changes or a fitted decision head. It does not claim that a general chat model has never been fine-tuned for any purpose.

## Training lineage labels

- **Task-fine-tuned LLM weights**: verified training of an LLM-derived checkpoint for a downstream task, as documented for [Alex OpenJev](https://huggingface.co/AlexWortega/openjev).
- **Trained adapter or decision head**: verified fitted components on a model system, as documented for [Kev-4B](https://huggingface.co/jaredpalmer/kev-4b) and the project's [AnyJev L2 admission](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_CALIBRATION_NEXT_ADMISSION_2026-09-28.md).
- **Frozen general-model weights**: a source says the run reads a fixed checkpoint without a task-specific update, as documented by [SemIf](https://github.com/TheoLeeCJ/SemIf) and the [AnyJev L0 admission](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_L0_NATIVE_P0_REPEAT_ADMISSION_2026-09-28.md).
- **Rules, no learned model weights**: deterministic baseline.
- **Training lineage not verified**: the reviewed source does not establish task-specific training or adaptation. This does not mean the model was never fine-tuned.

The [category evidence review](REPORT_CATEGORY_REVIEW_2026-10-02.md) contains the full roster mapping and source limits. In particular, lineage remains unknown for many general-purpose model families and specialist models whose available sources establish their interface or intended use but not task-specific weight changes.
