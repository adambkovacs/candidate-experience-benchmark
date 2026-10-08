# 05 Session outline: "Do models like Jev get it right when correctness is business-critical?"

Speaker: Adam Kovacs. Date: 2026-10-08. Format: 15 minutes plus Q&A. Audience: agentic builders, engineers and AI-curious people, mixed seniority, some non-engineers.

Version 1, written 2026-10-08 from the four input notes 01 to 04. 01b-deep-analysis.md did not exist when this was written; see section 8 for where its insights slot in.

Skeleton: one answer, three proofs, one rule, one call to action. Everything else lives in the appendix for Q&A. The System 1 / System 2 idea is the spine: it opens the talk, explains every proof, and names the rule.

Every number below is agreement with the frozen provisional v0.2 reference on the same 60 synthetic reviews. "Matched" always means "matched that reference". Never "accuracy".


## 1. The answer and the three proofs

**The answer, in Adam's voice:**

> Jev matched our provisional reference on 54 of 60 reviews for about half a cent a pass, frontier LLMs got 58 to 59 for four to forty times the spend, and every one of Jev's misses was a System 2 moment, so a business-critical workflow buys correctness with an agree-or-defer rule and a human queue, not with a score.

**The three proofs:**

| # | Proof | Answers which part of the blurb | Why this one and not the others |
|-|-|-|-|
| 1 | The gap is five reviews. Jev 54/60, Opus 5.5 high 59/60, Sonnet 5.5 58/60 in all nine cells; Jev about $0.006 a pass versus Opus about $0.22 (estimate). Jev matched all 25 serious-concern references. | "Where that helps" | It is the fairest single picture of what System 1 buys you and what it gives up. Insight 14 (cost frontier) and insight 12 (clones) say the same thing with more rows; they go to the appendix. |
| 2 | The soup review. Zero of seven decision models noticed it was off-topic; 89 of 113 general LLM setups did. The reviews that split the decision models are the ones a human pauses on. | "Where uncertainty still matters" | It is the one finding a mixed room will remember, and it shows System 1 running out in a way nobody has to take on faith. Insight 10 is its source. Insight 5 (equal scores hide different answers) and 6 (stable is not right) are stronger for engineers only; appendix. |
| 3 | The two controls every team reaches for first did not work here. A 0.9 confidence gate left a 0.96-confident wrong answer in and withheld 13 right ones; a longer prompt made 21 of 39 setups worse. | "How much confidence should a workflow demand" | It clears the ground for the rule. Without it, the rule sounds like one more option. Insight 8 (reference fragility) and 9 (class balance) matter but answer questions the audience has not asked yet; appendix. |

**The rule:** agree or defer. Two cheap typed models, accept only identical four-field answers, defer the rest to a person. Solar Decide + Perplexity Decider: 53 accepted, 0 accepted errors, 7 deferred, $0.037 for both over 60 reviews.

**The call to action:** star the public benchmark repo and ask Adam for early access to classification-bench.


## 2. Run of show

Clock is the start time of each beat. Word budgets are for spoken notes only. Full notes follow the table in section 2b, each marked for the counting script. Total budget: 1,800 words. Measured total in section 7.

