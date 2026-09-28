# Codex repeat roster controller

`scripts/codex_repeat_roster.py` prepares the remaining 15 Codex subscription configurations whose frozen historical P0/P1/P2 triples are marked `eligible_first_pass` in `results/repeatability-v1/coverage.json`. It does not include the dedicated GPT-6 Luna medium, GPT-6 Sol high, or separately audited GPT-6 Sol medium lanes. It rejects configurations outside its explicit roster and does not admit max or ultra effort.

The controller reconstructs each historical batch of ten from the saved 60 development inputs, rubric, P0/P1/P2 prompt files, output schema, paired manifest, and raw request attempts. All six original batches per condition must have the exact saved prompt, schema, membership, model, effort, timeout, ChatGPT auth mode, successful status, and reference isolation. These sources, the frozen runner, and this controller are hash-bound in each new plan. No reference labels or earlier predictions are read for inference preparation. The first observed order is rotated across repeat two and three; each condition gets a new three-record smoke and six fresh batches of ten.

Preparation is offline. For example:

```sh
python3 scripts/codex_repeat_roster.py --config codex-gpt-5.6-luna-high prepare
python3 scripts/codex_repeat_roster.py --config codex-gpt-5.6-luna-high runtime-check
```

Preparation exclusively creates `repeat2/manifest.json` and `repeat3/manifest.json` under that configuration's results folder. Stop if either already exists. Review both byte hashes, the source bindings, historical request reconstruction, actual order, subscription availability, and quota before dispatch. Do not run `prepare` again to overwrite a frozen plan. The read-only runtime check verifies the local CLI version, ChatGPT login, and required flags; it does not make a model request or prove quota availability.

Every smoke or development phase requires an exact root-review receipt held **outside this public repository**. Pass its absolute private path and SHA-256 hash. Keep account quota figures and the private path out of commits. The receipt has `schema: "codex-repeat-roster-root-review-v1"`, `approved: true`, exact `configuration_id`, `repeat`, `condition`, `phase`, `manifest_sha256`, `controller_sha256`, `model`, `effort`, and `runtime: "codex-cli 0.155.0-alpha.16.4"`. A development receipt must also bind the inspected smoke file through `smoke_inspection_sha256`; a smoke receipt must leave that field absent or null. Its private `quota` object records `source: "Codex get_usage_limits"`, `checked_at_utc` in UTC, `ordinary_usage_allowed: true`, `spend_control_reached: false`, positive `weekly_remaining_percent`, and positive `five_hour_remaining_percent` when reported (otherwise `null`). The quota observation must be at most five minutes old at admission. A changed or stale receipt fails before the runner checks login or calls the model. This snapshot does not guarantee quota for the entire phase. No paid overage or reset credit is authorized.

After validation, the wrapper writes a public `smoke.admission-<review hash>.json` or `development.admission-<review hash>.json` in the phase folder. It contains the exact phase, model, plan and controller hashes, the private receipt hash, and `dispatch_status: "not_asserted"`. It contains no account figures or private path. **Admission is not dispatch:** if the CLI/runtime check fails before the first request, this attestation remains but the frozen runner has no started phase journal. Review the runner's claim, journal and attempts to determine what actually happened.

After a reviewed receipt exists, dispatch the next condition in the plan's order. Replace the placeholders with the reviewed paths and hashes:

```sh
python3 scripts/codex_repeat_roster.py --config codex-gpt-5.6-luna-high smoke --repeat repeat2 --condition P2 --manifest-sha256 PLAN_SHA256 --review-receipt /private/tmp/PRIVATE_REVIEW.json --review-sha256 REVIEW_SHA256
python3 scripts/codex_repeat_roster.py --config codex-gpt-5.6-luna-high inspect --repeat repeat2 --condition P2 --manifest-sha256 PLAN_SHA256 --note 'Three raw smoke results inspected; unchanged controls and valid predictions.'
python3 scripts/codex_repeat_roster.py --config codex-gpt-5.6-luna-high development --repeat repeat2 --condition P2 --manifest-sha256 PLAN_SHA256 --review-receipt /private/tmp/PRIVATE_DEVELOPMENT_REVIEW.json --review-sha256 NEW_REVIEW_SHA256
```

Development needs its own fresh root review, bound to the same frozen plan and the inspected smoke. The private frozen runner enforces a new ephemeral CLI context per request, the original parser, exclusive phase claims, durable started/completed/stopped evidence, exact condition order, no automatic retry, and a stop on the first non-OK batch. It strips API-key environment variables. A stopped or ambiguous phase is not resumed by this controller; preserve its evidence and use a separately reviewed recovery decision. Repeat three cannot begin before all repeat-two development conditions complete.

The offline preflight on 2026-09-28 found the local CLI at `0.155.0-alpha.16.4` with ChatGPT login active. Quota observations stay in the private receipt and must be refreshed for each dispatch. The CLI patch change and hidden serving behavior remain observational limitations, as recorded in each plan.
