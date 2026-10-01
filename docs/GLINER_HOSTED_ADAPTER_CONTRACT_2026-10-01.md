# Fastino hosted GLiNER2.5-Decide adapter contract, 1 October 2026

**Status: offline contract candidate; no execution admitted.** The existing [four-head proposal](GLINER_HOSTED_PROTOCOL_PROPOSAL_2026-09-30.md) fixes the inputs, policy, label order, P0/P1/P2 composition, and canonical serialization. This note records the verified Fastino API boundary and the gaps that still prevent a response parser or paid run. No key, account, inference request, download, or charge was used.

## Verified request boundary

Fastino's [inference reference](https://docs.fastino.ai/inference) documents `POST https://api.fastino.ai/v1/chat/completions` with required `model` and `messages`. For an encoder, it accepts a top-level dictionary `schema` with `classifications` entries in this shape: `{ "task": "sentiment", "labels": ["positive", "negative", "neutral"], "multi_label": false, "top_k": 1 }`. It documents several tasks in one schema over the same user-message text. The [live public catalog](https://api.fastino.ai/v1/base-models), read 1 October 2026, lists `fastino/GLiNER-2.5-Decide` as inference-capable and supporting `classifications`. It does not list `constrained_classification` for this model. Thus the [proposal's four ordered classification entries](GLINER_HOSTED_PROTOCOL_PROPOSAL_2026-09-30.md#exact-proposed-payload-construction) use published request fields; successful four-head behavior is still unverified.

The full existing policy, four questions, and criterion descriptions can be placed in `messages[0].content` exactly as the proposal specifies, followed by the single feedback JSON object. The classification schema has no documented label-description or trusted policy field. Fastino says the user message is the **text to analyze**, so sending those bytes does not prove the encoder follows them as instructions. Do not claim a clean policy or P0/P1/P2 effect without inspecting a guarded smoke. The [GLiDE/System One endpoint](https://docs.fastino.ai/concepts/decision-models) has typed questions and probabilities for `fastino/glide`; that is a different interface and model.

For clarity, this is the proposed wire shape for the existing input-only `DEV-001`. `FULL_P0_INSTRUCTION` and `FOUR_HEAD_SCHEMA` denote the exact computed values in the [proposal](GLINER_HOSTED_PROTOCOL_PROPOSAL_2026-09-30.md), not literal strings to send. The record ID stays outside the wire body:

```python
feedback = ("The panel sent the questions format beforehand and gave me time to think. "
            "I wasn't selected, but I left knowing exactly which clinical examples I could strengthen. "
            "That feedback was genuinely useful.")
request = {
    'model': 'fastino/GLiNER-2.5-Decide',
    'messages': [{'role': 'user', 'content': FULL_P0_INSTRUCTION + '\n\n' + compact({'feedback': feedback})}],
    'schema': FOUR_HEAD_SCHEMA,
    'threshold': 0.5,
    'include_confidence': True,
    'store': False,
    'stream': False,
}
```

The [inference reference](https://docs.fastino.ai/inference) documents those control fields and one conversation per call. The exact `FOUR_HEAD_SCHEMA` and `compact` rules are in the proposal; the exact `DEV-001` feedback comes from [`data/pilot/inputs.jsonl`](../data/pilot/inputs.jsonl). Authentication is a bearer header outside the saved body.

## Parser boundary and blockers

The [documented response](https://docs.fastino.ai/inference#response) is a chat-completion envelope with `choices[0].message.content` containing serialized JSON. Its example has `classifications: {}` because it requests only entities; it **does not document the shape of a classification result**, much less four Decide heads. The [public OpenAPI](https://docs.fastino.ai/openapi.json), read 1 October 2026, types the outer `ChatCompletionResponse` but not that inner four-head object. Therefore a specific label/confidence extraction path cannot yet be implemented honestly. Persist raw status, redacted headers, body, returned model, usage and timing before parsing; treat missing, extra or malformed heads as invalid attempts rather than repairing them. Freeze the parser only after the separately admitted `DEV-001`–`DEV-003` smoke reveals actual response fields. Confidence must remain separate from GLiDE's typed Choice distribution.

The public [model](https://api.fastino.ai/v1/models) and [base-model](https://api.fastino.ai/v1/base-models) catalogs, read 1 October 2026, list 8,192 maximum input tokens and $0.15 per million input **and** output tokens. The base-model entry has `max_output_tokens: null`; the general catalog's `max_tokens: 8192` is not a proven billable output ceiling. Multiplying two hypothetical 8,192-token maxima by both rates gives $0.0024576/request, $0.0073728/three, or $0.147456/60, **conditional arithmetic only**, not a safe reservation. Actual account tariff, entitlement, quota, fees and worst-case bill remain unknown. The [inference error table](https://docs.fastino.ai/inference#errors) includes 402/403 billing denials and 425/429/503 warmup or capacity outcomes; there are no automatic retries. Any separately authorized later attempt must preserve the prior attempt and unknown-charge bound. No Fastino spending authority follows from the separate OpenRouter ledger.

Before admission, verify account access and an enforceable cost ceiling; count the **complete** policy, definitions, schema, prompt addition and feedback under the hosted tokenizer for every record/condition without truncation; and inspect the exact four-head result and policy use on a separately approved three-record smoke. No hosted revision mapping to the English Hub checkpoint [`fastino/GLiNER2.5-Decide`](https://huggingface.co/fastino/GLiNER2.5-Decide) has been verified. Keep that checkpoint, multilingual Decide and general Multi separate as required by the [checkpoint audit](GLINER_DECIDE_ADMISSION_AUDIT_2026-10-01.md).
