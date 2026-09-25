# Qwen P2 continuation result

The exact Qwen 3.6 35B A3B thinking-on route through AkashML/fp8 returned HTTP 429 for DEV-042. The provider identified a shared upstream pool queue timeout. Execution stopped after this one request; no retry or model substitution occurred. DEV-043 through DEV-060 remain unsent.

The accumulated P2 evidence now contains 37 valid outputs and five service errors across 42 attempted records. It is not a complete paired prompt comparison. Earlier failures and timings remain unchanged. See [reconciliation.json](reconciliation.json) for the source hashes and exact IDs.

The actual charge for DEV-042 is unavailable. The ledger retains its full $0.0299008 reservation as an unknown-cost upper bound and releases the rest of the $0.60 allocation. Aggregate accounted usage is $6.04068449650, including historical unknown-cost upper bounds, leaving $3.95931550350 under the approved $10 cap. This is not a claim that the provider billed the reserved amount.

The first process invocation stopped before any network request because no key was present in its environment. The subsequent invocation used the previously authorized local credential file. It made one inference request, as recorded in the closed attempt journal. No reference labels or prior predictions were sent.

The public endpoint preflight showed the exact route, controls and prices, but did not establish available request capacity. No further automatic continuation is scheduled for this rate-limited route.
