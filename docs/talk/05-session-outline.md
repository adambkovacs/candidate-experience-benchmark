# 05 Session outline v2: "Do models like Jev get it right when correctness is business-critical?"

Speaker: Adam Kovacs. Date: 2026-10-08. Format: 15 minutes plus Q&A. Audience: agentic builders, engineers and AI-curious people, mixed seniority, some non-engineers. Delivery: Adam's laptop over Zoom to a TV, AEA branding, saved answers replayed from JSON with an honest "replay" badge, no live inference.

Version 2, written 2026-10-08 after the independent review in 05r-outline-review.md (verdict REVISE) and the computed insights in 01b-deep-analysis.md. Every 05r blocking finding is addressed; the changelog in section 9 says how. v1 stays in git history (commit 4093b84a).

Skeleton: one answer, three proofs, one rule, one call to action. Everything else lives in the appendix for Q&A. The System 1 / System 2 idea is the spine: it opens the talk, explains every proof, and names the rule.

Every number is agreement with the frozen provisional v0.2 reference on the same 60 synthetic reviews. "Matched" always means "matched that reference", never "accurate". Costs carry the label the deck feed gives them today (`public-site/deck/data/answer.json`): "known provider charge", "observed charge" or "API-equivalent estimate". A cost-checker lane is resolving actual provider charges into 06-cost-check.md; that file did not exist when v2 was written, so 06 may relabel some costs and the deck should re-read the feed before export.

## 1. The answer and the three proofs

**The answer, in Adam's voice:**

> So on 60 test reviews, Jev matched our provisional key on 54, general models from a 26B open-weight model up to Opus matched 58 or 59 for roughly four to forty times the estimated spend, and most of Jev's six misses sat on reviews a person would pause on, but two were plain errors, and one of those was a harassment report marked as needing no follow-up. So if the decision matters, what you buy is a rule that hands the hard ones to a person.

**The three proofs:**

| # | Proof | Answers which part of the blurb | Why this one and not the others |
|-|-|-|-|
| 1 | The gap is five reviews. Jev 54, 53, 52 over three passes; Opus 5.5 high 59, 58, 58; Sonnet 5.5 58 in all nine cells. Jev about $0.006 a pass (known provider charge, OpenRouter pass) against Opus about $0.22 (API-equivalent estimate). Jev matched all 25 serious-concern references and still marked the harassment report as needing no follow-up. | "Where that helps" | It is the fairest single picture of what System 1 buys and gives up, and the harassment review threads through all three proofs and the rule. Insight 14 (cost frontier) and 12 (clones) say the same with more rows; appendix. |
| 2 | The soup review. Zero of seven decision models noticed it was off-topic, while 89 of the 113 general configurations with valid answers answered "can't tell" on all four fields. The reviews that split the decision models are the ones a person pauses on. | "Where uncertainty still matters" | The one finding a mixed room will remember, and it shows System 1 running out without anyone taking it on faith. Insight 10 is the source. Insights 5 and 6 are stronger for engineers only; appendix. |
| 3 | A calibrated confidence number is still not a per-review gate, and a longer prompt did not reliably help. Jev's confidence is calibrated on average (ECE 0.011, against Clef Flash 0.358) and it was still 0.96 on a wrong testimonial. Its ten least-confident reviews include seven of the ten hardest, so the number knows "hard", not "off-topic". | "How much confidence should a workflow demand" | It clears the ground for the rule. 01b section 8 turned v1's unmeasured "nobody is calibrated" into a measured and fairer claim. Insights 8 and 9 answer questions the room has not asked yet; appendix. |

**The rule:** agree or defer. Two cheap models that fail differently, accept only identical four-field answers, defer the rest to a person. Decision-model example: Solar Decide + Perplexity Decider, 53 accepted, 0 accepted errors, 7 deferred, $0.037 known charge for both over 60 reviews. General-model example from 01b: Qwen3.8 27B low + Gemma 4 26B thinking-on, 58 accepted, 0 errors, 2 deferred, $0.0686 observed, pass-sensitive.

**The call to action:** a four-step Monday recipe, star the public benchmark now, and classification-bench is being open-sourced, so ask Adam for early access.

## 2. Run of show

Clock is the start time of each beat. Word budgets are for spoken notes only; measured counts are in section 7. Total target 1,550 words so the talk lands at about 14:00 with the three audience moments.

