# Qwen continuation attempt: DEV-043

The exact frozen AkashML route returned HTTP 429 with provider code `queue_timeout` and limit source `upstream_provider_shared_pool`. This is a provider-capacity rejection. It does not establish an exhausted OpenRouter account or project cap.

The episode stopped after DEV-043. The composite now has 43 attempted positions: 37 valid outputs and six retained service errors. DEV-044 through DEV-060 remain never sent. No failed position was retried. The new unknown charge is retained at its full $0.0299008 bound; actual billing is unknown. The unused $0.5083136 allocation was released.

`responses.public.jsonl` is a publication copy with the account identifier removed from the error body. The original `responses.jsonl` remains private and unchanged. Its SHA-256 is acdc80a942919a237c275d1d9e7e65449812e32626b8f5d59f5bb95a34f601e5. The reconciliation binds that private original, so readers can inspect the redacted error but cannot independently reproduce the original-body hash from this public copy. This redaction changes no prediction, error code or accounting outcome.

The [reconciliation](reconciliation.json), [attempt](attempts.jsonl), [journal](journal.jsonl), [frozen manifest](manifest.json) and [review](root-review.json) preserve the attempted membership and stopping decision. Further episodes require a new review and budget admission. Repeated catalogue availability does not prove this endpoint has capacity.
