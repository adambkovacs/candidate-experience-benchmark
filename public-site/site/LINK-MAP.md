# Link map: one report page to Read, Explore and Method

The report used to be one page. It is now three: `index.html` (Read), `explore.html` (every analyst panel) and `method.html`.
Every element id kept its name. `index.html` carries a small script that forwards old links, so existing links keep working,
but new links should point at the new page directly.

## Query strings

| Old link | New link |
|---|---|
| `index.html?run=<id>#inspect` (also `case`, `experiment`, `compareRun`, `cohort`, `category`) | `explore.html?run=<id>#inspect`, same query and hash |

## Anchors, one row per id on the old page

| Old link | New link |
|---|---|
| `index.html#top` | `index.html#top` |
| `index.html#main` | `index.html#main` |
| `index.html#overview` | `index.html#overview` |
| `index.html#page-title` | `index.html#page-title` |
| `index.html#example-title` | `index.html#example-title` |
| `index.html#study-map-title` | `explore.html#study-map-title` |
| `index.html#study-explanation` | `explore.html#study-explanation` |
| `index.html#story` | `explore.html#story` |
| `index.html#story-title` | `explore.html#story-title` |
| `index.html#story-specialist` | `explore.html#story-specialist` |
| `index.html#story-jev-grid` | `explore.html#story-jev-grid` |
| `index.html#story-prompts` | `explore.html#story-prompts` |
| `index.html#story-prompt-chart-title` | `explore.html#story-prompt-chart-title` |
| `index.html#story-prompt-caption` | `explore.html#story-prompt-caption` |
| `index.html#story-prompt-change` | `explore.html#story-prompt-change` |
| `index.html#story-repeat` | `explore.html#story-repeat` |
| `index.html#story-flip-grid` | `explore.html#story-flip-grid` |
| `index.html#story-change-select` | `explore.html#story-change-select` |
| `index.html#story-change-text` | `explore.html#story-change-text` |
| `index.html#story-change-answers` | `explore.html#story-change-answers` |
| `index.html#story-change-source` | `explore.html#story-change-source` |
| `index.html#takeaway-title` | `index.html#takeaway-title` |
| `index.html#framing-title` | `explore.html#framing-title` |
| `index.html#report-lens` | `explore.html#report-lens` |
| `index.html#report-lens-title` | `explore.html#report-lens-title` |
| `index.html#report-cohort` | `explore.html#report-cohort` |
| `index.html#report-lens-count` | `explore.html#report-lens-count` |
| `index.html#report-lens-note` | `explore.html#report-lens-note` |
| `index.html#extended-run-status` | `explore.html#extended-run-status` |
| `index.html#outcome-chart` | `explore.html#outcome-chart` |
| `index.html#outcome-title` | `explore.html#outcome-title` |
| `index.html#outcome-condition` | `explore.html#outcome-condition` |
| `index.html#outcome-category` | `explore.html#outcome-category` |
| `index.html#outcome-coordinate` | `explore.html#outcome-coordinate` |
| `index.html#outcome-count` | `explore.html#outcome-count` |
| `index.html#outcome-plot` | `explore.html#outcome-plot` |
| `index.html#outcome-point-title` | `explore.html#outcome-point-title` |
| `index.html#outcome-point-count` | `explore.html#outcome-point-count` |
| `index.html#outcome-run` | `explore.html#outcome-run` |
| `index.html#outcome-run-detail` | `explore.html#outcome-run-detail` |
| `index.html#run-ranking` | `explore.html#run-ranking` |
| `index.html#overview-condition` | `explore.html#overview-condition` |
| `index.html#overview-surface` | `explore.html#overview-surface` |
| `index.html#overview-count` | `explore.html#overview-count` |
| `index.html#overview-specialists` | `explore.html#overview-specialists` |
| `index.html#overview-rows` | `explore.html#overview-rows` |
| `index.html#overview-toggle` | `explore.html#overview-toggle` |
| `index.html#cross-category` | `explore.html#cross-category` |
| `index.html#cross-category-title` | `explore.html#cross-category-title` |
| `index.html#cohort-reviews` | `explore.html#cohort-reviews` |
| `index.html#cohort-reviews-title` | `explore.html#cohort-reviews-title` |
| `index.html#review-evidence` | `explore.html#review-evidence` |
| `index.html#review-evidence-title` | `explore.html#review-evidence-title` |
| `index.html#disputed-search` | `explore.html#disputed-search` |
| `index.html#disputed-subset` | `explore.html#disputed-subset` |
| `index.html#disputed-model` | `explore.html#disputed-model` |
| `index.html#disputed-field` | `explore.html#disputed-field` |
| `index.html#disputed-count` | `explore.html#disputed-count` |
| `index.html#disputed-list` | `explore.html#disputed-list` |
| `index.html#disputed-detail` | `explore.html#disputed-detail` |
| `index.html#agreement-policy` | `explore.html#agreement-policy` |
| `index.html#agreement-policy-title` | `explore.html#agreement-policy-title` |
| `index.html#reference-sensitivity` | `explore.html#reference-sensitivity` |
| `index.html#reference-sensitivity-title` | `explore.html#reference-sensitivity-title` |
| `index.html#clef-first-pass` | `explore.html#clef-first-pass` |
| `index.html#clef-first-pass-title` | `explore.html#clef-first-pass-title` |
| `index.html#clef-first-pass-results` | `explore.html#clef-first-pass-results` |
| `index.html#analysis-update` | `explore.html#analysis-update` |
| `index.html#analysis-update-title` | `explore.html#analysis-update-title` |
| `index.html#analysis-refresh-summary` | `explore.html#analysis-refresh-summary` |
| `index.html#analysis-refresh-table` | `explore.html#analysis-refresh-table` |
| `index.html#analysis-refresh-cutoffs` | `explore.html#analysis-refresh-cutoffs` |
| `index.html#liquid-prompt-chart` | `explore.html#liquid-prompt-chart` |
| `index.html#clef-repeat-chart` | `explore.html#clef-repeat-chart` |
| `index.html#deep-insights` | `index.html#deep-insights` |
| `index.html#deep-insights-title` | `index.html#deep-insights-title` |
| `index.html#findings` | `method.html#findings` |
| `index.html#findings-title` | `method.html#findings-title` |
| `index.html#analysis-library` | `explore.html#analysis-library` |
| `index.html#prompt-analysis` | `explore.html#prompt-analysis` |
| `index.html#prompt-headline` | `explore.html#prompt-headline` |
| `index.html#prompt-deck` | `explore.html#prompt-deck` |
| `index.html#finding-prompts` | `explore.html#finding-prompts` |
| `index.html#kev-prompt-analysis` | `explore.html#kev-prompt-analysis` |
| `index.html#kev-prompt-title` | `explore.html#kev-prompt-title` |
| `index.html#kev-prompt-results` | `explore.html#kev-prompt-results` |
| `index.html#jev-prompt-analysis` | `explore.html#jev-prompt-analysis` |
| `index.html#jev-prompt-title` | `explore.html#jev-prompt-title` |
| `index.html#jev-prompt-results` | `explore.html#jev-prompt-results` |
| `index.html#repeat-analysis` | `explore.html#repeat-analysis` |
| `index.html#repeat-title` | `explore.html#repeat-title` |
| `index.html#repeat-results` | `explore.html#repeat-results` |
| `index.html#repeat-notes` | `explore.html#repeat-notes` |
| `index.html#repeat-notes-title` | `explore.html#repeat-notes-title` |
| `index.html#evidence-note-search` | `explore.html#evidence-note-search` |
| `index.html#evidence-note-status` | `explore.html#evidence-note-status` |
| `index.html#repeat-note-prompts` | `explore.html#repeat-note-prompts` |
| `index.html#repeat-note-changes` | `explore.html#repeat-note-changes` |
| `index.html#repeat-note-stable` | `explore.html#repeat-note-stable` |
| `index.html#repeat-note-invalid` | `explore.html#repeat-note-invalid` |
| `index.html#evidence-note-empty` | `explore.html#evidence-note-empty` |
| `index.html#jev-analysis` | `explore.html#jev-analysis` |
| `index.html#jev-headline` | `explore.html#jev-headline` |
| `index.html#jev-deck` | `explore.html#jev-deck` |
| `index.html#finding-jev` | `explore.html#finding-jev` |
| `index.html#cost-analysis` | `explore.html#cost-analysis` |
| `index.html#cost-headline` | `explore.html#cost-headline` |
| `index.html#cost-deck` | `explore.html#cost-deck` |
| `index.html#finding-cost` | `explore.html#finding-cost` |
| `index.html#hard-analysis` | `explore.html#hard-analysis` |
| `index.html#hard-headline` | `explore.html#hard-headline` |
| `index.html#hard-deck` | `explore.html#hard-deck` |
| `index.html#finding-hard` | `explore.html#finding-hard` |
| `index.html#analysis-source` | `explore.html#analysis-source` |
| `index.html#jev` | `explore.html#jev` |
| `index.html#jev-title` | `explore.html#jev-title` |
| `index.html#jev-score` | `explore.html#jev-score` |
| `index.html#inspect-jev` | `explore.html#inspect-jev` |
| `index.html#jev-note` | `explore.html#jev-note` |
| `index.html#models` | `explore.html#models` |
| `index.html#models-title` | `explore.html#models-title` |
| `index.html#compare-search` | `explore.html#compare-search` |
| `index.html#compare-run-select` | `explore.html#compare-run-select` |
| `index.html#field-comparison` | `explore.html#field-comparison` |
| `index.html#explore` | `explore.html#explore` |
| `index.html#explore-title` | `explore.html#explore-title` |
| `index.html#experiment-select` | `explore.html#experiment-select` |
| `index.html#metric` | `explore.html#metric` |
| `index.html#experiment-title` | `explore.html#experiment-title` |
| `index.html#experiment-context` | `explore.html#experiment-context` |
| `index.html#condition-grid` | `explore.html#condition-grid` |
| `index.html#experiment-note` | `explore.html#experiment-note` |
| `index.html#roster-count` | `explore.html#roster-count` |
| `index.html#roster-search` | `explore.html#roster-search` |
| `index.html#roster-list` | `explore.html#roster-list` |
| `index.html#result-count` | `explore.html#result-count` |
| `index.html#search` | `explore.html#search` |
| `index.html#condition-filter` | `explore.html#condition-filter` |
| `index.html#surface-filter` | `explore.html#surface-filter` |
| `index.html#family-filter` | `explore.html#family-filter` |
| `index.html#category-filter` | `explore.html#category-filter` |
| `index.html#training-filter` | `explore.html#training-filter` |
| `index.html#interface-filter` | `explore.html#interface-filter` |
| `index.html#effort-filter` | `explore.html#effort-filter` |
| `index.html#sort` | `explore.html#sort` |
| `index.html#clear-run-filters` | `explore.html#clear-run-filters` |
| `index.html#include-incomplete` | `explore.html#include-incomplete` |
| `index.html#score-heading` | `explore.html#score-heading` |
| `index.html#comparison-list` | `explore.html#comparison-list` |
| `index.html#usage` | `explore.html#usage` |
| `index.html#usage-title` | `explore.html#usage-title` |
| `index.html#usage-run-select` | `explore.html#usage-run-select` |
| `index.html#usage-summary` | `explore.html#usage-summary` |
| `index.html#inspect` | `explore.html#inspect` |
| `index.html#inspect-title` | `explore.html#inspect-title` |
| `index.html#inspect-run-select` | `explore.html#inspect-run-select` |
| `index.html#run-detail` | `explore.html#run-detail` |
| `index.html#method` | `method.html#method` |
| `index.html#method-title` | `method.html#method-title` |
| `index.html#reference-note` | `explore.html#reference-note` |
| `index.html#source-links` | `explore.html#source-links` |

New ids: `index.html` adds `decisions`, `gap`, `hard-reviews`, `controls`, `rule`, `limits`, `team` and `next`. `explore.html` adds `explore-top`, `how-it-works`, `scores` and `sources`. `method.html` adds `harness`.
