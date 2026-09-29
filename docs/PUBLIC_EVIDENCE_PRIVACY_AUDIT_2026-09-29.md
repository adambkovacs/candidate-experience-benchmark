# Provider account identifier in tracked evidence

**Verdict: REQUEST-CHANGES for any publication that retains the 28 raw files below.** The finding is **BLOCKING**: a normal reader of the public repository can obtain a provider account identifier from `raw_error_response.user_id`. The same identifier occurs 29 times across 28 tracked JSONL files at HEAD. This is account metadata, **not evidence of an API key**. It is nevertheless contrary to the project's [public evidence privacy contract](PUBLIC_EVIDENCE_PRIVACY.md) and goal of keeping private account data out of public evidence. No identifier value is reproduced here.

The audit used `git grep -l '"user_id"' HEAD -- results public-evidence public-site` and parsed the matching JSONL records to count exact JSON field paths. All 29 matches are `raw_error_response.user_id`; none are in `public-site/` or `public-evidence/`. One file has two occurrences. The files below are exact repository-relative paths at HEAD; each link opens the source evidence. The scan is a current-tree inventory, not a history audit. Some public report files contain *links* to these raw files without containing the identifier themselves.

| Tracked evidence file | `raw_error_response.user_id` occurrences |
| --- | ---: |
| [`results/gemini-openrouter-prep-v3/p0-ready-v1/gemini38-flash-high/smoke-attempts.jsonl`](../results/gemini-openrouter-prep-v3/p0-ready-v1/gemini38-flash-high/smoke-attempts.jsonl) | 1 |
| [`results/hosted-unattempted-continuation-v2/openrouter-paid-gemma4-26b-a4b-on-p2/development.jsonl`](../results/hosted-unattempted-continuation-v2/openrouter-paid-gemma4-26b-a4b-on-p2/development.jsonl) | 1 |
| [`results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p1/development.jsonl`](../results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p1/development.jsonl) | 1 |
| [`results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p2/development.jsonl`](../results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p2/development.jsonl) | 1 |
| [`results/mistral119-recovery-prep-v1/high-smoke.jsonl`](../results/mistral119-recovery-prep-v1/high-smoke.jsonl) | 1 |
| [`results/mistral119-recovery-prep-v1/none-smoke.jsonl`](../results/mistral119-recovery-prep-v1/none-smoke.jsonl) | 1 |
| [`results/mistral119-recovery-prep-v2/high-smoke.jsonl`](../results/mistral119-recovery-prep-v2/high-smoke.jsonl) | 1 |
| [`results/mistral119-recovery-prep-v2/none-smoke.jsonl`](../results/mistral119-recovery-prep-v2/none-smoke.jsonl) | 1 |
| [`results/openrouter-mistral119-none-2026-09-23/smoke.jsonl`](../results/openrouter-mistral119-none-2026-09-23/smoke.jsonl) | 1 |
| [`results/openrouter-mistral119-none-cooldown-2026-09-24/smoke.jsonl`](../results/openrouter-mistral119-none-cooldown-2026-09-24/smoke.jsonl) | 1 |
| [`results/openrouter-mistral119-none-recovery-2026-09-23/smoke.jsonl`](../results/openrouter-mistral119-none-recovery-2026-09-23/smoke.jsonl) | 1 |
| [`results/openrouter-mistral24-na-2026-09-23/development-from009-timeout600.jsonl`](../results/openrouter-mistral24-na-2026-09-23/development-from009-timeout600.jsonl) | 1 |
| [`results/openrouter-mistral24-na-2026-09-23/development-from015-partition-recovery.jsonl`](../results/openrouter-mistral24-na-2026-09-23/development-from015-partition-recovery.jsonl) | 1 |
| [`results/openrouter-mistral24-na-2026-09-23/development-from020-partition.jsonl`](../results/openrouter-mistral24-na-2026-09-23/development-from020-partition.jsonl) | 1 |
| [`results/openrouter-mistral24-na-2026-09-23/reconciled-partial-after429.jsonl`](../results/openrouter-mistral24-na-2026-09-23/reconciled-partial-after429.jsonl) | 1 |
| [`results/openrouter-mistral24-na-2026-09-23/reconciled-partial-paused.jsonl`](../results/openrouter-mistral24-na-2026-09-23/reconciled-partial-paused.jsonl) | 2 |
| [`results/openrouter-partition-mistral119-high-2026-09-23/smoke.jsonl`](../results/openrouter-partition-mistral119-high-2026-09-23/smoke.jsonl) | 1 |
| [`results/openrouter-partition-mistral119-none-2026-09-23/smoke.jsonl`](../results/openrouter-partition-mistral119-none-2026-09-23/smoke.jsonl) | 1 |
| [`results/openrouter-qwen3-8b-hosted-plan-2026-09-24/off-p0-smoke3-results.jsonl`](../results/openrouter-qwen3-8b-hosted-plan-2026-09-24/off-p0-smoke3-results.jsonl) | 1 |
| [`results/openrouter-qwen3-8b-hosted-plan-2026-09-24/on-p0-smoke3-results.jsonl`](../results/openrouter-qwen3-8b-hosted-plan-2026-09-24/on-p0-smoke3-results.jsonl) | 1 |
| [`results/prompt-comparison-v1-2026-09-24/qwen27-low-hosted-addendum-v1/P2-development.jsonl`](../results/prompt-comparison-v1-2026-09-24/qwen27-low-hosted-addendum-v1/P2-development.jsonl) | 1 |
| [`results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen36-35b-a3b-on/P1/smoke.jsonl`](../results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen36-35b-a3b-on/P1/smoke.jsonl) | 1 |
| [`results/qwen36-on-p2-final19-v4/development.jsonl`](../results/qwen36-on-p2-final19-v4/development.jsonl) | 1 |
| [`results/qwen36-on-p2-final20-v3/development.jsonl`](../results/qwen36-on-p2-final20-v3/development.jsonl) | 1 |
| [`results/qwen36-on-p2-final21-v2/development.jsonl`](../results/qwen36-on-p2-final21-v2/development.jsonl) | 1 |
| [`results/qwen36-prompt-recovery-v1/off-p2-development.jsonl`](../results/qwen36-prompt-recovery-v1/off-p2-development.jsonl) | 1 |
| [`results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl`](../results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl) | 1 |
| [`results/qwen36-prompt-recovery-v1/on-p2-development.jsonl`](../results/qwen36-prompt-recovery-v1/on-p2-development.jsonl) | 1 |