| Beat | Clock | Length | Slide titles | On the slide (max 12 words) plus the visual | Engagement | Word budget | Sources for every number |
|-|-|-|-|-|-|-|-|
| 1. Cold open and answer | 0:00 | 1:05 | S1 Title; S2 The answer | S1: talk title, name. Visual: a single review card fading in. S2: "Jev 54 of 60. Frontier 58 to 59. Buy correctness with a rule." Visual: two bars and a gap. | Moment 1: "Hands up if you've shipped an LLM classifier to production. Keep it up if you check it with a second model." | 160 | 01 §1; 01 §3 rows 2, 8, 9 |
| 2. Bio | 1:05 | 0:40 | S3 About me | "Adam Kovacs. AI Enablement Academy. Six years Amazon and AWS talent intelligence." Visual: portrait, repo URL in footer. | none | 95 | 03 §5 |
| 3. The field | 1:45 | 1:30 | S4 The launch wave (hero); S5 Three ways to get a typed decision | S4: "Jev, 15 September. Twenty-two days later, three more on one day." Visual: animated dated timeline. S5: "Native choice head. Fine-tuned encoder. LLM with JSON schema." Visual: three columns, one row for "can say the form doesn't apply". | none | 210 | 02 Part C; 02 A4; 02 B17; 02 B10 ($17) |
| 4. Proof 1: the gap | 3:15 | 2:10 | S6 Five reviews; S7 What a pass cost | S6: "Jev 54. Opus 59. Sonnet 58. Gemma 59." Visual: seven bars out of 60. S7: "One Jev pass: $0.006 known. One Opus pass: $0.22 estimated." Visual: two coins, different scales, labelled "known" and "estimate". | none | 290 | 01 §3 rows 2, 4, 5, 8, 9, 10; 01 insight 1 |
| 5. Proof 2: the soup | 5:25 | 2:35 | S8 One of the 60 (text only); S9 Zero of seven (hero); S10 Where they split | S8: the review text. Visual: nothing else. S9: "0 of 7 decision models. 89 of 113 general setups." Visual: seven cards flipping. S10: "26 reviews, all seven matched. Two reviews, all seven missed." Visual: histogram 0 to 7. | Moment 2: "Seven purpose-built decision models saw this review. Shout how many flagged it as off-topic." | 330 | 01 insight 10; 01 §3 row 18; 01 §5 item 1 |
| 6. Proof 3: two controls | 8:00 | 2:15 | S11 Confidence is not the gate; S12 Longer prompt, worse answers | S11: "Wrong at 0.96. Threshold 0.9 withheld 13, nine were right." Visual: 60 dots, colour by kept/withheld, two red dots kept. S12: "Level 1 to 2: 4 better, 14 same, 21 worse." Visual: Clef 54, 51, 49 stepping down. | none | 300 | 01 insight 3; 01 §3 rows 6, 7, 13, 14; 01 §5 item 2; 02 A1 (TypeSafe confidence page) |
| 7. The rule | 10:15 | 2:20 | S13 Agree or defer (hero); S14 The policy | S13: "Two one-cent models. Agree: accept. Disagree: a person." Visual: 60 cards sorting into two columns. S14: five policy lines plus the question. Visual: static list. | Moment 3: "Which would you trust: one model at 0.96 confidence, or two one-cent models that agree?" | 300 | 01 insight 7; 01 §6; 01 §3 rows 16, 17 |
| 8. The tool and call to action | 12:35 | 1:50 | S15 classification-bench; S16 Star the repo | S15: "Runs offline, 272 tests. Two live routes. Public release pending." Visual: pipeline diagram. S16: "github.com/adambkovacs/candidate-experience-benchmark. Early access: ask me." Visual: QR code. | none | 215 | 04 §2, §3, §6, §7; 03 §2 |
| End | 14:25 | buffer 0:35 | | | | | |

Budget sum: 1,900 words would overrun; the notes below are written to land under 1,800. Measured count in section 7.

### 2b. Speaker notes in full

Spoken voice, first person. Bracketed text is a stage direction, not spoken, and is excluded from the word count.

[notes beat=1]
So, quick show of hands. Hands up if you've shipped an LLM classifier to production. [pause] Keep it up if you check it with a second model. [pause, look around] That gap between the first hands and the second hands is this talk.

I spent three weeks on one question. TypeSafe calls Jev a System One model. Fast, typed, one forward pass, no text to parse. And I wanted to know whether a System One model gets it right when the decision matters to the business. So I built a benchmark. Sixty synthetic candidate reviews, four judgments on each, and I ran Jev against about forty other setups on the same reviews.

