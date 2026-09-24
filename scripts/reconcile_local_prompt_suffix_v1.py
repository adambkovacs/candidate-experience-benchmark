#!/usr/bin/env python3
"""Offline reconciliation of the interrupted Qwen3.5 4B P2 local prompt run."""

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from development_benchmark import KEYS, read_rows, score, valid

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path('results/local-prompt-suffix-v1/manifest.json')
SUFFIX = Path('results/local-prompt-suffix-v1/development-suffix.jsonl')
DEST = Path('results/local-prompt-suffix-v1/reconciliation.json')
IDS = [f'DEV-{number:03d}' for number in range(1, 61)]
CONFIGURATION = 'qwen3.5-4b-sdk-thinking-on'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, relative, expected=None):
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Unsafe evidence path')
    path = root / relative
    actual = digest(path)
    if expected is not None and actual != expected:
        raise ValueError(f'Evidence hash differs: {relative}')
    return path, {'file': relative, 'sha256': actual}


def jsonl(path):
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError(f'Incomplete JSONL line: {path}')
    lines = [line for line in raw.splitlines() if line.strip()]
    return [json.loads(line) for line in lines], [hashlib.sha256(line).hexdigest() for line in lines]


def checked_rows(rows, events, line_hashes, expected_ids, manifest_hash, controller_hash,
                 configuration, variant, phase, pending=None):
    if [row.get('id') for row in rows] != expected_ids:
        raise ValueError('Saved row IDs differ from canonical prefix')
    if len(events) != 2 * len(rows) + (1 if pending else 0):
        raise ValueError('Journal event count differs from saved attempts')
    for index, row in enumerate(rows):
        started, finished = events[2 * index:2 * index + 2]
        decision = row.get('decision') or {}
        status = decision.get('status')
        if (row.get('configuration'), row.get('variant'), row.get('phase')) != (configuration, variant, phase):
            raise ValueError('Saved row belongs to another configuration')
        if row.get('manifest_sha256') != manifest_hash or row.get('controller_sha256') != controller_hash:
            raise ValueError('Saved row control binding differs')
        if row.get('reference_labels_read') is not False:
            raise ValueError('Reference labels were read during inference')
        if status not in ('ok', 'invalid_output', 'control_failure', 'service_failure', 'timeout'):
            raise ValueError('Unknown saved outcome')
        if status == 'ok' and not valid(decision.get('prediction')):
            raise ValueError('Invalid prediction marked ok')
        if (started.get('event'), finished.get('event')) != ('started', 'finished') or any(
            event.get('id') != row['id'] or event.get('attempt_id') != row.get('attempt_id')
            for event in (started, finished)
        ):
            raise ValueError('Attempt journal does not match saved row')
        if (started.get('request_sha256') != row.get('request_sha256') or
            started.get('manifest_sha256') != manifest_hash or
            (phase == 'development_suffix' and started.get('controller_sha256') != controller_hash) or
            finished.get('status') != status or finished.get('output_sha256') != line_hashes[index]):
            raise ValueError('Attempt journal hash or status differs')
    if pending:
        event = events[-1]
        if (event.get('event'), event.get('id'), event.get('attempt_id'),
            event.get('request_sha256')) != pending:
            raise ValueError('Unfinished original attempt differs')