## Source bindings and current exposure

These are immutable experimental records, not disposable log noise. For example, the [hosted continuation frozen manifest](../results/hosted-unattempted-continuation-v2/openrouter-paid-gemma4-26b-a4b-on-p2/frozen-manifest.json) and its [v3 counterpart](../results/hosted-unattempted-continuation-v3/openrouter-paid-gemma4-26b-a4b-on-p2/frozen-manifest.json) refer to an affected development file. The [Qwen P2 episode manifests](../results/qwen36-on-p2-never-sent-episodes-v1/episode-001/manifest.json) and [generation metadata](../results/generation-metadata-v1/manifest.json) refer to affected Qwen records. Recovery and budget manifests likewise refer to the Mistral and Qwen smoke/development files. The [public explorer data](../public-site/data.json) references some affected raw evidence paths, making the unsanitized tracked bytes easy to reach even though the explorer JSON does not contain `user_id` itself. A path reference alone is not proof of a cryptographic source binding; each binding must be checked when a versioned export is built.

A targeted scan of tracked `results/`, `public-evidence/`, and `public-site/` files found **zero full-format matches** for common `sk-`, `ghp_`, `github_pat_`, `AIza`, `xox*`, and `Bearer` credential patterns. That is a limited pattern scan, not proof that all secrets are absent. The separate [credential audit](CREDENTIAL_AUDIT_2026-09-28.md) describes its broader checks. The confirmed exposure here is a provider account identifier, not a credential. No raw values were printed during this audit.

## Versioned correction without changing frozen inputs

1. First copy each exact affected HEAD blob to private storage outside the public repository, with a private inventory of original path and SHA-256. Verify the copies before changing any tracked path. Keep active controller inputs and frozen manifests byte-identical while runs continue.
2. Build a new `public-evidence/provider-account-redaction-v1/` export from those verified private originals. Remove or replace `raw_error_response.user_id` in every affected JSONL row, including repeated or nested copies discovered by a recursive scan. Preserve response status, failure classification, attempts, request text, prediction, token use, observed cost, and timing. Do not convert unknown cost or outcomes to zero. Emit a mapping from original path and private SHA-256 to public path and SHA-256, with the redaction policy and exporter source hash.
3. At export time, parse both versions and verify record order, IDs, outcomes, predictions, and all retained measurement fields. Verify that no account identifier or credential pattern survives in the public export. Provide a public verifier that checks mapping hashes and report/source bindings from a clean checkout. The public copy cannot independently prove the bytes of the private original; its private SHA-256 is an attestation.
4. Update publication paths and report bindings to the sanitized copy, then test the full clean-checkout build. Only after the private backup and public verifier pass should the raw tracked files be removed from the current tree. Do not rewrite existing experimental manifests, replay requests, or alter live runners. Historical Git commits remain separately exposed unless a later, explicitly authorized history-remediation decision addresses them.

