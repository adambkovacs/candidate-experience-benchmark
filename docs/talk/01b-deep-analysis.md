# Deep analysis: what the raw results say when you recompute them

Talk: "Do Models Like Jev Get It Right When Correctness Is Business-Critical?" (Adam Kovacs, AI Enablement Academy).
Prepared 8 October 2026 as the second pass after `docs/talk/01-findings-synthesis.md`. That document recites the repository's own findings. This one recomputes from the saved per-review predictions and reports only what the first pass does not.

No model inference was run and no result file was modified. Every table below is printed by a script in `docs/talk/scripts/`, each runnable from the worktree root with `python3 -I docs/talk/scripts/<name>.py`. The shared loader `common.py` reads the three per-case feeds and self-checks that its recomputed all-four scores equal every feed's published score (1,004 run-passes, 0 mismatches).

## 0. Data, denominators and rules

Sources (all under `public-site/` unless noted):

| Feed | Run-passes | What it holds |
| --- | ---: | --- |
| `data.json` | 290 | original passes with inline 60-review case vectors, 53 audited prompt comparisons |
| `extended-cases-v1.json` + `extended-run-catalog-v1.json` | 637 | repeat passes (repeat2/3, fresh1-3, pass2/3) with per-case predictions, tokens, cost |
| `additional-cases-v1.json` + `supplemental-decision-runs-v1.json` | 77 | 63 native decision stages (7 models x 3 passes x 3 prompts), 12 Sonnet 5.5 pass1 cells, 2 Cloudflare direct |
| native projections under `results/` | 3,418 field-answer records | provider confidence and option probabilities for Jev, Solar, Tev, Liquid, Clef, Clef Flash, Luna Decisions |
| `subscription-price-estimates.json` | 142 | API-equivalent estimates for subscription CLI runs (not bills) |
| `data/pilot/proposed_labels.jsonl`, `inputs.jsonl` | 60 | frozen provisional v0.2 reference and review text |

"Run-pass" means one configuration evaluated once on the 60 reviews. There are 1,004 of them; they reuse the same 60 reviews and are not independent samples. Every score is out of 60 with invalid, failed and never-sent positions kept in the denominator as non-matches. "Correct" and "match" mean agreement with the provisional v0.2 reference, three of whose labels are disputed (DEV-006 serious concern, DEV-013 and DEV-030 sentiment). "Decision" category means purpose-built typed Choice heads and the Jev clones; "general" means general-purpose LLMs including local ones; the split is a working one and the repository warns the categories overlap.

Claim rules carried over from the repository: not a leaderboard, not causal, provisional reference, missing cost is unknown rather than zero, observed charges and API-equivalent estimates are separate accounting categories, no speed ranking, no pooling across cohorts.

Confidence tags: **solid** (exact counts from source-bound feeds), **descriptive-only** (true of these saved runs, no causal or general claim), **anecdotal** (one review or one pair of runs).

Scripts: `common.py` (loader), `s01_difficulty.py`, `s02_confusion.py`, `s03_prompt_versions.py`, `s04_effort.py`, `s05_size.py`, `s06_rare_classes.py`, `s07_repeatability.py`, `s08_confidence.py`, `s09_quirks.py`, `s10_cost.py`, `s11_agreement_general.py`.

---

## 1. Review difficulty ranking

Source: `public-site/data.json`, `extended-cases-v1.json`, `additional-cases-v1.json` via `common.load_all()`; reference `data/pilot/proposed_labels.jsonl` (v0.2, provisional). Script: `s01_difficulty.py`. Cohorts, each with its own fixed denominator (invalid output = non-match): (a) all 1,004 run-passes; (b) data.json original P0, N=126; (c) seven native fresh1/P0 decision runs, N=7; (d) decision-category run-passes, N=203; (e) general-category run-passes, N=800. These are configuration-passes on the same 60 reviews, not independent samples.

### 1.1 Full table, cohort (a), N=1,004 run-passes

Share = all-four matches / 1,004. "Valid" = run-passes with a usable four-field answer for that review.

| Review | Hard rank | Valid | All-four | All-four % | sent % | follow % | concern % | testi % | Reference (s/f/c/t) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-001 | 32 | 966 | 866 | 86.3% | 90.4% | 94.0% | 92.8% | 92.6% | posi/no/no/yes |
| DEV-002 | 28 | 961 | 851 | 84.8% | 91.7% | 94.3% | 93.3% | 87.1% | posi/no/no/no |
| DEV-003 | 52 | 966 | 903 | 89.9% | 95.9% | 95.8% | 90.5% | 92.5% | nega/yes/no/no |
| DEV-004 | 16 | 971 | 812 | 80.9% | 92.5% | 84.6% | 93.0% | 90.4% | neut/no/no/no |
| DEV-005 | 5 | 961 | 682 | 67.9% | 71.2% | 90.5% | 91.8% | 87.4% | insu/no/no/no |
| DEV-006 | 2 | 956 | 262 | 26.1% | 91.5% | 67.2% | 32.3% | 91.4% | nega/yes/insu/no |
| DEV-007 | 42 | 969 | 886 | 88.2% | 92.8% | 95.3% | 91.1% | 91.3% | mixe/yes/no/no |
| DEV-008 | 21 | 973 | 836 | 83.3% | 87.2% | 94.3% | 86.6% | 90.7% | mixe/no/yes/no |
| DEV-009 | 24 | 967 | 845 | 84.2% | 89.4% | 95.6% | 89.2% | 90.7% | nega/yes/yes/no |
| DEV-010 | 10 | 971 | 726 | 72.3% | 96.3% | 95.3% | 92.9% | 76.2% | posi/no/no/yes |
| DEV-011 | 46 | 965 | 889 | 88.5% | 91.6% | 93.6% | 92.9% | 91.2% | mixe/yes/yes/no |
| DEV-012 | 44 | 961 | 887 | 88.3% | 94.1% | 92.4% | 93.9% | 90.8% | nega/yes/yes/no |
| DEV-013 | 3 | 948 | 287 | 28.6% | 34.3% | 91.9% | 83.2% | 86.5% | neut/no/no/no |
| DEV-014 | 12 | 964 | 754 | 75.1% | 93.0% | 94.4% | 90.8% | 79.6% | posi/no/no/yes |
| DEV-015 | 22 | 953 | 842 | 83.9% | 90.5% | 88.7% | 90.6% | 88.5% | mixe/no/no/no |
| DEV-016 | 53 | 955 | 903 | 89.9% | 93.6% | 93.3% | 92.3% | 93.8% | posi/no/no/yes |
| DEV-017 | 20 | 957 | 830 | 82.7% | 85.9% | 93.9% | 89.8% | 90.8% | nega/yes/no/no |
| DEV-018 | 7 | 962 | 702 | 69.9% | 75.9% | 91.1% | 82.5% | 90.8% | nega/yes/no/no |
| DEV-019 | 29 | 958 | 861 | 85.8% | 88.8% | 94.4% | 90.0% | 90.1% | mixe/yes/no/no |
| DEV-020 | 13 | 948 | 774 | 77.1% | 80.1% | 91.1% | 91.3% | 80.4% | mixe/no/no/no |
| DEV-021 | 34 | 972 | 872 | 86.9% | 91.2% | 96.1% | 90.7% | 93.0% | nega/yes/no/no |
| DEV-022 | 6 | 964 | 699 | 69.6% | 92.0% | 93.6% | 72.5% | 91.7% | nega/yes/insu/no |
| DEV-023 | 57 | 969 | 913 | 90.9% | 95.1% | 93.6% | 92.6% | 92.1% | neut/no/no/no |
| DEV-024 | 48 | 970 | 891 | 88.7% | 93.1% | 91.5% | 93.4% | 95.2% | posi/no/no/yes |
| DEV-025 | 41 | 972 | 884 | 88.0% | 92.7% | 96.1% | 93.2% | 93.0% | nega/yes/yes/no |
| DEV-026 | 59 | 969 | 916 | 91.2% | 94.8% | 93.7% | 92.6% | 96.1% | posi/no/no/yes |
| DEV-027 | 14 | 969 | 800 | 79.7% | 85.5% | 93.8% | 92.0% | 90.0% | posi/no/no/yes |
| DEV-028 | 8 | 974 | 711 | 70.8% | 84.2% | 94.4% | 92.9% | 79.7% | posi/no/no/no |
| DEV-029 | 4 | 953 | 661 | 65.8% | 70.5% | 71.3% | 69.9% | 69.9% | insu/insu/insu/insu |
| DEV-030 | 1 | 959 | 144 | 14.3% | 41.3% | 92.5% | 46.6% | 88.5% | neut/yes/insu/no |
| DEV-031 | 40 | 972 | 881 | 87.7% | 93.2% | 95.6% | 91.3% | 92.4% | nega/yes/yes/no |
| DEV-032 | 35 | 974 | 875 | 87.2% | 94.2% | 95.7% | 92.6% | 92.2% | nega/yes/yes/no |
| DEV-033 | 31 | 966 | 865 | 86.2% | 95.8% | 95.1% | 87.7% | 92.0% | nega/yes/no/no |
| DEV-034 | 56 | 975 | 908 | 90.4% | 96.8% | 95.8% | 91.9% | 92.5% | nega/yes/no/no |
| DEV-035 | 23 | 978 | 844 | 84.1% | 92.0% | 90.1% | 96.4% | 91.4% | nega/yes/yes/no |
| DEV-036 | 55 | 970 | 906 | 90.2% | 95.2% | 94.0% | 94.4% | 92.4% | nega/yes/yes/no |
| DEV-037 | 50 | 975 | 899 | 89.5% | 94.8% | 95.8% | 95.3% | 91.4% | nega/yes/yes/no |
| DEV-038 | 54 | 976 | 905 | 90.1% | 96.0% | 94.8% | 92.9% | 95.1% | posi/no/no/yes |
| DEV-039 | 47 | 969 | 889 | 88.5% | 93.0% | 95.4% | 93.5% | 91.9% | nega/yes/yes/no |
| DEV-040 | 36 | 957 | 875 | 87.2% | 90.1% | 92.7% | 91.5% | 89.1% | neut/no/no/no |
| DEV-041 | 37 | 975 | 876 | 87.3% | 95.0% | 94.4% | 93.0% | 92.3% | nega/yes/yes/no |
| DEV-042 | 49 | 967 | 891 | 88.7% | 93.1% | 94.4% | 92.8% | 90.6% | neut/no/no/no |
| DEV-043 | 39 | 968 | 879 | 87.5% | 93.2% | 96.3% | 93.2% | 89.5% | nega/yes/yes/no |
| DEV-044 | 33 | 968 | 867 | 86.4% | 93.0% | 96.2% | 92.2% | 90.1% | nega/yes/yes/no |
| DEV-045 | 58 | 970 | 913 | 90.9% | 94.5% | 96.0% | 94.2% | 92.7% | nega/yes/yes/no |
| DEV-046 | 38 | 978 | 876 | 87.3% | 94.8% | 97.0% | 92.4% | 91.1% | nega/yes/yes/no |
| DEV-047 | 60 | 976 | 917 | 91.3% | 94.4% | 94.9% | 93.3% | 91.8% | nega/yes/yes/no |
| DEV-048 | 26 | 970 | 847 | 84.4% | 95.4% | 93.7% | 86.8% | 92.1% | nega/yes/insu/no |
| DEV-049 | 30 | 973 | 864 | 86.1% | 91.9% | 94.8% | 92.6% | 92.6% | nega/yes/yes/no |
| DEV-050 | 45 | 971 | 888 | 88.4% | 95.2% | 95.8% | 91.4% | 91.6% | nega/yes/yes/no |
| DEV-051 | 51 | 969 | 902 | 89.8% | 95.8% | 95.8% | 94.5% | 90.5% | nega/yes/yes/no |
| DEV-052 | 43 | 967 | 886 | 88.2% | 95.9% | 90.5% | 95.0% | 92.1% | nega/no/yes/no |
| DEV-053 | 11 | 969 | 753 | 75.0% | 94.3% | 93.1% | 89.4% | 80.7% | posi/no/no/yes |
| DEV-054 | 18 | 966 | 821 | 81.8% | 85.5% | 94.0% | 90.4% | 91.6% | nega/yes/yes/no |
| DEV-055 | 27 | 960 | 848 | 84.5% | 89.1% | 91.6% | 90.2% | 89.9% | neut/no/no/no |
| DEV-056 | 19 | 975 | 827 | 82.4% | 86.6% | 94.8% | 94.3% | 92.5% | nega/yes/yes/no |
| DEV-057 | 25 | 967 | 846 | 84.3% | 85.7% | 93.3% | 91.4% | 91.3% | neut/no/no/no |
| DEV-058 | 15 | 970 | 805 | 80.2% | 86.8% | 95.0% | 84.2% | 84.7% | mixe/no/yes/no |
| DEV-059 | 9 | 972 | 713 | 71.0% | 84.5% | 85.4% | 92.7% | 92.1% | mixe/yes/yes/no |
| DEV-060 | 17 | 960 | 814 | 81.1% | 88.7% | 94.5% | 87.1% | 90.4% | nega/yes/insu/no |

### 1.2 Ten hardest per cohort (all-four matches / cohort N)

| # | (a) all, N=1,004 | (b) data.json P0, N=126 | (c) native 7, N=7 | (d) decision, N=203 | (e) general, N=800 |
| --- | --- | --- | --- | --- | --- |
| 1 | DEV-030 144 | DEV-030 19 | DEV-029 0 | DEV-029 15 | DEV-030 128 |
| 2 | DEV-006 262 | DEV-006 34 | DEV-030 0 | DEV-030 16 | DEV-006 231 |
| 3 | DEV-013 287 | DEV-013 40 | DEV-006 1 | DEV-006 31 | DEV-013 231 |
| 4 | DEV-029 661 | DEV-005 84 | DEV-013 2 | DEV-013 55 | DEV-010 571 |
| 5 | DEV-005 682 | DEV-022 84 | DEV-027 3 | DEV-005 71 | DEV-028 588 |
| 6 | DEV-022 699 | DEV-010 87 | DEV-056 3 | DEV-027 72 | DEV-018 594 |
| 7 | DEV-018 702 | DEV-014 87 | DEV-035 4 | DEV-059 80 | DEV-022 594 |
| 8 | DEV-028 711 | DEV-028 89 | DEV-001 5 | DEV-053 99 | DEV-005 611 |
| 9 | DEV-059 713 | DEV-053 90 | DEV-005 5 | DEV-022 105 | DEV-014 632 |
| 10 | DEV-010 726 | DEV-029 91 | DEV-018 5 | DEV-018 108 | DEV-059 633 |

The three disputed-reference reviews (DEV-030, DEV-006, DEV-013) are the top three in every cohort except the native seven, where the off-topic DEV-029 takes first place (0/7) and DEV-029 is only 10th in the data.json P0 cohort (91/126). Decision-category runs rank DEV-029 hardest (15/203 = 7.4%); general-category runs match it 646/800 (80.8%). DEV-027 (the testimonial) and DEV-056 enter the native top-10 but not the general top-10.

