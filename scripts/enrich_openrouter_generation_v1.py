#!/usr/bin/env python3
"""Read-only provider timing/usage enrichment. Never submits inference requests."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from openrouter_benchmark import fetch, load_key
from development_benchmark import ROOT

FIELDS = ('id', 'model', 'provider_name', 'generation_time', 'latency',
          'native_tokens_prompt', 'native_tokens_completion', 'native_tokens_reasoning',
          'native_tokens_cached', 'total_cost', 'created_at', 'finish_reason')

def inventory(root):
    sources, ids = {}, set()
    for path in sorted((root / 'results').rglob('*.jsonl')):
        if 'generation-metadata-v1' in path.parts:
            continue
        raw = path.read_bytes()
        found = []
        try:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except (ValueError, UnicodeDecodeError):
            continue
        for row in rows:
            body = row.get('raw_response') or {}
            ident = body.get('id') if isinstance(body, dict) else None
            if (isinstance(ident, str) and re.fullmatch(r'gen-[A-Za-z0-9_-]+', ident)
                    and (row.get('surface') == 'openrouter' or row.get('provider_endpoint'))):
                found.append(ident)
                ids.add(ident)
        if found:
            sources[str(path.relative_to(root))] = {
                'sha256': hashlib.sha256(raw).hexdigest(), 'generation_ids': found}
    return {'kind': 'openrouter-generation-metadata-v1', 'sources': sources,
            'ids': sorted(ids), 'inference_submitted': False,
            'timing_note': 'generation_time is OpenRouter-reported generation duration in milliseconds. It does not establish pure accelerator inference time or per-record latency for batches.',
            'source': 'https://openrouter.ai/docs/api/api-reference/generations/get-generation'}

def retrieve(ident, key):
    try:
        response = fetch('/generation?id=' + quote(ident, safe=''), key, timeout=30)
        data = response['data']
        if data.get('id') != ident:
            raise ValueError('Generation identity mismatch')
        return {'id': ident, 'status': 'ok', 'data': {k: data.get(k) for k in FIELDS}}
    except Exception as exc:
        return {'id': ident, 'status': 'unavailable', 'error_type': type(exc).__name__,
                'http_status': getattr(exc, 'code', None)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--workers', type=int, default=6, choices=range(1,9))
    args = parser.parse_args()
    folder = ROOT / 'results/generation-metadata-v1'
    folder.mkdir(exist_ok=True)
    manifest_path = folder / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = inventory(ROOT)
        with manifest_path.open('x') as out:
            out.write(json.dumps(manifest, indent=2) + '\n')
    path = folder / 'metadata.jsonl'
    existing = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    completed = {x['id'] for x in existing}
    pending = [ident for ident in manifest['ids'] if ident not in completed]
    key = load_key(args.env_file)
    if not key:
        raise ValueError('OpenRouter key unavailable')
    print(json.dumps({'unique_requests': len(manifest['ids']), 'pending': len(pending)}), flush=True)
    with path.open('a') as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, row in enumerate(pool.map(lambda ident: retrieve(ident, key), pending), 1):
            out.write(json.dumps(row) + '\n'); out.flush(); os.fsync(out.fileno())
            if index % 100 == 0:
                print(json.dumps({'metadata_requests_finished': index}), flush=True)
    print(json.dumps({'complete': True, 'inference_requests': 0}), flush=True)

if __name__ == '__main__':
    main()
