#!/usr/bin/env python3
"""Export the audited provider-error JSONL without provider account identifiers.

The originals and frozen manifests remain private inputs. The public mapping
attests to their SHA-256 hashes but cannot authenticate private bytes alone.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'provider-error-public-evidence-v1'
POLICY = 'remove-only-raw_error_response.user_id-v1'
PUBLIC_DIR = Path('public-evidence/provider-errors-v1')
INVENTORY = (
    ('results/gemini-openrouter-prep-v3/p0-ready-v1/gemini38-flash-high/smoke-attempts.jsonl', '7b19266c711e19ad1e0320d29db3ca4b191d5ec0ccefb5875d07b118d828d26f', 1),
    ('results/hosted-unattempted-continuation-v2/openrouter-paid-gemma4-26b-a4b-on-p2/development.jsonl', 'd9f4a06f88961858dea2225d06dd6bd8cd2fa54db3e21720b68828bacb0bbeda', 1),
    ('results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p1/development.jsonl', 'd2790f8a47c18712562461d5e24cb980c5dd0a2517a78754cfa67a376a3ef84b', 1),
    ('results/hosted-unattempted-continuation-v2/qwen27-low-hosted-addendum-v1-p2/development.jsonl', 'baee6573b99d7b0da48c32348ca7b997b73f294ea173c84509ea3f4c030378a0', 1),
    ('results/mistral119-recovery-prep-v1/high-smoke.jsonl', '785a8e541bad3c1f91cb81af5cded554f50ce0b8d16be83a2fbc3c488768f875', 1),
    ('results/mistral119-recovery-prep-v1/none-smoke.jsonl', '5f70b7d22e96c82efd0e28362f55884a5c9b086fa517d92ddc10c03366180e79', 1),
    ('results/mistral119-recovery-prep-v2/high-smoke.jsonl', 'a919904e3712818055dcbd36908b4756924d0dc5a3cb3e4e349accd92ab4d233', 1),
    ('results/mistral119-recovery-prep-v2/none-smoke.jsonl', '29187b648dd9c946cc9ebf3f6b8670382d02dfed45f0b847351a091de2482b22', 1),
    ('results/openrouter-mistral119-none-2026-09-23/smoke.jsonl', '9e9e2b2ca02a64f11f2af4b3c01591a60f9977b93472a529242fb691586f9897', 1),
    ('results/openrouter-mistral119-none-cooldown-2026-09-24/smoke.jsonl', 'cf1419123a08b7eecc003ad6aaf4540bf35c698a551e088d3b80e32e15249c92', 1),
    ('results/openrouter-mistral119-none-recovery-2026-09-23/smoke.jsonl', '56f6878301774afb6bf417c4147f22f8f80bec8ac4291b0285cdc6defdb04ff4', 1),
    ('results/openrouter-mistral24-na-2026-09-23/development-from009-timeout600.jsonl', '39017e47931f7c78a7588592ed634069884d12a09c6e4f6c9c90ee67eaa5ce6d', 1),
    ('results/openrouter-mistral24-na-2026-09-23/development-from015-partition-recovery.jsonl', '589d044cdc5b32a8df5a5d59df9dfbc653311bedc6c7f5703b6c9fbcc11c5abd', 1),
    ('results/openrouter-mistral24-na-2026-09-23/development-from020-partition.jsonl', '33586afb8a173a61f6e2755b7fb186f7591d8f743e0f0cd846c994c7e917c2cd', 1),
    ('results/openrouter-mistral24-na-2026-09-23/reconciled-partial-after429.jsonl', '153cb5fcb1986e081016f61122da30c1eedfa75989b41b3b72f3c6a36829ba93', 1),
    ('results/openrouter-mistral24-na-2026-09-23/reconciled-partial-paused.jsonl', '6837377492437e53cb3a16912c2dd430876bdeeae55fa15e4ec66ca547d9e48b', 2),
    ('results/openrouter-partition-mistral119-high-2026-09-23/smoke.jsonl', 'dd5daaf099a57de2e823948ddac14eac3aea239ba5acee74a1cc1edeefb3d3d6', 1),
    ('results/openrouter-partition-mistral119-none-2026-09-23/smoke.jsonl', '8d6a31bb87294aeff157731e712a92dbca2f4f71939154c45fdfcc2de6c4aaab', 1),
    ('results/openrouter-qwen3-8b-hosted-plan-2026-09-24/off-p0-smoke3-results.jsonl', '80e7ace4bd5cdd97a1cef162e8d7749b5c51f32596878d1c6867befa74593793', 1),
    ('results/openrouter-qwen3-8b-hosted-plan-2026-09-24/on-p0-smoke3-results.jsonl', '9a5adeb753f4b32570cadb90eb193db88fccf18bbd59d11b9b648a2517dc1996', 1),
    ('results/prompt-comparison-v1-2026-09-24/qwen27-low-hosted-addendum-v1/P2-development.jsonl', '3e2bae718e61e6763ed98f5ad532f2c5fe87b16e5212c5bd67f9f3476b372c17', 1),
    ('results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen36-35b-a3b-on/P1/smoke.jsonl', '3d70b1a6f5035e5d9a87da8565f595fcedde052b788817f49bf989cd1bb9f317', 1),
    ('results/qwen36-on-p2-final19-v4/development.jsonl', '148c51bd739d8816c70a5973a8740124a7a2e18830ac277c4328273f7186a9d5', 1),
    ('results/qwen36-on-p2-final20-v3/development.jsonl', '4477412e4dd2c37ab77421e321f9ea19d7d3dbc7773c83b4520cdc98879574bd', 1),
    ('results/qwen36-on-p2-final21-v2/development.jsonl', '200a9b44d2c04a401d9f16d773524e97d9949325864dc9e742be5b1743e5fe60', 1),
    ('results/qwen36-prompt-recovery-v1/off-p2-development.jsonl', '301bcdfe3c65952c3996d39eafd02b14a8971790fc4455976f1c710276fd452e', 1),
    ('results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl', '6df034ce5f2864539b0ec5b7e7805ab8d2df4d7b24f77072a57f8690fca064fc', 1),
    ('results/qwen36-prompt-recovery-v1/on-p2-development.jsonl', '06dfa3870d1e1a5fb2d3b2e2aa93800a1762ba36872dea783ccf93e977ee232a', 1),
)

ERROR_KEYS = {'message', 'code', 'metadata'}
META_KEYS = {'raw', 'provider_name', 'is_byok', 'limit_source', 'remedy_hint',
             'provider_error_code', 'retry_after_seconds',
             'retry_after_seconds_raw', 'headers'}
SENSITIVE_KEY = re.compile(r'(?i)^(?:user_?id|account_?id|api_?key|authorization|access_?token|refresh_?token|email|credential|secret)$')
TOKEN = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})\b|\bBearer\s+[A-Za-z0-9._~+/-]{24,}', re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':')) + '\n').encode()


def _safe(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe path')
    path = (root / p).resolve()
    path.relative_to(root.resolve())
    return path


def _scan(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY.fullmatch(key):
                raise ValueError(f'Unexpected sensitive field: {key}')
            _scan(child)
    elif isinstance(value, list):
        for child in value:
            _scan(child)
    elif isinstance(value, str) and TOKEN.search(value):
        raise ValueError('Credential-like text in public export')


def _sanitize_rows(source, expected_count):
    if not source.endswith(b'\n'):
        raise ValueError('Incomplete JSONL source')
    lines = source.splitlines()
    if not lines or any(not line for line in lines):
        raise ValueError('Empty JSONL row')
    output = []
    removals = 0
    for line in lines:
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError('JSONL row is not an object')
        cleaned = copy.deepcopy(row)
        raw = cleaned.get('raw_error_response')
        if raw is not None:
            if not isinstance(raw, dict) or set(raw) != {'error', 'user_id'}:
                raise ValueError('Unknown provider error shape')
            if not isinstance(raw['user_id'], str) or not raw['user_id']:
                raise ValueError('Invalid provider account identifier type')
            error = raw['error']
            if not isinstance(error, dict) or set(error) != ERROR_KEYS:
                raise ValueError('Unknown provider error fields')
            meta = error['metadata']
            if not isinstance(meta, dict) or not set(meta) <= META_KEYS:
                raise ValueError('Unknown provider metadata fields')
            if 'headers' in meta and (not isinstance(meta['headers'], dict) or
                                      not set(meta['headers']) <= {'Retry-After'}):
                raise ValueError('Unknown provider headers')
            account = raw.pop('user_id')
            removals += 1
            # The exact account value must occur only in the approved field.
            if account in json.dumps(cleaned, ensure_ascii=False):
                raise ValueError('Account identifier also occurs outside approved field')
        _scan(cleaned)
        if raw is not None:
            expected = copy.deepcopy(row)
            del expected['raw_error_response']['user_id']
            if expected != cleaned:
                raise ValueError('Non-account evidence changed')
        elif cleaned != row:
            raise ValueError('Unexpected evidence change')
        output.append(canonical(cleaned))
    if removals != expected_count:
        raise ValueError('Account identifier count drift')
    return b''.join(output), len(lines)


def _tracked_inventory(root):
    result = subprocess.run(['git', 'grep', '-l', '-F', '"user_id"', '--',
                             'results', 'public-evidence', 'public-site'],
                            cwd=root, text=True, capture_output=True, check=False)
    if result.returncode == 1:  # Git's ordinary no-match result after untracking.
        return set()
    if result.returncode != 0:
        raise RuntimeError('Tracked provider-account scan failed')
    return set(result.stdout.splitlines())


def build(root=ROOT, inventory=INVENTORY, enforce_tracked_set=True):
    root = Path(root).resolve()
    expected = {path for path, _, _ in inventory}
    if len(expected) != len(inventory):
        raise ValueError('Duplicate inventory path')
    # An eventual git rm --cached keeps private originals on the live host.
    # Their pinned bytes remain mandatory; only their tracked status may change.
    if enforce_tracked_set and not _tracked_inventory(root).issubset(expected):
        raise ValueError('Tracked provider-account inventory drift')
    outputs = {}
    entries = []
    for relative, original_sha, count in inventory:
        if not relative.startswith('results/') or not relative.endswith('.jsonl'):
            raise ValueError('Unexpected source path')
        original = _safe(root, relative).read_bytes()
        if digest(original) != original_sha:
            raise ValueError(f'Original source hash drift: {relative}')
        public, rows = _sanitize_rows(original, count)
        public_rel = str(PUBLIC_DIR / relative)
        outputs[public_rel] = public
        entries.append({'originalPath': relative, 'privateOriginalSha256': original_sha,
                        'publicPath': public_rel, 'publicSha256': digest(public),
                        'rowCount': rows, 'removedFieldPaths':
                        {'raw_error_response.user_id': count}})
    script_sha = digest(Path(__file__).read_bytes())
    manifest = {'schema': SCHEMA, 'policy': POLICY, 'policySha256': digest(POLICY.encode()),
                'exporterPath': 'scripts/export_provider_error_public_evidence.py',
                'exporterSha256': script_sha, 'sources': entries}
    outputs[str(PUBLIC_DIR / 'manifest.json')] = canonical(manifest)
    return outputs


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Existing public export differs: {path}')
        return
    tmp = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    try:
        with tmp.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def export(root=ROOT, inventory=INVENTORY, enforce_tracked_set=True, check=False):
    root = Path(root).resolve()
    outputs = build(root, inventory, enforce_tracked_set)
    if check:
        for rel, data in outputs.items():
            if _safe(root, rel).read_bytes() != data:
                raise ValueError(f'Public export mismatch: {rel}')
    else:
        # All source validation is complete before the first public write.
        for rel, data in outputs.items():
            _write_atomic(_safe(root, rel), data)
    return outputs


def verify_public(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads(_safe(root, PUBLIC_DIR / 'manifest.json').read_bytes())
    if (manifest.get('schema'), manifest.get('policy'), manifest.get('policySha256')) != (
            SCHEMA, POLICY, digest(POLICY.encode())):
        raise ValueError('Public export policy mismatch')
    if manifest.get('exporterSha256') != digest(Path(__file__).read_bytes()):
        raise ValueError('Exporter source binding mismatch')
    sources = manifest.get('sources')
    if not isinstance(sources, list) or len(sources) != len(INVENTORY):
        raise ValueError('Public source inventory mismatch')
    if [e.get('originalPath') for e in sources] != [p for p, _, _ in INVENTORY]:
        raise ValueError('Public original path inventory mismatch')
    expected_files = {str(PUBLIC_DIR / 'manifest.json')}
    expected_files.update(e.get('publicPath') for e in sources)
    actual_files = {str(p.relative_to(root)) for p in (root / PUBLIC_DIR).rglob('*')
                    if p.is_file()}
    if actual_files != expected_files:
        raise ValueError('Unexpected public export file set')
    for e, (_, original_sha, expected_count) in zip(sources, INVENTORY):
        if e.get('privateOriginalSha256') != original_sha:
            raise ValueError('Private hash attestation mismatch')
        if e.get('publicPath') != str(PUBLIC_DIR / e['originalPath']):
            raise ValueError('Public source path mismatch')
        if e.get('removedFieldPaths') != {'raw_error_response.user_id': expected_count}:
            raise ValueError('Redaction count mismatch')
        data = _safe(root, e['publicPath']).read_bytes()
        if digest(data) != e.get('publicSha256'):
            raise ValueError('Public source hash mismatch')
        if not data.endswith(b'\n'):
            raise ValueError('Incomplete public JSONL')
        rows = [json.loads(line) for line in data.splitlines()]
        if len(rows) != e.get('rowCount'):
            raise ValueError('Public row count mismatch')
        for row in rows:
            _scan(row)
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Compare export with private originals')
    mode.add_argument('--check-public', action='store_true', help='Verify public hashes without originals')
    args = p.parse_args()
    if args.check_public:
        verify_public()
    else:
        export(check=args.check)


if __name__ == '__main__':
    main()