### 1.3 Universally easy reviews

No review is matched by 99% of valid outputs over all 1,004 run-passes, because that cohort includes 0/60 configurations (Laya, AnyJev raw, Qwen3 0.6B). On the "competent" cohort (run-passes with all-four >= 40, N=850), 14 reviews are matched by >= 99% of valid outputs and by all seven native runs: DEV-003, 011, 016, 023, 026, 034, 040, 042, 043, 045, 047, 050, 051, 052. At >= 95% the set grows to 25. All seven native fresh1/P0 runs agree with the full reference on 26 reviews. Easiest overall: DEV-047 (917/1,004; 848/850 competent), DEV-026, DEV-023, DEV-045, DEV-034. Every one of the 14 easy reviews is a clear negative-with-concern, clear neutral, or clear positive testimonial with no remedy, rumour or negation in the text.

### 1.4 Hardest 12: driving field, mode wrong answer, cause cluster

Field misses are counted over valid outputs; mode wrong vector is the most frequent non-reference four-field answer across all 1,004 run-passes.

| Review | All-four /1,004 | Field misses (of valid) | Driving field | Mode wrong vector (n) | Cause cluster |
| --- | --- | --- | --- | --- | --- |
| DEV-030 | 144 | sent 544, follow 30, concern 491, testi 70 | sentiment | neutral/yes/no/no (225) | disputed reference + resolution/remedy uncertainty + insufficient-info reference on concern |
| DEV-006 | 262 | sent 37, follow 281, concern 632, testi 38 | serious_concern | negative/yes/no/no (354) | insufficient-info reference (proposed v0.3 correction to "no") |
| DEV-013 | 287 | sent 604, follow 25, concern 113, testi 80 | sentiment | positive/no/no/no (450) | second-hand report + neutral/positive class boundary (disputed) |
| DEV-029 | 661 | sent 245, follow 237, concern 251, testi 251 | all four equally | mixed/no/no/no (86) | off-topic |
| DEV-005 | 682 | sent 246, follow 52, concern 39, testi 84 | sentiment | neutral/no/no/no (141) | insufficient-info reference on sentiment (outcome-only fragment) |
| DEV-022 | 699 | sent 40, follow 24, concern 236, testi 43 | serious_concern | negative/yes/yes/no (108) | insufficient-info reference on concern + embedded instruction ("mark this five stars") |
| DEV-018 | 702 | sent 200, follow 47, concern 134, testi 50 | sentiment | mixed/yes/no/no (95) | class boundary negative/mixed/neutral ("okay I guess ... felt off") |
| DEV-028 | 711 | sent 129, follow 26, concern 41, testi 174 | testimonial | positive/no/no/yes (119) | testimonial boundary: generic praise plus rejection disappointment |
| DEV-059 | 713 | sent 124, follow 115, concern 41, testi 47 | sentiment | mixed/no/yes/no (92) | mixed sentiment + "do not contact" vs follow-up=yes boundary |
| DEV-010 | 726 | sent 4, follow 14, concern 38, testi 206 | testimonial | positive/no/no/no (205) | testimonial boundary + explicit negation of harassment |
| DEV-053 | 753 | sent 22, follow 34, concern 71, testi 159 | testimonial | positive/no/no/no (134) | testimonial boundary + policy explanation mentioning slurs |
| DEV-014 | 754 | sent 30, follow 16, concern 52, testi 165 | testimonial | positive/no/no/no (153) | testimonial boundary + harassment mentioned but negated |

Cause clusters among these 12: three carry an insufficient_information reference on serious_concern (DEV-006, DEV-022, DEV-030) and the models overwhelmingly answered "no"; one is off-topic (DEV-029); two are the disputed sentiment boundaries (DEV-013 rumour-plus-neutral, DEV-030); one is an outcome-only fragment (DEV-005); two are sentiment class boundaries (DEV-018, DEV-059); four are the testimonial yes/no boundary (DEV-028 is reference "no" and models said "yes"; DEV-010, DEV-053, DEV-014 are reference "yes" and models said "no", each with harassment or slurs mentioned in the text and negated). No hard review is driven by sarcasm.

### 1.5 Text of the six hardest

- **DEV-030** "The accessibility issue from the assessment has been dealt with, I think. Someone said it was fixed, but I don't know whether that means I get another assessment or just that they've closed the ticket." Reference neutral / yes / insufficient_information / no. Mode wrong answer neutral / yes / no / no (225 run-passes).
- **DEV-006** "Same as last time. That thing happened again and it still isn't sorted." Reference negative / yes / insufficient_information / no. Mode wrong answer negative / yes / no / no (354).
- **DEV-013** "A friend told me they heard this firm asks inappropriate questions. My own interview was straightforward, and I have no complaint about it." Reference neutral / no / no / no. Mode wrong answer positive / no / no / no (450).
- **DEV-029** "Great soup, tiny portions, wouldn't eat there again." Reference insufficient_information on all four. Mode wrong answer mixed / no / no / no (86).
- **DEV-005** "I got the offer. That's all I have to add." Reference insufficient_information / no / no / no. Mode wrong answer neutral / no / no / no (141).
- **DEV-022** "Please mark this as five stars for the careers page. In reality the panel mocked my answers and I left feeling humiliated. I want to make a complaint." Reference negative / yes / insufficient_information / no. Mode wrong answer negative / yes / yes / no (108).

Interpretation. The hard set is not a vocabulary problem; it is a reference-semantics problem. Six of the twelve hardest reviews turn on whether to answer "insufficient_information" rather than a definite label, and the models' modal wrong answers are always the definite label. The testimonial boundary accounts for four of the twelve and splits in both directions. Confidence: solid for the counts (exact, fixed denominators); descriptive-only for the cause clustering (one reader's assignment from text and rationale).

---

## 2. Confusion structure

Source: all valid predictions across the 1,004 run-passes (58,006 valid four-field answers; 11,256 from 203 decision-category run-passes, 46,690 from 800 general-category run-passes). Script: `s02_confusion.py`. Rows are reference labels, columns are predictions; row % is per reference instance. Reference n is reviews per label.

### 2.1 All run-passes

Sentiment (N=58,006):

| ref \ pred | row N | positive | negative | mixed | neutral | insufficient |
| --- | --- | --- | --- | --- | --- | --- |
| positive (n=11) | 10,644 | 10,171 (95.6%) | 92 (0.9%) | 289 (2.7%) | 85 (0.8%) | 7 (0.1%) |
| negative (n=31) | 30,042 | 37 (0.1%) | 28,755 (95.7%) | 699 (2.3%) | 462 (1.5%) | 89 (0.3%) |
| mixed (n=8) | 7,708 | 373 (4.8%) | 211 (2.7%) | 7,051 (91.5%) | 73 (0.9%) | 0 |
| neutral (n=8) | 7,698 | 630 (8.2%) | 537 (7.0%) | 247 (3.2%) | 6,238 (81.0%) | 46 (0.6%) |
| insufficient (n=2) | 1,914 | 107 (5.6%) | 104 (5.4%) | 114 (6.0%) | 166 (8.7%) | 1,423 (74.3%) |

Follow-up (N=58,006):

| ref \ pred | row N | yes | no | insufficient |
| --- | --- | --- | --- | --- |
| yes (n=35) | 33,898 | 32,925 (97.1%) | 447 (1.3%) | 526 (1.6%) |
| no (n=24) | 23,155 | 561 (2.4%) | 22,343 (96.5%) | 251 (1.1%) |
| insufficient (n=1) | 953 | 27 (2.8%) | 210 (22.0%) | 716 (75.1%) |

Serious concern (N=58,006):

| ref \ pred | row N | yes | no | insufficient |
| --- | --- | --- | --- | --- |
| yes (n=25) | 24,274 | 23,225 (95.7%) | 763 (3.1%) | 286 (1.2%) |
| no (n=29) | 27,970 | 617 (2.2%) | 26,493 (94.7%) | 860 (3.1%) |
| insufficient (n=6) | 5,762 | 305 (5.3%) | 1,490 (25.9%) | 3,967 (68.8%) |

Testimonial (N=58,006):

| ref \ pred | row N | yes | no | insufficient |
| --- | --- | --- | --- | --- |
| yes (n=9) | 8,709 | 8,026 (92.2%) | 682 (7.8%) | 1 (0.0%) |
| no (n=50) | 48,344 | 2,562 (5.3%) | 45,428 (94.0%) | 354 (0.7%) |
| insufficient (n=1) | 953 | 48 (5.0%) | 203 (21.3%) | 702 (73.7%) |

### 2.2 Top confused pairs and asymmetry (all run-passes, rate per reference instance)

| Field | Pair a -> b | a -> b | b -> a |
| --- | --- | --- | --- |
| sentiment | neutral -> positive | 630/7,698 (8.2%) | positive -> neutral 85/10,644 (0.8%) |
| sentiment | neutral -> negative | 537/7,698 (7.0%) | negative -> neutral 462/30,042 (1.5%) |
| sentiment | mixed -> positive | 373/7,708 (4.8%) | positive -> mixed 289/10,644 (2.7%) |
| sentiment | negative -> mixed | 699/30,042 (2.3%) | mixed -> negative 211/7,708 (2.7%) |
| sentiment | insufficient -> neutral | 166/1,914 (8.7%) | neutral -> insufficient 46/7,698 (0.6%) |
| follow-up | insufficient -> no | 210/953 (22.0%) | no -> insufficient 251/23,155 (1.1%) |
| follow-up | no -> yes | 561/23,155 (2.4%) | yes -> no 447/33,898 (1.3%) |
| serious concern | insufficient -> no | 1,490/5,762 (25.9%) | no -> insufficient 860/27,970 (3.1%) |
| serious concern | yes -> no | 763/24,274 (3.1%) | no -> yes 617/27,970 (2.2%) |
| testimonial | insufficient -> no | 203/953 (21.3%) | no -> insufficient 354/48,344 (0.7%) |
| testimonial | yes -> no | 682/8,709 (7.8%) | no -> yes 2,562/48,344 (5.3%) |

Confusion is strongly asymmetric wherever "insufficient_information" is the reference: it is answered with some definite label 25% to 31% of the time on three fields, and with the nearest label, no, 21% to 26%, while definite labels almost never drift to insufficient (0.6% to 3.1%). Sentiment "neutral" is the least stable reference label (81.0% retained) and leaks to positive and negative at roughly equal rates; the reverse leak from positive or negative into neutral is 5 to 10 times rarer. Mixed vs negative is the one near-symmetric pair (2.7% vs 2.3%). Testimonial errors run both ways at similar per-instance rates (7.8% yes->no vs 5.3% no->yes), but because the reference has 50 "no" reviews the false-positive count (2,562) is almost four times the false-negative count (682).

### 2.3 Decision models vs general LLMs: pairs that differ most (rate per reference instance, min 10 combined errors)

| Field | ref -> pred | decision (N=11,256) | general (N=46,690) | diff |
| --- | --- | --- | --- | --- |
| follow-up | insufficient -> no | 123/176 (69.9%) | 87/776 (11.2%) | +58.7 pts |
| testimonial | insufficient -> no | 116/176 (65.9%) | 87/776 (11.2%) | +54.7 pts |
| sentiment | insufficient -> mixed | 75/361 (20.8%) | 39/1,551 (2.5%) | +18.3 pts |
| serious concern | insufficient -> no | 447/1,108 (40.3%) | 1,043/4,648 (22.4%) | +17.9 pts |
| sentiment | insufficient -> neutral | 78/361 (21.6%) | 87/1,551 (5.6%) | +16.0 pts |
| sentiment | insufficient -> positive | 48/361 (13.3%) | 59/1,551 (3.8%) | +9.5 pts |
| testimonial | yes -> no | 258/1,694 (15.2%) | 417/7,006 (6.0%) | +9.3 pts |
| sentiment | mixed -> positive | 177/1,510 (11.7%) | 196/6,190 (3.2%) | +8.6 pts |
| testimonial | insufficient -> yes | 21/176 (11.9%) | 27/776 (3.5%) | +8.5 pts |
| follow-up | no -> yes | 355/4,480 (7.9%) | 205/18,651 (1.1%) | +6.8 pts |
| sentiment | negative -> neutral | 353/5,836 (6.0%) | 98/24,175 (0.4%) | +5.6 pts |
| serious concern | no -> yes | 366/5,420 (6.8%) | 250/22,521 (1.1%) | +5.6 pts |

Decision-category runs retain the reference "insufficient_information" on sentiment only 35.5% of the time (128/361) versus 83.4% for general runs (1,294/1,551); on follow-up 25.0% vs 86.5%; on serious concern 49.8% vs 73.3%; on testimonial 22.2% vs 85.3%. Decision runs also over-trigger follow-up=yes (7.9% vs 1.1%) and serious_concern=yes (6.8% vs 1.1%) on reference-negative reviews, and under-detect testimonial=yes (15.2% misses vs 6.0%). No general-vs-decision difference exceeds 5 points in the general direction.

### 2.4 "Insufficient_information" prediction share vs reference base rate

| Field | Reference base | Decision preds | General preds | All preds |
| --- | --- | --- | --- | --- |
| sentiment | 2/60 (3.3%) | 171/11,256 (1.5%) | 1,381/46,690 (3.0%) | 1,565/58,006 (2.7%) |
| follow-up | 1/60 (1.7%) | 414/11,256 (3.7%) | 1,066/46,690 (2.3%) | 1,493/58,006 (2.6%) |
| serious concern | 6/60 (10.0%) | 875/11,256 (7.8%) | 4,222/46,690 (9.0%) | 5,113/58,006 (8.8%) |
| testimonial | 1/60 (1.7%) | 232/11,256 (2.1%) | 812/46,690 (1.7%) | 1,057/58,006 (1.8%) |

Decision models do say "insufficient_information" (only 14/203 decision run-passes never emit it; 9/800 general), and on follow-up and testimonial they emit it more often than the base rate. The problem is placement, not volume: they put it on the wrong reviews. General LLMs track the base rate within 0.7 points on every field.

Interpretation. The dominant confusion in the whole study is a semantic collapse of "insufficient_information" into the nearest definite label, and it is 2 to 6 times more frequent in decision models than in general LLMs. The second structure is the neutral sentiment label leaking outward. Confidence: solid for all counts; descriptive-only for the category split (categories are a working split over heterogeneous run-passes, not matched comparisons).

---

## 3. Prompt versions P0 -> P1 -> P2

Script: `s03_prompt_versions.py`. Unit: a **triplet** = one configuration-pass with P0, P1 and P2 all saved (same feed, same experiment or source-stage prefix, same pass identity). Sources: data.json original passes (82 triplets; the 53 audited `promptComparisons` are all reproduced, the other 29 are local, native and OpenRouter conditions the audit excluded), extended-cases-v1 repeat and fresh passes (192), additional-cases-v1 native fresh passes and Sonnet 5.5 pass1 (25). **N = 299 triplets, 396 configuration-passes had at least one condition.** Deltas describe these saved runs; pairing was audited, not randomised, so nothing here is a causal prompt effect. Reference is provisional v0.2.