The answer in one sentence. Jev matched our reference on 54 of 60. Frontier LLMs got 58 to 59, for four to forty times the spend. And every one of Jev's misses was a System Two moment. So a business-critical workflow buys correctness with a rule, and I'll show you the rule.
[/notes]

[notes beat=2]
Quick bit about me. I'm Adam, co-founder of the AI Enablement Academy, where teams build AI tools on their own work. Before that I spent six years at Amazon in recruiting, and I started the talent intelligence service for AWS recruiting. So I have read the pile. Thousands of lines of candidate feedback, and nobody classifies it consistently by hand. And vendors kept telling me their classifier was accurate. Amazon taught me to build the measure before trusting the tool. That's why this benchmark exists.
[/notes]

[notes beat=3]
So, where did all this come from? Jev launched on 15 September. [timeline builds] Twenty-two days later, on 1 October, Cloudflare, Perplexity and AWS all shipped a decision model on the same day. OpenAI's Decisions API went to public beta on 6 October. And in between there are about fifteen others, most of them a frozen Qwen or Gemma plus a small head that scores the options in one pass. Together trained theirs for seventeen dollars. Most of them speak the same wire format, so switching models is a base URL change.

[taxonomy] And the way I think about it, there are three ways to get a typed decision out of software today. A native choice head. State in, probabilities out, no generated text. That's Jev, Clef, d1, Perplexity. A fine-tuned encoder, the BERT family, fast and cheap, with the label set frozen at training time. And an LLM with a JSON schema, which is what most of us run today. The shape is guaranteed, the label is still generated token by token, and you get no probabilities. All three answer the question on the form. Only one of them can write back and say the form doesn't apply. Hold that thought for the soup.
[/notes]

[notes beat=4]
So, proof one. The gap is five reviews.

I gave every model the same 60 reviews and the same four questions. What's the sentiment. Does this need a follow-up. Is there a serious concern. Is this a testimonial we could use. And I compared every answer against a reference that two humans checked.

[bars] Jev matched the reference on all four fields for 54 of the 60. Claude Opus 5.5 at high effort got 59. Sonnet 5.5 got 58, in every one of nine cells. Gemma 4 26B got 59. Qwen3.8 27B got 59.

Now cost. [coins] A Jev pass over all 60 reviews was about six tenths of a cent, and that's a known provider charge. The Opus pass was about 22 cents, and that one is an API-equivalent estimate, because it ran on a subscription. So that's four to forty times the spend for five more matches.

And I want to be fair to Jev, because TypeSafe may be in the room. Jev caught all 25 reviews where the reference flags a serious concern. Every one. If your workflow is about never missing the harassment report, that's the number you care about.

So five reviews out of 60 is the difference between 90 percent and 98 percent. In most workflows that's fine. In a workflow that escalates harassment reports, those five reviews are the whole product. And that's the System One trade. You get speed and price. You give up the last few percent. The question is which reviews sit in that last few percent. That's proof two.
[/notes]

[notes beat=5]
So this is one of the 60 reviews. [slide shows only the text] "Great soup, tiny portions, wouldn't eat there again."

Seven purpose-built decision models saw this review. Shout how many flagged it as off-topic. [pause, take two or three answers]

[reveal] Zero. Zero of seven. Five of them said sentiment mixed, no follow-up, no concern, not a testimonial. Jev said the same. Perplexity came closest and put "insufficient information" on two of the four fields. And among the general LLMs, 89 of 113 setups said what you'd say: this is not about recruitment.

I think this is the cleanest picture of what System One means. The typed classifier answered the question on the form. It did not notice the form didn't apply. That's the move Kahneman describes. System One answers the question fast. System Two steps back and asks whether it's the right question.

And the soup has company. [histogram] I looked at where the seven decision models split. On 26 of the 60 reviews all seven matched the reference. On two reviews all seven missed. And the reviews they split on are the ones a person would pause on. "That thing happened again and it still isn't sorted." Vague recurrence. "Someone said it was fixed, I think." Uncertain resolution. A friend heard a rumour, and my own interview was fine. Three of those are also the three reviews where our own human reviewers disagreed with each other.