| Beat | Clock | Length | Slides | On the slide (max 12 words) plus the visual | Engagement | Budget | Sources for every number |
|-|-|-|-|-|-|-|-|
| 1. Cold open and answer | 0:00 | 1:10 | S1 Title; S2 The answer | S1: talk title, name, the harassment review text. Visual: the review card only. S2: "Jev 54 of 60. General models 58 to 59. Buy a rule." Visual: two bars, the gap shaded. | Moment 1: "Hands up if you've shipped an LLM classifier to production. Keep it up if you check it with a second model." | 125 | `answer.json` `jev_all_four`, `opus55_high`, `sonnet55_xhigh`; `disputed-reviews-v1.json` DEV-059 |
| 2. Bio | 1:10 | 0:25 | S3 About me | "Adam Kovacs. AI Enablement Academy. Six years Amazon and AWS talent intelligence." Visual: portrait, repo URL in footer. | none | 55 | 03 §5 |
| 3. The launch wave | 1:35 | 1:00 | S4 The launch wave | "Jev, 15 September. About two weeks later, everyone shipped one." Visual: dated timeline, simple build. | none | 120 | `timeline.json` (verified entries only); 02 Part C |
| 4. Proof 1: the gap | 2:35 | 2:05 | S5 Five reviews; S6 What a pass cost | S5: "Jev 54, 53, 52. Opus 59, 58, 58. Sonnet 58 nine times." Visual: bars with three-pass ranges. S6: "Jev $0.006, known charge. Opus $0.22, estimate." Visual: two cards, no size encoding. | none | 265 | `answer.json` all keys; 05r R3 (Opus three passes, `claude-roster-repeats.json` series `opus55-high-batch10`); `jev-confidence-findings.json` DEV-059 follow-up 0.49; 01 §3 row 5 |
| 5. Proof 2: the soup | 4:40 | 2:35 | S7 One of the 60 (text only); S8 Zero of seven (hero, replay); S9 Where they split | S7: the review text. S8: "0 of 7 decision models. 89 of 113 general configurations said can't tell." Visual: seven cards flipping, exact answers. S9: "26 reviews all seven matched. Two reviews all seven missed." Visual: histogram 0 to 7. | Moment 2: "Seven purpose-built decision models saw this review. Shout how many flagged it as off-topic." | 285 | `disputed-reviews-v1.json` DEV-029 answers; `hard-cases.json` histogram and texts; `results/cross-category-v1/findings.md` (89/113/117); 01b §8 soup table; `docs/REFERENCE_REVIEW_V1.md` |
| 6. Proof 3: the number next to the answer | 7:15 | 2:20 | S10 0.96 and still wrong (hero, replay); S11 More instructions, no reliable gain | S10: "Calibrated on average. Still 0.96 on a wrong testimonial." Visual: testimonial field, 60 dots, one hollow red dot at 0.96 stays lit while a threshold line sweeps. S11: "Plain to framing 15 up, 15 same, 9 down. Framing to tree 4, 14, 21." Visual: Clef 54, 51, 49 stepping, with a truncation footnote. | none | 300 | 01b §8 calibration table and hard-10 overlap; `jev-confidence-findings.json` (DEV-027 0.96, DEV-059 0.49, sentiment 0.9 threshold); `prompt-levels.json` tally and Clef series; `docs/CLEF_OPENROUTER_FINDINGS.md` line 21 |
| 7. The rule | 9:35 | 2:35 | S12 Agree or defer (hero); S13 The policy and the queue | S12: "Two cheap models. Agree: accept. Disagree: a person." Visual: 60 cards sorting into two columns, then a second pair re-sorts them. S13: five policy lines, the queue count, the closing question. | Moment 3: show of hands. "Hands up for one model at 0.96. Hands up for two cheap models that agree." | 300 | `native-agreement-policy-v1.json` (all 21 pairs); `docs/talk/scripts/s12_escalation_queue.py` output (queue 35 of 60; 5 zero-error pairs; 6 pairs accepted the soup); 01b §11, §12.2, §12.3 |
| 8. The tool and the Monday recipe | 12:10 | 1:40 | S14 classification-bench; S15 Monday | S14: "Runs offline, 272 tests. Two live routes. Being open-sourced." Visual: pipeline diagram. S15: "Monday: label 60, add can't tell, run two, count the queue." Visual: QR code to the public repo. | none | 180 | 04 §2, §3, §7; 03 §2; Adam's answer on open-sourcing |
| End | 13:50 | buffer 1:10 | | | | | |

Timing method: 140 words per minute for narrative, 130 for number-dense beats, plus the reviewer's interaction costs (moment 1: 25 s, moment 2: 35 s, moment 3: 15 s, hero builds 8 s each). Hard-stop landing line at S12 if the chair signals at 13:00: "That's the rule. The repo has everything else."

### 2b. Speaker notes in full

Spoken voice, first person. Bracketed text is a stage direction, not spoken, and is excluded from the word count.

[notes beat=1]
So, this is one of the 60 candidate reviews. [read S1] "Nice staff. After the trial shift the manager kept asking me out even after I said no twice. I've asked the recruiter to stop him contacting me." Is that a serious concern? Does someone need to follow up? Everyone here got both right in two seconds, and that gut answer is what Kahneman calls System One. TypeSafe borrowed that name for Jev, a model that gives you a typed answer in one pass, and I wanted to know how far it carries when the decision matters. Hands up if you've shipped an LLM classifier to production. [pause] Keep it up if you check it with a second model. [pause] That gap is this talk.
[/notes]

[notes beat=2]
Quick bit about me. I'm Adam, co-founder of the AI Enablement Academy, and before that I spent six years at Amazon in recruiting, where I started the talent intelligence service for AWS. So I have read the pile of candidate feedback, every vendor told me their classifier was accurate, and Amazon taught me to build the measure before trusting the tool.
[/notes]

[notes beat=3]
So, where did all this come from? Jev launched on 15 September, and TypeSafe did something I want to give them credit for: they published a page listing where Jev fails, and almost nobody does that. [timeline builds] About two weeks later, on 1 October, Cloudflare and AWS shipped decision models on the same day, Perplexity's landed that week, and OpenAI's Decisions API went to public beta on 6 October. In between there are a dozen or more others, and most of them speak the same wire format, so switching models is a base URL change.
[/notes]

[notes beat=4]
So, proof one. The gap is five reviews.

Every model got the same 60 reviews and the same four questions: sentiment, does this need a follow-up, is there a serious concern, and is this a testimonial we could use. About the answer key: an AI assistant drafted the 60 reviews and the key, a person then checked all 60, review by review, and three labels are still disputed, which is why I call it provisional.

