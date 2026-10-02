# Run selection, prompt coverage and subscription prices

The Resource use and Individual run sections now each have a run selector. Both update the same selected run and URL, so readers do not need to return to the top of the page. Historical single-comment Fable, Sonnet and Opus views link to their later batch-of-ten prompt series where available. A missing historical condition is not filled with results from a different request setup. See the [coverage audit](PROMPT_COVERAGE_AUDIT_2026-10-02.md).

The [subscription price feed](../public-site/subscription-price-estimates.json) provides current public API-equivalent estimates, with exact model rate sources and dates. These estimates include measured cache reads and writes and count reasoning within output once. They are not subscription bills. The original Fable high run in the reported screenshot is estimated at $1.19895; its separate batch-of-ten P0 is $0.60676. [Pricing methods and missing values](SUBSCRIPTION_PRICE_ESTIMATES.md) explain the calculation.

The user confirmed that a person checked all 60 reference answers. Current website copy reflects that confirmation. Original versioned labels, earlier audit findings and historical scores remain intact.

Verification: all 103 UI tests and 9 Python pricing/reader tests passed. A browser check at 1440×1000 verified the historical-to-matched-series link, lower-page selector, cache token fields, price and source link. At 390×844, both selectors stayed synchronized and document width equaled viewport width, with no horizontal overflow. These checks establish the local revision; publication is verified separately after deployment.

Publication verified: commit `4efe38ff` passed [Pages run 36989523124](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36989523124). Live HTML, application scripts, presentation CSS and price feed match the published commit byte-for-byte. The preceding failed CI deployment did not replace the live site; its clean-checkout pricing dependency was fixed and retested.

The Sonnet follow-up adds four effort settings and links the older Claude/Codex views to their completed comparable series. Its records are available as source JSONL; the current individual-comment panel links those records rather than reconstructing them. A local browser check verified that selecting Sonnet high/P2 in Resource use also updates the Individual run selector and URL. The 390px layout has no horizontal overflow.

Final Sonnet checks: all 36 development closures and 12 manifests verified. The repeat explorer rendered all nine xhigh scores, each 58/60, on desktop and 390px mobile without horizontal overflow. Synthetic stopped-phase and missing-usage checks preserve partial outcomes and prevent absent token data from appearing as a zero price. The repeat section reports pairwise changes without implying that the completed series is still running.

The final reporter passed all three focused tests, including a public-only checkout. The 11 pricing/reader tests passed. Export validation confirms all 688 evidence mappings; no private raw captures outside the sanitized bundle are staged. The staged secret scan passed, and the active OpenRouter ledger and ignored `.env` remain outside the commit.

The final expanded UI suite passed 114 tests, including synthetic closed runs with missing usage and distinct stopped/running/unstarted phases.
