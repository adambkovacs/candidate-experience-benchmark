# Current work checklist

Updated 30 September 2026. This is the current coordination list. Frozen manifests and saved responses establish execution status; this checklist does not authorize spending or change the experiment protocol. See [current goals](CURRENT_GOALS.md) and the [detailed roster](REMAINING_ROSTER_2026-09-29.md).

## Active assignments

- [x] **OpenJev publication — root / publish_on_triple:** All nine generated-off and nine generated-on phases are published in bf5777ac. Pages run 36749343379 succeeded; live HTML and feed SHA-256 values exactly match the commit.
- [x] **OpenJev generated-on — resume_generated:** All nine full phases closed; final session 22425 exited 0. The nine phases contain 540 saved attempts, 482 valid and 58 retained invalid outputs. Completion and record hashes passed pinned verification.
- [ ] **SemIf generated — resume_generated:** Fresh1/P0 closed with 60 saved, 52 valid and eight retained invalid outputs. Fresh1/P2 closed with 60 saved, 58 valid and two retained invalid outputs (DEV-029/055). Root independently verified completion/output hashes and predecessors. Fresh1/P1 full phase closed with 60 saved, 38 valid and 22 retained invalid outputs; root independently verified hashes. The first full P0/P1/P2 pass is complete (3/9 conditions). Fresh2/P1 smoke closed with two valid outputs and one retained schema echo. Root inspected raw responses and verified frozen bindings, then admitted the full fresh2/P1 development phase. It closed with 60 saved, 38 valid and 22 invalid outputs; root verified frozen bindings and completion hashes. All predictions and validity outcomes match the first P1 pass. Four of nine full phases are closed. Fresh2/P0 smoke closed with two valid outputs and one schema echo; root read the raw responses, verified frozen bindings and admitted its full development stage.
- [ ] **Hosted decision smoke adapter — decision_route_audit:** Jev and Kev smokes each closed with three valid responses and observed charges. Kev native P0 passes one and two each closed with 60 valid outputs and $0.004703412 observed cost; all 60 classifications match across them. Pass three stopped at DEV-026 after 25 valid responses. The separately reviewed DEV-027–060 continuation closed with 34 valid responses and $0.002665572 observed cost. The interrupted series has 59 observed valid responses, $0.004624830 known cost, and one DEV-026 unknown charge retained at its $0.000344064 upper bound; it is not a clean third pass. [Terminal reconciliation](../results/route-audits/kev-fresh3-continuation-20260930/terminal-reconciliation.json) binds raw responses and ledger settlements. Native P1/P2 transformations are documented in [the reviewed proposal](NATIVE_DECISION_PROMPT_PROTOCOL_2026-09-30.md); offline manifests are prepared and the execution adapter review passed; live admission remains pending.
- [x] **Kev findings — root:** updated reporter and visible repeat explorer are pushed in 9e58749e. They show two clean passes plus 59 valid responses and one unknown in the interrupted series, confidence coverage, tokens, observed charges and separate timeout timing. Fourteen reporter tests, 55 repeat UI tests and a clean staged export passed. Deployment 36746773009 succeeded; live script and feed SHA-256 values match 9e58749e and the following documentation-only commit.
- [ ] **Integration — root:** review closed evidence and new adapter, stage only completed artifacts, run checks, commit and push, then verify the deployed website.

- [x] **Native hosted P1/P2 preparation:** four offline Kev/Jev manifests with 60 input-only requests and three planned pass identities each are prepared and verified in `results/route-audits/native-variants-offline-20260930`. Seven tests pass, including leakage, drift and immutable-output checks. Review verdict: APPROVE for offline preparation. RESIDUAL: live endpoint refresh, provider context accounting, smoke inspection and spending admission remain required; no execution is authorized by these manifests.

- [ ] **Native P1/P2 execution adapter — root:** implementation reviewed; 12 offline tests pass, including whole-pass budget gating, exact receipts, no replay, raw/ledger reconciliation, and endpoint-snapshot tampering. Review verdict APPROVE for implementation. RESIDUAL: no provider pre-dispatch tokenizer for all inputs; future context errors stop the pass. The runner holds the shared ledger lock for a stage, so it serializes this lane. No live stage is admitted; exact receipt, current route and available budget remain required.
- [ ] **AnyJev generated readiness — publish_on_triple:** read-only frozen-plan/runtime audit passed; 15 combined controller/reporter tests pass. No fresh execution exists. Exact hosted Qwen 0.6B endpoint unavailable in current API check. First smoke needs root receipt and free native host; SemIf retains the host.