[bars] Jev matched the key on all four fields for 54, 53 and 52 of 60 over three passes. Claude Opus 5.5 at high effort matched 59, 58 and 58, Sonnet 5.5 matched 58 in every one of nine cells, and a 26B open-weight Gemma and a 27B Qwen each matched 59. Now cost. [cards] A Jev pass over all 60 reviews cost about six tenths of a cent, and that's a known provider charge from the OpenRouter pass. The Opus pass was about 22 cents, and that one is an API-equivalent estimate. So that's roughly four to forty times the spend for five more matches.

And credit where it's due: Jev caught all 25 reviews where the key flags a serious concern, including the one I read you. But on that same review Jev said nobody needed to follow up, at 0.49 confidence, so hold that number for proof three. You get a typed answer at a fraction of a cent, and you give up the last few percent.
[/notes]

[notes beat=5]
So this is another one of the 60. [S7 shows only the text] "Great soup, tiny portions, wouldn't eat there again."

Seven purpose-built decision models saw this review. Shout how many flagged it as off-topic. [pause, repeat two or three answers for the mic]

[reveal, replay badge on] Zero of seven. Four of them said the sentiment was mixed, no follow-up, no concern, not a testimonial. Solar said negative. Liquid and Perplexity said "can't tell" on the sentiment, and still answered no on the business fields. Jev isn't one of the seven, but its saved answer was the same mixed, no, no, no, and it said no serious concern at 0.91 confidence when the honest answer was "can't tell". And 89 of the 113 general configurations that returned a valid answer said "can't tell" on all four fields.

So the classifier answered the question on the form, and it did not notice the form didn't apply, which is the slower move Kahneman calls System Two: wait, is this even the right question?

And the soup has company. [histogram] On 26 of the 60 reviews all seven decision models matched the key, on two reviews all seven missed, and the ones they split on are the ones a person would pause on. [S9 quote] "The accessibility issue from the assessment has been dealt with, I think." Three of those are the reviews where a second, AI review of our key said the key itself might be wrong. So the misses weren't random. They landed on reviews that weren't about hiring, reviews too vague to call, and reviews where our own key wasn't sure, and that's good news, because you can route those to a person.
[/notes]

[notes beat=6]
So, proof three. The number next to the answer.

Jev returns a confidence with every answer, and the fair thing first: on average it is calibrated. Pooled over 720 answers its expected calibration error was 0.011, while Clef Flash sat at 0.358. [S10, replay badge] And Jev was still 0.96 confident that the review where the train got cancelled and the interviewers switched to video was negative and not a testimonial, and the key says the opposite. On sentiment, a 0.9 gate threw away nine good answers to catch four bad ones, and it still let that testimonial through. In fairness, the same gate would have caught the harassment follow-up miss, because that one sat at 0.49. Jev's ten least-confident reviews include seven of the ten hardest in the whole study, so it knows "hard". It does not know "off-topic", because on the soup it said no serious concern at 0.91. A calibrated number is still not a per-review gate.

The other fix I'd reach for is a longer prompt. I tried plain, then classifier framing, then a full decision tree, and in these saved runs the framing step scored higher in 15 of 39 setups, the same in 15, lower in 9. Adding the tree on top scored higher in 4, the same in 14, lower in 21. Cloudflare's Clef went 54, 51, 49 across the three, in every one of three passes, with one caveat: that route may only read about the first 2,000 tokens of state, so the tree may simply have been cut off. So the fix I'd reach for first was the one I'd trust least.
[/notes]

[notes beat=7]
So, the rule. Agree or defer. Run two cheap models on every review, accept only identical four-field answers, and send the rest to a person.

I wrote the rule down before computing a single pair, then looked at all 21 pairs of the seven decision models. Five pairs let zero errors through. [S12 sorts] The one on the slide, Solar Decide plus Perplexity Decider, agreed on 53 and sent 7 to a person, for under four cents for both, and I picked it after seeing all 21, so treat it as an example. It deferred the soup, the three disputed labels and the 0.96 testimonial. And the harassment review? Both models got it right, so the rule simply overrules Jev's miss.

Zero errors on these 60 is not zero errors on the next 60. And agreement only helps when the models fail differently, because six of the 21 pairs gave the soup the same wrong answer and accepted it. That's also why a second frontier model is a weak check: 44 run-passes from seven families gave one identical answer set, missing exactly the three disputed reviews.

So the rule is two cheap models that agree, whatever their category. [S12 re-sorts] Across 853 costed pairs, Qwen 27B at low effort plus Gemma 26B with thinking on accepted 58 with zero errors and deferred 2, for about seven cents observed, and 35 pairs beat Solar plus Perplexity on coverage and cost, none with a decision model in it. On other Gemma passes that pair let one error through, so it's one draw.

The agreement rule decides what a model may auto-accept, and the escalation lines are the workflow. In a harassment workflow the 25 serious concerns reach a person regardless of which model you use, so the model's job is the other 35, and on this set the rule auto-accepts 25 of those cleanly and sends 10 to a person. That cost exists with or without a model.

[S13] Hands up for one model at 0.96. [pause] Hands up for two cheap models that agree. [pause]
[/notes]

[notes beat=8]
So, this benchmark taught me what a runner has to do: count the missing answers, reject broken formats, keep the labels away from the model, know what each request cost, and run it more than once. I pulled those lessons into a tool called classification-bench: your inputs, your labels, and it reports agreement and how often an answer flips between repeats. Where it stands: the pipeline runs offline with 272 tests, it has made small real calls through OpenRouter and Cloudflare's Clef, the Claude Code and Codex routes are built but untested live, and we're open-sourcing it, so ask me for early access.