def reconcile(root=ROOT):
    root = Path(root).resolve()
    manifest_path, manifest_source = source(root, str(MANIFEST))
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('version'), manifest.get('configuration'), manifest.get('variant'),
        manifest.get('phase'), manifest.get('canonical_denominator'), manifest.get('allowed_ids'),
        manifest.get('ambiguous_parent_id')) != (
            'local-prompt-suffix-v1', CONFIGURATION, 'P2', 'development_suffix', 60, IDS[19:], IDS[18]):
        raise ValueError('Unsupported suffix manifest')
    binding = manifest['binding']
    bound = {}
    for key in ('parent_manifest', 'parent_preflight', 'parent_controller', 'parent_review',
                'interruption_audit', 'original_output', 'original_journal', 'original_smoke_inspection'):
        path, bound[key] = source(root, binding[key], binding[key + '_sha256'])
    controller_path, bound['suffix_controller'] = source(root, 'scripts/local_prompt_suffix_v1.cjs',
                                                         manifest['controller_sha256'])
    del controller_path
    audit = json.loads((root / binding['interruption_audit']).read_text())
    if (audit.get('unfinished', {}).get('id') != IDS[18] or
        audit['unfinished'].get('retry_authorized') is not False or
        audit['saved'].get('count') != 18 or audit['saved'].get('status_counts') !=
            {'ok': 14, 'invalid_output': 4} or
        audit['evidence'].get('development_output_sha256') != bound['original_output']['sha256'] or
        audit['evidence'].get('development_journal_sha256') != bound['original_journal']['sha256'] or
        audit['evidence'].get('development_terminal_exists') is not False or
        (root / binding['original_terminal']).exists()):
        raise ValueError('Original interruption audit differs')
    original, original_hashes = jsonl(root / binding['original_output'])
    original_events, _ = jsonl(root / binding['original_journal'])
    unfinished = audit['unfinished']
    checked_rows(original, original_events, original_hashes, IDS[:18],
                 binding['parent_manifest_sha256'], binding['parent_controller_sha256'],
                 CONFIGURATION, 'P2', 'development',
                 ('started', IDS[18], unfinished['attempt_id'], unfinished['request_sha256']))
    if Counter(row['decision']['status'] for row in original) != {'ok': 14, 'invalid_output': 4}:
        raise ValueError('Original saved outcomes differ')
    for row in original:
        if row.get('preflight_sha256') != binding['parent_preflight_sha256']:
            raise ValueError('Original preflight binding differs')

    output_path, bound['suffix_output'] = source(root, str(SUFFIX))
    journal_path, bound['suffix_journal'] = source(root, str(SUFFIX.with_name('development-suffix.attempts.jsonl')))
    terminal_path, bound['suffix_terminal'] = source(root, str(SUFFIX.with_name('development-suffix.terminal.json')))
    terminal = json.loads(terminal_path.read_text())
    suffix, suffix_hashes = jsonl(output_path)
    events, _ = jsonl(journal_path)
    suffix_ids = [row.get('id') for row in suffix]
    if not suffix or suffix_ids != IDS[19:19 + len(suffix)] or len(suffix) > 41:
        raise ValueError('Suffix rows are not a canonical DEV-020–060 prefix')
    checked_rows(suffix, events, suffix_hashes, suffix_ids, manifest_source['sha256'],
                 manifest['controller_sha256'], CONFIGURATION, 'P2', 'development_suffix')
    for row in suffix:
        if (row.get('parent_manifest_sha256') != binding['parent_manifest_sha256'] or
            row.get('interruption_audit_sha256') != binding['interruption_audit_sha256']):
            raise ValueError('Suffix parent binding differs')
    if not isinstance(terminal.get('runtime_attestation'), dict) or any(
        row.get('runtime_attestation') != terminal['runtime_attestation'] for row in suffix
    ):
        raise ValueError('Suffix runtime attestation differs from terminal')
    statuses = Counter(row['decision']['status'] for row in suffix)
    completed = terminal.get('status') == 'completed'
    if (terminal.get('status') not in ('completed', 'stopped') or
        terminal.get('configuration') != CONFIGURATION or terminal.get('variant') != 'P2' or
        terminal.get('phase') != 'development_suffix' or
        terminal.get('manifest_sha256') != manifest_source['sha256'] or
        terminal.get('controller_sha256') != manifest['controller_sha256'] or
        terminal.get('output_sha256') != bound['suffix_output']['sha256'] or
        terminal.get('journal_sha256') != bound['suffix_journal']['sha256'] or
        terminal.get('canonical_denominator') != 60 or terminal.get('parent_saved_rows') != 18 or
        terminal.get('ambiguous_original_id') != IDS[18] or terminal.get('requested_suffix_records') != 41 or
        terminal.get('claimed_attempts') != len(suffix) or
        terminal.get('finished_attempts') != len(suffix) or terminal.get('saved_rows') != len(suffix) or
        terminal.get('ok_rows') != statuses['ok'] or
        terminal.get('invalid_output_rows') != statuses['invalid_output'] or
        terminal.get('ambiguous_timeout') is not False):
        raise ValueError('Suffix terminal disagrees with saved evidence or has active ambiguity')
    if completed:
        if (len(suffix) != 41 or terminal.get('stopped_reason') is not None or
            statuses['control_failure'] or statuses['service_failure'] or statuses['timeout']):
            raise ValueError('Completed terminal contains a stopping failure')
    elif (suffix[-1]['decision']['status'] not in ('control_failure', 'service_failure', 'timeout') or
          not terminal.get('stopped_reason')):
        raise ValueError('Partial suffix lacks its terminal failure')
    if statuses['timeout'] and suffix[-1]['decision'].get('cancellation_acknowledged') is not True:
        raise ValueError('Unacknowledged timeout remains unsafe')

    review_path, bound['execution_review'] = source(root, 'results/local-prompt-suffix-v1/execution-review-root.json')
    review = json.loads(review_path.read_text())
    release_path, bound['lock_release'] = source(root, 'results/local-prompt-suffix-v1/lock-release-root.json',
                                                review.get('lock_release_receipt_sha256'))
    release = json.loads(release_path.read_text())
    if (review.get('approved_for_execution') is not True or
        review.get('manifest_sha256') != manifest_source['sha256'] or
        review.get('controller_sha256') != manifest['controller_sha256'] or
        review.get('interruption_audit_sha256') != bound['interruption_audit']['sha256'] or
        review.get('allowed_ids') != IDS[19:] or
        release.get('interruption_audit_sha256') != bound['interruption_audit']['sha256'] or
        release.get('original_lock_sha256') != binding['stale_lock_sha256'] or
        release.get('pid_absent_verified') is not True or release.get('lock_removed') is not True):
        raise ValueError('Execution review or lock release differs')

    refs_path, bound['provisional_references'] = source(root, 'data/pilot/proposed_labels.jsonl')
    pairs_path, bound['pairs'] = source(root, 'data/pilot/pairs.json')
    _, bound['scorer'] = source(root, 'scripts/development_benchmark.py')
    refs = read_rows(refs_path)
    if [row['id'] for row in refs] != IDS:
        raise ValueError('Reference denominator differs from canonical 60')
    attempts = original + suffix
    predictions = [{'id': row['id'], 'status': row['decision']['status'],
                    **({'prediction': row['decision']['prediction']} if row['decision']['status'] == 'ok' else {})}
                   for row in attempts]
    evaluation = score(refs, predictions, json.loads(pairs_path.read_text()))
    truth = {row['id']: row['proposed_labels'] for row in refs}
    all_four = sum(row['decision']['status'] == 'ok' and row['decision']['prediction'] == truth[row['id']]
                   for row in attempts)
    elapsed = [row.get('elapsed_seconds') for row in attempts]
    elapsed_valid = [value for value in elapsed if isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and value >= 0]
    usage_missing = []
    prompt_tokens = completion_tokens = 0
    for row in attempts:
        stats = row.get('stats') or {}
        p, c = stats.get('promptTokensCount'), stats.get('predictedTokensCount')
        if type(p) is int and type(c) is int and p >= 0 and c >= 0:
            prompt_tokens += p
            completion_tokens += c
        else:
            usage_missing.append(row['id'])
    never_sent = IDS[19 + len(suffix):]
    return {
        'version': 'local-prompt-suffix-reconciliation-v1',
        'configuration': CONFIGURATION, 'variant': 'P2', 'phase': 'development',
        'denominator': 60, 'saved_rows': len(attempts), 'claimed_attempts': len(attempts) + 1,
        'ambiguous_outcome_ids': [IDS[18]], 'never_sent_ids': never_sent,
        'never_sent_count': len(never_sent), 'coverage_complete': False,
        'status_counts': dict(Counter(row['decision']['status'] for row in attempts)),
        'valid_outputs': evaluation['valid_outputs'], 'all_four_correct': all_four,
        'field_accuracy': {key: evaluation['metrics'][key]['accuracy'] for key in KEYS},
        'evaluation': evaluation, 'reference_status': 'AI-reviewed provisional; development only',
        'resource': {'surface': 'lmstudio_sdk', 'cost_usd': None,
                     'cost_note': 'Local execution; API billing not applicable. Device electricity and amortization unmeasured.',
                     'timing_scope': 'local diagnostic; interrupted original and suffix are not a complete paired timing run',
                     'elapsed_prediction_seconds_available': len(elapsed_valid),
                     'elapsed_prediction_seconds_sum': sum(elapsed_valid),
                     'elapsed_prediction_seconds_median': statistics.median(elapsed_valid) if elapsed_valid else None,
                     'prompt_tokens_observed_sum': prompt_tokens,
                     'completion_tokens_observed_sum': completion_tokens,
                     'usage_missing_record_ids': usage_missing,
                     'cache_tokens_observed': None},
        'terminal': {'status': terminal['status'], 'saved_rows': terminal['saved_rows'],
                     'stopped_reason': terminal.get('stopped_reason')},
        'sources': {'manifest': manifest_source, **bound},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=DEST,
                        help='Relative output path; written exclusively after terminal validation')
    args = parser.parse_args()
    report = reconcile(args.root)
    root = args.root.resolve()
    target = root / args.output
    if target.resolve() != root and root not in target.resolve().parents:
        raise ValueError('Output must be inside repository')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(target)


if __name__ == '__main__':
    main()
