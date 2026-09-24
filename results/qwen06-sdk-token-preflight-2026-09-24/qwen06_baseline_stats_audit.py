import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

workspace = Path(__file__).resolve().parent.parent
repo = Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo')
evidence_dir = workspace / 'results/qwen06-sdk-token-preflight-2026-09-24'
counts_file = evidence_dir / 'counts.json'
renders_file = workspace / 'work/qwen06-all-prompts-rendered.json'
output_file = evidence_dir / 'baseline-stats-audit.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


counts = json.loads(counts_file.read_text())
renders = json.loads(renders_file.read_text())
assert len(counts) == len(renders) == 360
source_paths = {row['source_file'] for row in renders if row['variant'] == 'P0'}
assert len(source_paths) == 2
saved = {}
sources = {}
for source in sorted(source_paths):
    path = repo / source
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert len(rows) == 60
    assert len({row['id'] for row in rows}) == 60
    for row in rows:
        assert isinstance(row['stats']['promptTokensCount'], int)
        saved[(source, row['id'])] = row['stats']['promptTokensCount']
    sources[source] = digest(path)

matched = 0
for render, count in zip(renders, counts, strict=True):
    assert (render['id'], render['configuration'], render['variant'], render['rendered_sha256']) == (
        count['id'], count['configuration'], count['variant'], count['rendered_sha256'])
    if render['variant'] != 'P0':
        continue
    original = saved[(render['source_file'], render['id'])]
    assert count['prompt_tokens'] == render['saved_prompt_tokens'] == original
    matched += 1
assert matched == 120

result = {
    'audited_utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Independently read stats.promptTokensCount from both frozen P0 development JSONL files; compared each to public-SDK count and offline-render copied count.',
    'source_sha256': sources,
    'renders_sha256': digest(renders_file),
    'counts_sha256': digest(counts_file),
    'auditor_sha256': digest(Path(__file__)),
    'p0_rows_compared': matched,
    'p0_rows_matching': matched,
    'p0_rows_mismatching': 0,
    'reference_labels_read': False,
    'inference_requests': 0,
    'limitation': 'Token counts match saved P0 stats; token-sequence identity and runtime template application for P1/P2 remain unproven.'
}
with output_file.open('x') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps({'output': str(output_file), 'matched': matched, 'sha256': digest(output_file)}))