So this is what I'd do on Monday. Pull 60 of your own cases and label them yourself, before any model sees them. Give every question a "can't tell" option. Run two cheap models and keep only the answers they agree on. Then count how many land in the human queue, and whether the rare cases you care about made it through. Every scored answer is in the public repo, so star it. We're building this together. Thank you.
[/notes]

## 3. Main deck slide list (15 slides) with visual briefs

Hero moments: S8 (soup reveal), S10 (the 0.96 dot), S12 (agree or defer). S8 and S10 are "live replay" moments: the slide reads saved JSON and reveals answers one at a time with a small "replay of saved answers, 2026-10" badge, so it feels live and stays honest. S4 is a simple build, not a hero. v1 numbering: v1 S9 is now S8, v1 S11 is now S10.

Data feeds are files under `public-site/deck/data/` unless stated; each entry there carries its own source file and JSON path.

| Slide | Title | What moves | What the audience should feel | Data feed |
|-|-|-|-|-|
| S1 | Title | The harassment review (DEV-059) fades in as a card under the title, fully legible. Nothing else. | Stakes, from the first frame. | `public-site/disputed-reviews-v1.json` review DEV-059 `feedback` |
| S2 | The answer | Two bars grow out of 60: Jev to 54, Opus 5.5 high to 59, each with a thin three-pass range mark. The gap shades. Then "buy a rule" appears. | The whole talk in one frame. | `answer.json` `jev_all_four`, `opus55_high`; ranges from `claude-roster-repeats.json` series `opus55-high-batch10` and `prompt-levels.json` `jev_openrouter.P0` |
| S3 | About me | Static. Portrait left, three lines right, repo URL in the footer. | "This person has read the pile." | 03 §5 |
| S4 | The launch wave | Timeline from 15 September to 7 October. Jev lands first. On the second click, 1 October fires Cloudflare and AWS together, Perplexity ticks in the same week, OpenAI on 6 October. Verified entries only; unverified rows are not drawn. | "This moved fast, and it is still moving." | `timeline.json` `entries` where `verified` is true |
| S5 | Five reviews | Five horizontal bars out of 60 with explicit configuration labels: Jev 1.13 direct P0 (54, range 52 to 54 on OpenRouter repeats), Opus 5.5 high batch 10 (59, range 58 to 59), Sonnet 5.5 xhigh (58, nine cells), Gemma 4 26B A4B thinking-on (59), Qwen3.8 27B low (59). Not sorted by score. | "That's close. That's also five candidates." | `answer.json` all score keys; `prompt-levels.json` `jev_openrouter.P0` |
| S6 | What a pass cost | Two cards, same size. Left: "Jev, OpenRouter P0 pass, $0.006, known provider charge". Right: "Opus 5.5 high, $0.22, API-equivalent estimate, not a bill". No shared axis, no size encoding. | "Cost is not the constraint." | `answer.json` `jev_cost_known_usd`, `opus_cost_estimate_usd` |
| S7 | One of the 60 | The soup review text only, large, centred. Holds while the room shouts. | Mild amusement, then a bet. | `disputed-reviews-v1.json` DEV-029 `feedback` |
| S8 | Zero of seven (hero, replay) | Seven model cards face down, one click per flip. Exact answers: Tev, Clef, Clef Flash, Luna show "mixed / no / no / no"; Solar "negative / no / no / no"; Liquid "can't tell / no / no / no"; Perplexity "can't tell / no / no / can't tell". Counter ticks 0 of 7. A separate small card below for Jev, marked "not in the seven": "mixed / no / no / no, no concern at 0.91". Last click: "General configurations: 89 of 113 said can't tell on all four". | A laugh, then a chill. | `disputed-reviews-v1.json` DEV-029 `answers[]`; 01b §8 soup table for Jev; `results/cross-category-v1/findings.md` line 58 |
| S9 | Where they split | Histogram, x axis 0 to 7 mismatching models, y axis reviews. Bars rise 26, 15, 12, 1, 2, 1, 1, 2. Two verbatim quotes (DEV-006, DEV-030) appear beside the 6 and 7 bars. | "The hard ones are hard for a reason." | `hard-cases.json` `histogram`, `reviews_with_4_or_more_mismatches[].text` |
| S10 | 0.96 and still wrong (hero, replay) | Testimonial field only. Sixty dots placed by Jev's confidence. A threshold line sweeps from 0.5 to 0.95; dots below it turn hollow. One red hollow-ringed dot at 0.96 stays lit throughout, labelled DEV-027. A footnote shows the ECE pair: Jev 0.011, Clef Flash 0.358. | "The gate kept the embarrassing one." | `jev-confidence-findings.json` testimonial `wrongCases` and thresholds; 01b §8 calibration table |
| S11 | More instructions, no reliable gain | Three steps for Clef: 54, 51, 49, each with a small drop. Beside it the 39-setup tally in two rows: plain to framing 15 / 15 / 9, framing to tree 4 / 14 / 21. Footnote: "Clef route may read only about 2,000 state tokens". | "The thing I'd do first didn't reliably help." | `prompt-levels.json` `models.clef`, `tally_39_setups` |
| S12 | Agree or defer (hero) | Sixty cards in a grid. Two stamps land on each; matching cards slide left into "accepted 53, 0 disagreed with the key", mismatching cards slide right into "a person, 7". Price tag "$0.037 known charge, both runs". Second click re-sorts with the Qwen + Gemma pair: 58 left, 2 right, "$0.069 observed, one draw". | "That's the whole rule, and I could build it tomorrow." | `native-agreement-policy-v1.json` pair Solar + Perplexity; 01b §11 Table A row 1 |
| S13 | The policy and the queue | Static five lines of policy. Beside them a 60-card strip in three bands: 25 serious concerns to a person regardless of model, 25 auto-accepted cleanly, 10 to a person by disagreement or "can't tell". Last click: the two-option question. | "Which would I trust?" | `docs/talk/scripts/s12_escalation_queue.py` and the reviewer's `s12_full_policy_routing.py`, which agree; 01 §6 policy lines |
| S14 | classification-bench | Pipeline diagram: bring data, plan, run, evaluate, report. Two routes lit (OpenRouter, Clef), three amber (Claude Code, Codex, Liquid / Solar / Qwen). Badge: "being open-sourced". | "This person is not overselling." | 04 §2, §3, §7 |
| S15 | Monday | Four lines of the recipe and a QR code to github.com/adambkovacs/candidate-experience-benchmark. Print the frozen commit short SHA in the footer. | An easy next step. | 03 §2; frozen commit to be set at deck export |

