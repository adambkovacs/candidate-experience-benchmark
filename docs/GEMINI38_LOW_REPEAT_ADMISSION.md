# Gemini 3.8 Flash low repeat admission

This offline plan treats the saved P0, P1 and P2 conditions as the first pass
of one matched repeat series. It does not change the original P0
`identity_unverified` stop or send that batch again. The
[recovered-parent adapter](../scripts/gemini_openrouter_recovered_parent_adapter_v1.py)
ties the first P0 generation to its original request, response, provider
metadata and known charge, then reconciles only the five previously unsent
suffix batches. Its [admission proof](../results/gemini-openrouter-prep-v3/recovered-38-low-p0-admission-v1/recovered-p0-v1-admission.json)
accounts for six distinct development attempts and 60 ordered records. The
[historical review](../results/repeatability-v1/gemini38-low-historical-review-v1.json)
preserves the original failure and the cross-version parent binding.

The frozen v2 P0 has the same seven request payloads, payload hashes and
reservation bounds as a v3 reconstruction. P1 and P2 are v3 conditions whose
manifests bind that admitted v2 P0 identity. All three use
`google/gemini-3.8-flash`, `low` effort, the Google AI Studio route,
temperature 0, 8,192 maximum output tokens, strict JSON schema, no tools,
no fallback, 300-second timeout and batch10 development groups. Both v2 and
v3 use the same `codex_batch_benchmark.parse_batch` parser. Frozen model
reasoning and endpoint pricing/control fields match across the three
conditions. The historical 60-record condition outcomes are 60/60 valid in
each case. This supports a first-pass eligibility decision; it does not make
the observational prompt comparison causal or independently adjudicate the
provisional reference labels.

The [dedicated controller](../scripts/gemini38_low_repeat.py) prepares two
additional passes: repeat 2 in P1, P2, P0 order and repeat 3 in P2, P0, P1
order. Each condition is a new three-record smoke request followed, only after
inspection and exact review, by six ten-record development requests. The
controller reconstructs every frozen request and historical source binding,
checks current public route/pricing before loading a key, reserves against the
shared master and child ledger before dispatch, saves bounded raw evidence
before parsing, never retries a chat completion, and stops with the reservation
held if a charge is unknown or delivery ambiguous. The run path reads inputs
but not the per-record reference labels. No allocation, credential load,
provider request or budget mutation has been made for this plan.

Historical observed development charges were $0.02149275 (P0), $0.02229150
(P1) and $0.02648100 (P2), totaling $0.07026525. The separate three smoke
requests totaled $0.00617025. At the frozen route price, one new pass has
request reservation bounds of $0.50912475 (P0), $0.51452700 (P1) and
$0.54328125 (P2). Both passes sum to $3.13386600 if all 42 requests hit their
individual upper bounds. The largest single bound is $0.07782375.

A proposed $0.30 child partition would fit the stated $0.61379731850 master
headroom, leaving $0.31379731850 for the other pending scope. Admission is
strictly sequential: a known settled charge frees its reservation before the
next request. Historical charges suggest roughly $0.15287100 for two comparable
passes including smoke, but that is an estimate, not a guaranteed invoice or
completion promise. If actual charges accumulate toward the individual bounds,
the $0.30 partition must stop before its cap. The remaining 15-request scope
needs its own separate budget decision. No partition has been allocated.

Before any live admission, root must review the exact two manifest hashes,
allocate the child partition, verify current public model/endpoint pricing and
controls, and issue the phase-specific review receipt. A fresh smoke requires
raw identity and output inspection before its development phase. The frozen
historical proof is a source binding, never permission to replay an old
ambiguous request.
