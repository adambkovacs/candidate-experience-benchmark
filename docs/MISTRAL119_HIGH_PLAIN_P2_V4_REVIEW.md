# Plain Mistral high: independent P2 admission

The plain `mistral` route has two stopped smoke attempts. The original fresh1/P0 and the later fresh1/P1 each sent only DEV-001, received HTTP 429, and retained a separate $0.04177920 unknown-cost bound. Neither smoke passed. Their DEV-002/003 requests remain unsent, and this P2 plan does not send them. [P0 terminal](../results/repeatability-v1/mistral119-high-plain-authority-v1/terminal-public.json) · [P1 terminal](../results/repeatability-v1/mistral119-high-plain-authority-v1/remaining8-v4/terminal-public.json)

This proposal isolates the previously unopened fresh1/P2 stage. Its three smoke and 60 development payloads are byte-identical to P2 in the reviewed [eight-stage plan](../results/repeatability-v1/mistral119-high-plain-authority-v1/remaining8-v4/fresh1/manifest.json). It retains model `mistralai/mistral-small-2603`, provider `mistral`, high reasoning, temperature zero, and the original output schema. A new configuration ID records the independent order. It is not a clean repeat of P0 or P1. [P2 proposal](../results/repeatability-v1/mistral119-high-plain-authority-v1/independent-p2-v4/proposal.json) · [P2 plan](../results/repeatability-v1/mistral119-high-plain-authority-v1/independent-p2-v4/fresh1/manifest.json)

The proposal is offline and unadmitted. It requests one new OpenRouter-only v4 child capped at $0.75. Each request reserves at most $0.04177920, and the controller checks available child capacity before each sequential reservation. The cap cannot guarantee all 63 requests; a capacity stop leaves later requests unsent. Existing unknown bounds remain in their original sealed children. [Controller](../scripts/mistral119_high_plain_p2_v4_execution.py)

Review and execution order:

1. Verify the source-bound proposal and run the focused offline tests: `python3 scripts/mistral119_high_plain_p2_v4_execution.py verify` and `PYTHONPATH=scripts python3 -m pytest -q tests/test_mistral119_high_plain_p2_v4.py`.
2. Independently review the exact proposal and controller. Record the root review receipt. Under the current v4 authority and master locks, check the $22.38 cumulative cap and allocate one exact $0.75 child with its matching OpenRouter-only hold. A route catalog check must still match the frozen model, provider, prices and request bytes. Listing the route does not prove shared-pool capacity.
3. Generate the fresh1/P2 smoke stage receipt, approve it, and dispatch `smoke --fresh-pass fresh1 --condition P2 --review <exact-smoke-receipt>`. The controller claims the stage once and stops on a failed or unknown request. Never replay one.
4. Inspect all three saved raw smoke responses. Only an accepted, unchanged three-call inspection permits a fresh development receipt and `development --fresh-pass fresh1 --condition P2 --review <exact-development-receipt>`. The 60 development requests then run in frozen order with sequential reservations and no automatic retry.

No child allocation, authority hold, inference request or ledger write is part of this proposal. Provider capacity remains unverified by a live smoke.
