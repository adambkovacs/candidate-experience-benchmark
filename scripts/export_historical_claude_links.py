#!/usr/bin/env python3
"""Bind 14 historical public links to redacted, immutable evidence copies."""

import argparse
import json
import tempfile
from functools import lru_cache
from pathlib import Path

import export_claude_public_evidence as exporter

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/claude-subscription-2026-09-21')
BUNDLE = Path('public-evidence/claude-20260928/historical-links')
AUDIT = Path('docs/PRIVATE_EVIDENCE_REMOVAL_CANDIDATES_2026-09-28.json')
NAMES = (
    'fable51-high-development.jsonl',
    'fable51-low-development-session.jsonl',
    'fable51-max-development.jsonl',
    'fable51-medium-development.jsonl',
    'fable51-xhigh-development.jsonl',
    'haiku45-not_applicable-development-session.jsonl',
    'opus5-high-development-session.jsonl',
    'opus5-max-development.jsonl',
    'opus5-medium-development.jsonl',
    'opus5-xhigh-development.jsonl',
    'sonnet5-high-development-session.jsonl',
    'sonnet5-max-development.jsonl',
    'sonnet5-medium-development.jsonl',
    'sonnet5-xhigh-development.jsonl',
)
SOURCES = tuple(str(BASE / name) for name in NAMES)


def expected(root=ROOT):
    audit = json.loads((Path(root) / AUDIT).read_text())
    if audit.get('schema') != 'private-evidence-removal-preparation-v1':
        raise ValueError('Historical link audit schema changed')
    candidates = {entry['path']: entry for entry in audit['removal_candidates']}
    if any(path not in candidates or not candidates[path]['backup_verified'] for path in SOURCES):
        raise ValueError('Historical link lacks a verified private backup')
    return {path: candidates[path]['sha256'] for path in SOURCES}


def check(root=ROOT):
    root = Path(root)
    exporter.verify_public(root / BUNDLE, root)
    mapping = json.loads((root / BUNDLE / 'mapping.json').read_text())
    entries = {entry['originalPath']: entry for entry in mapping['entries']}
    if set(entries) != set(SOURCES):
        raise ValueError('Historical link source set changed')
    for source, digest in expected(root).items():
        item = entries[source]
        if item['privateOriginalSha256'] != digest or item['redacted'] is not True:
            raise ValueError('Historical link private binding or redaction changed')
        public = exporter.safe_path(root, item['publicPath'])
        rows = [json.loads(line) for line in public.read_bytes().splitlines()]
        if len(rows) != 60:
            raise ValueError('Historical link lost a development record')
    return entries


def build(root=ROOT):
    root = Path(root)
    bindings = expected(root)
    for relative, digest in bindings.items():
        source = root / relative
        if exporter.sha(source.read_bytes()) != digest:
            raise ValueError(f'Historical source hash changed: {relative}')
        original = [json.loads(line) for line in source.read_bytes().splitlines()]
        public = [json.loads(line) for line in exporter.redact_file(source).splitlines()]
        if len(original) != 60 or len(public) != 60 or any(
                exporter.redact(before) != after for before, after in zip(original, public)):
            raise ValueError(f'Historical source redaction changed a non-private field: {relative}')
    report = {'schema': 'historical-claude-public-links-v1', 'recordsPerSource': 60,
              'sourceBindings': [{'path': path, 'sha256': digest}
                                 for path, digest in sorted(bindings.items())]}
    with tempfile.TemporaryDirectory(prefix='historical-claude-links-') as temporary:
        input_path = Path(temporary) / 'report.json'
        input_path.write_bytes(exporter.canonical(report))
        exporter.export(input_path, root / BUNDLE, root)
    return check(root)


@lru_cache(maxsize=4)
def public_path_map(root=ROOT):
    return {source: entry['publicPath'] for source, entry in check(Path(root)).items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    entries = check() if args.check else build()
    print(f'Historical Claude public links verified: {len(entries)} sources')


if __name__ == '__main__':
    main()
