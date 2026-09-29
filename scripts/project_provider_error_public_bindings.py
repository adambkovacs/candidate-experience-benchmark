#!/usr/bin/env python3
"""Project saved public explorer links onto verified provider-error public copies.

This does not rebuild scores or replace frozen source hashes. It works from
already-published data.json and the sanitized public export only.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

if __package__:
    from .export_provider_error_public_evidence import PUBLIC_DIR, ROOT, verify_public
else:
    from export_provider_error_public_evidence import PUBLIC_DIR, ROOT, verify_public

SCHEMA = 'provider-error-public-binding-projection-v1'
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
SOURCE = Path('public-site/data.json')
OUTPUT = Path('public-site/data-provider-errors-v1.json')
MANIFEST = Path('public-site/provider-error-projection-v1.manifest.json')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def _pairs(manifest):
    if manifest.get('schema') != 'provider-error-public-evidence-v1':
        raise ValueError('Wrong provider-error export schema')
    result = {}
    for item in manifest['sources']:
        old = item['originalPath']
        if old in result:
            raise ValueError('Duplicate private path mapping')
        result[old] = {key: item[key] for key in
                       ('originalPath', 'privateOriginalSha256',
                        'publicPath', 'publicSha256')}
    return result


def project_data(data, manifest, source_sha):
    """Rewrite only exact evidence URLs, retaining a separate hash attestation."""
    pairs = _pairs(manifest)
    seen = set()

    def visit(value):
        if isinstance(value, dict):
            return {key: visit(child) for key, child in value.items()}
        if isinstance(value, list):
            return [visit(child) for child in value]
        if isinstance(value, str):
            for old, pair in pairs.items():
                if old not in value:
                    continue
                if value != GITHUB + old:
                    raise ValueError('Unsupported private evidence path context')
                seen.add(old)
                return GITHUB + pair['publicPath']
        return value

    if not isinstance(data, dict) or 'publicEvidenceProjection' in data:
        raise ValueError('Expected unprojected public explorer data')
    result = visit(data)
    if not seen:
        raise ValueError('No affected public evidence URLs found')
    result['publicEvidenceProjection'] = {
        'schema': SCHEMA, 'sourceDataPath': str(SOURCE),
        'sourceDataSha256': source_sha,
        'mapping': [pairs[p] for p in sorted(seen)],
        'privacyLimit': 'Private originals are attested by hash; the public copies and their hashes are independently verifiable.',
    }
    return result


def build(root=ROOT):
    root = Path(root).resolve()
    verify_public(root)
    original = (root / SOURCE).read_bytes()
    map_raw = (root / PUBLIC_DIR / 'manifest.json').read_bytes()
    mapped = project_data(json.loads(original), json.loads(map_raw), sha(original))
    output = canonical(mapped)
    summary = {'schema': SCHEMA, 'sourceDataPath': str(SOURCE),
               'sourceDataSha256': sha(original),
               'providerErrorManifestPath': str(PUBLIC_DIR / 'manifest.json'),
               'providerErrorManifestSha256': sha(map_raw),
               'projectionPath': str(OUTPUT), 'projectionSha256': sha(output),
               'projectorPath': 'scripts/project_provider_error_public_bindings.py',
               'projectorSha256': sha(Path(__file__).read_bytes()),
               'mappedSourceCount': len(mapped['publicEvidenceProjection']['mapping'])}
    return output, canonical(summary)


def run(root=ROOT, check=False):
    root = Path(root).resolve()
    output, summary = build(root)
    for relative, expected in ((OUTPUT, output), (MANIFEST, summary)):
        path = root / relative
        if check:
            if not path.exists() or path.read_bytes() != expected:
                raise ValueError(f'Stale public provider-error projection: {relative}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    return output, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args()
    run(args.root, check=args.check)


if __name__ == '__main__':
    main()
