# Public OpenRouter catalog check, 2026-09-29 Budapest time

The unauthenticated public [models catalog](https://openrouter.ai/api/v1/models) returned HTTP 200 at 2026-09-28 22:08:44 UTC. [catalog.raw.json](catalog.raw.json) preserves the exact response bytes; [catalog-audit.json](catalog-audit.json) records its SHA-256, 460-entry count and search result. No inference endpoint, credential, model download or local model was used.

The case-insensitive search covered `id`, `name`, `canonical_slug` and `hugging_face_id` for `qwen3-0.6b`, `qwen3-1.7b` and `qwen3.5-4b`. It found zero entries. The historical `qwen/qwen3-0.6b-04-28:free` ID is absent from this catalog. Nearby listed Qwen3 8B and Qwen3.5 9B/27B entries are different models and cannot stand in for the requested local artifacts.

With no exact catalog ID, there was no endpoint metadata to query. This snapshot establishes catalog absence at retrieval time only. It does not prove permanent unavailability, capacity, artifact identity or quantization. Recheck the exact route immediately before any local dispatch; the existing small-local admission policy limits positive route attestations to less than 24 hours, and a negative catalog search alone is not a runtime attestation.