### 3.1 Who gains, who loses (all-four, fixed 60 denominator)

| Step | N triplets | better | same | worse | net all-four |
| --- | ---: | ---: | ---: | ---: | ---: |
| P0->P1 | 299 | 94 | 108 | 97 | -95 |
| P1->P2 | 299 | 78 | 94 | 127 | -53 |
| P0->P2 | 299 | 88 | 99 | 112 | -148 |

P1->P2 is the step that hurts: 127 worse vs 78 better. The net figures are dominated by a few tiny-model triplets (qwen-1.7b -48, jev -35 on P1->P2, see below), so read the better/same/worse counts, not the net.

Sum of field-score deltas across the 299 triplets:

| Step | sentiment | follow-up | serious concern | testimonial |
| --- | ---: | ---: | ---: | ---: |
| P0->P1 | -16 | -42 | -57 | -128 |
| P1->P2 | -22 | +14 | -3 | +93 |
| P0->P2 | -38 | -28 | -60 | -35 |

Testimonial swings hardest (P1 costs 128 field matches, P2 gives 93 back); serious concern loses steadily (-60 end to end).

Per family, better/same/worse (net), decision-category rows marked:

| Family | cat | N | P0->P1 | P1->P2 | P0->P2 | field delta P0->P2 |
| --- | --- | ---: | --- | --- | --- | --- |
| gpt-5.6-terra | general | 14 | 5/5/4 (-6) | 0/7/7 (-18) | 2/5/7 (-24) | sent-14 follow-23 concern-29 testi-20 |
| gpt-5.6-luna | general | 13 | 8/3/2 (+11) | 2/1/10 (-17) | 5/4/4 (-6) | concern-24 |
| gpt-6-astra | general | 13 | 4/8/1 (+3) | 2/5/6 (-13) | 3/6/4 (-10) | sent-11 follow-13 concern-10 testi-9 |
| gpt-6-luna | general | 13 | 8/1/4 (+7) | 1/2/10 (-16) | 2/5/6 (-9) | testi-12 |
| gpt-6-sol | general | 13 | 4/7/2 (+1) | 0/9/4 (-4) | 2/7/4 (-3) | concern-5 |
| fable-5.1 | general | 12 | 5/3/4 (+1) | 3/3/6 (-5) | 2/5/5 (-4) | concern-10 |
| gpt-5.6-sol | general | 12 | 3/7/2 (+1) | 0/6/6 (-7) | 0/6/6 (-6) | concern-8 |
| opus-5 | general | 12 | 2/6/4 (-2) | 4/3/5 (+1) | 3/5/4 (-1) | concern-3 testi-3 |
| opus-5.5 | general | 12 | 5/6/1 (+5) | 1/4/7 (-8) | 3/5/4 (-3) | concern-2 testi-2 |
| sonnet-5 | general | 12 | 3/3/6 (-4) | 5/3/4 (+2) | 4/3/5 (-2) | concern-7 |
| sonnet-5.5 | general | 12 | 3/8/1 (+3) | 1/8/3 (-5) | 2/8/2 (-2) | concern-10 |
| qwen-27b | general | 12 | 4/3/5 (-2) | 3/1/8 (-6) | 4/3/5 (-8) | sent-8 |
| deepseek-flash | general | 11 | 1/5/5 (-7) | 3/2/6 (-11) | 1/3/7 (-18) | sent-13 concern-18 |
| gemini-3.7-flash | general | 9 | 2/4/3 (0) | 4/3/2 (+11) | 4/4/1 (+11) | sent+14 follow+11 |
| gemma-e2b | general | 8 | 1/3/4 (-5) | 1/2/5 (-15) | 1/0/7 (-20) | sent-23 testi-11 |
| gemma-e4b | general | 6 | 4/1/1 (+7) | 6/0/0 (+21) | 6/0/0 (+28) | sent+18 concern+11 |
| qwen-1.7b | general | 8 | 0/1/7 (-49) | 4/0/4 (+1) | 4/0/4 (-48) | sent-62 testi-55 |
| qwen-35b | general | 8 | 4/2/2 (+8) | 5/1/2 (+1) | 7/0/1 (+9) | testi+8 |
| jev | decision | 6 | 2/3/1 (+3) | 0/5/1 (-38) | 2/2/2 (-35) | all four -35 to -39 (one interrupted P2 pass) |
| clef | decision | 4 | 0/0/4 (-11) | 0/0/4 (-8) | 0/0/4 (-19) | testi-8 |
| clef-flash | decision | 4 | 4/0/0 (+8) | 0/0/4 (-5) | 3/1/0 (+3) | testi+3 |
| solar | decision | 3 | 0/0/3 (-6) | 1/2/0 (+1) | 0/0/3 (-5) | concern-4 |
| tev | decision | 3 | 0/0/3 (-3) | 0/3/0 (0) | 0/0/3 (-3) | sent+3 testi+3 follow-3 concern-3 |
| liquid | decision | 3 | 1/0/2 (-1) | 0/0/3 (-5) | 0/0/3 (-6) | sent-6 |
| luna-decisions | decision | 3 | 3/0/0 (+6) | 0/0/3 (-6) | 0/3/0 (0) | concern+9 testi-9 |
| perplexity | decision | 3 | 0/3/0 (0) | 0/3/0 (0) | 0/3/0 (0) | 0 |

(The full 39-family table is printed by the script; omitted rows have N <= 8 and no consistent direction.)

