# Current-tree Claude quota evidence remediation

Executed on 2026-09-28: the 648 exact captures are removed from the Git index
and individually ignored. Working originals and private backup bytes remain intact. The [candidate manifest](PRIVATE_EVIDENCE_REMOVAL_CANDIDATES_2026-09-28.json)
binds every proposed removal to the original SHA-256 and to the independently
retained private backup. The [exact ignore proposal](PRIVATE_EVIDENCE_IGNORE_PROPOSAL_2026-09-28.txt)
contains one rooted path per candidate; it has no directory-wide pattern.

The current tracked-results scan parsed JSON and JSONL, including JSON embedded
in `stdout`. It found 648 quota-bearing files. All 648 match a backup copy by
path, byte count, and SHA-256, with no backup gap. The 745-entry private backup
also holds 97 path/provenance-only files. Those 97 are excluded from this removal
proposal to preserve source bindings. Another 1,028 tracked files have only a
private home-path lead and are not removal candidates. Three additional files
matched a broad Bearer-text pattern; local inspection found natural-language
auth-scheme descriptions, not a token or confirmed secret. Their paths and
reason codes remain in the manifest for review. No account or credential value
is copied into the manifest.

The 648 candidates are distributed across these existing trees:

| Tree | Files |
| --- | ---: |
| `results/repeatability-v1` | 486 |
| `results/prompt-comparison-v1-2026-09-24` | 86 |
| `results/subscription-batch-p0-2026-09-23` | 39 |
| `results/claude-subscription-2026-09-21` | 24 |
| `results/claude-subscription-2026-09-23` | 13 |

The [Pages workflow](../.github/workflows/pages.yml) now checks the three
immutable [public Claude bundles](../public-evidence/claude-20260928/) and
tests their source hashes, redaction, report bindings, and public-site byte
equality. The synthetic exporter tests reject changed evidence and changed
bindings. These checks do not recompute every published score from the redacted
raw evidence; the original source-bound builders remain available for private
archival rebuilds. The public bundles retain classifications, request identity,
usage, model identity, and timing fields. Account-wide quota utilization and
reset data are absent from those public copies.

The current `public-site/data.json` also contains 14 historical evidence URLs
pointing at proposed removals; `findings.json` repeats those URLs 28 times.
The [historical-link export](../scripts/export_historical_claude_links.py)
has now saved 14 redacted public copies with 840 preserved development rows and
original/public SHA-256 mappings. Its public-only checker passes in the
temporary checkout with the 648 originals absent. The
[explorer builder](../scripts/build_public_explorer.py) routes only those exact
14 source paths to the new public copies. The site JSON has been rebuilt and reviewed: 14 run URLs and their 28 findings
references now use these copies. Only those URLs, the export timestamp, and the
findings source hash changed; scores and usage are unchanged.

The masked-read dependency audit found that the three archival builders and
their source-based tests require private originals:
`build_claude_roster_findings.py`, `build_claude_repeat_findings.py`, and
`build_haiku_matched3_findings.py`. Their source-based tests should run only in
an environment with the retained private backup. All three public-bundle
checks passed under masking. Other Pages Python checks passed under masking,
except the SemIf report check, which was already stale without masking. The
mask is a dependency probe, not proof of a clean checkout: it does not hide
directory entries or intercept every form of file I/O.

An actual temporary checkout was also extracted from `git archive HEAD` with
exactly the 648 candidate paths omitted. The three published Claude bundles
verified, all three site reports matched their bundle reports byte-for-byte,
and the exporter plus public-release tests passed (8 tests). This validates
the public Claude release path independently of the private originals. It
does not claim that every unrelated repository check passes; SemIf currently
has a separate stale-report check.

The executed current-tree sequence was:

1. Rebuild and check `public-site/data.json` and `public-site/findings.json`.
   Require zero evidence URLs pointing to the 648 candidates and 14 historical
   run URLs pointing to the new redacted bundle, while scores and usage remain
   unchanged.
2. Re-run [the inventory tool](../scripts/audit_private_evidence_removal.py)
   against the verified private backup. Require 648 quota candidates, zero
   backup gaps, and identical path/SHA-256 pairs to the reviewed manifest.
3. Apply the 648 rooted lines in the ignore proposal to `.gitignore`. Produce
   a NUL-delimited pathspec from the manifest's `removal_candidates[].path`
   values and use `git rm --cached --pathspec-from-file=<pathspec> --pathspec-file-nul`.
   This changes the index only; do not remove working or private backup bytes.
4. Check the staged deletion set equals the 648 manifest paths exactly. Run
   the Pages public checks in a fresh checkout and independently verify the
   private backup again. Review the diff before committing.

This sequence is **not executed** by the inventory tool. A current-tree removal
does not erase already published Git history. Historical exposure requires a
separate decision and cannot be described as resolved by this change.

## Final verification

The staged deletion set exactly matches all 648 manifest paths. All candidate
working originals and private backups were rehashed against the manifest. A
fresh archive of the staged Git tree, without any private originals, passed
every command in the Pages workflow: all report checks, public bundle checks,
JavaScript checks, and 97 Python tests plus three UI tests. The final SemIf
report also passed; the stale-report observation above belongs to the earlier
dependency probe. Git history is unchanged and still contains historical captures.