So the failure surface is predictable. Off-topic, insufficient information, disputed boundaries. That's good news for a builder, because you can route the predictable part to a person and leave the model on the rest. The bad news is what the model tells you about its own certainty. That's proof three.
[/notes]

[notes beat=6]
So, proof three. The two controls every team reaches for first didn't work on this set.

Control one, a confidence threshold. Jev returns a confidence number with every answer, and the obvious rule is only act above 0.9. [dots] Jev said the review where the train got cancelled and they switched the candidate to video was negative and not a testimonial, at 0.96 confidence. It called the soup review a serious concern at 0.91. On sentiment, a 0.9 threshold removed all four of Jev's errors, and it also withheld 13 reviews, nine of which were right. So on this data the threshold buys coverage loss faster than it buys error removal, and it leaves the most embarrassing errors in. TypeSafe's own docs say the thresholds depend on your domain and you have to test on your own data. They're right. We did, and nobody's confidence number was calibrated.

Control two, a longer prompt. When the classifier is wrong, the instinct is to write the SOP into the prompt. I tried three prompt levels. Plain, then classifier framing, then a full decision tree. [steps] Across 39 setups, going from level one to level two made 4 better, 14 the same and 21 worse. Cloudflare's Clef went 54, 51, 49, in every one of three passes. Jev stayed flat at 54. So more instructions were the least reliable lever in the whole study.

And both controls fail for the same reason. They ask one System One model to know what it doesn't know. That's a System Two job. So I stopped asking one model and started asking two.
[/notes]

[notes beat=7]
So, the rule. Agree or defer.

Run two cheap, typed decision models on every review. Accept the answer only when both return the identical four-field answer. Otherwise it goes to a person.

I fixed that rule before I looked at any numbers, then ran it over all 21 pairs of the seven decision models. [cards sort] The best pair was Solar Decide plus Perplexity Decider. They agreed on 53 of 60. Zero of those 53 disagreed with the reference. Seven went to the human queue. Total cost for both models over all 60 reviews, just under four cents. Four of the 21 pairs kept zero errors. The worst pair sent 27 of 60 to a person.

And look at what the seven deferred reviews were. The soup. The three disputed labels. The testimonial Jev was 0.96 sure about. Five of Jev's six misses landed in that queue. That's a System Two handoff built out of two System One models and one comparison.

Two honest caveats. This is 60 development reviews, so zero errors here is not zero errors on the next 60. And when both models share a blind spot, like all seven did on the soup, agreement doesn't catch it. So the full policy on the slide has three more lines. Any serious concern flagged by either model goes to review regardless. Any "insufficient information" goes to a person. And you measure recall on the rare classes, the nine testimonials and the 25 serious concerns, rather than the four-field total.

So let me ask you. Which would you trust: one model at 0.96 confidence, or two one-cent models that agree?
[/notes]

[notes beat=8]
So, this benchmark taught me what a benchmark runner has to do. Count the missing answers. Reject answers that break the format. Keep the reference labels away from the model. Know exactly which request you sent and what it cost. And run it more than once.

I pulled those lessons out of this one dataset and built a tool called classification-bench. You bring your own inputs, your own decision fields, your own labels. It runs the models and prompts you pick and reports agreement, per-label scores, and how often an answer flips between repeats.

Where it stands today. The whole pipeline runs offline, with 272 tests. It has made small, real calls through OpenRouter and Cloudflare's Clef. The Claude Code and Codex routes are built, and I haven't sent them a real request yet. It is not public yet. When it is, I'll say so.

What you can do now. The candidate experience benchmark is public, MIT, and every saved answer is in the repo. Star it, break it, send me a review that fools all seven. And if you want early access to classification-bench, come find me after. We're building this together. Thank you.
[/notes]


