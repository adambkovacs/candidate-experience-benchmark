# Public results explorer

The static public view lives in `public-site/`. It contains site assets and an explicitly allowlisted export of saved outcomes, synthetic feedback, provisional references, timing, token usage and recorded charges or estimates. It excludes credentials, raw requests, local filesystem paths, internal journals, budget balances and outstanding-work notes.

The visible project name is **Candidate Experience Feedback Benchmark**. The GitHub repository is `adambkovacs/candidate-experience-benchmark`, renamed from `recruitment-feedback-demo` on 2026-09-24. Historical evidence retains original paths and identifiers so frozen hashes are unchanged. The existing local checkout directory also retains its original name to avoid breaking active processes.

## Build and validate

Run `python3 scripts/build_public_explorer.py` after refreshing saved reports, then `python3 scripts/build_findings.py` to rebuild the analysis. The exporter reads baseline and prompt evidence, with explicit condition and eligibility information. Native interfaces and descriptive comparisons remain distinct from audited generative prompt pairs.

Run `python3 scripts/build_findings.py --check`, `python3 -m unittest discover -s tests -p test_findings.py`, `python3 -m unittest discover -s tests -p test_public_explorer.py`, and `node --check public-site/app.js`. Serve the repository locally and open `/public-site/` to inspect filters, comparisons and case details.

Every score uses the 60-record denominator. Configuration views may overlap or include continuations; they are not independent model samples. Validity means conformance to the output contract, while agreement means a judgment matches a provisional reference.

## Findings and reproducibility

The page leads with analysis of prompt changes, Jev's disagreement patterns, observed costs and reviews that need closer inspection. `scripts/build_findings.py` computes `public-site/findings.json` from saved evidence. Its source hashes and cohort definitions make the selection and arithmetic inspectable; `--check` rejects a stale generated file.

The [findings report](FINDINGS.md) explains the observed patterns and reference-adjudication priorities. Charts retain exact-value tables and evidence links. Links can select an individual review with `?run=<run-id>&case=<review-id>#inspect`. Rebuilding analysis never runs a model or changes reference labels.

## Resource reporting

Batch usage is counted once per request. Missing usage stays unknown. Cache and reasoning counts retain provider semantics. Subscription API-equivalent estimates are not actual charges.

TypeSafe Jev exposes a token-price estimate in the saved evidence. The public view labels it separately from observed charges. Unknown-charge bounds are retained separately and must not be described as money spent.

Timing is measured request duration, not total experiment wall time. Failed attempts can contribute to duration. Single-record calls, ten-record subscription batches and native specialist operations are different workloads. Local timing is diagnostic and depends on hardware, runtime and quantization; it must not be used as a hosted speed ranking.

## Publish

The site needs no server, account connection, inference key or paid hosting service. The [GitHub Pages workflow](../.github/workflows/pages.yml) publishes **only `public-site/`**, using GitHub's [documented custom workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Pushes that change the public bundle trigger deployment; manual dispatch is also available.

The live public URL is https://adambkovacs.github.io/candidate-experience-benchmark/. The initial redesigned release deployed successfully in [GitHub Actions run 36056691201](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36056691201) and was checked in the browser with 244 saved views. Nine exporter tests, JavaScript syntax checks, desktop interactions and a 390-pixel mobile layout check passed. Deployment and browser checks should be repeated after later releases. Vercel remains an alternative static host, with `public-site/` as its project root and no build command.
