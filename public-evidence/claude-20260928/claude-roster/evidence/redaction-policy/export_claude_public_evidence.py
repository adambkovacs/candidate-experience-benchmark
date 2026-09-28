#!/usr/bin/env python3
"""Export a verified Claude report with private account diagnostics removed.

This creates a separate public view. Frozen private evidence and its SHA-256
bindings remain unchanged; a public bundle cannot authenticate those originals.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'claude-public-evidence-export-v1'
DROP = object()
PRIVATE_KEYS = {
    'access_token', 'refresh_token', 'api_key', 'apikey', 'authorization',
    'password', 'secret', 'credential', 'credentials', 'email', 'orgid',
    'orgname', 'accountid', 'account_id', 'organization_id', 'cwd',
    'rate_limit_info', 'rate_limit_events', 'unifiedwindows', 'utilization',
    'resetsat', 'reset_at', 'overagestatus', 'overagedisabledreason',
    'ratelimittype',
}
HOME = re.compile(r'/Users/[^/\s"\\]+')
BEARER = re.compile(r'(?i)\bBearer\s+(?!\[REDACTED\])[^\s"\\]+')
TOKEN = re.compile(r'\bsk-[A-Za-z0-9_-]{16,}\b')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Binding path escapes source root')
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def redact(value):
    if isinstance(value, dict):
        if value.get('type') == 'rate_limit_event':
            info = value.get('rate_limit_info', {})
            if not isinstance(info, dict) or not isinstance(info.get('isUsingOverage'), bool):
                raise ValueError('Rate-limit event lacks no-overage evidence')
            return {'type': 'rate_limit_event',
                    'rate_limit_info': {'isUsingOverage': info['isUsingOverage']}}
        result = {}
        for key, item in value.items():
            low = key.lower()
            if low in PRIVATE_KEYS or low.endswith('_token'):
                continue
            if key == 'stdout' and isinstance(item, str):
                try:
                    embedded = json.loads(item)
                except (ValueError, TypeError):
                    cleaned = redact(item)
                else:
                    cleaned = (json.dumps(redact(embedded), ensure_ascii=False,
                                          sort_keys=True, separators=(',', ':'))
                               if isinstance(embedded, (dict, list)) else redact(item))
            else:
                cleaned = redact(item)
            if cleaned is not DROP:
                result[key] = cleaned
        return result
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := redact(item)) is not DROP]
    if isinstance(value, str):
        return TOKEN.sub('[REDACTED_TOKEN]', BEARER.sub('Bearer [REDACTED]',
                         HOME.sub('[REDACTED_HOME]', value)))
    return value


def assert_redacted(value):
    if isinstance(value, dict):
        if value.get('type') == 'rate_limit_event':
            if (set(value) != {'type', 'rate_limit_info'} or
                    not isinstance(value['rate_limit_info'], dict) or
                    set(value['rate_limit_info']) != {'isUsingOverage'} or
                    not isinstance(value['rate_limit_info']['isUsingOverage'], bool)):
                raise ValueError('Private quota event remains')
            return
        for key, item in value.items():
            low = key.lower()
            if low in PRIVATE_KEYS or low.endswith('_token'):
                raise ValueError(f'Private field remains: {key}')
            if key == 'stdout' and isinstance(item, str):
                try:
                    embedded = json.loads(item)
                except (ValueError, TypeError):
                    assert_redacted(item)
                else:
                    assert_redacted(embedded)
            else:
                assert_redacted(item)
    elif isinstance(value, list):
        for item in value:
            assert_redacted(item)
    elif isinstance(value, str):
        if HOME.search(value) or TOKEN.search(value) or BEARER.search(value):
            raise ValueError('Private profile or token text remains')


def redact_file(path):
    original = path.read_bytes()
    if path.suffix == '.json':
        content = json.loads(original)
        cleaned = redact(content)
        assert_redacted(cleaned)
        return original if cleaned == content else canonical(cleaned)
    if path.suffix == '.jsonl':
        if not original.endswith(b'\n'):
            raise ValueError(f'Incomplete JSONL source: {path}')
        rows = [json.loads(line) for line in original.splitlines()]
        cleaned = [redact(row) for row in rows]
        if any(row is DROP for row in cleaned):
            cleaned = [row for row in cleaned if row is not DROP]
        assert_redacted(cleaned)
        return original if cleaned == rows else b''.join(canonical(row) for row in cleaned)
    # Code and other non-JSON source files are copied without byte changes.
    return original


def _source_groups(value):
    if isinstance(value, dict):
        if 'sourceBindings' in value:
            sources = value['sourceBindings']
            if not isinstance(sources, list):
                raise ValueError('Invalid sourceBindings list')
            yield sources
        for item in value.values():
            yield from _source_groups(item)
    elif isinstance(value, list):
        for item in value:
            yield from _source_groups(item)


def _binding_pairs(report):
    groups = list(_source_groups(report))
    if not groups:
        raise ValueError('Expected verified report with sourceBindings')
    pairs = {}
    for sources in groups:
        for item in sources:
            if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('sha256'), str):
                raise ValueError('Invalid source binding')
            path, digest = item['path'], item['sha256']
            if path in pairs and pairs[path] != digest:
                raise ValueError('Conflicting source bindings')
            pairs[path] = digest
    return pairs


def _rewrite_bindings(value, mapping):
    if isinstance(value, dict):
        result = {key: _rewrite_bindings(item, mapping) for key, item in value.items()}
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            pair = mapping.get(value['path'])
            if pair is None or pair['privateOriginalSha256'] != value['sha256']:
                raise ValueError('Report binding absent from verified source map')
            result['originalPath'] = value['path']
            result['privateOriginalSha256'] = value['sha256']
            result['path'] = pair['publicPath']
            result['sha256'] = pair['publicSha256']
        return result
    if isinstance(value, list):
        return [_rewrite_bindings(item, mapping) for item in value]
    return value


def _public_raw_fidelity(original, public):
    from claude_batch_benchmark import parse_batch_result
    before = [json.loads(line) for line in original.splitlines()]
    after = [json.loads(line) for line in public.splitlines()]
    if len(before) != len(after):
        raise ValueError('Raw capture count changed')
    fields = ('prediction', 'status', 'usage', 'model_usage', 'returned_models',
              'cli_duration_ms', 'cli_api_duration_ms',
              'cli_estimated_api_equivalent_usd', 'raw_response',
              'overage_observed')
    for old, new in zip(before, after):
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise ValueError('Invalid raw capture')
        members = old.get('record_ids')
        if new.get('record_ids') != members or new.get('exit_code') != old.get('exit_code'):
            raise ValueError('Raw request identity changed')
        try:
            old_body, new_body = json.loads(old['stdout']), json.loads(new['stdout'])
            old_result = parse_batch_result(old_body, old['exit_code'], members)
            new_result = parse_batch_result(new_body, new['exit_code'], members)
        except (ValueError, TypeError, KeyError):
            # Transport failures may have no parseable CLI body. The canonical
            # projection still proves every non-private field was retained.
            if new != redact(old):
                raise ValueError('Unparseable raw capture changed beyond redaction')
            continue
        if any(old_result.get(key) != new_result.get(key) for key in fields):
            raise ValueError('Raw prediction, usage, or timing changed')


def _attempt_fidelity(original, public):
    before = [json.loads(line) for line in original.splitlines()]
    after = [json.loads(line) for line in public.splitlines()]
    fields = ('prediction', 'status', 'usage', 'model_usage', 'returned_models',
              'cli_duration_ms', 'cli_api_duration_ms',
              'cli_estimated_api_equivalent_usd', 'actual_billed_usd',
              'overage_observed', 'request', 'requested_model', 'ids')
    if len(before) != len(after):
        raise ValueError('Attempt count changed')
    for old, new in zip(before, after):
        if any(old.get(key) != new.get(key) for key in fields):
            raise ValueError('Attempt prediction, usage, billing, or controls changed')


def export(private_report, output_dir, root=ROOT):
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_rel = output_dir.relative_to(root)
    if not output_rel.parts or output_rel.parts[0] == 'results':
        raise ValueError('Use a distinct public evidence directory')
    report = json.loads(Path(private_report).read_text())
    pairs = _binding_pairs(report)
    mapping = {}
    generated = {}
    for relative, expected in sorted(pairs.items()):
        source = safe_path(root, relative)
        original = source.read_bytes()
        if sha(original) != expected:
            raise ValueError(f'Private source binding changed: {relative}')
        public = redact_file(source)
        changed = public != original
        public_path = output_rel / 'evidence' / relative
        generated[str(public_path)] = public
        if '.raw.jsonl' in relative:
            _public_raw_fidelity(original, public)
        if '.attempts.jsonl' in relative:
            _attempt_fidelity(original, public)
        mapping[relative] = {'originalPath': relative,
                             'privateOriginalSha256': expected,
                             'publicPath': str(public_path),
                             'publicSha256': sha(public),
                             'redacted': changed}
    cleaned_report = redact(_rewrite_bindings(report, mapping))
    assert_redacted(cleaned_report)
    public_report = canonical(cleaned_report)
    policy_source = Path(__file__).read_bytes()
    policy_path = str(output_rel / 'evidence' / 'redaction-policy' / Path(__file__).name)
    generated[policy_path] = policy_source
    public_map = canonical({'schema': SCHEMA, 'publicReportSha256': sha(public_report),
                            'redactionPolicy': {'path': policy_path,
                                                'sha256': sha(policy_source)},
                            'entries': [mapping[key] for key in sorted(mapping)]})
    generated[str(output_rel / 'report.json')] = public_report
    generated[str(output_rel / 'mapping.json')] = public_map
    for relative, content in sorted(generated.items()):
        path = safe_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    verify_public(output_dir, root)
    return mapping


def _all_bindings(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        for item in value.values():
            yield from _all_bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_bindings(item)


def verify_public(output_dir, root=ROOT):
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.relative_to(root)
    mapping = json.loads((output_dir / 'mapping.json').read_text())
    if mapping.get('schema') != SCHEMA or not isinstance(mapping.get('entries'), list):
        raise ValueError('Invalid public mapping')
    policy = mapping.get('redactionPolicy')
    if not isinstance(policy, dict) or not isinstance(policy.get('path'), str):
        raise ValueError('Missing redaction policy binding')
    policy_path = safe_path(root, policy['path'])
    policy_path.relative_to(output_dir)
    if sha(policy_path.read_bytes()) != policy.get('sha256'):
        raise ValueError('Redaction policy hash changed')
    report_raw = (output_dir / 'report.json').read_bytes()
    if sha(report_raw) != mapping.get('publicReportSha256'):
        raise ValueError('Public report hash changed')
    report = json.loads(report_raw)
    assert_redacted(report)
    entries = {}
    for item in mapping['entries']:
        original, public = item['originalPath'], item['publicPath']
        if original in entries or not isinstance(item.get('privateOriginalSha256'), str):
            raise ValueError('Invalid public mapping entry')
        path = safe_path(root, public)
        raw = path.read_bytes()
        if sha(raw) != item['publicSha256']:
            raise ValueError('Public evidence hash changed')
        if path.suffix in ('.json', '.jsonl'):
            values = ([json.loads(line) for line in raw.splitlines()]
                      if path.suffix == '.jsonl' else json.loads(raw))
            assert_redacted(values)
        elif item['redacted']:
            raise ValueError('Unsupported redacted evidence type')
        entries[original] = item
    for item in _all_bindings(report):
        original = item.get('originalPath')
        mapped = entries.get(original)
        if mapped is None or (item.get('privateOriginalSha256'), item.get('path'), item.get('sha256')) != (
                mapped['privateOriginalSha256'], mapped['publicPath'], mapped['publicSha256']):
            raise ValueError('Public report binding differs from mapping')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-report', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true', help='Verify an existing public bundle')
    args = parser.parse_args()
    if args.check:
        verify_public(args.output_dir, args.source_root)
    else:
        if args.private_report is None:
            parser.error('--private-report is required for export')
        export(args.private_report, args.output_dir, args.source_root)
    print('Public Claude evidence verified')


if __name__ == '__main__':
    main()