## 3. Main deck slide list (16 slides) with visual briefs

Hero moments, where motion earns its place: S4 (launch wave), S9 (soup reveal), S13 (agree or defer). Everything else is a build or a static.

Data feeds are files under `public-site/` in the benchmark repo unless stated. Where a feed does not exist as JSON, the brief says what to build and from which markdown table.

| Slide | Title | What moves | What the audience should feel | Data feed |
|-|-|-|-|-|
| S1 | Title | A single review card fades in behind the title, text slightly blurred. Nothing else. | Curiosity. "What is that review?" | none (use DEV-029 text from `disputed-reviews-v1.json`) |
| S2 | The answer | Two bars grow out of 60: Jev to 54, frontier to 59. The five-review gap highlights. Then the words "buy correctness with a rule" appear. | The whole talk in one frame. Relief that the talk has a point. | `findings.json` field `charts.costAgreement` (Jev row `typesafe-jev113-v2`, Opus row); `subscription-price-estimates.json` field `runs.opus55-high-batch10` |
| S3 | About me | Static. Portrait left, three lines right, repo URL in the footer. | "This person has read the pile." | 03-speaker.md §5 |
| S4 | The launch wave (hero) | A horizontal timeline from 15 September to 7 October. Jev lands first, alone. A beat of silence. Then 1 October fires three logos at once (Cloudflare, Perplexity, AWS). Then OpenAI on 6 October. Then the smaller entries fill in between as quick ticks. | "This moved fast, and it is still moving." | Build `timeline.json` from 02-landscape.md Part C (date, maker, model, verified flag). Only show entries confirmed from a primary or near-primary source. Drop Mercury Decide. |
| S5 | Three ways to get a typed decision | Three columns slide in. A final row appears across all three: "Can say the form doesn't apply": no, no, yes. | A mental map they can take home. | 02-landscape.md A1, B17 (static content) |
| S6 | Five reviews | Seven horizontal bars out of 60. Jev first at 54. The others fill to 58 and 59. The gap between 54 and 59 is shaded. | "That's close. That's also five candidates." | `findings.json` field `charts.costAgreement`; rows: Jev direct P0 54, Opus 5.5 high 59, Sonnet 5.5 xhigh 58, Gemma 4 26B 59, Qwen3.8 27B 59 (01 §2 insight 1 table) |
| S7 | What a pass cost | Two circles at different scales. Jev labelled "$0.006, known provider charge". Opus labelled "$0.22, API-equivalent estimate". Different outline styles so the audience sees these are two kinds of number. Never on one axis. | "Cost is not the constraint." | `subscription-price-estimates.json` field `runs.opus55-high-batch10`; Jev charge from docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md |
| S8 | One of the 60 | The review text only, large, centred. No labels, no chart. Holds while the room shouts. | Mild amusement, then a bet. | `disputed-reviews-v1.json` record DEV-029 |
| S9 | Zero of seven (hero) | Seven model cards face down. On the click, they flip one by one. Each shows "mixed / no / no / no" or similar. None shows "off-topic". A counter ticks 0 of 7. Then a second row fades in: "General LLMs: 89 of 113 said not about recruitment". | A laugh, then a chill. "The classifier answered the form." | `disputed-reviews-v1.json` record DEV-029, per-model answers; `results/cross-category-v1/findings.md` for 89/113 |
| S10 | Where they split | Histogram, x axis 0 to 7 mismatching models, y axis number of reviews. Bars rise: 26, 15, 12, 1, 2, 1, 1, 2. The 0 bar is calm; the 7 bar pulses once. Three quoted reviews appear beside the 4 to 7 end. | "The hard ones are hard for a reason." | `findings.json` field `charts.hardCases`; quotes from `disputed-reviews-v1.json` (DEV-006, DEV-030, DEV-013) |
| S11 | Confidence is not the gate | Sixty dots for the sentiment field. On click, dots below 0.9 grey out (13 withheld, 9 of them green). Then switch field to testimonial: one red dot stays lit, labelled 0.96. | "The threshold kept the embarrassing one." | `jev-confidence-findings.json` (per-field retained, withheld, wrong-retained; wrong-case confidences DEV-027 0.96, DEV-029 0.91) |
| S12 | Longer prompt, worse answers | Three steps for Clef: 54, 51, 49, each appearing with a short drop. Beside it, a tally for 39 setups: 4 up, 14 flat, 21 down. | "The thing I'd do first is the thing that didn't work." | docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md (Clef table); docs/FINDINGS.md (39-setup tally). No JSON feed; designer hardcodes. |
| S13 | Agree or defer (hero) | Sixty review cards in a grid. Two model stamps land on each card. Where the stamps match, the card slides left into "accepted" (53). Where they differ, the card slides right into "a person" (7). The accepted column shows "0 errors". A price tag: $0.037. | "That's the whole rule, and I could build it tomorrow." | `native-agreement-policy-v1.json` pair Solar + Perplexity (accepted 53, errors 0, deferred 7, charge $0.03749436); deferred IDs listed in 01 §6 |
| S14 | The policy | Static five lines. Last line is the closing question, which appears on click. | "Which would I trust?" | 01 §6 proposed operating policy, lines 2, 3, 4, 5, 6 |
| S15 | classification-bench | Pipeline diagram: bring data, plan, run, evaluate, report. Two routes lit green (OpenRouter, Clef). Three routes amber (Claude Code, Codex, Liquid / Solar / Qwen). "Public release pending" badge. | "This person is not overselling." | 04 §2, §3, §7 |
| S16 | Star the repo | QR code and URL. "Early access: ask me." | An easy next step. | github.com/adambkovacs/candidate-experience-benchmark |

