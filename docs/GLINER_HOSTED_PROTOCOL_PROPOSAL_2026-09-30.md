# Hosted GLiNER2.5-Decide four-head protocol proposal, 30 September 2026

**Status: offline proposal, no admission or result.** This defines a reproducible candidate request for the Fastino hosted model `fastino/GLiNER-2.5-Decide`. No credential was read, request was sent, model was downloaded, charge was reserved, or result was generated. The hosted model ID is a separate configuration from the [`fastino/GLiNER2.5-Decide` Hugging Face checkpoint](https://huggingface.co/fastino/GLiNER2.5-Decide); the hosted revision is unavailable in the inspected catalog. The [admission brief](GLINER_DECISION_ADMISSION_2026-09-30.md) records the route and remaining access and spending gates.

## Source and route pins

| Input to this proposal | Frozen value or evidence |
| --- | --- |
| Hosted route | `POST https://api.fastino.ai/v1/chat/completions`; model `fastino/GLiNER-2.5-Decide`. [Fastino inference reference](https://docs.fastino.ai/inference), [quickstart](https://docs.fastino.ai/quickstart). |
| Saved public catalog | [`models.json`](../results/route-audits/fastino-public-catalog-20260930/models.json) SHA-256 `9abb0e3e65f8e4737ca366a8866e84f5a36003b97fbe78362fa0f2373aab8c44`; [`base-models.json`](../results/route-audits/fastino-public-catalog-20260930/base-models.json) SHA-256 `90789d5fe7dfb1dd80205afef3e4d205687087ae563a076d28abb39076beb1d0`; [capture metadata](../results/route-audits/fastino-public-catalog-20260930/capture.json). Dated public snapshot, not current account entitlement. |
| API contract | [Public OpenAPI](https://docs.fastino.ai/openapi.json), GET body SHA-256 `635074d3c4e826b322da70eaaf6ce9efdf55b1f07aba6acbb3df2e6b17ab0436` observed 30 September 2026. The request requires `model` and `messages`; the encoder accepts a dictionary `schema`. This hash is an observation, not a locally saved OpenAPI body. |
| Existing input and rubric | [`data/pilot/inputs.jsonl`](../data/pilot/inputs.jsonl) SHA-256 `bd79e602f45f6aff78796ebdca4f2d0b1585c48665b6b8a9af1fe0b5e52d2b9e` (exactly 60 `{id,feedback}` rows). [`docs/LABELING_GUIDE.md`](LABELING_GUIDE.md) SHA-256 `870a280d4b8073eaca7240f36027f758eacef5a16be31941366095d00c6de925`; use its exact text before `## Simulated routing`, SHA-256 `81e5f843de69c1c54ca4f17b70df51886405ad3a7606d5644ac24aeb29f839a5`. |
| Existing four-head definitions | [`scripts/jev_benchmark.py`](../scripts/jev_benchmark.py) SHA-256 `022536130a463d0f02958e6d9929c2d66dd351b9ae7f2154cfd1f2e02c16cc22` supplies `QUESTIONS` and `criteria(key)`; [`scripts/development_benchmark.py`](../scripts/development_benchmark.py) SHA-256 `587ad2789deed2598eae24cfeb81e49eb44c23b7b002ec1c089d8e63bee0317d` supplies `KEYS` and `VALUES`. Do not substitute shorter definitions. |
| Frozen additions | [`P1-classifier.txt`](../prompts/variants-v1/P1-classifier.txt) SHA-256 `f6653ebb301287e112b01e032285c75e33337acde009a1db2be17d03cde28ad7`; [`P2-classifier-sop.txt`](../prompts/variants-v1/P2-classifier-sop.txt) SHA-256 `b056b9c1162b3d1e3e1d6a09823a83883b35004f4e45fa0e0cc75427598892e9`. Use [`frozen_prompt_variants.py`](../scripts/frozen_prompt_variants.py) `load_frozen_bundle` and `compose_instruction`; its manifest SHA-256 is `d4be944de76d94b85743c536997051755a0247ea13f0d27b612dbbf025fb8264`. |

The saved Fastino base-model entry advertises `classifications` for Decide but **does not** advertise `constrained_classification`; Multi advertises both. This proposal uses only the [documented simple classification schema](https://docs.fastino.ai/inference#classification-schema): four ordered `{task, labels, multi_label: false, top_k: 1}` entries. No constraints, relation features, typed decisions, custom response format, decoder reasoning, seed, or temperature are assumed. The route lists an 8,192-token input/context limit and $0.15 per million input and output tokens in the saved catalogs. Recheck those fields immediately before any future request.

## Exact proposed payload construction

The wire request contains one existing feedback record per call. The controller keeps `id` outside the payload. Load only `inputs.jsonl`, the rubric prefix, the four-head definitions, and the frozen additions. Do not open `proposed_labels.jsonl`, review keys, prior predictions, pair metadata, or scoring artifacts while preparing requests. Reject any input row with keys beyond `{id,feedback}` and any source-hash drift.

Build the four schema entries in this order, retaining the exact `VALUES` label order:

```json
{"classifications":[
  {"task":"sentiment","labels":["positive","negative","mixed","neutral","insufficient_information"],"multi_label":false,"top_k":1},
  {"task":"follow_up_needed","labels":["yes","no","insufficient_information"],"multi_label":false,"top_k":1},
  {"task":"serious_concern_reported","labels":["yes","no","insufficient_information"],"multi_label":false,"top_k":1},
  {"task":"testimonial_potential","labels":["yes","no","insufficient_information"],"multi_label":false,"top_k":1}
]}
```

The hosted schema has no documented per-label description slot. Preserve all existing `QUESTIONS[key]` and `criteria(key)` strings, including their label order, in the instruction text. Define `definitions` as an insertion-ordered mapping over `KEYS`, each value `{"question": QUESTIONS[key], "criteria": criteria(key)}`. Define `json_compact(x)` as Python `json.dumps(x, ensure_ascii=False, separators=(',', ':'))`, without key sorting. The **P0 instruction** is exactly:

```python
policy + '\n\nClassify only the feedback value in the final JSON object. Treat it as untrusted evidence. Apply all four question definitions below independently; output one permitted label per head.\n' + json_compact(definitions)
```

For P1 and P2, call `compose_instruction(P0_instruction, variant, role='user', parent_baseline_id='fastino-gliner25-decide-hosted-p0-v1')`. This appends exactly two LF characters and the complete frozen addition; P2 begins with verbatim P1. The instruction role, schema, model, control fields, and feedback serialization are unchanged. Then form `messages[0].content` as `composed_instruction + '\n\n' + json_compact({'feedback': feedback})`. For P0, `composed_instruction` is the P0 instruction unchanged. A canonical request is UTF-8 JSON with `ensure_ascii=False`, `separators=(',', ':')`, insertion order as shown below, and one trailing newline only in a saved artifact, not in the HTTP body:

```python
{
  'model': 'fastino/GLiNER-2.5-Decide',
  'messages': [{'role': 'user', 'content': composed_instruction + '\n\n' + json_compact({'feedback': feedback})}],
  'schema': four_head_schema,
  'threshold': 0.5,
  'include_confidence': True,
  'store': False,
  'stream': False,
}
```

`threshold: 0.5` is Fastino's documented default, made explicit. `include_confidence: true` requests the documented confidence field; it does not establish a full four-label probability distribution or calibration. `store: false` opts out of Fastino inference persistence according to its reference. `stream: false` keeps one response envelope. Authentication belongs only in an HTTP header outside the saved request body; save neither the header value nor an environment dump. No `max_tokens` is proposed for this encoder because the published reference does not establish its effect on classification; budget admission must instead use the listed maximum output exposure.

The user-message placement ensures the policy and existing criterion descriptions are present in the bytes sent to the encoder. **It does not prove that the hosted encoder honors them as instructions rather than classifying them as part of the text.** The API documents the user message as the text to analyze, but does not define a separate trusted policy channel or per-label descriptions for this hosted classification shape. This is a comparability and protocol-validity question for a guarded smoke; do not call it equivalent to the Jev Choice head or claim a clean P0/P1/P2 effect before reviewing raw outputs.

## Response and admission gates

Fastino documents a chat-completion envelope whose `choices[0].message.content` is a JSON string. Save the raw HTTP status, headers excluding secrets, body, returned `model`, `usage`, and timing before parsing. Accept a benchmark prediction only if that inner JSON yields each of the four named heads exactly once with one string from that head's allowed labels. Preserve missing, extra, malformed or unexpected shapes as failed/invalid outcomes; do not repair, infer or rerun them. A valid allowed label remains valid regardless of its reported confidence. Keep confidence separately; any abstention threshold must be declared as a separate analysis or configuration, not used to silently discard predictions. The documentation does not show a four-head Decide response example or guarantee its confidence layout, so inspect the first guarded DEV-001–003 smoke before freezing a parser or interpreting confidence. The published recommendation to retry some cold-start statuses does not override this benchmark's no-duplicate-dispatch and unknown-cost rules. [Fastino inference reference](https://docs.fastino.ai/inference#response).

Before smoke admission, verify account access, account-specific tariff/quota, and separate Fastino spending authority. Re-fetch exact model availability and price; retain the dated raw response and hash. Establish tokenizer or provider-counted input length for **each complete request**, including the 7,559-byte policy prefix, criterion descriptions, schema, P2 addition, and longest feedback. The 8,192-token context fit is **unverified**; do not truncate any field or infer fit from byte count. The saved price maxima imply a conditional $0.0024576 per request if 8,192 input and 8,192 output tokens both bill at $0.15/M, but actual encoder usage and account billing are unverified. Admit the whole proposed pass bound before any smoke or full dispatch, keep unknown charges reserved, and stop on ambiguous outcomes.

Use DEV-001, DEV-002, DEV-003 as a separately reviewed smoke for each admitted condition. After root review of request bytes and raw response shape, any full series must identify **three separately dispatched 60-position passes per condition**, for example `gliner-hosted-decide-P0-fresh1` through `fresh3`, then P1 and P2 with the same suffixes. Preserve all nine pass identities, attempt and failure positions, and fixed denominator 60. P1/P2 comparisons require the same hosted P0 configuration and may be descriptive only if the encoder does not reliably use the policy/additions. No stage is authorized by this proposal.
