# Offline tokenizer audit reproduction

These are byte-for-byte archives of the scripts used for the AnyJev and OpenJev token preflights. The manifest records their original execution paths, commands, Python environments and hashes. Local artifact paths are specific to this benchmark host; no credentials are included.

Both scripts force offline Hugging Face operation and load tokenizers only. The OpenJev script reuses the pinned server normalization and rendering methods without constructing a model. Its counts reproduce recorded prompt usage, but artifact context metadata does not establish the historical live server limit.

Outputs use exclusive creation. To reproduce an audit, retain the pinned artifacts and source checkout, use a new output filename, and record the new script/output hashes. Do not overwrite original evidence. Archived scripts expect their original workspace location; adapt paths explicitly on another machine and preserve that adapted version separately.

Results: [AnyJev preflight](../anyjev-generated-phase2-token-preflight-2026-09-23.json) and [OpenJev preflight](../openjev-generated-phase2-token-preflight-2026-09-23.json). These audits do not establish the remaining smoke, scheduling or paired-comparison gates.

The archived SemIf script reproduces [its separate audit](../semif-generated-phase2-token-preflight-2026-09-23.json), which embeds the original command and working directory. SemIf historical generated hashes describe decision intent, so this is source reconstruction, not historical generated-message parity.