Motion rules for the whole deck: one idea moves per slide; every hero has a static PNG fallback; numbers animate from zero only once per slide; no motion on quoted review text.


## 4. Appendix slide list (12 backup slides for Q&A)

| Slide | Title | Content | Source |
|-|-|-|-|
| A1 | Hosted decision models, one card each | Jev ($0.042/M input, early access, no changelog), OpenAI Decisions on gpt-6-luna ($0.10/M, public beta, refusal type), Perplexity Decider ($0.02/M, Apache-2.0 v1), Liquid d1 ($0.04/M per blog methodology), Solar Decide (beta, price unverified). Pricing per million input tokens, output free. | 02 Part D |
| A2 | Open-weight decision models | Clef and Clef-flash (Apache-2.0, Workers AI price unverified), Strands Decider 2B, Kev family, d1-3B, Nimble 9B, Tev1 4B. Decision Index snapshot, labelled self-reported where it is. | 02 B3, B4, B6, B8, B10, B11; Part D quality snapshot |
| A3 | Prompt levels P0 / P1 / P2 | Decision models, every pass: Clef 54/51/49, Luna 49/51/49, Clef Flash 45/47/46, Solar 55,53,54 / 53,52,51 / 53,52,52, Jev OpenRouter 54,53,52 / 54,53,54 / 54,interrupted,54. 39-setup tally P0 to P1 and P1 to P2. | 01 insight 4 |
| A4 | Confidence bins | Jev P0 per field: wrong, retained at 0.9, wrong retained, withheld (of which correct). Solar at 0.9 and 0.99. Tev at 0.9. Note: retrospective, Jev did not abstain, no threshold validated. | 01 insight 3 |
| A5 | Reference sensitivity | Flipping DEV-006: 212 runs up, 168 down, 257 unchanged of 637. DEV-013 and DEV-030 the same way. Per-run deltas from minus 3 to plus 3. | 01 insight 8; `reference-sensitivity-v1.json` field `scenario_summaries` |
| A6 | Cost table, seven decision models | Known charge per 60 one-review requests: Clef Flash $0.012, Luna $0.013, Perplexity $0.015, Liquid $0.016, Tev $0.016, Solar $0.022, Clef $0.032 (estimate). Whole seven-model study under $1.20. Gemini effort pair: low 56/60 at $0.063, high 55/60 at $0.257. | 01 insight 14 |
| A7 | Limits and the claims we do not make | Not a leaderboard. Not causal. Not real-world accuracy (60 synthetic reviews, 340 planned never generated). Reference provisional v0.2, three labels disputed. Missing cost is unknown, not zero. No speed ranking. No pooling of 1,004 run entries. | 01 §4, §7 |
| A8 | classification-bench detail | What works (offline end to end, 272 tests, OpenRouter one route, Clef 42 of 42 valid), what is wired and not live (Claude Code, Codex, Liquid, Solar, Qwen), what is not built (OpenAI Decisions, unlabeled runs, several report items). Private repo, release pending. | 04 §2, §3 |
| A9 | Equal scores hide different answers | Sonnet 5.5 xhigh 58/60 in all nine cells, changed DEV-006 and DEV-030 between passes. Gemma E2B 35/60 while changing nine reviews. Jev P2 fresh1 and fresh3 both 54, differ on DEV-030. | 01 insight 5 |
| A10 | Stable is a property of the serving stack | Perplexity Decider 54/60 in all nine runs, identical answers, same errors every time. Laya 0/60 three passes, unchanged. AnyJev raw 0/60, unchanged. | 01 insight 6 |
| A11 | Class balance and the testimonial trap | Reference: testimonial 9 yes / 50 no / 1 insufficient. All-no scores 50/60. Tev recall 9/9 precision 9/12; Luna recall 6/9 precision 6/6; same field total, opposite failure. | 01 insight 9 |
| A12 | All 21 agreement pairs | Full table: accepted 33 to 53, accepted errors 0 to 4. Four zero-error pairs. Deferred IDs for Solar + Perplexity. Human review cost unmeasured; no pair selected for production. | 01 insight 7; `native-agreement-policy-v1.json` |