This proposal follows the existing [Claude public export boundary](PUBLIC_EVIDENCE_PRIVACY.md) and [exporter](../scripts/export_claude_public_evidence.py), but needs a versioned provider-error JSONL exporter and tests. **RESIDUAL:** the targeted credential scan may miss other formats, and current-tree removal alone will not erase earlier public Git history. Neither limits the confirmed account-identifier exposure or the publication block.

## Prepared export and publication handoff

The new [provider-error exporter](../scripts/export_provider_error_public_evidence.py) now validates the 28 exact original SHA-256 values and the tracked file set before writing. It rejects unfamiliar provider-error fields, changed removal counts, a second occurrence of an account identifier elsewhere in a row, and credential-like text under the current policy. It removes only `raw_error_response.user_id`, compares every other parsed JSON value, and writes [28 sanitized JSONL copies and a provenance manifest](../public-evidence/provider-errors-v1/manifest.json). The manifest contains source and public hashes, row counts, and the removed field path/count; it contains no identifier value. The [regression tests](../tests/test_export_provider_error_public_evidence.py) cover field fidelity, drift, tampering, idempotence, and public-only verification. `--check` requires the private originals; `--check-public` verifies the published bundle without them. The latter cannot establish fidelity to private bytes on its own.

Publication is **not yet corrected**. The 28 original files remain tracked and readable in the public repository while live work uses their frozen hashes. The next coordinated release needs a versioned public binding resolver, not a substitution in the old manifests:

- [The public explorer builder](../scripts/build_public_explorer.py) emits evidence URLs and source bindings into [data.json](../public-site/data.json), which currently names ten affected files. Regenerate a public projection with explicit `originalPath`/`privateOriginalSha256` and mapped `publicPath`/`publicSha256`, keeping original experimental hashes as attestations. Its downstream [findings builder](../scripts/build_findings.py) and tests need to bind that new projection. The Pages workflow currently only validates `data.json` syntax; add an export verifier and a deterministic public-data check.
- The [Qwen-off continuation report builder](../scripts/build_qwen36_off_continuation_findings.py) and its [published report](../public-site/qwen36-off-continuation-findings.json) bind an affected recovery file. The hosted continuation, Qwen episode, recovery, and generation-metadata manifests also reference affected originals. Preserve those manifests; adapt public-facing report checks to a separate sanitized-source mapping with score, failure, cost, and token fidelity. Existing live [Qwen admission code](../scripts/qwen36_off_fresh_repeat_admission.py) and other controllers must continue seeing their original bytes.
- [Pages checks](../.github/workflows/pages.yml) presently run the hosted wave, Qwen continuation, public findings, and other report verifiers against checked-out `results/`. Before untracking the 28 originals, run every affected check from a clean staged checkout using only sanitized public evidence and versioned report projections. `git rm --cached` can retain local copies for active work, but it makes originals absent in CI; without the resolver and verifier, that would break publication checks. Coordinate this step with the owner of live Qwen runs.

The prepared exporter does **not** remove originals, change Git history, rewrite existing frozen evidence, or update a public report. Earlier commits remain accessible after any current-tree cleanup. The exact account identifier may be a provider user ID rather than an authentication secret; credential rotation is not inferred from this evidence.

## Versioned explorer and findings candidates

A separate [binding projector](../scripts/project_provider_error_public_bindings.py) maps the affected links in saved [data.json](../public-site/data.json) to the sanitized copies. It produced [data-provider-errors-v1.json](../public-site/data-provider-errors-v1.json) and a [projection manifest](../public-site/provider-error-projection-v1.manifest.json). Ten distinct source files appear in twelve explorer links. The projection records both the private original SHA-256 **attestation** and the actual public-copy SHA-256; it never returns the private hash as though it verified the sanitized bytes. Every non-link value in the explorer data is unchanged. The [findings candidate](../public-site/findings-provider-errors-v1.json) was rebuilt from that projected data; its score charts equal the current [findings.json](../public-site/findings.json) exactly. These are candidate filenames, not a switch of the site's active feeds.

The existing [explorer builder](../scripts/build_public_explorer.py) now has a `--provider-error-projection` mode that reads saved public data and verified sanitized evidence without reading any of the 28 originals. Its default full rebuild is unchanged and still needs original evidence. The [findings builder](../scripts/build_findings.py) accepts explicit `--source` and `--output` paths for the candidate, while its default remains `data.json` to `findings.json`. A temporary checkout fixture containing public data, the sanitized bundle and labels, but **no `results/` directory**, ran both projection and findings commands and reproduced the same score charts. The focused [projector tests](../tests/test_project_provider_error_public_bindings.py) cover link-only rewrites, distinct private/public hashes, unsupported path context, and the clean public fixture.

Review commands from the repository root:

