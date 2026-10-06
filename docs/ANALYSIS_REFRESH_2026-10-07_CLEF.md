# Clef repeat update, 7 October 2026

The [combined analysis feed](../public-site/analysis-refresh.json) now includes the source-bound [Clef closed-repeat report](../public-site/clef-closed-repeat-findings.json). Its [terminal-evidence builder](../scripts/build_clef_closed_repeat_findings.py) verifies the saved stages; the combined [analysis builder](../scripts/build_analysis_refresh.py) checks the public and reviewed report copies byte for byte, rebuilds the report, and retains its source hashes. The earlier Clef first-pass and P0 checkpoint statements remain dated snapshots.

Seven of the nine declared Clef cells contain 60 valid answers. The three clean P0 passes each matched all four provisional reference labels on 53/60 reviews, with no label changes between passes. P1 scored 52/60, 51/60 and 51/60. One follow-up decision changed between the first pass and each later pass; the later two agreed. Only fresh2/P2 is a clean full pass, scoring 49/60.

Fresh1/P2 has 59 valid answers, 48 known four-label matches and one unknown outcome after its exact never-sent continuation. Fresh3/P2 stopped after one unknown outcome and left 59 reviews unsent. Neither interrupted P2 cell has a clean 60-answer score, so the three-pass P2 repeat comparison is unavailable. These are repeated classifications of the same 60 synthetic reviews, scored offline against the [provisional reference key](REFERENCE_REVIEW_V1.md), not independent samples. The [full findings note](CLEF_CLOSED_REPEATS_2026-10-07.md) gives field-level results, class balance and paired differences.

The report's input-token tariff figures are estimates from saved valid responses. Unknown attempts retain separate conservative reservations. Neither is a provider invoice, and pure inference duration is unavailable.