Also hold in reserve, not as slides: the rules baseline (10/60, 01 insight 13) and invalid-output counts (01 insight 11), as spoken answers.


## 5. Likely Q&A questions

| # | Question | Short honest answer | Point at |
|-|-|-|-|
| 1 | So which model is best? | I can't rank them. The runs differ in route, batch size, effort and prompt implementation. On these saved runs Opus 5.5 and Gemma 4 26B had the most matches; that's a description of one pass, not a ranking. | A7; 01 §4 |
| 2 | Sixty synthetic reviews. How real is that? | Not real-world. The reviews are AI-written and concern-enriched. The 340 planned validation records were never generated. Nothing here estimates performance, prevalence or fairness on real candidate text. | A7; 01 §7 |
| 3 | Isn't your reference the weak point? | Partly, yes. It is v0.2, human-checked, with three disputed labels. Flipping one of them moves 212 runs up and 168 down. When a one-point difference decides a vendor, your label quality is the bottleneck. | A5 |
| 4 | Is Jev faster? | I can't say. Client request time mixes network, CLI, batch and operator time, and pure inference latency isn't available on every surface. TypeSafe and Cloudflare publish their own latency numbers; I didn't measure speed. | A7; 02 B1, B3 |
| 5 | Why not pay for Opus at 59? | You can, at four to forty times the estimated spend, and the 59 is one pass. Sonnet scored 58 in all nine cells and still changed two reviews between passes. The aggregate hides that. | A9; S7 |
| 6 | Would agree-or-defer hold in production? | Unknown. The rule was fixed before calculation but scored on the same 60 reviews used for everything else. Human review cost of the deferred set is unmeasured. Treat it as a policy to test. | A12; 01 §6 |
| 7 | What about the open-source Jev clones? | One, OpenJev native, came within a few points at 53 to 54. The rest ranged from 39 down to 0. "Jev-like" on a model card tells you nothing; the saved run does. | 01 insight 12 |
| 8 | Did you count invalid outputs? | Yes, in the denominator. AnyJev's generated path wrapped every answer in a code fence and scored 0 of 60. Native choice heads had almost no format failures. | 01 insight 11 |
| 9 | Why was Jev perfect on serious concern and wrong on the testimonial? | Class balance. There are 25 serious concerns and 9 testimonials. Answering no to every testimonial already scores 50 of 60. Field totals hide whether a model finds the nine. | A11 |
| 10 | Can I run this on my own task? | Yes, with classification-bench, once it is public. It runs offline today with 272 tests and has made small live calls through two routes. Ask me for early access. | A8; S15 |

