# Adam's brief, in his own words

Collected from the working session on 2026-10-08. Quotes are verbatim (typos kept); bracketed notes are the conductor's.

## The original request

> there is this presentation of the findings (https://adambkovacs.github.io/candidate-experience-benchmark/presentation.html#opening/0) but I really don't like it need bunch of updates and changes first use a fable subagents to reason through the results and findings and come up with a plan for my session that is 15 minutes long plus qa. the session is titled "Do Models Like Jev Get It Right When Correctness Is Business-Critical?", but its not about just jev but other classifiers, and using various llm models for the task as well, and presenting the findings, learnings, interesting insights etc.

> session description: "TypeSafe describes Jev as a System One model for typed, probabilistic decisions inside software. Adam will look at where that helps, where uncertainty still matters, and how much confidence a business-critical workflow should demand"

> its important that we need to present what we did in the https://github.com/adambkovacs/candidate-experience-benchmark what we learned, what outcomes we saw etc. then we also want to introduce somewhere at the end the classification bench harness for users to run their own usecases (the repo is still work in progress). this is a harness that people can use with giving an openrouter api token for any model and also supporting coding harnesses like claude code or codex for models from anthropic and openai to run their own benchmark on their own usecases using their own inputs (including what should be classified or made a decision on), it'll have the same functionality like the recruitment-feedback-demo which is a working demo

> we need to start with of course describing what are these classifiers like jev (https://docs.typesafe.ai/introduction), and others like openai gpt luna decision api, clef (https://blog.cloudflare.com/clef-decision-models/), the liquid ai stuff (d1 I think), openjev, senf or what, laya, and any other new model (one of the findings is that after the launch Jev got punches from many other AI labs releasing their own version, like aws, perplexity, etc. what are these etc.) finetunned models for classification, why this matters, what are they good for. maybe we also need a bit of explanation on what sort of decision are they good for, system one vs system two thinking, open ended questions, ambiguity etc. (some of these we found in the recruitment testimonial bench)

> somewhere at the beginning we can stuff about adam (see bio: Adam Kovacs is co-founder and Chief AI Strategist of the AI Enablement Academy. He is also a Co-founding Member and International Ambassador of the Agentics Foundation and Executive Director of OPEN Talent Society., his gh and what he builds ...) can go into the findings, some of them are already mentioned in the repo, some of them are up here: https://adambkovacs.github.io/candidate-experience-benchmark/

> then we'll need a session outline and plan, you should review it (the audience will be agentic builders, techies, and agentic curious people at all levels, some engineers some maybe not, at various levels and seniority)

> use /adam-voice for writting content

> i need engagement questions as well (raise your hand if, and whatever makes sense

> i need to make sure that the presentation page fits on the screen and I dont need to scroll, but yes to multiple pages.

> you animation, motion graphics, threejs, do your absolute fucking best, like this is your opportunity to show what a great presentation, and animation and motion graphich person you are and this a work you would showcase as a presentation at the interview for your dream job and you need to prove that you;re the world best. use opus 5.5. subagents for this presentation and motion work. check your work, dont stop until its excellent

## Later instructions, in order

> use ruflo orchestrator, for research work we dont need a fable model, switch that to opus or sonnet, the tasks that need deep reasoning and planning use fable, not every task requires the smartest model, we need to be aware of our quotas (the motion graphic agent should be opus 5.5)

> make sure you use any /anti-slop skills as well not just /adam-voice

> are there more findings? more insights? interesting findings? model specific stuff? p0-p1-p2 version specific stuff? don't just recitate what the current findings are, use your own analysis too

> review the current plan, How would you improve on it to make it better? Be brutally honest and critical but highly constructive, effective, and practical, aiming for maximum ROI. [...] I'm thriving for excellence and not perfection.

> I agree with your recommendations, one note, on the motion graphics, go all out okay, feel free to use three js everywhere where it adds value and creates visual wows, gsap, whatever you need

> [answers] 1. I host the event, typesafe not in the room. 2. the harness will be opensourced. 3. my own laptop in chrome shared over zoom, not sure about resolution, we'll use an external tv, so maybe it wont be 4k, but at least full hd. 4. replay, make it look like its live, or at least give it that we're showing you what happens. 5. aea branding why not [logo path given]

> here are some extra useful skill that might come handy: https://github.com/charlie947/motion-graphics-skills

> if needed you can also use codex subagents for image generation (we dont have video gen capability yet)

> dont stress about fucking date and days like that, it doesnt matter. for run prices you use the api token for jev and openrouter in the demo folder and in the env in the codebuild folder and check run prices from logs if needed

> but now that you had so many new research findings come in and you created outline and deck foundation and all that. should we run another round of review? How would YOU improve on all of those [...] for example did we btw have 3 passes or three passes per p0/p1/p2 making it 9 passes? are results presented like that

> agree with your change and improvement recommendations, just make sure we dont have drift in anti slop and adam voice

> regarding findings and consequences, do we talk about the fact that not hallucinating doesnt mean deterministic and standardized, that at scale "what could possibly go wrong" question has a wider blast radius for wrong decisions and classifications, e.g. a bad testimonial isn't ranked and you get trending on x and reddit the candidate telling the world how horribly they were treated, tanking your employer brand and making hiring hard. "good luck with building your brilliant startup without being able to hire good people willing to work for you"

> do we show examples of questions, tricky ones, the things that triggered findings, explanation for them? do we have contextually supportive animations and motion for these?

> also for the site redesign (not the presentation) are we just redesigning the UI, or the whole UX, structure, what are we presenting, where and how?

> it's fine if deep links need to be redone, prioritize excellent user experience

> we're closing up to usage quota btw, so this main convo stays fable, everything else should go either opus or sonnet

> not sure if btw all this animation can be done on github pages, if not then if its needed we can deploy to vercel [...] both website and presentation

> do we also have conclusions consequences of findings, and "how could you make this better", and potential fixes for errors found by the demo? what does the latest of the internet say about this? like fine tunned models, multiple runs (multiple multiple ones) in the dozens or hundreds or thousands and majority voting based on the results, the ruvector repo has a typesafe or decision version (this could also be a potential alternative or fix), anything else?

> also for the site redesign [...] based on your findings, you can also run some opus subagents to fix the current website showing the details, you can make it more upscale more premium, more high end, motions, stuff like that, go hard at it to make it premium and all that, but still with fixes and findings implemented

## The verdict on the first deployed deck (2026-10-08, after deploy)

> this is a horrible ai slop sounding mess this presentations. I'm also looking at it at many times I ask myself, wtf do you mean? maybe more words from the website and the talking points should be explicit on the presentation. use a fable agent to review the presentation and compare it to my original needs and what I said

[Conductor's note: the deck was built under a self-imposed "max 12 words of on-slide text per slide" rule from the outline. Adam's verdict says that rule produced cryptic fragments a viewer cannot follow without the speaker, and that the slides should carry the talking points and the site's explanations explicitly.]
