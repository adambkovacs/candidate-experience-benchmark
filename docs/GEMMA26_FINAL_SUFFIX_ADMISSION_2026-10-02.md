# Gemma 26B: final unsent fresh3/P2 suffix

The [sealed fifth-stage receipt](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fifth-suffix-017-046-v1/terminal-reconciliation-after-dev046.json) binds 30 valid DEV-017–046 attempts, $0.01109214 in known charges, no unknown charge, and $0.58890786 released from its $0.60 OpenRouter child. Its SHA-256 is `0feaf71c7040eae7b5edecb010fb016f0706a8ec27e1678f1c5365c070acdab4`. The [fifth controller](../scripts/gemma26_v2_fifth_suffix.py) rechecks the earlier DEV-002, DEV-005 and DEV-006 failures; the new controller calls that same gate and verifies the exact fifth claim, review, 30 journaled attempts, raw captures, child ledger, and master reconciliation. It permits only the 14 never-sent IDs **DEV-047–060**. This is a separate versioned stage, not a retry of any earlier request.

The [final controller](../scripts/gemma26_v2_final_suffix.py) and [manifest](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/final-suffix-047-060-v1/manifest.json) bind the original input-only fresh3/P2 payloads. The frozen full-context reserve is **$0.01974272 per request**. Fourteen maximum reservations total **$0.27639808**, fitting a proposed **$0.30 child** with $0.02360192 margin. After the fifth reconciliation, the locked $12.38 OpenRouter master had $11.70775157750 accounted and $0.67224842250 unallocated. A new $0.30 partition would leave $0.37224842250 at that checkpoint. Allocation must recheck the live locked master; this note and manifest do not reserve it.

The user's newer **$10 overall postapproval ceiling** also applies. The [immutable authority snapshot after the two Clef P0 stages](../results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl) retains $0.064884 for the initial Clef smoke, $0.60 for the Gemma fifth stage, $0.94374 for Clef development and $0.35394 for Flash development: **$1.962564 held**. The fifth-stage $0.60 remains a conservative carry until a separately reviewed release; its $0.01109214 observed charge does not automatically replace it in this ledger. A final-suffix $0.30 hold would bring this checkpoint to **$2.262564**, within the overall ceiling. At dispatch, the controller takes an exclusive lock on the global ledger, requires the exact root-reviewed head hash and immutable snapshot prefix, validates every hold and aggregate cap, then durably appends a unique $0.30 stage hold **before the first request**. A stale head, duplicate stage, or insufficient global authority blocks all inference. This hold remains conservative if startup fails after its append.

The controller also requires an exact new OpenRouter child, a root receipt binding the controller, manifest, predecessor gate, child allocation and global ledger head, and a fresh route check before the claim and before each send. A read-only check at **2026-10-02 14:18:45 UTC** matched [OpenRouter's `google/gemma-4-26b-a4b-it` DeepInfra listing](https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it/endpoints): `deepinfra/fp8`, DeepInfra, fp8, 262,144 context, $0.00000007 per prompt token and $0.00000034 per completion token, with the frozen $0.01974272 reserve. This does not establish that the provider will accept the next request. A provider failure stops the stage and retains its attempt and unknown-cost bound; no automatic replay occurs. The final phase remains unscored until all 60 positions, including preserved failures, are reconciled offline. It does not read reference labels or send them to the provider.

Offline checks are `python3 -m unittest tests.test_gemma26_v2_final_suffix -v` and `python3 scripts/gemma26_v2_final_suffix.py verify`. The [focused tests](../tests/test_gemma26_v2_final_suffix.py) check the sealed predecessor and exact 14-record slice, drift, locked global hold uniqueness and cap, child identity, route drift, duplicate claims, and a simulated first-request HTTP 429 that leaves DEV-048–060 unsent.

After independent review, the root can create the **new child only** with this exact allocation call (run from the repository root):

```python
import sys
sys.path.insert(0, 'scripts')
import gemma26_v2_final_suffix as final
from paid_budget_partitions_v3 import allocate
allocate(final.third.MASTER, final.BASE / 'budget.json', [{
    'id': final.PARTITION_ID,
    'cap_usd': str(final.CAP),
    'model': final.study.MODEL,
    'provider': final.study.PROVIDER,
    'reasoning': final.study.EFFORT,
}])
```

The root then saves `final.expected_review(manifest, manifest_sha, final.BASE / 'budget.json', final.sha(final.AUTHORITY))` to `final.STAGE / 'suffix.root-review.json'` using exclusive creation after reviewing the current authority head. The controller does not create or approve that receipt. Only after both reviewed records exist is the bounded dispatch command:

```text
python3 scripts/gemma26_v2_final_suffix.py run \
  --budget-manifest results/repeatability-v1/gemma26-on-fresh-matched3-v2/final-suffix-047-060-v1/budget.json \
  --root-review-receipt results/repeatability-v1/gemma26-on-fresh-matched3-v2/final-suffix-047-060-v1/fresh3/P2/suffix.root-review.json
```

The root must recheck the route and both locked ledgers at admission; this offline preparation does not allocate funds or send inference.