Two more to have ready: "Jev's confidence versus its option probability" (0.91 versus 0.94 on the same answer, neither calibrated; 01 insight 3) and "does hosted Jev drift" (Cloudflare's board saw 20 choices change in twelve days with no version change; 02 B1 and E8).


## 6. Risks and fallbacks

| Risk | Fallback |
|-|-|
| Projector washes out colour | Every chart carries its number as text. Kept versus withheld on S11 uses shape (filled versus hollow), never colour alone. Dark text on light background throughout. |
| No WebGL or no browser on the venue machine | Every hero (S4, S9, S13) has a static PNG and a three-step Keynote build. The deck opens without network; all JSON is baked in at export. |
| Time overrun | Cut order: first S5 taxonomy to one spoken sentence (saves 45 s). Then the prompt half of beat 6 to one line, "a longer prompt made 21 of 39 setups worse" (saves 50 s). Then bio to 20 s. Never cut the soup reveal or the rule. |
| Nobody shouts on moment 2 | Line ready: "I'll take that silence as 'most of them'. It was none of them." |
| Few hands on moment 1 | Line ready: "Good, then nobody here has to admit anything yet." |
| TypeSafe staff in the room | The talk credits Jev's 25 of 25 on serious concern and quotes TypeSafe's own confidence page approvingly. No "beats", no "better than". If challenged, point at A7. |
| A number is challenged | Every number has a path in sections 2 and 3. Reply with the path and the confidence tag from 01 (solid, descriptive-only, anecdotal). |
| Replay slides fail | No live demo was planned. Saved answers are static text on S8 and S9; the PNG fallback covers the rest. |


## 7. Word count per beat

Produced by `scripts/count-notes.ts` (bun) over the `[notes beat=N]` blocks, with bracketed stage directions removed before counting.

| Beat | Words | Budget |
|-|-|-|
| 1 Cold open and answer | 160 | 160 |
| 2 Bio | 85 | 95 |
| 3 The field | 202 | 210 |
| 4 Proof 1 | 258 | 290 |
| 5 Proof 2 | 276 | 330 |
| 6 Proof 3 | 264 | 300 |
| 7 The rule | 269 | 300 |
| 8 The tool and call to action | 195 | 215 |
| Total | 1,709 | 1,800 |


## 8. Pending: integrate 01b-deep-analysis.md

01b did not exist when v1 was written. When it lands, its insights slot in here:

| If 01b adds | Where it goes |
|-|-|
| A sharper statement of why decision models share blind spots on off-topic input | Beat 5 notes, the paragraph after the histogram; S10 subtitle |
| A calibration curve or reliability plot for any model | Beat 6, replacing the sentence "nobody's confidence number was calibrated" with the measured number; new appendix slide A13 |
| An out-of-sample or split test of the agree-or-defer rule | Beat 7 caveat paragraph; A12 |
| Per-class recall and precision across all seven decision models | A11, and one spoken line in beat 7 on the rare classes |
| Anything on cost per deferred review or human-queue cost | Beat 7 ("human review cost is unmeasured" becomes a number); S13 price tag |
| A finding that changes the one-sentence answer | Section 1 and S2 first; then beat 1 notes |

Rule for integration: nothing from 01b enters a main-deck slide unless it carries a source path and a confidence tag from 01's scheme.
