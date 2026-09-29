# DeepSeek low live endpoint check, 2026-09-29

Checked at 2026-09-29 01:55:43 UTC against the public [OpenRouter model catalog](https://openrouter.ai/api/v1/models) and [DeepSeek V4.1 Flash endpoint catalog](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints). These were unauthenticated catalog GETs only; no inference request or API key was used.

The frozen execution manifest is SHA-256 `c1c685db6a4e6a9c4b8376d1d11adc98942fcf9f66eb137daed867b1dc2c5004`. Its route is `deepseek/deepseek-v4.1-flash`, provider tag `open-inference/fp4`, provider name `OpenInference`, quantization `fp4`, low reasoning, 1,048,576-token context, temperature 0, 4,096 max output tokens and no fallback.

The exact model appears once in the live catalog, and the endpoint catalog contains one matching provider-tag entry for that model. The endpoint is present, not missing. Its identity fields, context length, provider prices and supported parameters match the frozen endpoint snapshot. The material difference is `status`: frozen `0`, live `-2`. The reviewed runner requires `status == 0`, so its exact route selector rejects this endpoint as unavailable. The endpoint still advertises `reasoning_effort`; the model catalog lists `low` among supported efforts.

The model-level catalog prices have also changed from frozen prompt/completion/cache-read values `0.0000001` / `0.0000005` / `0.00000001` to live values `0.0000003` / `0.0000012` / `0.000000006` USD per token. The selected endpoint's own prompt/completion/cache-read prices remain `0.0000001` / `0.0000005` / `0.00000001`. This is model-catalog metadata drift; it is separate from the endpoint status rejection. The live endpoint reports a 943,718-token maximum completion length, above the frozen 4,096-token request bound.

Live-response SHA-256 values: model catalog `292ea48a24c0e3c6f3717b2054b00af75ee18f0e631798165cbf44a35a1861e7`; endpoint catalog `4b68453f491a79899f361a76c2143057707f72a5ca8d024f98ceb1ec6b7b11be`. The prior development attempt stopped before claim, reservation or inference. No launch was attempted after this check. Any relaunch remains subject to root review and a fresh exact-route check.

## Follow-up check

At 2026-09-29T02:48:55.876489+00:00, a second unauthenticated model/endpoint catalog check found one exact provider entry, still with status `-2`. The frozen selector returned `Endpoint unavailable or identity mismatch`. No inference, key access, reservation or dispatch occurred. This check confirms continued unavailability; it does not reassert every earlier price observation.

## Endpoint reachable, frozen controls differ

At 2026-09-29T03:19:34.110783+00:00, unauthenticated discovery returned an endpoint accepted by the availability selector, but the subsequent exact frozen-control check rejected metadata drift. No inference, claim, reservation or key access occurred. The existing series remains blocked; availability alone does not authorize changed controls.

```json
{
  "pricing": {
    "frozen": {
      "prompt": "0.0000001",
      "completion": "0.0000005",
      "input_cache_read": "0.00000001",
      "discount": 0
    },
    "live": {
      "prompt": "0.00000003",
      "completion": "0.0000005",
      "input_cache_read": "0.00000001",
      "discount": 0
    }
  }
}
```