Motion rules for the whole deck: one idea moves per slide; every hero has a static PNG fallback; numbers animate from zero only once per slide; no motion on quoted review text; the replay badge is on S8 and S10 whenever saved answers are revealed one at a time; click counts are written on the slide notes (S8: seven clicks plus two; S12: two clicks).

## 4. Appendix slide list (12 backup slides for Q&A)

| Slide | Title | Content | Source |
|-|-|-|-|
| A1 | Hosted decision models, one card each | Jev ($0.042/M input, early access, no changelog, publishes a failure-mode page), OpenAI Decisions on gpt-6-luna ($0.10/M, public beta, refusal type), Perplexity Decider ($0.02/M, Apache-2.0 v1), Liquid d1 ($0.04/M per blog methodology), Solar Decide (beta, price unverified). | 02 Part D |
| A2 | Open-weight decision models | Clef and Clef-flash (Apache-2.0, Workers AI price unverified), Strands Decider 2B, Kev family, d1-3B, Nimble 9B, Tev1 4B. Decision Index snapshot, labelled self-reported where it is. | 02 B3, B4, B6, B8, B10, B11; Part D |
| A3 | Prompt levels P0 / P1 / P2 | Five decision models, every pass, from the feed. 39-setup tally all three steps: plain to framing 15/15/9, plain to tree 7/16/16, framing to tree 4/14/21. "In these saved runs." Clef truncation caveat. 01b: P2 pushes decision models from "no" to "insufficient" on serious concern. | `prompt-levels.json`; 01b §12.6 |
| A4 | Confidence and calibration | Pooled ECE per native model (Jev 0.011, Liquid 0.035, Tev 0.047, Luna 0.074, Solar 0.145, Clef 0.217, Clef Flash 0.358). Confidence versus option probability differ by more than 0.2 on 55% of Flash answers. Jev per-field retrospective thresholds. Hard-10 overlap table. All retrospective; no abstention executed. | 01b §8; `jev-confidence-findings.json` |
| A5 | Who wrote the key, and how fragile it is | An OpenAI assistant drafted the 60 reviews and the key; a person checked all 60 on 2 October 2026; a separate AI review disputes three labels. Flipping DEV-006 alone: 212 runs up, 168 down, 257 unchanged of 637. All three flipped: per-run deltas from minus 3 to plus 3. | `docs/PILOT_AUDIT.md`; `README.md` line 171; `docs/REFERENCE_REVIEW_V1.md`; `reference-sensitivity-v1.json` `scenario_summaries` |
| A6 | Cost table, seven decision models | Known charge per 60 one-review requests: Clef Flash $0.012, Luna $0.013, Perplexity $0.015, Liquid $0.016, Tev $0.016, Solar $0.022, Clef $0.032 (estimate). Nine-run series: $1.2013 including a Clef estimate, plus up to $0.13 unknown charge, which is unknown rather than zero. Gemini effort pair: low 56/60 at $0.063, high 55/60 at $0.257. | 01 insight 14; 05r R8 |
| A7 | Limits and the claims we do not make | Not a leaderboard. Not causal. Not real-world accuracy (60 synthetic reviews, 340 planned never generated). Key is provisional v0.2, AI-drafted, person-checked, three labels disputed. Missing cost is unknown, not zero. No speed ranking. No pooling of 1,004 run entries. Batch, route and effort differ between runs. Frozen commit SHA printed here. | 01 §4, §7 |
| A8 | classification-bench detail | Works: offline end to end, 272 tests, OpenRouter one route, Clef 42 of 42 valid. Wired, not live: Claude Code, Codex, Liquid, Solar, Qwen. Not built: OpenAI Decisions, unlabeled runs, several report items. Being open-sourced; release date not set. | 04 §2, §3 |
| A9 | Equal scores hide different answers | Sonnet 5.5 xhigh 58/60 in all nine cells, changed DEV-006 and DEV-030 between passes. 01b: 31 of 50 decision groups changed nothing in three passes versus 11 of 202 general groups; general models flip the hard reviews. | 01 insight 5; 01b §12.4 |
| A10 | All 21 pairs and the queue | Full table from the script: accepted, accepted errors, deferred, accepted-with-concern, accepted-with-can't-tell, human queue. Union reaching a person ranges 32 to 42 of 60 under the full policy. For Solar + Perplexity: 25 concerns from either model, 7 "can't tell", 7 deferred, union 35; of the 35 non-concern reviews, 25 auto-accepted and 10 to a person. Five zero-error pairs; Solar sits in four of them. Six pairs accepted the soup with the same wrong answer. No pair selected. | `docs/talk/scripts/s12_escalation_queue.py`; `native-agreement-policy-v1.json` |
| A11 | Rare classes and the "can't tell" collapse | Testimonial 9 yes / 50 no / 1 insufficient; all-no scores 50/60. Tev recall 9/9 precision 9/12; Luna recall 6/9 precision 6/6. 01b: reference "insufficient" is answered as a definite label 22% to 26% of the time; decision runs match those cells at 19% to 45%, general at 71% to 84%. | 01 insight 9; 01b §12.1 |
| A12 | Agreement with general models, and frontier convergence | 853 costed pairs: Qwen 27B low + Gemma 26B on, 58/0/2, $0.0686 observed; Gemma 31B off + DeepSeek Flash low, 55/0/5, $0.0207; 35 pairs dominate Solar + Perplexity. Same model twice is not a second opinion (Qwen 35B off agrees with itself on 9 wrong answers). 44 run-passes from seven families share one identical answer set missing exactly the three disputed reviews. | 01b §11, §12.2, §12.3 |

