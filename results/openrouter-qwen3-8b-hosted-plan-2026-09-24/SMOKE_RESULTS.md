# Hosted Qwen3-8B smoke results

Both P0 smoke conditions stopped on Alibaba upstream shared-pool HTTP 429 errors. Reasoning off saved two valid outputs followed by one service error. Reasoning on saved the invalid JSON string `"useful feedback"`, then one service error; DEV-003 was not sent. Both processes exited normally after the adapter stopped dispatch. No full60 or P1/P2 run started, and no retry or model substitution occurred.

The [root inspection and closure](root-smoke-inspection-and-closure.json) binds raw results, terminal journals and sealed child ledgers. Known charges total $0.000672100. The two missing charge receipts retain a combined $0.034398208 upper bound; that amount is not observed spending. The unused portion of the two $0.40 allocations returned to the shared $5 budget.

The exact model and sole provider were checked live by the adapter before inference. Responses and errors identify Alibaba. The next step is verified upstream capacity recovery or a separately reviewed hosted route; failed smoke records must remain in the evidence if any continuation is later run. Existing local Qwen8 results do not substitute for these hosted conditions.

Only fictional DEV-001–003 feedback was sent. No reference labels were included. Automatic approval initially rejected the commands on a sensitive-data premise; review accepted the same commands after the repository's synthetic-data provenance and exact payloads were supplied. The rejected commands did not start processes or incur charges.
