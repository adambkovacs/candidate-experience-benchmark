# Public results explorer

The static public view lives in `public-site/`. It contains only the site assets and an explicitly allowlisted export of saved outcomes, synthetic feedback, provisional references, timing, token usage and reported charges. It excludes API credentials, raw requests, local filesystem paths, internal journals, budget balances and outstanding-work notes.

The public page separates valid output from agreement with each of the four provisional judgments. Every score uses the 60-record development denominator. Configuration views can overlap or include retries and are not independent model samples. Paired prompt findings are observational.

Run `python3 scripts/build_public_explorer.py` after refreshing the underlying reports. This reads `results/comparison/summary.json`, `cases.json`, and eligible saved paired evaluations. It counts batch tokens once per request, preserves missing usage, and never converts subscription API-equivalent estimates into actual charges. Cache and reasoning counts retain provider semantics. Timing is summed request time, not wall time or a cross-provider speed ranking.

Validate with `python3 -m unittest discover -s tests -p test_public_explorer.py` and `node --check public-site/app.js`. Serve the repository locally and open `/public-site/` to review.

For Vercel, deploy **only `public-site/`** as a static project with no build command. Do not deploy the repository root. No backend, account connection, inference key or paid service is needed by the page. No public deployment was created by this implementation.