Held as spoken answers, not slides: the rules baseline (10/60, 01 insight 13) and invalid-output counts (01 insight 11).

## 5. Likely Q&A questions

| # | Question | Short honest answer | Point at |
|-|-|-|-|
| 1 | So which model is best? | I can't rank them. Runs differ in route, batch size, effort and prompt implementation. Several setups reached 59, including a 26B open-weight model, and that describes one pass each. | A7; 01 §4 |
| 2 | Sixty synthetic reviews. How real is that? | Not real-world. An OpenAI assistant wrote the 60 reviews and drafted the key, people checked all 60 on 2 October, and the 340 planned validation records were never generated. Nothing here estimates performance, prevalence or fairness on real candidate text. | A5, A7; 01 §7 |
| 3 | Isn't your key the weak point? | Partly, yes. It is v0.2, person-checked, and a separate AI review disputes three labels. Flipping one of them moves 212 runs up and 168 down. When a one-point difference decides a vendor, your label quality is the bottleneck. | A5 |
| 4 | Is Jev faster? | I can't say. Client request time mixes network, CLI, batch and operator time, and pure inference latency isn't available on every surface. TypeSafe and Cloudflare publish their own latency numbers; I didn't measure speed. | A7; 02 B1, B3 |
| 5 | Why not pay for Opus at 59? | You can, at about 38 times the estimated spend, and Opus held 58 to 59 over three passes against Jev's 52 to 54. Sonnet scored 58 in all nine cells and still changed two reviews between passes, so the aggregate hides movement on the hard ones. | A9; S6 |
| 6 | Would agree-or-defer hold in production? | Unknown. The rule was fixed before the pairs were computed but scored on the same 60 reviews used for everything else, and the human review cost of the deferred set is unmeasured. Treat it as a policy to test. | A10; 01 §6 |
| 7 | What about the open-source Jev clones? | OpenJev native came within a few points at 53 to 54, Kev-4B sat at 46 to 49, Alex 4B at 39, SemIf at 35 to 36, and several scored zero. "Jev-like" on a model card tells you nothing; the saved run does. | 01 insight 12 |
| 8 | Did you count invalid outputs? | Yes, in the denominator. AnyJev's generated path wrapped every answer in a code fence and scored 0 of 60. Native choice heads had almost no format failures, and 01b shows failures land on the hard reviews, not the long ones. | 01 insight 11; 01b §12.9 |
| 9 | Jev found every serious concern but missed the testimonial. Why? | It found all 25. Its three misses on that field were "can't tell" reviews it called no. The testimonial miss was the train review, where "cancelled" seems to have outweighed "helpful". TypeSafe's own docs list literal reading as failure mode one. | A4; 02 A3 |
| 10 | Can I run this on my own task? | Yes, with classification-bench. It runs offline today with 272 tests and has made small live calls through two routes. It is being open-sourced; ask me for early access. | A8; S14 |
| 11 | TypeSafe engineer: did you ask a separate relevance question first? Your docs say to split judgments. | No, and that's a fair hit. Every model got the same four questions with a "can't tell" option. A relevance check up front is cheap and I'd expect it to help on the soup. That's the next run. | 02 A3; A7 |
| 12 | Your key was written by an OpenAI model. Aren't you measuring who thinks like GPT? | Possibly in part. People checked all 60, and if GPT-style models had a home advantage, OpenAI's own decision model didn't get it: Luna Decisions matched 49. I can't rule out that LLM-written text suits LLMs, which is one reason the key is provisional. | A5; `prompt-levels.json` `luna` |
| 13 | Jev isn't in your seven or your pairs. Why? | The seven were a matched first-pass panel through one route, and Jev's runs sit outside it. The answers are public, so pairing Jev offline is a small analysis with no new inference, and I haven't done it yet. | A10; 05r R13 |
| 14 | CTO: with your full policy, how big is the human queue? | On this set, 35 of 60. Split it the way the workflow does: 25 serious concerns reach a person whatever model you run, and of the other 35 reviews the rule auto-accepts 25 and sends 10 to a person, 7 by disagreement and the rest by a "can't tell". The set is concern-heavy by design. On real feedback the share depends on how often concerns happen, which this can't tell you. | A10; `s12_escalation_queue.py` |
| 15 | Is 54 versus 59 real on 60 reviews? | It held across three passes each: Jev 54, 53, 52 and Opus 59, 58, 58. On first passes Opus matched five reviews Jev missed and missed none Jev matched. It's still one set of 60 synthetic reviews and a provisional key, so read it as a direction. | A9; 01 insight 2 |
| 16 | Opus ran ten reviews per request and Jev one. Fair? | Not identical. Batch, route and effort all differ, which is why I don't rank. It's on the limits slide. | A7 |
| 17 | Cloudflare: Clef reads about 2,000 tokens of state. Was your long prompt truncated? | Possibly. Your route warning says so, and our notes treat truncation as a constraint, not a cause. | A3; `docs/CLEF_OPENROUTER_FINDINGS.md` |

