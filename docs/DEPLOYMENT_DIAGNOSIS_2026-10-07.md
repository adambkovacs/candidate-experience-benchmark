# Pages deployment diagnosis, 7 October 2026

Retry Pages once for the final integrated release. Both failed runs have confirmed GitHub server errors. The evidence does not identify a static-bundle defect, and a Vercel fallback still needs account usage and cost verification to satisfy the user's no-new-hosting-charges constraint.

## Confirmed failures

| Run | Commit | Evidence | Failure boundary |
| --- | --- | --- | --- |
| [37654306323](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37654306323) | `bde58866c3ffe4458951075315d4beef0ee440cb` | Checks, artifact upload and deployment succeeded. | Last successful release in the inspected run list. |
| [37654945050](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37654945050/job/112907862324) | `102149b0c3d436c9144993ce084a7131f417eb5a` | Static checks, Pages configuration and artifact upload succeeded. `actions/deploy-pages@v4` then returned HTTP 500 when creating the deployment at 16:57:16 UTC. | GitHub Pages deployment API. |
| [37655106691](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37655106691) | `f1901937c4a78986c4b519a880b8849155facda4` | The run summary annotation reports `Internal server error. Correlation ID: 6441eff8-0f6d-41fd-a58e-cadbe2cf7c75`. REST reports zero jobs, zero check runs and zero artifacts; its downloadable log ZIP has zero entries. | GitHub Actions before any job started. |

The first failure's request ID is `BC21:94B20:1DFC9AE:60B5E38:6AC679E8`. Its uploaded `github-pages` artifact is `11497684708`, 6,293,829 bytes, with expiry at 16:57:09 UTC on 8 October. The action's error recommends rerunning later.

The workflow file is unchanged between successful `bde58866` and failed `f1901937`. It has a manual dispatch trigger, `pages: write` and `id-token: write` permissions, and one concurrency group with `cancel-in-progress: false`. No workflow edit follows from these failures. See [the workflow](../.github/workflows/pages.yml).

[GitHub Status](https://www.githubstatus.com/) reports Actions and Pages operational at inspection. Its 7 October incident was resolved at 16:25 UTC, before these failures. That incident is context; the available evidence does not establish that it caused the later errors. GitHub's internal root cause remains unknown.

## Recommended release action

After root commits, checks and pushes the integrated release, dispatch its remote `main`:

```bash
gh workflow run pages.yml --ref main --repo adambkovacs/candidate-experience-benchmark
gh run list --workflow pages.yml --repo adambkovacs/candidate-experience-benchmark --limit 5 --json databaseId,headSha,status,conclusion,url
```

Confirm the new run's `headSha` matches the intended pushed release. Wait for its terminal result, then fetch the changed public assets and compare their bytes with that exact commit. An HTTP 200 alone does not confirm the updated release. Existing [publication evidence](TODO.md) remains the baseline until those checks pass.

Rerunning the old successful or failed SHA would publish an older bundle. If the release remains exactly `f1901937`, the alternative is `gh run rerun 37655106691 --repo adambkovacs/candidate-experience-benchmark`; a new integrated release needs a fresh dispatch.

## Vercel fallback readiness

The Vercel plugin's `list_teams`, `list_projects` and `get_team` calls succeeded. The accessible team is `AI Enablement Academy's projects` (`ai-enablement-academys-projects`, `team_i4H55wCP0O5bOS8GYWoF6KvF`). Its complete 18-project response contains no candidate-experience benchmark project. These calls establish connector access; they do not establish zero-cost deployment authority.

Vercel CLI 61.1.0 is installed. `vercel project inspect --non-interactive` returns `link_required` from both the repository root and `public-site`. [The existing static configuration](../public-site/vercel.json) sets clean URLs and response headers. The fallback should publish only the reviewed, committed `public-site` bundle into a separate benchmark project after the intended team, current plan, remaining included usage and spend controls have been checked.

[Vercel's usage documentation](https://vercel.com/docs/pricing/manage-and-optimize-usage) lists CDN requests, transfer, build minutes and deployment storage as priced resources. The connector's team response exposes no billing plan or usage fields, so zero incremental cost is unverified. Do not substitute a bare `vercel --prod` command in the unlinked working directory. If the fresh Pages dispatch fails again, resolve those Vercel facts before deployment; preserve the Pages errors and avoid changes to unrelated projects, billing or domains.

## Inspection boundary

This diagnosis used GitHub REST/CLI run records and logs, the public Actions summary, GitHub Status, read-only Vercel connector calls and CLI project inspection. It did not deploy, change hosting or billing, rerun inference, reveal credentials, or use a browser workaround. Root owns the integrated release and its publication verification.