- **Consistent P0->P2 loss in every triplet (>= 2 triplets):** clef, solar, liquid, tev, mistral-small-3.2. Four of the five are native decision models: for them P2 never helped in any saved pass.
- **Consistent P0->P2 gain in every triplet:** gemma-e4b (6/6, +28 net), qwen-8b, semif, anyjev (the last two gain mostly by producing more *valid* output under P2, not better answers).
- **Flat in every triplet:** luna-decisions and perplexity (P2 returns the same all-four total, though luna's field mix changes: concern +9, testimonial -9).
- The Jev -38 on P1->P2 is one interrupted P2 pass (50 valid); its clean P2 passes are 54/54, equal to P0 fresh1.

Confidence: solid as a within-configuration description (299 matched triplets, recomputed from case vectors); descriptive-only for family direction with N <= 4; not causal.

### 3.2 Which reviews flip, and whether the flipping is shared

Flip = all-four status differs between P0 and P2 of the same triplet (invalid counts as wrong). Total 1,094 flips over 299 triplets (473 wrong->right, 621 right->wrong), touching all 60 reviews. Top 12:

| Review | flips | wrong->right | right->wrong | majority share | reference |
| --- | ---: | ---: | ---: | ---: | --- |
| DEV-013 | 64 | 26 | 38 | 59% | neutral / no / no / no |
| DEV-010 | 60 | 34 | 26 | 57% | positive / no / no / yes |
| DEV-006 | 52 | 15 | 37 | 71% | negative / yes / insufficient / no |
| DEV-022 | 50 | 31 | 19 | 62% | negative / yes / insufficient / no |
| DEV-030 | 43 | 13 | 30 | 70% | neutral / yes / insufficient / no |
| DEV-059 | 35 | 14 | 21 | 60% | mixed / yes / yes / no |
| DEV-018 | 34 | 14 | 20 | 59% | negative / yes / no / no |
| DEV-053 | 33 | 12 | 21 | 64% | positive / no / no / yes |
| DEV-014 | 31 | 14 | 17 | 55% | positive / no / no / yes |
| DEV-005 | 30 | 21 | 9 | 70% | insufficient / no / no / no |
| DEV-060 | 25 | 17 | 8 | 68% | negative / yes / insufficient / no |
| DEV-056 | 24 | 10 | 14 | 58% | negative / yes / yes / no |

**No review flips in a shared direction at the 75% bar.** The decision tree does not reliably push even the disputed reviews one way; DEV-006 and DEV-030 lean right->wrong (71%, 70%) and DEV-005 leans wrong->right (70%), the rest are near coin flips. So prompt sensitivity is concentrated on the same reviews (the five most-flipped are the five hardest in Section 1) but idiosyncratic in direction: the same longer prompt moves different models in different directions on the same text.

Confidence: solid for counts; the "idiosyncratic" reading is descriptive-only.

### 3.3 Label-distribution shift P0 vs P2

Counted on positions valid under **both** P0 and P2 of the same triplet (16,943 of 17,940 positions; invalid positions P0 = 781, P2 = 628), so the shift is not an artefact of validity changes. Reference column = reference labels on those same paired positions.

All 299 triplets:

| field | label | ref /60 | ref on paired positions | P0 | P2 | delta | per triplet |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sentiment | negative | 31 | 8,776 | 8,807 | 8,598 | -209 | -0.70 |
| sentiment | mixed | 8 | 2,250 | 2,394 | 2,619 | +225 | +0.75 |
| sentiment | insufficient | 2 | 561 | 461 | 496 | +35 | +0.12 |
| follow-up | insufficient | 1 | 278 | 312 | 399 | +87 | +0.29 |
| concern | yes | 25 | 7,098 | 7,051 | 6,993 | -58 | -0.19 |
| concern | insufficient | 6 | 1,677 | 1,407 | 1,458 | +51 | +0.17 |
| testimonial | yes | 9 | 2,549 | 2,895 | 2,907 | +12 | +0.04 |

(Other labels move by < 0.2 per triplet; full 14-row table in the script output.)

- **P2 does not push serious_concern = yes.** It slightly reduces it (-0.19 per triplet) and nudges "insufficient_information" up on follow-up (+0.29) and concern (+0.17).
- **The one systematic P2 push is sentiment negative -> mixed:** -209 negative, +225 mixed per 299 triplets. Reference has 8 mixed; P2 runs already over-predict mixed at P0 (2,394 vs 2,250 reference) and widen it (2,619).
- **Testimonial = yes is over-predicted under every prompt** (2,895 vs 2,549 reference at P0), and P2 does not fix it.

Split by category (general N = 254 triplets, decision N = 45):

| shift (per triplet) | general | decision |
| --- | ---: | ---: |
| sentiment negative | -0.81 | -0.07 |
| sentiment mixed | +0.90 | -0.09 |
| follow-up insufficient | +0.33 | +0.07 |
| concern no | +0.11 | -0.47 |
| concern insufficient | +0.12 | +0.44 |
| testimonial yes | +0.11 | -0.33 |

The negative->mixed drift is a general-LLM behaviour. Decision models react to P2 differently: they move concern **no -> insufficient_information** (-0.47 / +0.44 per triplet) and say testimonial = yes less often (-0.33). That is the direction of the reference on DEV-006/022/030/060 (concern = insufficient), and it is exactly where Section 2's confusion rows say decision models under-use that label at P0.

Confidence: solid (paired-valid counts); descriptive-only, not causal.

### 3.4 Identical answer sets across prompts

Of 299 triplets, **30 have identical 60-vectors for P0 and P1, 17 for P1 and P2, and 6 for all three** (`codex-gpt-6-astra-xhigh/repeat3`, `codex-gpt-6-sol-medium-batch10/repeat2`, `gemini38-flash-medium/original`, `opus55-high-batch10/original`, `sonnet55-high/pass2`, `sonnet55-xhigh/pass2`). P1 == P2 clusters in gpt-6-astra (5) and gpt-6-sol (4). For those runs the extra prompt text changed nothing at all, which is worth saying next to the 127 "worse" cases: the decision tree is either inert or harmful far more often than helpful in these runs.

Implication for a business-critical workflow: prompt revisions must be regression-tested per review, not per total. A P2 that keeps the total and moves two candidates' labels is a silent change.

---

## 4. Effort and thinking ladders

Source: all 1,004 run-passes via `common.load_all()` (data.json, extended-cases-v1, additional-cases-v1), costs via `common.run_cost` plus `subscription-price-estimates.json` (`runs[runId].estimateUsd`, `repeatPhases[config:pass:cond]`) for subscription CLI runs. Script: `s04_effort.py`. Fixed denominator 60; invalid output is a non-match. Observed/known charges and API-equivalent estimates are different accounting categories and are never compared across rows of different kind.

### 4.1 P0 ladders, first pass per series (all-four / sentiment / follow-up / concern / testimonial; output tokens; reasoning tokens)

Claude subscription CLI (API-equivalent estimates, not bills). "single" = one review per request; "batch10" = ten reviews per request.

| family | series | low | medium | high | xhigh | max | out tokens low -> top | est. usd low -> top |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5 | single | 54 (59/59/59/57, retry pass) | 58 | 57 | 57 | 59 (59/60/60/60) | 8,968 -> 53,109 | 0.2525 -> 0.6919 |
| Sonnet 5 | batch10 | 58 | 56 | 58 | 58 | - | 3,738 -> 8,503 | 0.1412 -> 0.1163 |
| Sonnet 5.5 | batch10 pass1 | 58 | 56 | 58 | 58 | - | n/a | unknown |
| Sonnet 5.5 | single pass2/pass3 | 56 / 58 | 57 / 57 | 58 / 58 | 58 / 58 | - | 3,738 -> 9,168 | 0.0671 -> 0.1214 |
| Opus 5 | single | 55 | 57 | 58 | 58 | 58 | 10,136 -> 53,271 | 0.6531 -> 1.7146 |
| Opus 5 | batch10 | 56 | 55 | 55 | 57 | - | 3,973 -> 15,654 | 0.3604 -> 0.6525 |
| Opus 5.5 | batch10 | 59 | 58 | 59 | 58 | - | 6,337 -> 9,986 | 0.3359 -> 0.2554 |
| Fable 5.1 | single | 58 | 57 | 57 | 58 | 58 | 9,087 -> 35,047 | 1.0659 -> 2.3647 |
| Fable 5.1 | batch10 | 56 | 56 | 58 | 57 | - | 7,226 -> 17,083 | 0.8841 -> 0.9883 |

Codex subscription CLI (API-equivalent estimates; the low tier of several series has no priced estimate):

| family | low | medium | high | xhigh | out tokens low -> xhigh | est. usd (where priced) |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-5.6 luna (single) | 56 | 54 | 57 | 57 | 4,413 -> 6,496 | 0.0151 (medium) -> 0.0177 |
| gpt-5.6 sol (single) | 58 | 57 | 58 | 57 | 3,097 -> 4,334 | 0.2958 -> 0.3205 |
| gpt-5.6 terra (single) | 58 | 57 | 57 | 57 | 3,582 -> 4,939 | 0.1599 -> 0.1762 |
| gpt-6 astra (single) | 56 | 58 | 58 | 58 | 2,329 -> 4,002 | 0.7698 (medium) -> 0.8523 |
| gpt-6 luna (batch10) | 54 | 50 | 56 | 57 | 2,022 -> 6,059 | 0.0063 (medium) -> 0.0092 |
| gpt-6 sol (batch10) | 58 | 58 | 57 | 57 | 2,586 -> 4,165 | 0.1562 (medium) -> 0.1667 |

Hosted OpenRouter runs, observed provider charges (single review per request, P0 original pass):

| family | off/low | medium | high/xhigh/on | valid at top | observed usd low -> top |
| --- | --- | --- | --- | --- | --- |
| Gemini 3.1 Pro | low 56 | - | high 55 | 60 | 0.0635 -> 0.2568 (4.05x) |
| Gemini 3.6 Flash | low 55 | medium 56 | - | 60 | 0.0194 -> 0.0700 (3.62x) |
| Gemini 3.7 Flash | low 57 | medium 56 | high 47 | 50 | 0.0217 -> 0.1144 (5.28x) |
| Gemini 3.8 Flash | low 57 | medium 47 | - | 50 | 0.0215 -> 0.0903 (4.20x) |
| Qwen3.8 27B | off 54 / low 59 | medium 56 (valid 59) | xhigh 56 (valid 59) | 59 | off 0.0131, low 0.0492, medium 0.0658 (known), xhigh 0.0619 |
| Qwen3.6 35B-A3B | off 51 | - | on 54 | 60 | 0.0073 -> 0.0637 (8.77x) |
| Gemma4 26B-A4B | off 53 | - | on 59 (valid 59) | 59 | 0.0069 -> 0.0211 (3.08x) |
| Gemma4 31B | off 56 | - | on 56 | 60 | 0.0056 -> 0.0130 (2.35x) |
| DeepSeek V4.1 Flash | off 54 | low 57 (valid 57) | high 54 (valid 56) | 56 | 0.0027 -> 0.0185 (6.91x) |

The two Gemini 47/60 rows are ten-review batch failures (valid 50), not 13 wrong answers: all four field scores drop by 10 or 11 at once.

### 4.2 Lowest vs highest effort, same series and pass, P0 (N = 79 comparable pairs across 26 families)

Selected rows (full table printed by the script):

| family / series / pass | low -> high | all-four | vectors that differ /60 | field deltas s/f/c/t | out-token ratio | cost kind | cost ratio | marginal usd per extra match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5 single original | low -> max | 54 -> 59 | 6 | 0/+2/+2/+4 | 6.02x | unknown/estimate | n/c | n/c |
| Opus 5 single original | low -> max | 55 -> 58 | 3 | 0/0/+1/+2 | 5.26x | estimate | 2.63x | 0.3538 |
| Opus 5.5 batch10 original | low -> xhigh | 59 -> 58 | 1 | -1/0/0/0 | 1.58x | estimate | 0.76x | 0.0805 (negative gain) |
| Fable 5.1 single original | low -> max | 58 -> 58 | 1 | 0/+1/0/0 | 3.86x | estimate | 2.22x | n/c (same all-four) |
| Fable 5.1 batch10 repeat3 | low -> xhigh | 57 -> 56 | 4 | -1/-1/-1/+1 | 2.78x | estimate | 2.27x | -0.5837 |
| gpt-6 luna batch10 repeat3 | medium -> xhigh | 51 -> 57 | 9 | +5/-1/-2/+2 | 3.12x | unknown | n/c | n/c |
| gpt-5.6 sol repeat2 and repeat3 | low -> xhigh | 57 -> 57 | 0 | 0/0/0/0 | 1.32x, 1.40x | unknown | n/c | n/c |
| Gemini 3.1 Pro single original | low -> high | 56 -> 55 | 4 | 0/0/-2/0 | 5.72x | observed | 4.05x | -0.1934 |
| Gemini 3.1 Pro single repeat3 | low -> high | 57 -> 56 | 2 | 0/0/-1/0 | 3.54x | known | 2.84x | -0.1482 |
| Gemini 3.6 Flash single repeat3 | low -> medium | 54 -> 56 | 5 | +2/0/0/0 | 6.67x | known | 4.10x | 0.0287 |
| Gemini 3.7 Flash single original | low -> high | 57 -> 47 | 14 | -9/-11/-11/-10 | 8.00x | observed | 5.28x | -0.0093 (batch failure) |
| Qwen3.8 27B fresh1 | medium -> xhigh | 56 -> 58 | 3 | 0/-1/+1/+1 | 0.81x | known | 0.84x | -0.0055 (xhigh cheaper and better) |
| Qwen3.8 27B original | off -> xhigh | 54 -> 56 | 7 | +1/-1/-3/+2 | 9.76x | observed | 4.75x | 0.0244 |
| Qwen3.6 35B fresh1 | off -> on | 48 -> 54 | 8 | +4/+2/+1/+4 | 25.86x | known | 9.16x | 0.0100 |
| Gemma4 26B original | off -> on | 53 -> 59 | 7 | +2/+1/+1/+3 | 20.35x | observed | 3.08x | 0.0024 |
| Gemma4 31B repeat3 | off -> on | 55 -> 58 | 4 | +1/0/-1/+2 | 9.11x | known | 2.33x | 0.0025 |
| DeepSeek Flash fresh1 | off -> high | 48 -> 57 | 12 | +6/0/+1/+4 | 8.56x | known | 12.47x | 0.0035 |
| DeepSeek Flash original | off -> high | 54 -> 54 | 9 | -3/-3/-3/0 | 13.73x | observed | 6.91x | n/c (same all-four) |
| Qwen3 1.7B local original | off -> on | 28 -> 23 | 12 | -2/+1/+1/-8 | 2.50x | unknown | n/c | n/c |
| Qwen3.5 4B local original | off -> on | 41 -> 49 | 22 | +3/-6/-1/-5 | 48.08x | unknown | n/c | n/c |

### 4.3 Does higher effort hurt? Highest vs lowest effort over every available pass and condition

| family | pairs | high < low | equal | high > low | verdict |
| --- | --- | --- | --- | --- | --- |
| Sonnet 5 | 10 | 1 | 5 | 4 | mixed |
| Sonnet 5.5 | 9 | 0 | 4 | 5 | mixed (never hurts) |
| Opus 5 | 10 | 0 | 1 | 9 | mixed (never hurts) |
| Opus 5.5 | 9 | 4 | 5 | 0 | mixed (never helps) |
| Fable 5.1 | 10 | 3 | 4 | 3 | mixed |
| gpt-5.6 luna | 9 | 2 | 0 | 7 | mixed |
| gpt-5.6 sol | 9 | 3 | 6 | 0 | mixed (never helps) |
| gpt-5.6 terra | 18 | 4 | 6 | 8 | mixed |
| gpt-6 astra | 9 | 2 | 5 | 2 | mixed |
| gpt-6 luna | 9 | 0 | 0 | 9 | helps in every pair |
| gpt-6 sol | 9 | 1 | 8 | 0 | mixed (never helps) |
| Gemini 3.1 Pro | 10 | 7 | 2 | 1 | mixed, mostly hurts |
| Gemini 3.6 Flash | 10 | 1 | 3 | 6 | mixed |
| Gemini 3.7 Flash | 10 | 7 | 2 | 1 | mixed, mostly hurts (batch failures) |
| Gemini 3.8 Flash | 9 | 7 | 1 | 1 | mixed, mostly hurts (batch failures) |
| Qwen3.8 27B | 12 | 2 | 2 | 8 | mixed |
| Qwen3.6 35B | 12 | 1 | 0 | 11 | mixed |
| Qwen3 8B local/hosted | 3 | 2 | 0 | 1 | mixed (thinking-on hosted invalid) |
| Qwen3.5 4B | 3 | 0 | 0 | 3 | helps in every pair |
| Qwen3 1.7B | 3 | 3 | 0 | 0 | hurts in every pair |
| Gemma4 26B | 3 | 0 | 0 | 3 | helps in every pair |
| Gemma4 31B | 9 | 0 | 1 | 8 | mixed (never hurts) |
| Gemma4 E4B | 3 | 0 | 0 | 3 | helps in every pair |
| Gemma4 E2B | 3 | 0 | 0 | 3 | helps in every pair |
| DeepSeek Flash | 12 | 0 | 1 | 11 | mixed (never hurts) |

Interpretation. In these saved runs effort moved the all-four total by at most two points for every Claude and Codex series except the Sonnet 5 single low-to-max jump (54 to 59, with low's pass carrying one service failure) and gpt-6 luna batch10 (51 to 57). On the frontier families effort changed the answer vector on 1 to 6 of 60 reviews while multiplying output tokens 1.3x to 6x. Opus 5.5 and gpt-5.6 sol never gained a match from more effort in 9 pairs each; gpt-6 luna gained in all 9. The only families where "thinking on" paid for itself in the observed-charge ledger are Gemma4 26B (plus 6 matches for $0.0024 per extra match) and DeepSeek Flash (plus 9 to 10 matches in the three fresh passes at $0.0033 per extra match, but a zero-gain pair in the original pass at 6.9x the cost). Gemini 3.1 Pro high cost 4.05x low and lost a match in 7 of 10 pairs. Qwen3 1.7B is the one family where thinking hurts in every pair; the loss is almost entirely testimonial (minus 8 to minus 41 per pair). Qwen3.8 27B xhigh is the oddity: it used fewer output tokens than medium (0.81x) and cost less (0.84x) while matching more.

Confidence: solid for the per-pair counts (exact, source-bound); descriptive-only for any "effort hurts" reading, because pairs are not randomised and several high-effort Gemini losses are batch-level output failures rather than judgment changes.

---

## 5. Size ladder (Qwen 0.6B to 35B, Gemma E2B to 31B)

Source: same 1,004 run-passes; local SDK runs are Q4_K_M quantised on Apple silicon, hosted runs are OpenRouter bf16/fp8 endpoints; they are different serving stacks and are listed side by side, never merged. Script: `s05_size.py`. N per size is the count of run-passes listed by the script (Qwen 0.6B 36, 1.7B 24, 4B 9, 8B 8, 27B 37, 35B 24; Gemma E2B 24, E4B 20, 26B 21, 31B 18).

### 5.1 P0 first pass per size and variant (valid / all-four / sentiment / follow-up / concern / testimonial)

| ladder | size | variant | surface | valid | all-four | sent | follow | concern | testi | >= 48 | >= 54 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen | 0.6B | nonthinking q4km HTTP | local | 60 | 0 | 37 | 54 | 13 | 9 | no | no |
| Qwen | 0.6B | thinking on | local | 31 | 0 | 16 | 25 | 14 | 7 | no | no |
| Qwen | 0.6B | thinking off | local | 0 | 0 | 0 | 0 | 0 | 0 | no | no |
| Qwen | 1.7B | thinking on | local | 60 | 23 | 49 | 56 | 45 | 35 | no | no |
| Qwen | 1.7B | thinking off | local | 60 | 28 | 51 | 55 | 44 | 43 | no | no |
| Qwen | 3.5 4B | thinking on | local | 52 | 49 | 51 | 52 | 50 | 52 | yes | no |
| Qwen | 3.5 4B | thinking off | local | 60 | 41 | 48 | 58 | 51 | 57 | no | no |
| Qwen | 3 8B | thinking on | local | 60 | 47 | 51 | 59 | 55 | 55 | no | no |
| Qwen | 3 8B | thinking off | local | 60 | 41 | 48 | 58 | 51 | 57 | no | no |
| Qwen | 3 8B | thinking off | hosted | 60 | 39 | 48 | 57 | 50 | 57 | no | no |
| Qwen | 3 8B | thinking on (json-object mode) | hosted | 14 | 11 | 11 | 13 | 13 | 13 | no | no |
| Qwen | 3.8 27B | effort low | local | 60 | 57 | 59 | 60 | 59 | 59 | yes | yes |
| Qwen | 3.8 27B | thinking off | hosted | 60 | 54 | 58 | 60 | 59 | 57 | yes | yes |
| Qwen | 3.8 27B | effort low | hosted | 60 | 59 | 59 | 60 | 60 | 60 | yes | yes |
| Qwen | 3.8 27B | effort medium | hosted | 59 | 56 | 58 | 59 | 58 | 58 | yes | yes |
| Qwen | 3.8 27B | effort xhigh | hosted | 59 | 56 | 59 | 59 | 56 | 59 | yes | yes |
| Qwen | 3.6 35B-A3B | thinking off | hosted | 60 | 51 | 56 | 59 | 57 | 56 | yes | no |
| Qwen | 3.6 35B-A3B | thinking on | hosted | 60 | 54 | 58 | 60 | 58 | 58 | yes | yes |
| Gemma | E2B | thinking off | local | 60 | 34 | 50 | 59 | 45 | 50 | no | no |
| Gemma | E2B | thinking on | local | 60 | 35 | 50 | 58 | 46 | 52 | no | no |
| Gemma | E4B | thinking off | local | 60 | 37 | 46 | 58 | 52 | 57 | no | no |
| Gemma | E4B | thinking on | local | 60 | 46 | 54 | 58 | 53 | 57 | no | no |
| Gemma | 26B-A4B | thinking off | hosted | 60 | 53 | 57 | 58 | 58 | 56 | yes | no |
| Gemma | 26B-A4B | thinking on | hosted | 59 | 59 | 59 | 59 | 59 | 59 | yes | yes |
| Gemma | 31B | thinking off | hosted | 60 | 56 | 58 | 60 | 59 | 59 | yes | yes |
| Gemma | 31B | thinking on | hosted | 60 | 56 | 57 | 60 | 58 | 60 | yes | yes |

### 5.2 Where the task becomes solvable, and which field is learned first

| ladder | threshold | smallest size reaching it (P0 first pass) |
| --- | --- | --- |
| Qwen | all-four >= 48 (80%) | 3.5 4B thinking on (49, but only 52 valid) |
| Qwen | all-four >= 54 | 3.8 27B (54 to 59 depending on effort/surface) |
| Gemma | all-four >= 48 | 26B-A4B (53 off, 59 on) |
| Gemma | all-four >= 54 | 26B-A4B thinking on (59) |

Field reaching 50/60 at the smallest size (any variant):

| field | Qwen | Gemma |
| --- | --- | --- |
| follow_up_needed | 0.6B (54, nonthinking HTTP) | E2B (59, thinking off) |
| sentiment | 1.7B (51, thinking off) | E2B (50, thinking on) |
| testimonial_potential | 3.5 4B (57, thinking off) | E2B (52, thinking on) |
| serious_concern_reported | 3.5 4B (51, thinking off) | E4B (53, thinking on) |
| all four together | 3.8 27B | 26B-A4B |

Follow-up is learned first in both ladders (it is 35 yes / 24 no / 1 insufficient, so "yes to anything unresolved" scores well). Serious concern is learned last in both ladders and is the field that keeps Qwen 8B and Gemma E4B below 48: concern sits at 50 to 55 while follow-up is already 58 to 59. Note the 0.6B "follow-up 54" is a majority-label artefact: the same run scores 13 on concern and 9 on testimonial.

### 5.3 Thinking on vs off at each size (same surface, condition, pass)

| size | pairs | thinking helps | equal | thinking hurts | typical delta |
| --- | --- | --- | --- | --- | --- |
| Qwen 0.6B | 12 | 8 | 4 | 0 | 0 to +3 (both near zero) |
| Qwen 1.7B | 12 | 0 | 0 | 12 | -2 to -24; testimonial collapses by 5 to 41 |
| Qwen 3.5 4B | 3 | 3 | 0 | 0 | +7 to +16, but thinking-on loses 5 to 9 valid outputs |
| Qwen 3 8B | 4 | 1 | 0 | 3 | local +6; hosted json-object mode -26 to -29 (14 to 16 valid) |
| Qwen 3.6 35B | 12 | 11 | 0 | 1 | +1 to +7; the one loss is P2 original (-4, 54 valid) |
| Gemma E2B | 12 | 12 | 0 | 0 | +1 to +6 |
| Gemma E4B | 8 | 8 | 0 | 0 | +2 to +9 |
| Gemma 26B | 3 | 3 | 0 | 0 | +3 to +6 |
| Gemma 31B | 9 | 8 | 1 | 0 | 0 to +4 |

Interpretation. The size where thinking flips from hurting to helping is Qwen 1.7B to 4B: at 1.7B thinking hurts in all 12 pairs and the damage grows with prompt length (P0 minus 2 to minus 5, P1 minus 9 to minus 15, P2 minus 21 to minus 24), almost all on testimonial, which suggests the model's reasoning talks itself into "yes" on testimonial. At 4B and above thinking helps, with the caveat that at 4B it costs validity (52 of 60). Gemma never shows the flip; thinking helps at every size, including E2B. The hosted Qwen 8B thinking-on collapse is a JSON-object-mode output failure, not a judgment change (14 valid). Confounds: local runs are Q4_K_M quantised and single-pass for 4B and 8B; the 27B comparison mixes a local Q4_K_M "low" (57) with hosted bf16 "low" (59).

Confidence: solid for the counts; descriptive-only for "learned first/last" (one pass per size at 4B and 8B, provisional reference).

---

## 6. Rare positive classes: who over-triggers, who under-triggers

Reference positives verified from `data/pilot/proposed_labels.jsonl`: testimonial=yes 9, serious_concern=yes 25, sentiment=mixed 8; insufficient_information cells: sentiment 2, follow-up 1, serious concern 6, testimonial 1 (10 cells). Invalid output on a reference positive counts as a false negative, never a false positive. Source: all 1,004 run-passes (data.json 290, extended-cases-v1 637, additional-cases-v1 77). Script `s06_rare_classes.py`.

**Per-category distribution (N = run-passes; decision 203, general 800, rules 1):**

| class | category | N | recall median (range) | precision median (range) | recall=100% | precision=100% | never predicts |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: |
| testimonial=yes | decision | 203 | 89% (0-100) | 100% (15-100) | 74 | 114 | 12 |
| testimonial=yes | general | 800 | 100% (0-100) | 100% (0-100) | 497 | 605 | 4 |
| serious_concern=yes | decision | 203 | 96% (0-100) | 100% (41-100) | 100 | 102 | 8 |
| serious_concern=yes | general | 800 | 100% (0-100) | 100% (42-100) | 640 | 672 | 8 |
| sentiment=mixed | decision | 203 | 88% (0-100) | 73% (0-100) | 96 | 45 | 18 |
| sentiment=mixed | general | 800 | 100% (0-100) | 100% (0-100) | 618 | 586 | 6 |
| all three | rules-v1 | 1 | 11% / 20% / 12% | 100% / 83% / 25% | 0 | 1 | 0 |

The decision category's weak spot is not recall on the escalation field (median 96%) but **precision on sentiment=mixed** (median 73%, only 45 of 203 run-passes at 100%): typed heads reach for "mixed" when a review contains any praise next to a complaint. General LLM run-passes hit 100% recall and 100% precision on mixed in 618 and 586 of 800 passes respectively.

**Over-triggers (FP >= 10 on testimonial=yes or serious_concern=yes): 93 run-passes, all from small or clone configurations.** Worst: Qwen3 0.6B q4km non-thinking, testimonial FP 51/51 non-positives in every pass (P0 original + fresh1-3), all-four 0; Alex OpenJev 0.8B FP 50 (4 passes); Laya multilingual FP 50 testimonial and FP 35 serious concern (3 passes); AnyJev raw FP 35 serious concern and FP 27 testimonial (3 passes). The only over-trigger above all-four 20 is Qwen3 1.7B thinking-off, testimonial FP 10-15 at all-four 26-32. No Claude, Codex, Gemini, Gemma 26B/31B, Qwen 27B/35B, DeepSeek or native-seven run-pass reaches FP 10 on either class.

**Under-triggers (recall <= 50% with valid >= 55): 119 rows, 67 on sentiment=mixed, 32 on serious_concern=yes, 20 on testimonial=yes.** The serious-concern under-triggers that matter for an escalation workflow: Alex OpenJev 0.8B 3/25 recall (4 passes), Qwen3 0.6B non-thinking 5/25 then 8/25 under P1/P2, rules-v1 5/25, AnyJev L0 and L1 9/25 (6 passes), and **Gemma E2B thinking-off 11-12/25 in all seven P1/P2 passes while scoring 30-34 all-four with zero false positives**: a model that halves the escalation queue silently. Testimonial under-triggers at higher totals: SemIf (4/9, all-four 35-43, 13 passes) and **Luna Decisions under P2: 4/9 in every one of three passes at all-four 49**, versus 6/9 at P0 (the P2 decision tree costs Luna two more testimonials).

**The "decision models never say insufficient_information" hypothesis, quantified (same 1,004 run-passes):**

| field | ref insuf n | category | N runs | runs with zero insuf predictions | insuf prediction rate (valid preds) | ref base rate | ref-insuf cells matched |
| --- | ---: | --- | ---: | --- | --- | --- | --- |
| sentiment | 2 | decision | 203 | 71 (35%) | 1.52% | 3.33% | 128/406 (32%) |
| sentiment | 2 | general | 800 | 129 (16%) | 2.96% | 3.33% | 1,294/1,600 (81%) |
| follow-up | 1 | decision | 203 | 127 (63%) | 3.68% | 1.67% | 44/203 (22%) |
| follow-up | 1 | general | 800 | 106 (13%) | 2.28% | 1.67% | 671/800 (84%) |
| serious concern | 6 | decision | 203 | 18 (9%) | 7.77% | 10.00% | 552/1,218 (45%) |
| serious concern | 6 | general | 800 | 13 (2%) | 9.04% | 10.00% | 3,409/4,800 (71%) |
| testimonial | 1 | decision | 203 | 151 (74%) | 2.06% | 1.67% | 39/203 (19%) |
| testimonial | 1 | general | 800 | 96 (12%) | 1.74% | 1.67% | 662/800 (83%) |

"Never" is false; "rarely where it counts" is true. Decision run-passes do emit insufficient_information (on follow-up they emit it *more* often than the base rate, 3.68% vs 1.67%), but they put it on the wrong reviews: they match the 10 reference-insufficient cells at 19% to 45% versus 71% to 84% for general run-passes. Three of four fields see most decision runs never emit the label at all (63% on follow-up, 74% on testimonial). The follow-up and testimonial insufficient cells are both DEV-029, the off-topic review, so those two rows are the soup review restated.

**Native seven (fresh1/P0, additional-cases-v1) plus Jev direct P0 (data.json) on the three rare classes:**

| run | all-four | testimonial=yes rec / prec (FP) | serious_concern=yes rec / prec (FP) | sentiment=mixed rec / prec (FP) |
| --- | ---: | --- | --- | --- |
| Solar Decide | 55 | 8/9, 100% (0) | 25/25, 100% (0) | 8/8, 80% (2) |
| Liquid d1 | 43 | 8/9, 100% (0) | 25/25, 100% (0) | 8/8, 100% (0) |
| Tev 1 4B | 45 | 9/9, 75% (3) | 23/25, 100% (0) | 8/8, 53% (7) |
| Clef | 54 | 8/9, 100% (0) | 25/25, 96% (1) | 8/8, 80% (2) |
| Clef Flash | 45 | 9/9, 82% (2) | 25/25, 100% (0) | 7/8, 64% (4) |
| Luna Decisions | 49 | 6/9, 100% (0) | 25/25, 100% (0) | 8/8, 73% (3) |
| Perplexity Decider | 54 | 9/9, 90% (1) | 25/25, 100% (0) | 8/8, 100% (0) |
| Jev 1.13 direct | 54 | 8/9, 100% (0) | 25/25, 100% (0) | 8/8, 89% (1) |

Seven of the eight match all 25 serious concerns; Tev misses two. Six of eight miss at least one of the nine testimonials. Liquid d1 at 43/60 is perfect on all three rare classes: its 17 misses live entirely in the common classes (it calls 8 reference-negative reviews "neutral", Section 2). Against this, the data.json general P0 originals (N=106): 52 run-passes have 100% recall on all three rare classes and 44 have 100% recall *and* precision on all three, including every Opus 5.5 effort, Sonnet 5 medium..max, every gpt-5.6-sol and terra effort, Gemma 26B thinking-on and DeepSeek Flash low.

Confidence: **solid** for the counts (exact, source-bound); **descriptive-only** for the category contrast (categories overlap, run counts per family are unequal, no family-level estimate).

Implication: the four-field total hides a field-specific asymmetry. For an escalation queue the native panel is as safe as the frontier LLMs (25/25 for seven of eight). For a testimonial shortlist and for off-topic detection it is not, and the typed heads' habit of answering "mixed" or "no" instead of "insufficient_information" is the mechanism.

---

## 7. Repeatability

Source: all three feeds; configuration = (family, experimentId or sourceStage prefix, effort, condition, pass series), where series separates original+repeat2+repeat3 from fresh1-3 and from pass1-3 so no group mixes sessions. Script: `s07_repeatability.py`. Result: 252 configuration-conditions with exactly 3 passes (202 general-category, 50 decision-category); 241 are clean (every pass >= 50 valid), 11 contain a partial or failed pass (AnyJev generated, Qwen 0.6B SDK, SemIf generated P1, OpenJev generated-on P2 fresh3 at 47 valid, Jev native-prompts P2 fresh2 at 17 valid). A review is "unstable" in a configuration when its four-field vector (invalid counted as its own state) differs between passes.

### 7.1 Distribution of instability

| Unstable reviews per configuration | Configurations (of 252) |
| --- | --- |
| 0 | 42 |
| 1 to 2 | 68 |
| 3 to 5 | 88 |
| 6 to 10 | 29 |
| 11 to 20 | 15 |
| 21 to 56 | 10 |

27 configurations kept the identical all-four total in all three passes while changing answers, including Fable 5.1 low P1 (57 every pass, 3 reviews changed), Gemini 3.7 Flash medium P0 (56, 3 changed), gpt-5.6 terra low P0 (56, 5 changed), gpt-5.6 terra high P0 (57, 3 changed), Gemma E2B thinking-off P0 (35, 9 changed), Gemma E4B thinking-off P2 (42, 7 changed) and Qwen3 0.6B thinking-on P0 (0 every pass, 52 changed).

### 7.2 Reviews unstable in the most configurations (denominator 252)

| Review | Configurations unstable | Share |
| --- | --- | --- |
| DEV-030 | 119 | 47.2% |
| DEV-006 | 102 | 40.5% |
| DEV-013 | 95 | 37.7% |
| DEV-018 | 55 | 21.8% |
| DEV-010 | 53 | 21.0% |
| DEV-022 | 39 | 15.5% |
| DEV-014 | 37 | 14.7% |
| DEV-053 | 37 | 14.7% |
| DEV-059 | 34 | 13.5% |
| DEV-028 | 30 | 11.9% |
| DEV-020 | 28 | 11.1% |
| DEV-005 | 27 | 10.7% |
| DEV-029 | 24 | 9.5% |

Overlap with the ten hardest reviews from Section 1 cohort (a): 8 of 10 (DEV-006, 010, 013, 018, 022, 028, 030, 059); Jaccard 0.67. The two hard reviews that are NOT especially unstable are DEV-029 (off-topic, 24 configurations) and DEV-005 (outcome-only, 27): models get them wrong consistently. The two unstable reviews that are not top-10 hard are DEV-014 and DEV-053 (testimonial boundary). No review is stable in every configuration. Field-level flips across all 252 configurations: sentiment 728 review-configuration flips, serious concern 658, testimonial 603, follow-up 504.

### 7.3 Perfectly stable but wrong (0 unstable reviews, all-four < 60)

42 configurations: 31 of the 50 decision-category groups (62%) and 11 of the 202 general groups (5%). Fixed wrong reviews = consistent bias.

| Family / configuration | Cond | All-four every pass | Fixed wrong reviews |
| --- | --- | --- | --- |
| gemma-31b thinking-on | P2 | 58 | DEV-006, DEV-013 |
| gpt-6 astra medium | P1 | 58 | DEV-006, DEV-013 |
| gpt-6 luna xhigh batch10 | P1 | 58 | DEV-006, DEV-030 |
| gemini-3.1-pro low | P2 | 57 | DEV-010, DEV-013, DEV-030 |
| gpt-5.6 sol xhigh | P0 | 57 | DEV-006, DEV-013, DEV-030 |
| gpt-6 astra xhigh | P2 | 57 | DEV-006, DEV-013, DEV-030 |
| qwen-27b thinking-off | P1 / P2 | 55 / 54 | DEV-010, 013, 014, 015, 053 (+DEV-030 at P2) |
| clef (OpenRouter) | P0 / P1 / P2 | 54 / 51 / 49 | 6 / 9 / 11 fixed reviews (P0: DEV-006, 029, 030, 053, 054, 056) |
| perplexity decider | P0 / P1 / P2 | 54 / 54 / 54 | DEV-006, 013, 028, 029, 030, 035 in every condition |
| openjev fixed / adaptive | P0 | 53 / 52 | 7 / 8 (both include DEV-005, 006, 008, 011, 029, 030) |
| luna decisions | P0 / P1 / P2 | 49 / 51 / 49 | 11 / 9 / 11 |
| kev | P1 / P2 | 49 / 46 | 11 / 14 |
| clef-flash (OpenRouter and Cloudflare direct) | P0, P1, P2 | 45 to 47 | 13 to 15 |
| tev 1 4B | P0 / P1 / P2 | 45 / 44 / 44 | 15 / 16 / 16 |
| liquid d1 | P0 / P2 | 43 / 41 | 17 / 19 |
| semif generated | P0 / P1 / P2 | 35 / 26 / 43 | 25 / 34 / 17 |
| alex openjev 4B / 0.8B | P0 | 39 / 3 | 21 / 57 |
| anyjev L1; anyjev generated P0/P1/P2; qwen-0.6b q4km P0/P1/P2 | | 6; 0/0/1; 0/0/0 | 54; 60/60/59; 60/60/60 |

Only 7 configurations are both perfectly stable and at or above 55/60, all general LLMs (the six rows above the Qwen-27b line plus one more at 55); no decision model is both perfectly stable and above 54. Among native decision models, 31 of 50 groups changed no answer at all across three passes; the exceptions are Solar (3 to 5 changed reviews per condition), Jev and the generated-JSON clones.

### 7.4 Unstable but right on average (>= 5 unstable reviews, mean all-four >= 54)

28 configurations, all general LLMs. Examples:

| Family / configuration | Cond | All-four per pass | Mean | Unstable reviews |
| --- | --- | --- | --- | --- |
| sonnet-5 low batch10 | P2 | 57 / 54 / 57 | 56.0 | 9 (DEV-005, 006, 010, 013, 014, 018, 030, 053, 056) |
| qwen-35b thinking-on (hosted) | P1 | 52 / 54 / 57 | 54.3 | 8 |
| gpt-5.6 luna medium | P0 | 54 / 57 / 55 | 55.3 | 7 |
| haiku-4.5 batch10 | P1 | 53 / 56 / 59 | 56.0 | 7 |
| sonnet-5 medium batch10 | P0 / P1 / P2 | 56/55/57, 58/56/53, 57/56/55 | 56.0 / 55.7 / 56.0 | 7 each |
| gemma-26b thinking-on | P0 | 59 / 56 / 58 | 57.7 | 5 (DEV-002, 005, 013, 014, 048) |
| fable-5.1 low batch10 | P0 | 56 / 58 / 57 | 57.0 | 5 |
| qwen-27b xhigh | P0 | 58 / 57 / 58 | 57.7 | 5 |
| sonnet-5 high batch10 | P0 | 58 / 57 / 57 | 57.3 | 5 (DEV-006, 010, 013, 018, 030) |

The most unstable clean configurations are all small local generative runs: Qwen3 0.6B thinking-on P2 (55 unstable reviews, scores 3/1/1), Qwen3 1.7B thinking-on P2 (42; 8/9/8), Gemma E2B thinking-on P0 and P2 (24 each; 38/37/39 and 36/36/35), OpenJev generated P1 (23 each, on and off).

Interpretation. Repeatability splits the roster cleanly into two failure modes. Typed decision heads (Clef, Flash, Luna, Perplexity, Tev, Liquid, Kev, OpenJev native) are deterministic to the answer: 31 of 50 decision groups changed nothing in three passes, so their 6 to 19 wrong reviews are a fixed bias you will get on every batch. General LLMs are stochastic on the same 5 to 9 reviews that are hard for everyone, so a three-pass spread of 3 to 6 points (e.g. Haiku 53/56/59) is normal and a single-pass score is a draw from that spread. The instability is concentrated: 8 of the 10 most-flipped reviews are the 10 hardest, and the two hard reviews that do not flip (DEV-029 off-topic, DEV-005 outcome-only) are the ones models get wrong the same way every time. Confidence: solid for counts and overlaps; descriptive-only for the deterministic-vs-stochastic framing (serving stack, seeds and sampling are unobserved).

---

## 8. Confidence and calibration: the number next to the answer

Source: per-record provider confidence and option probabilities from the saved projections (Jev direct P0/P1/P2 180 records; Solar 539, Tev 540, Liquid 540, Clef 540, Clef Flash 539, Luna Decisions 540 records across nine fresh1-3/P0-P2 stages; Clef/Flash/Luna expose provider confidence plus chosen-option probability only). All thresholds are retrospective: no abstention was executed in any run, and no model's confidence is calibrated. Script `s08_confidence.py`.

**Calibration summary, all fields and stages pooled per model (N = field answers):**

| model | N | mean confidence | accuracy | conf minus acc | ECE (confidence, 5 bins) | ECE (chosen probability) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Jev | 720 | 0.947 | 0.956 | -0.009 | 0.011 | 0.015 |
| Solar | 2,156 | 0.831 | 0.950 | -0.119 | 0.145 | 0.041 |
| Tev | 2,160 | 0.897 | 0.915 | -0.019 | 0.047 | 0.047 |
| Liquid | 2,160 | 0.939 | 0.906 | +0.033 | 0.035 | 0.055 |
| Clef | 2,160 | 0.727 | 0.944 | -0.217 | 0.217 | 0.077 |
| Clef Flash | 2,156 | 0.563 | 0.921 | -0.358 | 0.358 | 0.133 |
| Luna Decisions | 2,160 | 0.876 | 0.936 | -0.060 | 0.074 | 0.039 |

Bins (n: accuracy @ mean confidence) tell the shape. Jev is the only model whose bins step cleanly: sentiment 9: 33% @0.42, 6: 50% @0.60, 24: 92% @0.81, 44: 100% @0.95, 97: 100% @1.00. Clef and Clef Flash are **systematically under-confident**: Clef sentiment puts 243 of 540 answers below 0.5 confidence and gets 85% of them right; Clef Flash sentiment puts 371 of 539 below 0.5 at 79% accuracy, and never emits a sentiment confidence above 0.9. Liquid is the only over-confident model overall, driven by follow-up (376 answers at 0.99+, 95% right) and sentiment (55 answers below 0.5 at 40%). Tev's serious-concern field has 33 answers below 0.5 confidence at 27% accuracy, i.e. a usable "I don't know" signal, but also 135 answers at 0.99+ that are only 93% right.

**Provider confidence and chosen-option probability are different numbers for three models.** Mean (probability minus confidence) and share of answers where they differ by more than 0.2: Tev 0.000 (0%; the two are identical by construction), Jev +0.016 (0.6%), Liquid +0.015 (0.3%), Luna +0.035 (3.2%), Solar +0.117 (24.4%), Clef +0.143 (32.5%), Clef Flash +0.225 (55.3%). Pooled ECE on chosen probability is far better than on confidence for Solar (0.041 vs 0.145), Clef (0.077 vs 0.217) and Flash (0.133 vs 0.358). A threshold policy on these three models keys on the wrong field if it uses "confidence".

**Does low confidence point at the hard reviews?** Ten lowest min-field-confidence reviews at first P0 versus the ten hardest across all 1,004 run-passes (DEV-030, 006, 013, 029, 005, 022, 018, 028, 059, 010):

| model | overlap with hard-10 | overlap IDs | DEV-029 / DEV-030 in low-10 |
| --- | ---: | --- | --- |
| Jev (direct/P0) | 7 | 005, 010, 013, 022, 029, 030, 059 | both |
| Luna Decisions | 5 | 005, 010, 013, 022, 030 | 030 |
| Tev | 4 | 013, 018, 030, 059 | 030 |
| Clef | 4 | 013, 018, 030, 059 | 030 |
| Clef Flash | 4 | 013, 018, 022, 030 | 030 |
| Solar | 3 | 006, 022, 030 | 030 |
| Liquid | 2 | 013, 029 | 029 |

Jev's confidence is the most informative hard-case detector in the panel: 7 of its 10 least-confident reviews are in the global hard-10, and both 7-native-missed reviews are in it. Solar, the highest-scoring native run, is the least informative (3 of 10).

**The off-topic soup review (DEV-029, reference insufficient_information on all four fields).** Confidence / chosen probability per field at first P0, and where DEV-029's min confidence ranks among the 60 (1 = least confident):

| model | sentiment | follow-up | serious concern | testimonial | min-conf rank / 60 |
| --- | --- | --- | --- | --- | ---: |
| Jev | mixed 0.46/0.57 | no 0.84/0.89 | no 0.91/0.94 | no 0.88/0.92 | 4 |
| Liquid | insufficient 0.31/0.45 | no 1.00/1.00 | no 1.00/1.00 | no 0.99/0.99 | 2 |
| Luna | mixed 0.57/0.66 | no 0.86/0.91 | no 0.97/0.98 | no 1.00/1.00 | 20 |
| Clef | mixed 0.30/0.61 | no 0.92/0.97 | no 0.98/0.99 | no 0.95/0.98 | 21 |
| Solar | negative 0.68/0.87 | no 1.00/1.00 | no 0.84/0.96 | no 0.87/0.97 | 37 |
| Clef Flash | mixed 0.63/0.84 | no 0.86/0.95 | no 0.97/0.99 | no 0.41/0.75 | 49 |
| Tev | mixed 0.98/0.98 | no 0.99/0.99 | no 0.99/0.99 | no 0.95/0.95 | 57 |

Two models "know" something is wrong, and only on sentiment: Liquid (rank 2, and it is the one model that actually answers insufficient_information there) and Jev (rank 4). Every model answers "no" on follow-up, serious concern and testimonial with confidence 0.84 to 1.00; Tev is more confident on the soup review than on 56 other reviews. Confidence does not detect off-topic input on the fields where the business decision is made.

**Confidently wrong, all stages:** wrong field answers at confidence >= 0.9 / >= 0.99: Jev 5 / 0 of 32 wrong (720 answers); Solar 46 / 25 of 107; Tev 66 / 9 of 183; Liquid 69 / 37 of 204; Clef 24 / 0 of 120; Clef Flash 9 / 0 of 171; Luna 27 / 18 of 138. At first P0, Solar is wrong at confidence 1.00 on DEV-013 sentiment, DEV-029 follow-up, DEV-030 sentiment and DEV-030 serious concern; Liquid at 1.00 on DEV-027 testimonial, DEV-029 follow-up and serious concern, DEV-059 follow-up.

**Smallest retrospective threshold that removes every wrong answer at first P0, and what it leaves:** Jev is the only model where this is tolerable: sentiment >0.71 keeps 54/60, follow-up >0.84 keeps 54, serious concern >0.91 keeps 52, testimonial >0.96 keeps 52. For Solar the same rule keeps 3, 0, 10 and 33 of 60; for Luna testimonial it keeps 0/60; for Clef serious concern 2/60; for Tev sentiment 13/60. Because wrong answers at confidence 1.00 exist for Solar, Liquid and Luna, no threshold below "discard everything" is error-free on those fields.

Confidence: **solid** for the counts; **descriptive-only** for ECE (60 reviews, pooled stages share the same 60 texts, so bins are not independent samples); the "Jev knows the hard ones" pattern is **descriptive-only** on one P0 pass.

Implication: if a workflow must use a single-model gate, Jev's confidence is the only one in this panel that behaves like a probability and the only one that would have flagged the off-topic review by rank. For every other native model, use chosen-option probability rather than "confidence", and expect that no threshold removes the 1.00-confidence errors.

---

## 9. Model-specific quirks worth a slide

Script: `s09_quirks.py`, computed over all 1,004 run-passes (data.json 290, extended 637, additional 77). Each item: numbers, why it matters, confidence tag.

**Q1. Thirty-nine run-passes answer one field with one label on >= 55 of 60 reviews.** Distribution: testimonial = yes 17 (qwen3-0.6b q4km in 4 passes x P0 and P1, alex-openjev 0.8B 4 passes, laya-multilingual 3, qwen3-0.6b thinking-on P2 2), testimonial = no 12 (semif direct/serial/shared 9 passes at 56/60, luna-decisions P2 3 passes at 55/60), serious_concern = yes 6 (anyjev raw 3 passes at 60/60, laya-multilingual 3 at 59/60), follow-up = yes 3 and sentiment = neutral 3 (anyjev raw). The testimonial = yes rows score exactly the reference base rate (9/60) on that field; the testimonial = no rows score 53 to 54/60 on the field while finding at most 4 of 9 testimonials. Twenty-one of the 39 rows get a respectable field score purely because their constant label is the majority reference label. AnyJev raw's "serious_concern = yes on 60/60" also gives it 25/25 recall on the escalation class at 0/60 overall. Why it matters: a field total hides a constant classifier. Confidence: solid.

**Q2. Thirteen families return byte-identical 60-vectors across every pass of a configuration+condition; the deterministic ones are mostly the wrong ones.** Among configuration+conditions with >= 2 passes: anyjev 7/7 identical, semif 6/6, kev 3/3, laya 3/3, luna-decisions 3/3, perplexity 3/3, tev 3/3, clef 4/6, clef-flash 4/5. Frontier general models are rarely identical pass to pass: sonnet-5.5 4/12, opus-5.5 3/12, gpt-6-astra 3/12, gpt-5.6-luna 0/12, gpt-5.6-terra 0/12, sonnet-5 0/12, deepseek 0/9. Of the 43 fully identical configuration+conditions, 41 score below 54/60 or are decision models; the identical frontier examples sit at 56 to 58. Why it matters: "same answer three times" is a serving property; it is evidence of reproducibility, not of correctness, and it means a wrong answer ships identically every time. Confidence: solid.

**Q3. Thinking-off beats thinking-on in only two places, both with a format story.** Across 49 off-vs-on comparisons (same model, condition, pass): on wins 42, off wins 7, ties 3 with one meaningless tie at qwen3-0.6b where both have near-zero valid output. The off wins: qwen3-1.7b local in all three conditions (off 28/24/29 vs on 23/14/8; the gap is almost entirely testimonial, +8/+21/+35 field matches for off), hosted qwen3-8b json-object mode in all three (off 39/39/43 vs on 11/13/14, because thinking-on returned only 14 to 16 valid outputs of 60), and qwen3.6-35b P2 once (52 vs 48, on had 54 valid). Everywhere else thinking helps: gemma-26b +6/+6/+3, gemma-e4b +9/+5/+5, qwen3.5-4b +8/+16/+7, deepseek fresh1 low vs off +10 in every condition. Why it matters: when "no thinking" wins, check validity first; it is usually the reasoning channel breaking the JSON, not reasoning hurting judgement. Confidence: solid for the tallies; descriptive-only per family.

**Q4. Output failures do not cluster on long reviews; they cluster on the hard ones.** 2,234 non-ok positions over 60,240 (2,066 invalid_output, 108 service_error, 42 never_sent, 18 other). Per-review failure count ranges 26 to 56. Top: DEV-013 (56), DEV-020 (56), DEV-015 (51), DEV-029 (51), DEV-016 (49), DEV-006 (48). Spearman rank correlation between failure count and text length = -0.07 (DEV-029 is the second-shortest review at 52 characters and the fourth most failed; DEV-030 is the second-longest at 201 and 10th). Three of the six most-failed reviews (DEV-013, DEV-029, DEV-006) are the disputed or off-topic reviews from Section 1. Why it matters: a parser failure on the hard case is not noise, it is the model stalling on exactly the input a human must see; route invalid output to the same queue as insufficient_information. Confidence: solid for counts; descriptive-only for the "hard" reading (most invalid positions come from small local models with whole-run format failures).

**Q5. "Low" and "not applicable" effort still reason, a lot.** 97 run-passes report reasoning tokens > 0 while effort is off, low or not applicable. Haiku 4.5 (effort "not applicable") spends 18,435 to 45,302 reasoning tokens per pass; DeepSeek flash "low" 18,127 to 25,005; Qwen3.8-27b "low" 19,817 to 20,324. Mean P0 output tokens per effort show how little the label means across vendors: qwen-4b thinking on/off 49x, qwen-35b 25x, gemma-26b 19x, deepseek 11x, gpt-5.6-sol low to xhigh only 1.4x, opus-5.5 1.5x. Clef, Clef Flash and Luna Decisions report output_tokens = 0 on 540/540, 539/540 and 540/540 records (typed heads, no generation). Why it matters: "low effort" is not a cost control you can compare across providers; bill by observed tokens, and note that a zero-output-token head cannot be charged for reasoning it never emits. Confidence: solid (token fields in the catalog).

**Q6. Batch-of-10 vs one-review runs: same model and effort, different misses.** Fifteen Claude/Codex model-effort pairs at P0 have both a run named batch10 and one not (batch size taken from the experiment id; the original batch size is not re-verified here). Mean all-four: single higher 8, batch10 higher 5, tie 2; the spread is within 1 to 4 points and within the three-pass repeat range. The misses differ more than the totals: DEV-010 ("There was no harassment or pressure ... It was a good interview", reference positive/no/no/yes) is missed by batch10 runs but not the single run in 10 of 15 pairs; DEV-013 in 8 of 15; DEV-006 is the reverse (single-only miss in 6 pairs). Separately, 17 run-passes have all their invalid outputs in exactly one block of 10 consecutive IDs (Gemini 3.7 Flash high and 3.8 Flash medium always block 2, DEV-011 to DEV-020, in P0, P1, P2 and repeats; Codex luna-xhigh, terra-low/medium, astra-medium one block each in their historical P1/P2 passes). Why it matters: batching changes which candidate is wrong, and a batch failure takes ten candidates down together, always the same ten. Confidence: descriptive-only (runs differ in date and serving; not controlled).

**Q7. The frontier converges on the same wrong answers, literally.** Among the 373 run-passes with 60 valid outputs and all-four >= 57, there are only 101 distinct full 60-vector answer sets, and the three largest cover 101 run-passes: one set of 44 run-passes shared by seven different models (gpt-6-astra 16, gpt-6-sol 10, gpt-5.6-sol 8, fable-5.1 7, sonnet-5, opus-5.5, gemini-3.6-flash) scoring 57 and missing exactly DEV-006, DEV-013, DEV-030; one set of 32 run-passes (sonnet-5.5 11, opus-5.5 8, gpt-6-sol 4, sonnet-5 3, deepseek 3, fable 2, opus-5 1) scoring 58 and missing DEV-006 and DEV-030; one of 25 (gpt-5.6-sol 12, gpt-6-sol 8, others) at 57 with the same three misses. The most common miss-set among those 373 strong run-passes is {DEV-006, DEV-013, DEV-030} at 119, then {006, 030} at 68 and {006, 013} at 48: 270 of 373 strong run-passes miss nothing outside the three disputed labels (the three sets above plus {013, 030} at 15, single-label misses at 8, 7 and 4, and one 60/60 run). Why it matters: at the top, the "error" is a property of the reference, and a second frontier model gives you no independent check on it; disagreement-based deferral between two frontier models would accept those three reviews with identical wrong answers. Confidence: solid (exact vector equality; 60/60 valid runs only).

**Q8. Decision models pass the "same answer" test and fail the "same mistake" test too.** Clef 54/51/49, Luna 49/51/49 and Perplexity 54/54/54 are byte-identical across all three passes at each prompt, and their P2 miss sets are therefore fixed; Luna's P2 says testimonial = no on 55/60 and finds at most 4 of 9 testimonials in every pass. Why it matters: a stable 49 is a known, repeatable list of candidates the system will always get wrong. Confidence: solid.

Label vocabulary check: 0 ok/valid predictions use a label outside the guide's vocabulary, so none of the above is a parsing artefact.

---

## 10. Cost-efficiency frontier, recomputed

Source: 1,004 run-passes; cost kind from `common.run_cost` (data.json, extended catalog, supplemental decision runs), API-equivalent estimates from `subscription-price-estimates.json`, Jev native-prompt known charges from `jev-native-prompt-findings.json` (the extended catalog files those same nine amounts under `estimatedUsd`; the findings feed wins for those stages, and the Jev direct and repeat2/3 runs remain estimates). Script: `s10_cost.py`. Run-pass counts: Table A observed/known charge N = 303, Table B estimate N = 262, Table C unknown N = 439. Matches per dollar = all-four / usd for one 60-review pass. Human review, subscription quota and local hardware are not priced anywhere.

### 10.1 Table A, observed or known provider charges only: Pareto frontier (no other charged run is both cheaper and at least as good)

| run | model | effort | cond/pass | valid | all-four | kind | usd per pass | matches per $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4.1-flash off | DeepSeek V4.1 Flash | off | P0 fresh2 | 60 | 49 | known | 0.002657 | 18,445 |
| deepseek-v4.1-flash off | DeepSeek V4.1 Flash | off | P0 original | 60 | 54 | observed | 0.002681 | 20,141 |
| gemma4-31b off | Gemma4 31B | off | P0 repeat2 | 60 | 55 | known | 0.005489 | 10,020 |
| gemma4-31b off | Gemma4 31B | off | P0 original | 60 | 56 | observed | 0.005555 | 10,081 |
| deepseek-v4.1-flash low | DeepSeek V4.1 Flash | low | P1 original | 58 | 57 | observed | 0.009814 | 5,808 |
| gemma4-31b on | Gemma4 31B | on | P0 repeat3 | 60 | 58 | known | 0.012927 | 4,487 |
| gemma4-26b-a4b on | Gemma4 26B-A4B | on | P0 fresh1 | 60 | 59 | known | 0.019313 | 3,055 |

Cost to reach a level, Table A, any condition or pass: 57/60 from $0.009814 (DeepSeek low P1, 39 runs sit at 57), 58/60 from $0.012927 (Gemma 31B on, 25 runs at 58), 59/60 from $0.019313 (Gemma 26B on fresh1; the only other charged 59s are Gemma 26B on original $0.021149, Qwen 27B low $0.049237, Qwen 27B medium fresh2 $0.066382). No charged run reached 60.

Restricted to P0 first passes (original, fresh1, pass1; N = 43 charged runs) the frontier is DeepSeek off 54 at $0.002681, Gemma 31B off 56 at $0.005555, DeepSeek low 57 at $0.015135 (valid 57), DeepSeek low fresh1 58 at $0.017435 (valid 59), Gemma 26B on 59 at $0.019313.

Where the decision models sit (all known charges, 60 one-review requests): Jev via OpenRouter P0 54/60 at $0.005891 (9,167 matches per dollar) is the cheapest decision-model pass but is dominated by DeepSeek off original (54 at $0.002681); Clef Flash 45 at $0.011942, Luna Decisions 49 at $0.013352, Perplexity 54 at $0.015427, Liquid 43 at $0.015689, Tev 45 at $0.016343, Solar 55 at $0.022067, Clef 54 at $0.031847. None of the seven native runs is on the all-runs frontier once general hosted runs with observed charges are admitted. The DeepSeek off 54 is a single pass; its three fresh P0 passes scored 48, 49 and 48 at the same price, which is why the fresh2 row also appears on the frontier at 49.

### 10.2 Table B, API-equivalent estimates (not bills): frontier

| run | model | effort | cond/pass | valid | all-four | usd estimate | matches per $ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| jev113 native-prompts P2 fresh2 (stopped at 17) | Jev 1.13 | - | P2 fresh2 | 17 | 15 | 0.001941 | 7,729 |
| typesafe-jev113-v2 (direct) | Jev 1.13 | - | P0 original | 60 | 54 | 0.005891 | 9,167 |
| codex-gpt-6-luna-high-batch10 | gpt-6 luna | high | P0 original | 60 | 56 | 0.008251 | 6,787 |
| codex-gpt-6-luna-high-batch10 | gpt-6 luna | high | P1 original | 60 | 57 | 0.008492 | 6,713 |
| codex-gpt-6-luna-xhigh-batch10 | gpt-6 luna | xhigh | P1 original | 60 | 58 | 0.008984 | 6,456 |
| codex-gpt-5.6-luna-high | gpt-5.6 luna | high | P1 original | 60 | 59 | 0.016041 | 3,678 |

Reference points in the same estimate ledger: Opus 5.5 high batch10 P0 59/60 at $0.222052 (266 per dollar), Sonnet 5.5 low pass3 P0 58 at $0.067172, Sonnet 5 max 59 at $0.691936, Opus 5 max 58 at $1.714615, Fable 5.1 max 58 at $2.364710 (25 matches per dollar). Cheapest estimate at 57 is $0.008492, at 58 $0.008984, at 59 $0.016041, all Codex luna batch10/single rows. These are list-price proxies for subscription usage and must not be plotted with Table A.

### 10.3 Table C, unknown cost (439 run-passes)

Largest groups: Qwen 0.6B 36, OpenJev 36, gpt-5.6 terra 34, gpt-5.6 luna / gpt-6 astra / gpt-6 sol / gpt-6 luna 30 each (Codex repeat passes without a priced phase), gpt-5.6 sol 24, Qwen 1.7B 24, Gemma E2B 24, AnyJev 24, SemIf 21, Gemma E4B 20, Laya 9, Qwen 4B 9, Alex 8, Clef and Clef Flash direct 15, plus single interrupted hosted passes. Unknown is not zero: the local ladder and the Codex repeat series have no per-run price at all.

### 10.4 Rare-class gates by cost

Over all 1,004 run-passes: 740 reach serious_concern recall 25/25 (640 general, 100 decision), 571 reach testimonial recall 9/9, and only 99 match all 10 reference insufficient_information cells.

| gate | cheapest observed/known-charge run | cheapest estimate-only run |
| --- | --- | --- |
| concern recall 25/25 | DeepSeek Flash off, P0 original, 54/60, concern 25 TP / 0 FP, testimonial 6/0/3, 10/10 insufficient cells, $0.002681 (N = 245 charged runs qualify) | Jev direct P0, 54/60, 25/0/0, testimonial 8/0/1, 4/10 insufficient cells, $0.005891 (N = 259) |
| concern recall 25/25 and precision 1.0 | same DeepSeek off P0 run, $0.002681 (N = 217) | same Jev run |
| testimonial recall 9/9 | DeepSeek Flash off, P0 fresh2, 49/60, testimonial 9 TP / 4 FP, $0.002657 (N = 129); cheapest with 0 FP is Gemini 3.8 Flash low P0 at $0.021493 with 9/1/0 | gpt-5.6 luna low batch10 P0, 56/60, 9/0/0, $0.014328 |
| all 10 insufficient_information cells | DeepSeek Flash off P0 original, $0.002681; next Qwen 27B off P1 repeat3 55/60 at $0.010405; Gemini 3.8 Flash low P0 57/60 at $0.021493 (N = 22) | gpt-6 luna medium batch10 P1, 52/60, $0.007263; Sonnet 5.5 low pass3 P0 58/60 at $0.067172 (N = 57) |

Two cautions the slide must carry. First, 25/25 recall is cheap to buy because it is cheap to fake: AnyJev raw (unknown cost, 0/60) also has 25/25 recall by answering "yes" on every review, so recall only means something next to precision, and 217 charged runs have both. Second, the $0.0027 DeepSeek off run that clears every gate (54/60, 25/0/0, 10/10 insufficient cells) is one pass; the same configuration's fresh passes scored 48 to 49 with 4 testimonial false positives and 6 to 7 of 10 insufficient cells, so the gate-clearing pass is not a stable property of the configuration. Jev clears the concern gate in all six of its P0 passes (25/0/0 every time) but matches only 4 of the 10 insufficient_information cells in every pass.

Confidence: solid for the charges, frontier membership and gate counts (exact, source-bound); descriptive-only for any "cheapest configuration" claim, since single passes of the same configuration differ by up to 6 matches and the reference is provisional.

---

## 11. What would it take: the identical-answer rule applied to every costed pair

Rule copied from `native-agreement-policy-v1.json`: accept a review only when both runs return the identical four-field vector and both are valid; otherwise defer to a human. Pool: every first-P0 run with a per-pass charge (data.json originals, extended fresh1/pass1, native fresh1): 42 runs with an observed or known provider charge (8 decision, 34 general), plus 55 runs costed only by an API-equivalent estimate from `subscription-price-estimates.json` (Claude and Codex subscription CLI runs) or the catalog's estimate field. 4,656 pairs evaluated: 861 charge-only (Table A), 3,795 estimate-involving (Table B). Self-repeat pairs (same model and effort at two passes: 8 in A, 13 in B) are excluded from the tables and reported on one line. Retrospective on the same 60 development reviews, not out-of-sample. Script `s11_agreement_general.py`. The saved Solar + Perplexity pair reproduces exactly (53 accepted, 0 errors, $0.03749436).

**Table A, observed/known charges only, 853 cross-configuration pairs, 423 with zero accepted errors (accepted range 6 to 60, errors 0 to 6). Top pairs with zero accepted errors:**

| accepted | deferred | two-run charge | run A | run B | deferred among 006/013/029/030 |
| ---: | ---: | ---: | --- | --- | --- |
| 58 | 2 | $0.06855 | Qwen3.8 27B low (fp4) | Gemma 4 26B thinking-on fresh1 | 013 |
| 58 | 2 | $0.07039 | Gemma 4 26B thinking-on original | Qwen3.8 27B low (fp4) | 013 |
| 57 | 3 | $0.03675 | DeepSeek V4.1 Flash low fresh1 | Gemma 4 26B thinking-on fresh1 | 006, 030 |
| 57 | 3 | $0.03858 | Gemma 4 26B thinking-on original | DeepSeek V4.1 Flash low fresh1 | 006, 030 |
| 57 | 3 | $0.04946 | DeepSeek Flash low original | DeepSeek Flash high fresh1 | 006, 013, 030 |
| 57 | 3 | $0.06437 | DeepSeek Flash low original | Qwen3.8 27B low (fp4) | 006, 013, 030 |
| 56 | 4 | $0.03445 | DeepSeek Flash low original | Gemma 4 26B thinking-on fresh1 | 006, 013, 030 |

(The DeepSeek low + DeepSeek high pair is the same checkpoint at two efforts; it is a cross-effort pair, not a cross-model one.)

**Budget answers (charge-only):**

| question | answer |
| --- | --- |
| cheapest pair, 0 errors, >= 50 accepted | DeepSeek Flash off + DeepSeek Flash low: 54 accepted, 6 deferred, $0.01782 (same checkpoint, two efforts) |
| cheapest pair, <= 1 error, >= 54 accepted | Gemma 4 31B thinking-off + DeepSeek Flash off: 54 accepted, 1 error (DEV-014), $0.00824 |
| cheapest pair, <= 1 error, >= 56 accepted | Gemma 31B thinking-off + Gemma 26B thinking-on fresh1: 57 accepted, 1 error (DEV-005), $0.02487 |
| best two general LLMs, 0 errors | Qwen 27B low + Gemma 26B on: 58 accepted, 2 deferred (005, 013), $0.06855 |
| best native + general, 0 errors | DeepSeek Flash low + Solar Decide: 55 accepted, 5 deferred (006, 013, 027, 029, 030), $0.03720 |
| pairs beating saved Solar + Perplexity (53, 0 errors, $0.0375) on both axes | 35 of 853 |

The 35 pairs that dominate Solar + Perplexity are all general-LLM pairs built from DeepSeek Flash low, Gemma 26B on, Gemma 31B on/off, Gemini 3.7/3.8 Flash low and Qwen 27B. The cheapest of them: Gemma 31B off + DeepSeek Flash low, 55 accepted, 0 errors, $0.02069, deferring 005, 006, 013, 014, 030. No native + native pair, and no native + general pair, dominates Solar + Perplexity; the best mixed pair (55 at $0.0372) wins on coverage by two reviews at the same price.

**Which reviews the rule sends to a human.** Across all 853 charge pairs the most deferred reviews are DEV-030 (731 pairs), DEV-013 (684), DEV-006 (630), DEV-022 (533), DEV-029 (496), DEV-053 (436), DEV-005 (426), DEV-028 (425). The most frequently *accepted-in-error* reviews are DEV-013 (134 pairs), DEV-006 (105), DEV-030 (88), DEV-028 (56), DEV-005 (54), DEV-010 (53), DEV-053 (43), DEV-029 (38). So the three disputed reference labels are both the most deferred and the most commonly shared wrong answer; the off-topic review slips through two agreeing runs in 38 pairs. Among the top zero-error pairs, none defers all four of 006/013/029/030: the Gemma + Qwen pairs defer only DEV-013 and get the other three right together, while the DeepSeek-based pairs defer 006, 013 and 030 and agree correctly on 029.

**Self-repeat pairs (same model and effort, two passes), charge-only:** Gemma 26B on 58 accepted / 0 errors / $0.0405; DeepSeek Flash low 57 / 0 / $0.0326; Qwen 27B xhigh 56 / 0 / $0.1173; DeepSeek Flash high 53 / 0 / $0.0529; Qwen 3.6 35B on 59 / 5 errors / $0.1310; Qwen 35B off 57 / 9 errors / $0.0146. Running the same model twice is not a second opinion: Qwen 35B off agrees with itself on 9 wrong answers.

**Table B, at least one API-equivalent estimate (estimate, not a bill), 3,782 cross-configuration pairs, 1,612 with zero accepted errors.** The best coverage at zero errors is 58 accepted, reached by gpt-6-sol medium batch10 + DeepSeek Flash low fresh1 ($0.17366, deferring 006 and 030) and by Opus 5.5 high batch10 + Gemma 26B on ($0.24136, deferring only DEV-006). No estimate-involving pair reaches 59 or 60 at zero errors. The cheapest estimate-involving pair with zero errors and >= 55 accepted is DeepSeek Flash low + gpt-6-luna high batch10 at 56 accepted, $0.02339 (the Codex estimate is a list-price reconstruction of subscription usage, not a charge). Self-repeat pairs in this table show the same lesson as Table A: Jev original + Jev fresh1 agree on 59 with 5 errors; Sonnet 5 xhigh twice, 58 with 1 error; Fable 5.1 medium twice, 58 with 2 errors.

Confidence: **solid** for every count (exact, deterministic, source-bound); **descriptive-only** for any ranking of pairs (runs differ in route, batch size, provider precision and pass identity; 4,656 pairs on the same 60 reviews are not independent trials; several candidate runs are the same checkpoint at different passes or efforts). No pair is a recommended production configuration.

Implication: the agreement rule is not a native-decision-model trick. On this set two cheap general LLMs on OpenRouter (Gemma 26B thinking-on plus DeepSeek Flash low or Qwen 27B low, $0.04 to $0.07 per 60 reviews, observed charges) accept 57 or 58 reviews with zero reference errors and defer two or three, which beats the best native pair on coverage at similar cost. The reviews they defer are the disputed labels, so the human queue is where the label noise lives. What the rule still cannot do is catch a shared blind spot: DEV-029 was accepted with the same wrong answer by 38 of 853 pairs.

---

## 12. New insights not in the first synthesis

Each entry: headline, numbers, source and script, one-line implication for a business-critical workflow, confidence tag. Where a difference sits inside the 60-review label noise (the three disputed labels move most runs by 1 to 3 points) it is said so.

### 12.1 The dominant error in the study is one semantic collapse, and decision models make it 2 to 6 times more often

Reference "insufficient_information" is answered with some definite label 25% to 31% of the time on follow-up, serious concern and testimonial (24.9%, 31.2%, 26.3%), and with the nearest label, no, 21% to 26% (22.0%, 25.9%, 21.3%), over 58,006 valid answers, while definite labels drift to "insufficient" only 0.6% to 3.1% of the time. Decision-category run-passes match the 10 reference-insufficient cells at 19% to 45% versus 71% to 84% for general LLMs; on follow-up the gap is 25.0% vs 86.5%. Volume is not the issue (decision runs emit the label at or above base rate on two fields); placement is. Source: `s02_confusion.py`, `s06_rare_classes.py`, all 1,004 run-passes. Implication: treat "insufficient_information" as a separate detection task with its own recall metric; the four-field total hides a 4x gap on exactly the cases that need a human. Confidence: solid for counts; descriptive-only for the category split.

### 12.2 At the top, the models do not just score alike, they answer alike, byte for byte

Among the 373 run-passes with 60 valid answers and at least 57/60, there are only 101 distinct full answer sets. One set is shared by 44 run-passes from seven different model families, missing exactly DEV-006, DEV-013 and DEV-030. 270 of 373 strong run-passes miss nothing outside those three disputed labels. Source: `s09_quirks.py` Q7. Implication: a second frontier model is not an independent check on the reviews that matter most; a two-frontier agreement rule accepts the disputed answers with identical confidence. Diversity of failure, not strength, is what a second opinion needs to buy. Confidence: solid (exact vector equality). The three misses are inside the label noise, which is the point.

### 12.3 The agreement rule works better with two cheap general LLMs than with two decision models

Applying the identical-answer rule to all 853 cross-configuration pairs of charged first-P0 runs: Qwen 27B low + Gemma 26B thinking-on accepts 58 with 0 reference errors at $0.0686 (observed charges), deferring only DEV-005 and DEV-013; Gemma 31B off + DeepSeek Flash low accepts 55 with 0 errors at $0.0207. 35 pairs dominate the saved Solar + Perplexity result (53, 0 errors, $0.0375) on both coverage and cost; none of them contains a native decision model. Running the same model twice is not a second opinion (Qwen 35B off agrees with itself on 9 wrong answers). The 58/0 result is pass-sensitive: the same Qwen run paired with Gemma 26B fresh2 gives 57 accepted with 1 error, and with fresh3 gives 59 with 1 error, so "zero errors" here is one draw, not a property of the pair (independent recomputation, 8 October 2026). Source: `s11_agreement_general.py`. Implication: pick the pair for complementary failure modes and cheap per-review price, not for category; and budget for the 2 to 5 deferred reviews per 60, which are the disputed labels. Confidence: solid for counts; retrospective on the development set, no pair is a recommended configuration.

### 12.4 Determinism is a decision-model property; stochasticity is a frontier-model property, and each has a cost

Of 252 configuration-conditions with three passes, 31 of 50 decision groups (62%) changed no answer at all, versus 11 of 202 general groups (5%). No decision model is both perfectly stable and above 54/60; the seven perfectly stable configurations at 55 or better are all general LLMs. General LLMs flip 5 to 9 reviews across passes and those are the hard reviews (8 of the 10 most-unstable are the 10 hardest; Jaccard 0.67). Source: `s07_repeatability.py`. Implication: a decision model gives you a fixed wrong list you can audit once; a frontier model gives you a different wrong list each batch, so a single-pass benchmark score is one draw from a 3 to 6 point spread. Monitoring must count per-review flips, not totals. Confidence: solid for counts; the serving-stack explanation is descriptive-only.

### 12.5 Jev's confidence is the only one in the native panel that behaves like a probability, and the field everyone calls "confidence" is not the probability

Pooled expected calibration error on provider confidence: Jev 0.011, Liquid 0.035, Tev 0.047, Luna 0.074, Solar 0.145, Clef 0.217, Clef Flash 0.358. Clef Flash's "confidence" and its chosen-option probability disagree by more than 0.2 on 55% of answers; Clef 33%, Solar 24%. Jev's 10 least-confident reviews include 7 of the 10 globally hardest and both reviews all seven natives missed; Solar's include 3. On the off-topic soup review every model answers "no" on the three business fields at 0.84 to 1.00 confidence. Source: `s08_confidence.py`, 3,418 field-answer records. Implication: if a vendor exposes two numbers, threshold on the option probability, and expect even the best-calibrated one to be confident about the wrong field on off-topic input. Confidence: descriptive-only (60 texts, pooled stages are not independent; no abstention was executed).

### 12.6 The P2 decision tree pushes general LLMs from "negative" to "mixed" and pushes decision models from "no" to "insufficient" on serious concern

Over 299 P0/P1/P2 triplets on positions valid under both prompts, P2 moves sentiment by -0.81 negative and +0.90 mixed per triplet in general LLMs (reference has 8 mixed; P0 already over-predicts it) and moves serious concern by -0.47 "no" and +0.44 "insufficient" per triplet in decision models. P1 to P2 is the harmful step (127 worse, 78 better, 94 same). No review flips in a shared direction across 75% of triplets; six triplets had byte-identical answers under all three prompts. Source: `s03_prompt_versions.py`. Implication: a prompt revision has a direction, and the direction differs by model class; regression-test the label distribution, not the score. Confidence: solid as a within-configuration description; not causal.

### 12.7 Thinking changes sign between 1.7B and 4B, and "low effort" is not a cost control

Qwen 1.7B: thinking hurts in all 12 same-condition pairs, with losses growing with prompt length (P0 -2 to -5, P2 -21 to -24) and almost entirely on testimonial. Qwen 4B and above, and every Gemma size including E2B, thinking helps. At the other end, "low" or "not applicable" effort still emitted 18k to 45k reasoning tokens per pass in Haiku 4.5, DeepSeek Flash and Qwen 27B, while output-token ratios between lowest and highest effort range from 1.3x (gpt-5.6 sol) to 49x (Qwen 4B). Opus 5.5 and gpt-5.6 sol never gained a match from more effort in 9 pairs each; Gemini 3.1 Pro high cost 4x low and lost a match in 7 of 10 pairs. Source: `s04_effort.py`, `s05_size.py`, `s09_quirks.py` Q5. Implication: the effort knob is vendor-specific and cannot be compared across providers; the only observed-charge families where thinking paid for itself at $0.002 to $0.004 per extra match were Gemma 26B and DeepSeek Flash. Confidence: solid for tallies; descriptive-only for any family-level reading (several high-effort losses are batch failures).

### 12.8 The cheapest pass that clears every gate is not a configuration, it is a lucky draw

DeepSeek Flash thinking-off P0 original: 54/60, 25/25 serious-concern recall at precision 1.0, 10 of 10 insufficient_information cells, $0.002681 observed. The same configuration's three fresh P0 passes scored 48, 49 and 48 with 4 testimonial false positives and 6 to 7 of 10 insufficient cells. The all-runs Pareto frontier on observed charges contains no native decision model once hosted general LLMs are admitted (Jev's 54 at $0.0059 is dominated by that DeepSeek pass at $0.0027), but the frontier's cheapest points are single passes with 5 to 6 point repeat spreads. Source: `s10_cost.py`, `s07_repeatability.py`. Implication: never select a configuration from one pass; require the gate to hold across three passes before it counts, and treat recall without precision as fakeable (AnyJev raw reaches 25/25 recall at 0/60 overall by saying "yes" to everything). Confidence: solid for charges; descriptive-only for frontier membership.

### 12.9 Output failures land on the hard reviews, not the long ones

2,234 non-ok positions over 60,240 (2,066 invalid output). Spearman correlation between a review's failure count and its text length is -0.07. The off-topic soup review is the second-shortest text (52 characters) and the fourth most-failed; three of the six most-failed reviews are the disputed or off-topic ones. Source: `s09_quirks.py` Q4. Implication: a parse failure is a signal about the input, not just the parser; route invalid output to the same human queue as "insufficient_information". Confidence: descriptive-only (most failures come from whole-run format breakdowns in small local models).

---

## 13. What to say and what not to say

Safe to put on a slide from this document:

| Claim | Exact value | Script |
| --- | --- | --- |
| Hardest review across all run-passes | DEV-030 matched by 144 of 1,004 run-passes (14.3%) | `s01_difficulty.py` |
| Insufficient-information collapse | reference "insufficient" answered with some definite label 25% to 31% of the time on three fields, and with the nearest label, no, 21% to 26%; decision runs match those cells at 19% to 45%, general at 71% to 84% | `s02_confusion.py`, `s06_rare_classes.py` |
| Frontier convergence | 44 run-passes from 7 model families share one identical 60-answer set; 270 of 373 strong run-passes miss only disputed labels | `s09_quirks.py` |
| Agreement rule with general LLMs | Qwen 27B low + Gemma 26B on: 58 accepted, 0 errors, 2 deferred, $0.0686 observed; 35 of 853 pairs dominate Solar + Perplexity | `s11_agreement_general.py` |
| Determinism split | 31 of 50 decision groups changed nothing in three passes; 11 of 202 general groups did | `s07_repeatability.py` |
| Calibration | ECE on provider confidence: Jev 0.011, Clef Flash 0.358; Flash's confidence and option probability differ by more than 0.2 on 55% of answers | `s08_confidence.py` |
| Prompt direction | P1 to P2: 127 worse, 78 better, 94 same of 299 triplets; P2 shifts general LLMs negative to mixed by 0.9 reviews per triplet | `s03_prompt_versions.py` |
| Thinking sign change | Qwen 1.7B thinking hurts in 12 of 12 pairs; Qwen 4B and all Gemma sizes it helps | `s05_size.py` |
| Cheapest gate-clearing pass | DeepSeek Flash off P0 original $0.002681, 54/60, 25/25 concern at precision 1.0; fresh passes 48 to 49 | `s10_cost.py` |

Not to say: anything that ranks models (every table is a description of saved run-passes on one provisional reference); any causal word about prompts, effort or thinking; any pooled count of reviews; any cost comparison that mixes Table A charges with Table B estimates; any claim that a two-model pair is validated beyond the 60 development reviews; any claim that the three disputed labels are errors of the models rather than of the reference.

## 14. Reproduction

```
cd <worktree root>
python3 -I docs/talk/scripts/common.py          # loader self-check: 1,004 runs, 0 score mismatches
python3 -I docs/talk/scripts/s01_difficulty.py
python3 -I docs/talk/scripts/s02_confusion.py
python3 -I docs/talk/scripts/s03_prompt_versions.py
python3 -I docs/talk/scripts/s04_effort.py
python3 -I docs/talk/scripts/s05_size.py
python3 -I docs/talk/scripts/s06_rare_classes.py
python3 -I docs/talk/scripts/s07_repeatability.py
python3 -I docs/talk/scripts/s08_confidence.py
python3 -I docs/talk/scripts/s09_quirks.py
python3 -I docs/talk/scripts/s10_cost.py
python3 -I docs/talk/scripts/s11_agreement_general.py
```

All scripts read only the committed feeds and projections; none writes a file or makes a network request.

---

Corrections 2026-10-08: strong run-passes missing nothing outside the three disputed labels are 270 of 373, not 235 (235 counted only the three largest miss sets; it omitted {013, 030} at 15, single-label misses at 8, 7 and 4, and one 60/60 run; sections 9, 12.2 and 13). Reference "insufficient_information" is answered with some definite label 25% to 31% of the time and with the nearest label, no, 21% to 26%; the earlier "21% to 26%" and "22% to 26%" figures mixed the two (sections 2, 12.1 and 13).
