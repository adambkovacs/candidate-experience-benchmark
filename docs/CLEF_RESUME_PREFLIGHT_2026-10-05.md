# Clef Flash fresh1/P1 smoke preflight, 5 October 2026

This is a single-stage preparation record for `clef-flash/fresh1/P1/smoke`. It authorizes no call and creates no ledger hold. It follows the exact stage, request bytes, context, and reservation declared by the frozen [remaining-stage manifest](../results/clef-native-v1/repeat-continuation-v1/remaining-admission-v1.json). No interrupted Flash request is resumed: the prior `clef-flash/fresh3/P0` DEV-001 outcome remains unknown and is outside this stage.

## Read-only checks

- `python3 scripts/clef_native_remaining.py verify` passes. It prints manifest SHA-256 `51714fb352a47cb01d7a0f7236eb17625e933ee83af44fafc8d411af6bf6685c`.
- The exact routes in the frozen preparation are `@cf/cloudflare/clef` and `@cf/cloudflare/clef-flash`, each with 65,536 context. Root's 5 October connected-app catalog check found both exact model IDs and unchanged input prices: $0.24/M and $0.09/M respectively. The [official Clef Flash page](https://developers.cloudflare.com/workers-ai/models/clef-flash/) remains byte-identical to its frozen billing capture, SHA-256 `9bef672524b4f3a0b4111c122024c3081b498840162c8c267931101d221ad15c`.
- A refreshed shared-lock read of `results/postapproval-paid-work-2026-10-02.jsonl` found 17 holds totaling $5.797692 under the separate $10 authority, leaving $4.202308 at head SHA-256 `54d7a21fd3f32a7006e4c02e4e55afdfd1f0f608b525e0565da6c332ad7a8bc5`. The added $0.09 Mistral hold made the earlier candidate head stale; the candidate now binds this refreshed head. The proposed smoke reserves $0.017697 at the full 65,536-token context. No hold was appended.
- The live account-usage/quota endpoint was not found by the connected-app read. An earlier billing read returned `10000` authorization. Therefore remaining Cloudflare neurons/quota are unknown; the available dollar hold does not establish available provider quota.
- The parent `/Users/adamkovacs/Documents/codebuild/.env` contains the runner's supported aliases `CF_ACCOUNT_ID` and `CF_API_TOKEN`. I loaded them without printing either value and confirmed that the account ID hashes to `785f8836b4eca14fb2bed7716b4214ae99168c0d7ae6f526d08d30f550af08fc`, matching both the candidate and prior reviewed Clef grants; a nonempty token is also present. The connected-app transport does not send the bearer token to Cloudflare. The project-local `.env` lacks these names, but that does not block the parent env-file path.

## Candidate and command

The unapproved candidate is stored outside `remaining-grants/` at [the candidate grant](../results/clef-native-v1/repeat-continuation-v1/candidates/clef-flash-fresh1-p1-smoke-grant-candidate.json). It is deliberately marked `approved: false` and `reviewer: PENDING_ROOT_REVIEW`; the controller will reject it until root completes the exact-stage review and writes an approved grant. It is bound to the current locked authority head and must be rebuilt if that ledger changes.

After root verifies the account hash, reviews the candidate, and places the approved grant in the active grant location, the exact local stage command is:

```sh
python3 scripts/clef_native_remaining.py run --execute --model clef-flash --pass fresh1 --condition P1 --phase smoke --manifest results/clef-native-v1/repeat-continuation-v1/remaining-admission-v1.json --grant results/clef-native-v1/repeat-continuation-v1/remaining-grants/clef-flash-fresh1-p1-smoke-grant.json --env-file /Users/adamkovacs/Documents/codebuild/.env --wait-seconds 300
```

That command requires the verified Cloudflare account ID and a nonempty token in its process environment. It creates a ready request only after durable stage and request reservations. The connected-app operator must POST the saved request body to the exact account path `/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash`, preserve the complete tool result, and submit the app result using:

```sh
python3 scripts/clef_native_remaining.py submit --request <ready-request.json> --app-result-file <saved-app-result.json>
```

An unknown response stops this stage and is not retried. A separate reviewed smoke-result admission is required before any 60-record development stage. The runner's exact grant, predecessor, billing-page, and live-ledger checks are documented in [the continuation controller notes](CLEF_REMAINING_CONTROLLER_2026-10-02.md).

## Execution update

Root subsequently admitted and completed this smoke with three valid responses and reviewed its saved native outputs. See the [closed completion](../results/clef-native-v1/clef-flash/fresh1/P1/smoke/completion.json) and [smoke review](../results/clef-native-v1/clef-flash/fresh1/P1/smoke/root-smoke-review.json). The preparation statements above describe the pre-dispatch checkpoint.
