#!/usr/bin/env python3
"""Resolve audited private error evidence to verified public copies for reports.

The frozen original hash is an attestation. The bound SHA-256 is always the
actual sanitized file hash; no report claims to have rehashed a private source.
"""

from pathlib import Path

if __package__:
    from . import export_provider_error_public_evidence as exporter
else:
    import export_provider_error_public_evidence as exporter


def is_audited(relative):
    return str(relative) in {path for path, _, _ in exporter.INVENTORY}


def resolve(root, relative, expected_original_sha=None):
    root = Path(root).resolve()
    relative = str(relative)
    if not is_audited(relative):
        raise ValueError('Source is outside audited provider-error inventory')
    exporter.verify_public(root)
    manifest_path = root / exporter.PUBLIC_DIR / 'manifest.json'
    import json
    manifest = json.loads(manifest_path.read_bytes())
    matches = [item for item in manifest['sources'] if item['originalPath'] == relative]
    if len(matches) != 1:
        raise ValueError('Ambiguous public source mapping')
    item = matches[0]
    if expected_original_sha is not None and expected_original_sha != item['privateOriginalSha256']:
        raise ValueError('Frozen private-source hash differs from public attestation')
    public = exporter._safe(root, item['publicPath'])
    return public, {'path': item['publicPath'], 'sha256': item['publicSha256'],
                    'sourceKind': 'sanitized_public_copy',
                    'privateOriginalPath': relative,
                    'privateOriginalSha256Attestation': item['privateOriginalSha256'],
                    'privateOriginalVerification': 'not_rehashed_by_public_report'}
