# Public evidence and private CLI metadata

The benchmark preserves the model response used for each evaluation. That does not require publishing account-wide subscription usage. A read-only audit on 28 September 2026 found quota utilization and reset metadata in saved Claude CLI events and their parsed attempt records. The public website data files did not contain the audited quota keys. Some raw evidence already committed to GitHub did contain them.

## What is held from publication

New Claude captures are held locally while a separate export is verified. The original captures, attempt records, frozen manifests and hashes remain unchanged. This publication hold does not authorize rerunning requests or changing predictions. It does not stop inference that already passed its admission checks.

The audit identified quota metadata in 378 tracked repeat raw captures, 108 tracked repeat attempt files and 37 older tracked Claude source files. These counts describe the audited snapshot, not every historical Git object. Haiku and the ongoing Claude roster also have unpublished captures with the same metadata. No finding about credential exposure follows from those counts; the confirmed issue is account-wide quota metadata.

## Export contract

A public export must record the original relative path and SHA-256, the redacted public path and SHA-256, and the redaction policy. It must preserve the request, classification, model identity, recorded token counts, request timing and cost observations used in the analysis. Account/profile data, credentials and account-wide quota utilization or reset fields do not belong in that export. Relevant no-overage evidence must remain distinguishable from account-wide quota measurements.

Structured CLI envelopes may contain another JSON document in `stdout`. The exporter must inspect that embedded document too. Redaction must not be a broad text substitution that changes candidate feedback, policy text or model answers. The export process verifies the original evidence first, then checks that public copies retain the same predictions and measurement fields.

Public readers can verify the exported bytes and reproduce the supported parsing and scoring checks from those bytes. They cannot independently authenticate private original bytes from a hash alone. The publication mapping is an attestation about those originals, not proof that a reader downloaded them. Documentation and automated checks must state that boundary explicitly.

## Existing Git history

Creating a clean export does not remove older files from Git history. Existing published raw evidence requires a separate current-tree and history assessment. Preserve a verified private backup before any change. Do not rewrite historical manifests, silently replace their hashes, or claim past disclosure has been undone by deleting a working-tree file. A remote history rewrite is not part of the admitted export work.

## Current status

A byte-for-byte private backup of all 745 tracked files in the broader audit inventory is verified against their recorded SHA-256 values. That inventory includes profile/path patterns as well as quota keys; it is broader than the quota-only counts above. No originals were changed. The exporter passed six offline tests and an independent review. Three local export bundles now verify: Claude roster (2,003 source bindings), Haiku (200), and Opus 5.5 medium (128). All bound files are copied into each bundle so later source edits cannot change the exported evidence. JSON captures are redacted; source code is copied verbatim and can retain paths already present in the repository. The verifier checks hashes and the export checks parsing fidelity; neither independently recomputes every reported metric. Reports were rebuilt from verified originals immediately before export. These bundles have not been published yet. The benchmark's full completion still requires verified publication and an explicit disposition for the existing tracked metadata.