```sh
python3 scripts/export_provider_error_public_evidence.py --check
python3 scripts/export_provider_error_public_evidence.py --check-public
python3 scripts/build_public_explorer.py --provider-error-projection --check
python3 scripts/build_findings.py --source public-site/data-provider-errors-v1.json --output public-site/findings-provider-errors-v1.json --check
python3 -m unittest -q tests.test_export_provider_error_public_evidence tests.test_project_provider_error_public_bindings tests.test_findings
```

The private `--check` still requires each original's pinned bytes but now permits the files to be untracked later; it rejects any *additional* tracked `user_id` file. `--check-public` needs no originals. **Remaining publication blockers:** the site's active `data.json` and `findings.json` still use the old links; the default full explorer rebuild and other raw-source report/verifier commands in [Pages checks](../.github/workflows/pages.yml) still expect originals in a clean checkout. In particular, the [Qwen continuation builder](../scripts/build_qwen36_off_continuation_findings.py), recovery reports, and frozen source-bound checks need their own reviewed public binding or private-only verification mode. This task has not changed those commands, the workflow, or any frozen input. Untracking the originals before that coordinated migration would create a normal CI regression. The current Git tree and its history still disclose the identifier.

## Shared public report source resolver

The [public source resolver](../scripts/resolve_provider_error_public_source.py) and [shared hosted-report file/binding helper](../scripts/build_deepseek_fresh_repeat_findings.py) now resolve an audited private path to its verified sanitized copy for **reporting only**. They choose the public copy even when a local original is present. The returned binding's `path` and `sha256` identify the actual public bytes; `privateOriginalPath` and `privateOriginalSha256Attestation` carry the frozen hash separately with `privateOriginalVerification: not_rehashed_by_public_report`. An expected historical hash must equal the export manifest's original hash. An altered public file or unknown mapped path fails closed. The frozen execution controllers and manifests remain unchanged.

The [additional hosted reporter](../scripts/build_additional_hosted_fresh_repeat_findings.py), [first Qwen continuation reporter](../scripts/build_qwen36_off_continuation_findings.py), and [second-interruption reporter](../scripts/build_qwen36_off_second_interruption_findings.py) delegate their `file`/`bind` calls to that shared helper. At the reviewed snapshot, the DeepSeek-low additional report has no affected binding; each Qwen continuation report maps the affected off-P2 development JSONL once. Their existing source checks still compare the **private** hash against the manifest, while the emitted public binding uses the **public** hash. Focused [resolver tests](../tests/test_resolve_provider_error_public_source.py) cover both local-original-present and original-absent cases. The relocated Qwen reporter fixtures now include the verified public bundle, remove all 28 audited originals, and still build the partial or strictly closed synthetic phases. These tests do not prove that every other report command is portable after untracking.

Candidate regeneration commands (write to a review path or coordinated public output, never over an active frozen artifact):

```sh
python3 scripts/build_additional_hosted_fresh_repeat_findings.py --configuration openrouter-paid-deepseek-v41-flash-low --output /private/tmp/provider-mapped-additional-report.json
python3 scripts/build_qwen36_off_continuation_findings.py --output /private/tmp/provider-mapped-qwen-prior-report.json
python3 scripts/build_qwen36_off_second_interruption_findings.py --output /private/tmp/provider-mapped-qwen-second-report.json
python3 -m unittest -q tests.test_resolve_provider_error_public_source tests.test_additional_hosted_fresh_repeat_findings tests.test_build_qwen36_off_continuation_findings tests.test_build_qwen36_off_second_interruption_findings
```

The normal Pages report checks still need regenerated public JSON matching these bindings. A clean staged checkout must then run the complete workflow before the originals are untracked, because other readers of the 28 raw paths may bypass this shared helper. The provider export's original hashes remain attestations after untracking; a public reader can verify the sanitized copy but cannot reconstruct the removed account field or authenticate the private original.


## Current-tree release verification, 2026-09-29

All 53 Pages static commands now pass in a public-only snapshot with the 28 private originals absent. Fifty passed on the first pass; the three fixture-dependent commands passed after test-only corrections and initialization of a real temporary Git checkout. The final source, tests, reports and active public-feed bytes match the staged release; remaining snapshot differences are documentation and ignore rules. The synthetic tests retain their source and public-copy hash checks; no frozen execution controller was changed and no test was skipped.

The release removes the 28 originals from Git tracking while preserving their exact bytes locally and in a separately hash-verified private backup. Exact ignore rules prevent accidental re-addition. The site now selects the sanitized data and findings projections, and both Qwen reports bind the sanitized public file hash separately from the private original attestation. All nine Qwen condition/pass results are included in the new report. Earlier sections above describe the migration checkpoints; their statements that active feeds were unchanged or originals still tracked are superseded by this release.

Historical commits may still contain the provider account identifier. This release does not rewrite Git history or claim historical erasure. Deployment and live-file verification remain pending until the release workflow succeeds.