Two more to have ready: Jev's confidence versus its option probability differ by 0.016 on average and by more than 0.2 on under 1% of answers, while for Clef Flash they differ on 55%, so threshold on the probability for those models (01b §8). And hosted Jev drift: Cloudflare's board saw 20 choices change in twelve days with scores unchanged and no version change (02 B1 and E8).

## 6. Risks and fallbacks

| Risk | Fallback |
|-|-|
| TV over Zoom washes out colour or detail | Every chart carries its number as text. Kept versus withheld on S10 uses filled versus hollow, never colour alone. Dark text on light background. Test the deck on the venue TV from the back of the room before doors open. |
| No browser or JSON replay fails on the venue machine | Every hero (S8, S10, S12) has a static PNG and a three-step Keynote build. All JSON is baked in at export; the deck opens without network. |
| Time overrun | Cut order: first the bio to one sentence (saves 15 s). Then the Qwen + Gemma re-sort in beat 7 to one spoken line (saves 30 s). Then the Clef caveat in beat 6 (saves 15 s). Never cut the soup reveal, the 0.96 dot or the rule. Hard-stop line at S12: "That's the rule. The repo has everything else." |
| Nobody shouts on moment 2 | Line ready: "I'll take that silence as 'most of them'. It was none of them." Repeat any shouted answer for the mic and the recording. |
| Few hands on moment 1 | Line ready: "Good, then nobody here has to admit anything yet." |
| Hostile question on AI-authored data and key | Beat 4 says it first. Q&A 2 and 12 are ready, and A5 carries the authorship line. |
| Other vendors in the room (Cloudflare, Perplexity, OpenAI, AWS, Together) | Same collegial rule as for TypeSafe: credit what they publish, no "beats", no "better than". Clef truncation and Luna's 49 are stated as saved-run facts with their caveats. Q&A 17 is ready. |
| A number is challenged | Every number has a feed path or doc path in sections 2 and 3. Reply with the path and the confidence tag from 01 or 01b (solid, descriptive-only, anecdotal). |
| Numbers moving before the talk | Freeze a commit before deck export, print the short SHA on A7 and S15, and re-run `count-notes.ts`, `audit-slop.ts` and `s12_escalation_queue.py` after any change. |
| Inherited errors in 02 | 01 was corrected in commit 05528718 (four said mixed, five zero-error pairs, $1.2013 including a Clef estimate plus up to $0.13 unknown, Opus 5.5 high passes 59/58/58) and v2 uses those values. 02 Part C still says "twenty-two days"; fix it so site, notes and deck agree. |
| Name soup | Jev, Kev, Tev, Clef, Luna and Laya sound alike over Zoom. Spoken names are limited to Jev, Opus, Sonnet, Gemma, Qwen, Solar, Perplexity, Liquid and Clef. |
| QR code | Test it from the back row on the venue TV. The handle is adambkovacs, easy to mistype, so the URL is also printed in full. |
| Early-access promise | Adam confirmed classification-bench is being open-sourced. Until the repo is public, "early access" means Adam grants collaborator access by hand; do not show the private URL. |
| Cost labels change after 06-cost-check.md lands | Re-read `answer.json` before export and replace "known charge" or "estimate" wording on S6, S12 and A6 to match. |

## 7. Word count per beat, and the audit

Produced by `scripts/count-notes.ts` (bun) over the `[notes beat=N]` blocks, with bracketed stage directions removed before counting, and by `audit-slop.ts` over the whole file. Output pasted verbatim at the end of this file.

| Beat | Words | Budget |
|-|-|-|
| 1 Cold open and answer | 121 | 125 |
| 2 Bio | 61 | 55 |
| 3 The launch wave | 94 | 120 |
| 4 Proof 1 | 243 | 265 |
| 5 Proof 2 | 263 | 285 |
| 6 Proof 3 | 268 | 300 |
| 7 The rule | 337 | 300 |
| 8 The tool and the Monday recipe | 182 | 180 |
| Total | 1,569 | 1,550 |

## 8. Integrated from 01b, and what is still open

Integrated into v2: calibration table and hard-10 overlap (§8) in proof 3 and A4; the soup confidence table (§8) in proof 2 and S8; agreement with general models and the 853-pair analysis (§11, §12.3) in the rule beat, S12 and A12; frontier convergence (§12.2) in the rule beat and A12; determinism split (§12.4) in A9; "can't tell" collapse (§12.1) in A11; prompt direction (§12.6) in A3; output failures on hard reviews (§12.9) in Q&A 8.

Still open after v2:
- Pair Jev offline with each of the seven (05r R13). Label it post hoc and descriptive if run.
- 06-cost-check.md may relabel costs; re-read `answer.json` before deck export.
- Fix 02 Part C ("twenty-two days"); 01 is already corrected.
- Confirm the bio line "read the pile of candidate feedback" is one Adam is happy to say; 03 has no count behind it, so v2 uses no number.

## 9. Changelog: 05r findings and how v2 handles them

