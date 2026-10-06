# DeepSeek high current-price admission proposal

The [versioned controller](../scripts/deepseek_high_authority_v3.py) prepares a separate DeepSeek V4.1 Flash high configuration. It keeps the frozen model, `open-inference/fp4` provider, high reasoning, 1,048,576-token context, 4,096-token output limit, prompt text, record order, strict JSON schema, and input-only request policy. The only request-body change is the provider price ceiling: $0.0495/M input and $1.32/M output. Every new request hash is recalculated. The [original plans](../results/repeatability-v1/deepseek-high-fresh-matched3-v1/execution-manifest.json) and historical outcomes remain untouched.

A public [OpenRouter endpoint observation](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints) is saved in [public-route.json](../results/repeatability-v1/deepseek-high-authority-v3/public-route.json). It reports the exact model and provider, status 0, high reasoning support, and the saved token prices. A later live check found a lower prompt price of $0.04345/M. The controller accepts nonnegative live prompt and completion prices at or below the saved prices, while requiring all other pricing keys and route identity fields to match exactly. Request price ceilings and the full reserve remain fixed. The controller rechecks the live route and every planned request before a stage. These public reads did not use an account key or send an inference request.

The proposed child cap is **$0.90**. Each request needs the full **$0.0573112320** reserve before dispatch. The 567 planned smoke and development requests have a $32.4954685440 combined maximum at that reserve, so the child does not guarantee nine completed phases. The controller stops before the next request when the child cannot reserve it. It retains known charges, unknown-cost bounds, invalid outputs and provider failures. It never retries an attempted record. A phase starts only after an exact root receipt; development also requires an inspected three-record smoke, and later conditions require closed predecessors.

The [execution proposal](../results/repeatability-v1/deepseek-high-authority-v3/execution-manifest.json) is offline and unapproved. Its SHA-256 is `92a6d817c97c0d21e272b1cad8d4c14092d0a86381c3eea615a07b65f5d3ac3d`. The three plan hashes are:

| Pass | SHA-256 |
| --- | --- |
| fresh1 | `791fc75a1de7d8082c69e93075515264142b0a214b463af5745922d796cf708e` |
| fresh2 | `6343e7f8980b5f552ea52c374736a29b6d7443f6450e416b62c4a4273a650677` |
| fresh3 | `ef41a1d890df6b414daf16d69d628589c11b74ce9a5c3d1edae421f6f5f1f989` |

The first possible stage is fresh1/P0 smoke. Root review should check the source and route hashes, run `verify` and `live-check`, and confirm current master and OpenRouter-only authority capacity. Root must separately allocate one exact $0.90 v4 child at `results/repeatability-v1/deepseek-high-authority-v3/budget.json`, bound to `deepseek/deepseek-v4.1-flash`, `open-inference/fp4` and `high`. The controller requires the reviewed v3 OpenRouter-only hold for that child; it creates that hold only at first approved stage admission. It does not allocate a child or approve a stage.

After allocation, root can generate `stage_receipt('fresh1', 'P0', 'smoke', budget_path)` from the controller and inspect every field. The exact file must be `fresh1/P0/smoke.root-review.json` under the versioned result directory. Root sets `approved`, `independent_review`, and `authorized_by_root` to `true`, and `reviewer` to `root`. The receipt binds the controller, execution and pass hashes, budget manifest, $0.90 child, authority head and hold source. A changed head or source requires a new review. Subsequent stages need their own receipts. No receipt has been created by this proposal.

Read-only checks:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 scripts/deepseek_high_authority_v3.py verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 scripts/deepseek_high_authority_v3.py live-check --fresh-pass fresh1 --condition P0
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m pytest -q tests/test_deepseek_high_authority_v3.py tests/test_deepseek_high_fresh_repeat_execution.py tests/test_openrouter_budget_amendment_v3.py
```

These checks passed: 32 tests and seven subtests, plus the public live route check. The tests cover a lower live price, negative or increased prices, and a changed cache price. They include a real temporary $22.38 master amendment and $0.90 v4 child, and exercise the private gate's OpenRouter-only v3 hold, stale authority receipt rejection, and insufficient-capacity refusal. The controller source SHA-256 is `012c8c39b96039d7ec20b939dc89301310b7ce8c2dcdf70a9a2548bcadd10f3f`; the new test SHA-256 is `0678980edf4968e128f145ca2e207191b37f7c6d049881c029be45154eb731e6`. No child, authority hold, stage receipt, key access or inference was created during preparation.
