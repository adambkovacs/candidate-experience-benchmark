# Run selection, prompt coverage and subscription prices

The Resource use and Individual run sections now each have a run selector. Both update the same selected run and URL, so readers do not need to return to the top of the page. Historical single-comment Fable, Sonnet and Opus views link to their later batch-of-ten prompt series where available. A missing historical condition is not filled with results from a different request setup. See the [coverage audit](PROMPT_COVERAGE_AUDIT_2026-10-02.md).

The [subscription price feed](../public-site/subscription-price-estimates.json) provides current public API-equivalent estimates, with exact model rate sources and dates. These estimates include measured cache reads and writes and count reasoning within output once. They are not subscription bills. The original Fable high run in the reported screenshot is estimated at $1.19895; its separate batch-of-ten P0 is $0.60676. [Pricing methods and missing values](SUBSCRIPTION_PRICE_ESTIMATES.md) explain the calculation.

The user confirmed that a person checked all 60 reference answers. Current website copy reflects that confirmation. Original versioned labels, earlier audit findings and historical scores remain intact.

Verification: all 103 UI tests and 9 Python pricing/reader tests passed. A browser check at 1440×1000 verified the historical-to-matched-series link, lower-page selector, cache token fields, price and source link. At 390×844, both selectors stayed synchronized and document width equaled viewport width, with no horizontal overflow. These checks establish the local revision; publication is verified separately after deployment.