| Finding | Fix in v2 |
|-|-|
| B1 soup answer reversed | Beat 5 and S8 now say Jev answered no serious concern at 0.91 when the honest answer was "can't tell". |
| B2 prompt tally mislabelled, causal wording, Clef truncation | Beat 6, S11 and A3 label all three steps (15/15/9, 7/16/16, 4/14/21), say "in these saved runs", use no causal verbs, and carry the Clef 2,000-token caveat. S11 title is "More instructions, no reliable gain". |
| B3 date math | "About two weeks later" for 1 October; Cloudflare and AWS same day, Perplexity "that week"; OpenAI 6 October. S4 draws verified timeline entries only. |
| B4 key provenance | Beat 4 says once: an AI assistant drafted the reviews and the key, a person checked all 60, three labels disputed. Beat 5 says the disputes came from a second, AI review of the key. "Two humans" and "our human reviewers" are gone. A5 and Q&A 2, 3, 12 carry it. |
| B5 thesis contradiction | The answer now says most of Jev's six misses sat on reviews a person would pause on, two were plain errors, one a harassment report marked no follow-up. The "whole product" sentence is gone; DEV-059 opens the talk and threads through proofs 1 and 3 and the rule. |
| B6 speed claim | "You get speed and price" replaced by "a typed answer at a fraction of a cent". |
| B7 false taxonomy slide | S5 and the taxonomy paragraph are cut. The launch-wave beat is the timeline slide only, 60 seconds. |
| B8 rule beat holes | Beat 7 says the rule was written before the pairs were computed, that Adam looked at all 21 and picked an example not a winner, that five pairs had zero accepted errors, that six pairs accepted the soup with the same wrong answer, and that the full policy takes the queue from 7 to 35 of 60. The count comes from `docs/talk/scripts/s12_escalation_queue.py` and reconciles exactly with the reviewer's `s12_full_policy_routing.py` (commit 05528718): 25 concerns from either model, 7 can't-tell, 7 deferred, union 35, accepted clean 25, escalated 24, clarification 4, range 32 to 42 across the 21 pairs. |
| B9 unmeasured calibration claim | Replaced with 01b §8's measured result: Jev ECE 0.011 against Clef Flash 0.358, still 0.96 on a wrong testimonial, and seven of ten least-confident reviews in the hard ten. |
| B10 smaller number errors | Four said mixed; five zero-error pairs; DEV-030 quoted verbatim; "117 general-model configurations" and "89 of the 113 that returned a valid answer" used consistently; "frontier" reserved for Claude, GPT and Gemini. |
| B11 no buffer | Notes cut to the measured total in section 7; S5 removed; bio shortened; moment 3 is a two-option show of hands; buffer is about 1:10 at the stated rates. |
| R1, R2, R3, R4, R5, R6, R7 | Feed pointers moved to `public-site/deck/data/*.json`; S5 names all five bars with configuration labels and three-pass ranges; S6 is two cards with no size encoding; S8 carries the exact per-model answers and marks Jev as outside the seven; S10 shows one field with filled versus hollow dots and notes that a 0.9 gate catches the 0.49 miss; "two one-cent models" is now "two cheap models, under four cents together". |
| R8 cost totals | A6 says about $1.20 including one estimate plus up to $0.13 unknown; A5 pairs the minus 3 to plus 3 range with the all-three-flips scenario. |
| R9, R10, R11, R15 | The $17 line is cut; "a dozen or more"; Jev's repeat scores stated as 54, 53, 52; "lowest-coverage pair" wording is not needed because the line is cut; "every scored answer is in the public repo". |
| R12 open-ended moment 3 | Two-option show of hands. |
| R13 Jev not in the pairs | Listed as open work in section 8; Q&A 13 ready. |
| R14 re-run after 01b | Done; counts and audit at the end of this file. |
| R16 bio claims | No count is spoken; "read the pile" is flagged for Adam in section 8. |
| Section 5 voice notes | The five replacement lines are used; "Two honest caveats" is "Two caveats"; fragments are joined; sentences in the notes are written to Adam's spoken 18 to 22 word average. |
| Section 7 Q&A | Answers 1, 2, 3, 5, 7, 9 corrected; the seven missing questions added as 11 to 17. |
| Section 8 risks | Hostile authorship question, moving numbers and frozen SHA, inherited errors, other vendors, recording and stream, QR test, early-access promise, name soup, hard stop and click counts are all in section 6. |
| Adam's answers | "TypeSafe may be in the room" is gone, the 25/25 credit and the failure-mode-page credit stay, the CTA says classification-bench is being open-sourced, S8 and S10 are replay moments with a badge, AEA branding noted in the header. |

## 10. Script output

```
$ bun run scripts/count-notes.ts docs/talk/05-session-outline.md
beat 1: 121
beat 2: 61
beat 3: 94
beat 4: 243
beat 5: 263
beat 6: 268
beat 7: 337
beat 8: 182
total: 1569

$ bun run ~/.claude/skills/anti-slop/scripts/audit-slop.ts docs/talk/05-session-outline.md
Total Words: 7856
Slop Instances: 0
NO-SLOP Score: 100.0%

$ python3 -I docs/talk/scripts/s12_escalation_queue.py | head -6
Solar + Perplexity routing (reconciles with s12_full_policy_routing.py):
  deferred by disagreement 7 ['DEV-006', 'DEV-013', 'DEV-027', 'DEV-028', 'DEV-029', 'DEV-030', 'DEV-035']
  serious_concern = yes from either model 25; insufficient from either model 7; union reaching a person 35 of 60
  accepted with no routing 25; accepted but escalated for concern 24; accepted but routed for clarification 4
  non-concern reviews 35: auto-accepted clean 25, to a person 10 ['DEV-005', 'DEV-006', 'DEV-013', 'DEV-022', 'DEV-027', 'DEV-028', 'DEV-029', 'DEV-030', 'DEV-048', 'DEV-060']
pairs: 21  zero-accepted-error pairs: 5  pairs accepting soup with wrong answer: 6
```
