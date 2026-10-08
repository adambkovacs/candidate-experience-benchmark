# Deck data

- `timeline.json`: decision-model launch wave for S4. Source `docs/talk/02-landscape.md` Part C and Appendix. Hand-curated; `verified` is false where Part C or the Appendix says the date rests on secondary sources.
- `prompt-levels.json`: P0/P1/P2 pass scores for five decision models plus the 39-setup tally, for S12 and A3. Sources `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md`, `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, `docs/FINDINGS.md`. Regenerate with `python3 -I public-site/deck/data/build.py`.
- `hard-cases.json`: 0 to 7 mismatch histogram over 60 reviews and the six reviews with four or more mismatches, for S10. Source `public-site/disputed-reviews-v1.json`. Regenerate with `build.py`.
- `answer.json`: headline scores and costs for S2, S6, S7, each with file and JSON path. Sources are `public-site/findings.json`, `sonnet55-fresh-matched3.json`, `jev-native-prompt-findings.json`, `subscription-price-estimates.json`. Regenerate with `build.py`.
- `build.py`: reads the feeds and docs above, asserts every number, writes the three generated files. It does not touch `timeline.json`.
