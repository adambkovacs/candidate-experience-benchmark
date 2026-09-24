#!/usr/bin/env bash
# This wrapper performs paid inference ONLY when explicitly invoked after review.
set -euo pipefail

if [[ $# -ne 2 || ! "$1" =~ ^(P1|P2)$ || ! "$2" =~ ^(smoke|development)$ ]]; then
  echo 'Usage: run_after_review.sh P2|P1 smoke|development' >&2
  exit 2
fi
: "${Q27_BUDGET_MANIFEST:?Set the preallocated budget partition manifest path}"
: "${Q27_BUDGET_ID:?Set the exact preallocated partition ID}"

variant="$1"
phase="$2"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
manifest="$script_dir/execution-manifest.json"
manifest_sha='a7e8a9a8c088b74f0668c60bc32dd19703bc8c8fce4f2acbc020bfbdc26b1859'
extra=(--start 1)
if [[ "$phase" == development ]]; then
  : "${Q27_SMOKE_SUPPLEMENT:?Set the reviewed prompt-smoke-supplement-v1 path}"
  : "${Q27_SMOKE_SUPPLEMENT_SHA256:?Set its SHA-256}"
  extra+=(--prompt-smoke-supplement "$Q27_SMOKE_SUPPLEMENT"
          --prompt-smoke-supplement-sha256 "$Q27_SMOKE_SUPPLEMENT_SHA256")
fi

cd "$repo_root"
exec python3 scripts/openrouter_paid_benchmark.py \
  --model qwen/qwen3.8-27b --provider darkbloom/fp4 --reasoning low \
  --max-input-price 0.1 --max-output-price 1.8 --max-tokens 4096 \
  --phase "$phase" --timeout 120 --continue-on-invalid-output \
  --prompt-variant "$variant" \
  --parent-baseline-id openrouter-qwen27-low-darkbloom-fp4 \
  --prompt-execution-manifest "$manifest" \
  --prompt-execution-manifest-sha256 "$manifest_sha" \
  --prompt-configuration-id openrouter-qwen27-low-darkbloom-fp4 \
  --prompt-schedule-journal "$script_dir/execution-journal.jsonl" \
  --budget-partition-manifest "$Q27_BUDGET_MANIFEST" \
  --budget-partition-id "$Q27_BUDGET_ID" \
  --env-file /Users/adamkovacs/Documents/codebuild/.env \
  --output "$script_dir/${variant}-${phase}.jsonl" \
  "${extra[@]}"