- [x] **Solar Decide offline preparation — native_variants_prepare / root:** plan builder and five passing tests cover separate Upstage and Upstage ZDR route candidates, P0/P1/P2, and three planned full passes per condition. Root review: APPROVE for offline preparation. RESIDUAL: live access, response wrapper, context accounting and billing require smoke verification. Saved full-context bounds are $0.0786432 per three-record smoke and $1.572864 per full pass; these are conservative admission bounds, not observed costs. No requests or reservations were made.

- [ ] **SemIf four-phase publication — root:** `e2834ef8` pushed the second P1 result, source-bound feed and updated explanations. Root checked all 81 committed source hashes and 13 reporter/UI tests. Pages run `36758886171` is checking the bundle; live verification remains pending.

## Verified progress

- [x] SemIf generated first P0/P1/P2 pass published in `0184bb6d`. Pages run `36756829330` succeeded; public HTML and 3/9 feed match committed bytes. All-field agreement is 35/60, 26/60 and 43/60 respectively, with 8, 22 and 2 invalid outputs retained. Desktop/mobile field selection and keyboard focus were checked on the preceding UI version; the latest data changes passed UI tests. Fresh2/P1 execution continues separately.

- [x] OpenJev generated-on fresh1/P2: 60 saved responses, 52 valid and eight retained invalid outputs. Root verified completion hashes. Closed evidence and the fresh2/P1 smoke are saved in `69be3266`; the first P0/P1/P2 generated-on comparison is now public in 40c20a03.
- [x] Ruflo checkpoint save-back verified in both canonical databases; identical content SHA-256 `709cc8aa9a0b320e6af37b834774e6f4088208fce3b79e6884ba3e3fe638c83c`.

- [x] Website deployment 36731918630 succeeded for be554f15; live HTML, navigation, stylesheet and generated report hashes match the commit.
- [x] OpenRouter native smokes: Jev 3/3 valid, $0.000294294; Kev 3/3 valid, $0.000234864. These are protocol checks, not full benchmark scores.

- [x] OpenJev generated-off: all nine full phases closed; 540 attempts saved, 491 valid and 49 retained invalid outputs. The execution agent verified the pinned plan and completion hashes. Publication is a separate task above.
- [x] Primary-source decision-model route audit written: [report](DECISION_MODEL_ROUTE_AUDIT_2026-09-30.md). No inference was performed by that audit.
- [x] Existing Claude and Codex repeat groups completed as listed in the detailed roster. Do not dispatch them again.
- [x] Project `.env` exists with mode 0600 and is ignored by Git. Never include credentials in source, evidence or memory.

## Remaining execution and blockers

- [ ] Complete SemIf generated and AnyJev generated P0/P1/P2 repeat series under their own frozen protocols and the shared native host lock.
- [ ] Refresh hosted availability before any of the ten remaining exact generic local configurations. Do not resume the cancelled DeepSeek download.
- [ ] Finish the remaining hosted Qwen, Gemma, DeepSeek, Mistral and Gemini configurations listed in the detailed roster. Last reconciled OpenRouter capacity: $0.01967548250 unallocated under the $10 total cap. The proposed $17 total is not yet explicitly confirmed; willingness to add funds is recorded separately from a numeric cap increase. TypeSafe retains its separate $1 cap.
- [ ] Admit new decision models individually after exact route, interface, account access, price and context checks. A vendor's free preview listing does not establish account access. Preserve native probabilities separately from generated-letter logprobs. The 30 September check found no conventional Liquid, Upstage, Alibaba/DashScope, Together, Nace/Drex, Fastino or Cloudflare credential variables in this project's `.env` or the current process environment. This does not establish whether credentials exist elsewhere; direct-provider access remains unverified. OpenRouter Jev/Kev access is verified by their saved smokes.
- [ ] Resolve reference-review items with human adjudication where required. Preserve frozen labels and original scores.
- [ ] Finish full roster reconciliation and publish completed, failed, unsupported and blocked dispositions. The overall MVP is not complete merely because one repeat series is finished.

## Memory and ownership

Use Ruflo decision entries for approvals and verified checkpoints, and ReasoningBank patterns for reusable learnings. Verify shared persistence; a successful store response alone is insufficient. The repository remains the evidence archive, not the memory database. The separate private classification-bench project belongs to its own user-started task.
