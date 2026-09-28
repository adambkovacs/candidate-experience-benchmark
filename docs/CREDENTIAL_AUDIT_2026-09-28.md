# Credential audit, 28 September 2026

No exposed API credential was identified by the checks below. The repository-local `.env` is ignored, untracked and restricted to owner read/write access (`0600`). The committed `.env.example` contains empty values. Hosted adapters load selected keys from an environment variable or an explicitly supplied `.env` file; keys are not saved as configuration values.

An exact byte-match scan checked 15,592 tracked files against 34 secret values loaded privately from the existing local environment file. It found no matches and printed no values. This verifies those known values only.

A redacted Gitleaks history scan covered 327 commits and approximately 1.08 GB through the checkpoint containing `9cca967`. It reported 3,994 detections, all under its generic API-key rule. A separate audit inspected the actual Git blobs at every reported commit, file, line and column:

| Classification | Detections |
| --- | ---: |
| SHA-256 token, tokenizer or source-file digests | 3,991 |
| Local model identifiers in `modelKey` metadata | 3 |
| Unresolved detection locations | 0 |
| Identified credentials among these detections | 0 |

The classification examined 44 distinct commit/file blobs. The redacted scanner report has SHA-256 `2ef3dd61ab92f6d8f028c832659a83eb06b1080fba946fd49fdf6316822a09ea`. Detailed scanner and classification reports remain private; candidate values were not copied into documentation or memory. No broad scanner exemption or history rewrite was introduced.

These results describe the checks performed, not proof that every possible secret is absent. They do not resolve the separate historical provider-account-metadata issue in the [public evidence privacy record](PUBLIC_EVIDENCE_PRIVACY.md). New publications still require credential and privacy review. See [credential setup](CREDENTIALS.md) for the required local `.env` workflow.
