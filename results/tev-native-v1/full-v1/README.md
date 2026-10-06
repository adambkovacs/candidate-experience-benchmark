# Tev Decisions full-pass candidate

This executor is **prepared but unapproved**. It has made no new allocation or request. It uses the [frozen nine-phase plan](../plan.json): three fresh passes, each with P0, P1 and P2 over the same 60 input-only development records. The [three-review P0 smoke](../smoke.closure-audit.json) is reused once; the candidate has nine development stages and eight new three-review smokes. Every later stage requires the prior development stage to be complete, a reviewed stage receipt, and an accepted smoke inspection before its 60 requests.

The [OpenRouter Decisions reference](https://github.com/OpenRouterTeam/skills/blob/main/skills/openrouter-decisions/references/decisions-api.md) defines the typed Choice response and makes probabilities and confidence optional. This configuration pins `togethercomputer/tev1-4b-experimental`, provider `together`, revision `20260923`, four Choice questions, and the [public route price](../../route-audits/tev-public-20261006-evening/endpoints.json). The runner retains reported probabilities and confidence when present. It also retains actual output-token counts; the accepted smoke reported eight output tokens per request, while the listed completion price is zero. These fields do not establish calibration.

The proposed separate OpenRouter-only child cap is **$1.00**, subject to independent review and a new v4 authority hold. Each call reserves **$0.005505024**, four 32,768-token contexts at the listed input rate; actual known cost replaces the reserve after settlement. This rolling reserve stops before the child cap is crossed. The catalog names a Qwen3 tokenizer, but no all-540-request context fit has been proven. A context violation, unknown cost, provider error or transport error stops that stage with the original attempt retained. Sent positions are never retried by this adapter.

The [manifest](manifest.json) binds the original smoke, sealed child reconciliation, frozen request hashes, source files and public route snapshot. The [root review template](root-review.json) is unapproved. No full stage may run until review, allocation and a matching authority hold; each stage then needs its own root receipt. The first eligible stage is `fresh1/P0` development. No stage has been admitted.

Offline checks:

```sh
PYTHONPATH=scripts python3 scripts/tev_full_execution_v1.py verify
PYTHONPATH=scripts python3 -m unittest tests.test_tev_full_execution_v1 -q
```
