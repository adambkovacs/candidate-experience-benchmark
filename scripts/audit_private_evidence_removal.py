#!/usr/bin/env python3
"""Prepare an exact, read-only inventory of tracked private evidence."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'private-evidence-removal-preparation-v1'
QUOTA_KEYS = {
    'rate_limit_events', 'unifiedwindows', 'utilization', 'resetsat',
    'reset_at', 'ratelimittype', 'overagestatus', 'overagedisabledreason',
}
ACCOUNT_KEYS = {
    'accountid', 'account_id', 'organization_id', 'orgid', 'orgname',
    'access_token', 'refresh_token', 'api_key', 'apikey',
    'password', 'secret', 'credential', 'credentials',
}
HOME = re.compile(r'/Users/[^/\s"\\]+')
TOKEN = re.compile(r'\bsk-[A-Za-z0-9_-]{16,}\b|\bBearer\s+(?!\[REDACTED\])[^\s"\\]+', re.I)
SUSPECT = re.compile('|'.join(re.escape(k) for k in sorted(QUOTA_KEYS | ACCOUNT_KEYS | {'rate_limit_info'})), re.I)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative_path(value):
    path = Path(value)
    if not value or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('Backup contains an unsafe relative path')
    return path


def tracked_results(root):
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--', 'results'], cwd=root)
    return sorted(Path(item.decode('utf-8')) for item in raw.split(b'\0') if item)


def inspect_value(value, reasons):
    if isinstance(value, dict):
        if value.get('type') == 'rate_limit_event':
            info = value.get('rate_limit_info')
            if info != {'isUsingOverage': False} and info != {'isUsingOverage': True}:
                reasons.add('quota_metadata')
        for key, item in value.items():
            low = key.lower()
            if low in QUOTA_KEYS or (low == 'rate_limit_info' and
                                     item not in ({'isUsingOverage': False}, {'isUsingOverage': True})):
                reasons.add('quota_metadata')
            if low in ACCOUNT_KEYS:
                reasons.add('account_or_credential_field')
            if key == 'stdout' and isinstance(item, str):
                try:
                    embedded = json.loads(item)
                except (TypeError, ValueError):
                    if SUSPECT.search(item):
                        reasons.add('unparsed_stdout_suspect')
                else:
                    inspect_value(embedded, reasons)
            inspect_value(item, reasons)
    elif isinstance(value, list):
        for item in value:
            inspect_value(item, reasons)
    elif isinstance(value, str):
        if HOME.search(value):
            reasons.add('private_home_path')
        if TOKEN.search(value):
            reasons.add('credential_text_pattern')


def inspect_file(path):
    reasons = set()
    if path.suffix not in ('.json', '.jsonl'):
        return reasons
    with path.open(encoding='utf-8') as source:
        if path.suffix == '.json':
            try:
                inspect_value(json.load(source), reasons)
            except (ValueError, UnicodeError):
                reasons.add('unparsed_json')
        else:
            for line in source:
                if not line.strip():
                    continue
                try:
                    inspect_value(json.loads(line), reasons)
                except (ValueError, UnicodeError):
                    reasons.add('unparsed_jsonl')
                    if SUSPECT.search(line) or HOME.search(line) or TOKEN.search(line):
                        reasons.add('unparsed_sensitive_text')
    return reasons


def inventory(root, backup_dir):
    root, backup_dir = Path(root).resolve(), Path(backup_dir).resolve()
    manifest_path = backup_dir / 'backup-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('schema') != 'private-original-evidence-backup-v1' or
            manifest.get('originals_changed') is not False or
            manifest.get('skipped_changed_since_inventory') != [] or
            not isinstance(manifest.get('entries'), list)):
        raise ValueError('Private backup manifest is not a verified complete snapshot')
    backup = {}
    for item in manifest['entries']:
        path = relative_path(item['path'])
        if str(path) in backup or not str(path).startswith('results/'):
            raise ValueError('Duplicate or non-results private backup path')
        if (not isinstance(item.get('sha256'), str) or len(item['sha256']) != 64 or
                not isinstance(item.get('bytes'), int)):
            raise ValueError('Invalid private backup binding')
        backup[str(path)] = item

    sensitive = []
    unverified = []
    backup_gaps = []
    reason_counts = Counter()
    for relative in tracked_results(root):
        path = root / relative
        if not path.is_file() or relative.suffix not in ('.json', '.jsonl'):
            continue
        reasons = inspect_file(path)
        if not reasons:
            continue
        actual_hash = sha(path)
        expected = backup.get(str(relative))
        verified = bool(expected and expected['sha256'] == actual_hash and
                        expected['bytes'] == path.stat().st_size and
                        (backup_dir / relative).is_file() and
                        sha(backup_dir / relative) == actual_hash)
        row = {'path': str(relative), 'sha256': actual_hash, 'bytes': path.stat().st_size,
               'reasons': sorted(reasons), 'backup_verified': verified}
        sensitive.append(row)
        reason_counts.update(reasons)
        if not verified:
            row['backup_gap'] = ('absent_from_backup' if expected is None else
                                 'original_or_backup_hash_mismatch')
            unverified.append(row)
    sensitive_paths = {item['path'] for item in sensitive}
    backup_not_sensitive = sorted(set(backup) - sensitive_paths)
    backup_gaps.extend(backup_not_sensitive)
    quota_files = [item for item in sensitive if 'quota_metadata' in item['reasons']]
    for item in quota_files:
        if not item['backup_verified'] or any(reason.startswith('unparsed_') for reason in item['reasons']):
            backup_gaps.append(item['path'])
    candidates = [item for item in quota_files if item['backup_verified'] and
                  not any(reason.startswith('unparsed_') for reason in item['reasons'])]
    supplementary_backed = [item for item in sensitive if item['backup_verified'] and
                            item['path'] not in {row['path'] for row in quota_files}]
    return {'schema': SCHEMA, 'status': 'review_candidates_only_no_removal_authorized',
            'backup_manifest_sha256': sha(manifest_path),
            'counts': {'tracked_privacy_leads': len(sensitive),
                       'quota_bearing_tracked': len(quota_files),
                       'verified_removal_candidates': len(candidates),
                       'supplementary_backed_provenance': len(supplementary_backed),
                       'unbacked_review_leads': len(unverified),
                       'backup_manifest_entries': len(backup),
                       'backup_entries_not_detected_sensitive': len(backup_not_sensitive),
                       'reasons': dict(sorted(reason_counts.items()))},
            'removal_candidates': candidates,
            'supplementary_backed_provenance': supplementary_backed,
            'unverified_findings': unverified,
            'backup_gaps': sorted(set(backup_gaps)),
            'backup_entries_not_detected_sensitive': backup_not_sensitive}


PROBES = {
    'claude_roster_report': ['scripts/build_claude_roster_findings.py', '--output',
                             'public-site/claude-roster-repeats.json', '--check'],
    'claude_opus_medium_report': ['scripts/build_claude_repeat_findings.py', '--output',
                                  'public-site/claude-repeats.json', '--check'],
    'haiku_matched3_report': ['scripts/build_haiku_matched3_findings.py', '--output',
                              'public-site/haiku-fresh-matched3.json', '--check'],
    'claude_roster_tests': ['-m', 'unittest', 'tests.test_build_claude_roster_findings', '-q'],
    'claude_opus_medium_tests': ['-m', 'unittest', 'tests.test_build_claude_repeat_findings', '-q'],
    'haiku_matched3_tests': ['-m', 'unittest', 'tests.test_build_haiku_matched3_findings', '-q'],
    'public_roster_bundle': ['scripts/export_claude_public_evidence.py', '--output-dir',
                              'public-evidence/claude-20260928/claude-roster', '--check'],
    'public_haiku_bundle': ['scripts/export_claude_public_evidence.py', '--output-dir',
                            'public-evidence/claude-20260928/haiku', '--check'],
    'public_opus_medium_bundle': ['scripts/export_claude_public_evidence.py', '--output-dir',
                                  'public-evidence/claude-20260928/opus-medium', '--check'],
}


def dependency_audit(root, candidate_paths):
    """Mask original reads in read-only checks; this does not alter the checkout."""
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix='private-evidence-dependency-') as directory:
        temporary = Path(directory)
        (temporary / 'blocked.json').write_text(json.dumps([str(root / p) for p in candidate_paths]))
        sitecustomize = '\n'.join([
            'import builtins,json,os',
            'from pathlib import Path',
            "blocked=set(json.loads(Path(os.environ['BLOCKED_EVIDENCE_PATHS']).read_text()))",
            'old_path_open=Path.open',
            'old_open=builtins.open',
            'def check(path):',
            '    if str(Path(path).absolute()) in blocked:',
            "        raise FileNotFoundError('MASKED_PRIVATE_ORIGINAL: '+str(Path(path).absolute()))",
            'def path_open(self,*args,**kwargs):',
            '    check(self)',
            '    return old_path_open(self,*args,**kwargs)',
            'def builtin_open(file,*args,**kwargs):',
            '    if isinstance(file,(str,bytes,os.PathLike)):check(file)',
            '    return old_open(file,*args,**kwargs)',
            'Path.open=path_open',
            'builtins.open=builtin_open',
            '',
        ])
        (temporary / 'sitecustomize.py').write_text(sitecustomize)
        env = os.environ.copy()
        env['BLOCKED_EVIDENCE_PATHS'] = str(temporary / 'blocked.json')
        env['PYTHONPATH'] = str(temporary) + os.pathsep + str(root / 'scripts') + os.pathsep + str(root)
        findings = {}
        for name, args in PROBES.items():
            try:
                completed = subprocess.run([sys.executable, *args], cwd=root, env=env,
                                           capture_output=True, text=True, timeout=120)
            except subprocess.TimeoutExpired:
                findings[name] = {'status': 'timeout', 'original_required': None}
                continue
            output = completed.stdout + completed.stderr
            matched = re.search(r'^FileNotFoundError: MASKED_PRIVATE_ORIGINAL: (/.+)$',
                                output, re.M)
            findings[name] = {'status': 'blocked_on_private_original' if matched else
                              'passed_without_private_original' if completed.returncode == 0 else
                              'failed_for_other_reason',
                              'original_required': str(Path(matched.group(1)).relative_to(root)) if matched else None,
                              'exit_code': completed.returncode}
        return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dependency-audit', action='store_true')
    args = parser.parse_args(argv)
    report = inventory(args.source_root, args.backup_dir)
    if args.dependency_audit:
        report['clean_checkout_dependency_probe'] = dependency_audit(
            args.source_root, [item['path'] for item in report['removal_candidates']])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'counts': report['counts'], 'backup_gaps': len(report['backup_gaps']),
                      'dependency_probe': report.get('clean_checkout_dependency_probe')}))
    if report['backup_gaps']:
        raise SystemExit('Sensitive files or backup entries need manual reconciliation before removal')


if __name__ == '__main__':
    main()
