# Mistral Small 3.2 repeat 2, P1

The phase stopped at DEV-043 after 42 valid responses. Venice returned HTTP 429, identifying its upstream shared provider pool as temporarily rate limited. The saved phase contains one service error and 17 never-sent records; this is not a complete pass. No P0 request was sent after the order gate rejected advancement.

This was the paid OpenRouter route `mistralai/mistral-small-3.2-24b-instruct`, endpoint `venice/fp8`, quantization FP8, with no reasoning control. Reported charges for completed billed development requests total $0.00680893750. The DEV-043 charge is unknown; its $0.02502400000 reservation remains held. Total phase cost is therefore unavailable, not zero. The partition remains open.

The [frozen manifest](../manifest.json) preserves controls and requests. The [development journal](development.journal.jsonl) and [raw response evidence](development.responses.jsonl) preserve the stop and provider error. There was no automatic retry or model substitution. Pure inference time and remote hardware remain unavailable. Reference labels were excluded from inference.
