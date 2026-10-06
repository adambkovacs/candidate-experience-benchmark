# Tev OpenRouter Decisions smoke candidate

This is an **offline, unapproved** three-review smoke candidate. It has sent no Tev inference and has no budget allocation. The [frozen plan](plan.json) contains 60 input-only reviews for each of P0, P1 and P2 across three fresh passes. Only fresh1/P0 DEV-001–003 is runnable through the current smoke adapter. References stay outside requests and scoring remains offline.

The route is `togethercomputer/tev1-4b-experimental` through OpenRouter's [Decisions API](https://github.com/OpenRouterTeam/skills/blob/main/skills/openrouter-decisions/references/decisions-api.md), pinned to provider `together` and returned revision `togethercomputer/tev1-4b-experimental-20260923`. The [public endpoint snapshot](../route-audits/tev-public-20261006-evening/endpoints.json) lists a 32,768-token context and $0.042 per million prompt tokens with zero completion price. [The public audit](../route-audits/tev-public-20261006-evening/audit.json) documents the distinction from Together's direct generated-letter interface. Neither public listing proves this account can call Tev.

Each review sends the same four frozen Choice questions used in the native Jev/Liquid format. The adapter retains probabilities and confidence when present and marks each absent field unavailable. It does not infer their meaning or calibration. The worst-case reserve is four complete contexts × 32,768 tokens × $0.000000042 = **$0.005505024 per review**; the three-review smoke reserves **$0.016515072** inside a proposed **$0.025** OpenRouter-only child. This is a conservative billing bound, not a proof that every request fits the context. The plan's nine-pass total is planning information, not approval for nine passes.

Before any request, an independent reviewer must check the [candidate bindings](smoke-candidate.json), current endpoint/price, exact child allocation and v4 authority hold, then issue the root review receipt. The smoke runner refuses missing or mismatched review, budget, hold, route or request bytes. It claims the three positions once, reserves before each call, captures response bytes and preserves unknown costs. It never retries a sent position. Inspect all three wire responses and their optional fields before considering a full pass.

Offline checks:

```sh
PYTHONPATH=scripts python3 scripts/tev_native_v1.py verify
PYTHONPATH=scripts python3 -m unittest tests.test_tev_native_v1 -q
```

The proposed live entrypoint, **only after allocation and approval**, is:

```sh
PYTHONPATH=scripts python3 scripts/tev_smoke_v1.py run --receipt results/tev-native-v1/smoke.root-review.json --budget results/tev-native-v1/budget-manifest.json
```
