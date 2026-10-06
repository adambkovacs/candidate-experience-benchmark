#!/usr/bin/env python3
"""Offline-only proposal for never-sent Jev P2 fresh2 DEV-019..060.

There is deliberately no dispatch action. DEV-018's HTTP 429 has unknown cost
and remains attempted. A new independent shared-spend authority is required
before a separately reviewed executable continuation may be written.
"""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as decision
import openrouter_jev_native_full_v1 as jev
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke_v2

SCHEMA = 'jev-openrouter-native-p2-fresh2-unsent-v1'
CONFIG = 'jev-openrouter-native-p2-choice-v1'
BASE = ROOT / 'results/route-audits/jev-p2-fresh2-unsent-v1-20261006'
PARENT = jev.BASE / CONFIG / 'fresh2'
IDS = [f'DEV-{i:03d}' for i in range(19, 61)]
UNKNOWN = 'DEV-018'
BOUND = decision.bound(decision.ROUTES['jev'])
TAIL_BOUND = 42 * BOUND
AUTHORITY_SNAPSHOT = {
    'path': str(smoke_v2.AUTHORITY.relative_to(ROOT)),
    'sha256': '4516e72a3fafd52da879655bb4923ff6ef8852532002cf7baefd2c55ed9c4423',
    'cap_usd': '10.00', 'held_usd': '9.948371024',
    'headroom_usd': '0.051628976', 'captured_as': 'read_only_2026-10-06_not_live_admission'}
PINNED = {
    'attempts.jsonl': '493249b0ae707095319d9a5b1992899cbdeb3c392e37cdfa957c4208a112970f',
    'terminal-public.json': '60d05a7bc8e3741bf9cd35158022112cadf878f4645412202c060ea61c663919',
    'budget-reconciliation.json': 'c238add53debbd15a64097f3e03a769cdc4237597feb2c1f596726b3ef7ffda1',
    'unknown-cost-evidence.jsonl': '69cf28952a255ee6305f8d1107f2c6cae7ff061e6a28cd8497a5514c685828e5',
    'review-receipt.json': '0c9583e1fb199ded4f7164c4e354f2a4ad4768d2360525e7b8ea39b00e6af38b',
    'child_ledger': 'f526dcdc6bcfdd876fd17cc37e0b5a403d5569c4cc8b79d6d0bb8e7f7cc0f58d',
}


def _rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Parent source lacks terminal newline')
    return [json.loads(x) for x in raw.splitlines() if x.strip()]


def inspect_parent(parent_dir=PARENT, *, root=ROOT):
    parent_dir = Path(parent_dir)
    manifest = jev.verify(CONFIG, root=root)
    original = frozen.build_plan(root)[CONFIG]
    if (manifest['request_set_sha256'] != original['requests_sha256'] or
            manifest['ids'] != full.IDS or manifest['request_sha256'] !=
            [x['payload_sha256'] for x in original['requests']] or
            manifest['condition'] != 'P2' or manifest['route'] != 'jev'):
        raise ValueError('Frozen parent P2 request identity differs')
    for name in PINNED:
        if name == 'child_ledger':
            continue
        if smoke_v2.file_sha(parent_dir / name) != PINNED[name]:
            raise ValueError('Immutable parent source changed: ' + name)
    if (parent_dir / 'completion.json').exists():
        raise ValueError('Interrupted parent unexpectedly has completion')
    receipt = json.loads((parent_dir / 'review-receipt.json').read_text())
    if (receipt.get('schema') != full.SCHEMA + '-root-review' or
            receipt.get('configuration_id') != CONFIG or receipt.get('stage') != 'fresh2' or
            receipt.get('manifest_sha256') != smoke_v2.file_sha(jev.paths(jev.BASE, CONFIG)['manifest']) or
            receipt.get('runner_sha256') != smoke_v2.file_sha(full.__file__) or
            receipt.get('execution_adapter_sha256') != smoke_v2.file_sha(jev.__file__) or
            receipt.get('ids') != full.IDS or receipt.get('request_sha256') != manifest['request_sha256'] or
            receipt.get('reference_labels_sent') is not False):
        raise ValueError('Parent review receipt does not bind frozen request/parser')
    terminal = json.loads((parent_dir / 'terminal-public.json').read_text())
    if terminal != {'schema': 'jev-native-full-interruption-v1',
                    'configuration_id': CONFIG, 'stage': 'fresh2',
                    'status': 'stopped_http_429', 'valid_count': 17,
                    'failed_ids': [UNKNOWN], 'never_sent_ids': IDS,
                    'known_actual_cost_usd': '0.001940694',
                    'unknown_charge_upper_bound_usd': str(BOUND),
                    'attempts_sha256': PINNED['attempts.jsonl'],
                    'reference_labels_read': False, 'replayed_failed_request': False}:
        raise ValueError('Interrupted parent terminal differs')
    rows = _rows(parent_dir / 'attempts.jsonl')
    if len(rows) != 71:
        raise ValueError('Parent attempts differ from 17 completed plus one uncertain')
    reconciliation = json.loads((parent_dir / 'budget-reconciliation.json').read_text())
    child_path = Path(reconciliation.get('child_ledger', ''))
    expected_child = parent_dir.parent / ('fresh2.budget-' + receipt['partition_id'] + '.jsonl')
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != receipt['partition_id'] or
            child_path.resolve() != expected_child.resolve() or
            reconciliation.get('child_sha256') != PINNED['child_ledger'] or
            smoke_v2.file_sha(child_path) != PINNED['child_ledger'] or
            reconciliation.get('known_actual_usd') != terminal['known_actual_cost_usd'] or
            reconciliation.get('unknown_upper_bound_usd') != str(BOUND) or
            Decimal(reconciliation.get('unused_allocation_released_usd', '-1')) !=
            Decimal(receipt['child_cap_usd']) - Decimal(terminal['known_actual_cost_usd']) - BOUND):
        raise ValueError('Parent child reconciliation differs')
    child = _rows(child_path)
    if (len(child) != 38 or child[0] != {'event': 'budget', 'cap_usd': receipt['child_cap_usd']} or
            child[-1] != {'event': 'partition_closed',
                           'reason': 'Explicit terminal reconciliation; no further requests permitted'}):
        raise ValueError('Parent child budget events differ')
    known = Decimal(0)
    route = decision.ROUTES['jev']
    for i in range(17):
        item = original['requests'][i]
        reserve, started, response, parsed = rows[4*i:4*i+4]
        child_reserve, child_settle = child[1+2*i:3+2*i]
        attempt = reserve.get('attempt_id')
        request = base64.b64decode(started.get('request_base64', ''), validate=True)
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        body = json.loads(raw)
        cost = decision.response_cost(body)
        if ([x.get('stage') for x in (reserve, started, response, parsed)] !=
                ['reserved', 'started', 'response', 'parsed'] or
                any(x.get('id') != item['id'] or x.get('attempt_id') != attempt
                    for x in (reserve, started, response, parsed)) or
                reserve.get('request_sha256') != item['payload_sha256'] or
                request != decision.canonical(item['payload']) or
                reserve.get('reserved_cost_usd') != str(BOUND) or
                response.get('http_status') != 200 or response.get('cost_unknown') is not False or
                smoke_v2.sha(raw) != response.get('raw_response_sha256') or
                body != response.get('body') or body.get('model') != route['version'] or
                body.get('provider') != route['provider'] or
                parsed.get('valid') is not True or
                decision.validate_response(body, route) != parsed.get('prediction') or
                cost is None or cost != Decimal(response.get('actual_cost_usd', '-1')) or
                cost > BOUND or
                child_reserve != {'event': 'reserve', 'attempt_id': attempt,
                                  'record_id': receipt['partition_id'] + ':' + item['id'],
                                  'usd': str(BOUND)} or
                child_settle != {'event': 'settle', 'attempt_id': attempt, 'usd': str(cost)}):
            raise ValueError('Parent valid prefix differs at ' + item['id'])
        known += cost
    if known != Decimal(terminal['known_actual_cost_usd']):
        raise ValueError('Parent prefix observed cost differs')
    item = original['requests'][17]
    reserve, started, response = rows[68:71]
    attempt = reserve.get('attempt_id')
    request = base64.b64decode(started.get('request_base64', ''), validate=True)
    raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
    unknown = _rows(parent_dir / 'unknown-cost-evidence.jsonl')
    if ([x.get('stage') for x in (reserve, started, response)] !=
            ['reserved', 'started', 'response'] or
            any(x.get('id') != UNKNOWN or x.get('attempt_id') != attempt
                for x in (reserve, started, response)) or
            item['id'] != UNKNOWN or reserve.get('request_sha256') != item['payload_sha256'] or
            request != decision.canonical(item['payload']) or
            response.get('http_status') != 429 or response.get('cost_unknown') is not True or
            response.get('actual_cost_usd') is not None or
            smoke_v2.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or
            json.loads(raw) != response.get('body') or unknown != [response] or
            child[35] != {'event': 'reserve', 'attempt_id': attempt,
                          'record_id': receipt['partition_id'] + ':' + UNKNOWN,
                          'usd': str(BOUND)} or
            child[36].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child[36].get('attempt_id') != attempt or child[36].get('usd') != str(BOUND) or
            child[36].get('actual_cost_usd') is not None or
            child[36].get('evidence_sha256') != PINNED['unknown-cost-evidence.jsonl'] or
            Path(child[36].get('evidence_path', '')).resolve() !=
            (parent_dir / 'unknown-cost-evidence.jsonl').resolve()):
        raise ValueError('Parent DEV-018 unknown-cost attempt differs')
    return {'manifest_sha256': smoke_v2.file_sha(jev.paths(jev.BASE, CONFIG)['manifest']),
            'parent_source_sha256': PINNED, 'parent_child_ledger_path': str(child_path),
            'known_actual_cost_usd': str(known), 'unknown_charge_upper_bound_usd': str(BOUND),
            'valid_prefix_ids': full.IDS[:17], 'unknown_attempted_id': UNKNOWN,
            'never_sent_ids': IDS}


def build_manifest(*, parent_dir=PARENT, root=ROOT):
    parent = inspect_parent(parent_dir, root=root)
    original = frozen.build_plan(root)[CONFIG]
    requests = original['requests'][18:]
    if [x['id'] for x in requests] != IDS or TAIL_BOUND != Decimal('0.056448000'):
        raise ValueError('Never-sent Jev suffix or full-context bound differs')
    proposal = {'schema': SCHEMA + '-offline-proposal', 'status': 'blocked_shared_authority',
        'dispatch_enabled': False, 'inference_performed': False, 'reference_labels_read': False,
        'configuration_id': CONFIG, 'parent_stage': 'fresh2',
        'continuation_id': CONFIG + '-fresh2-DEV019-060-continuation-v1',
        'parent_scope': {'valid_prefix_count': 17, 'attempted_unknown_id': UNKNOWN,
                         'never_sent_count': 42, 'clean_repeat_credit': False},
        'parent_evidence': parent,
        'original_request_set_sha256': original['requests_sha256'],
        'original_request_sha256': [x['payload_sha256'] for x in original['requests']],
        'parser_sha256': smoke_v2.file_sha(ROOT / 'scripts/openrouter_decision_smoke.py'),
        'choice_parser_sha256': smoke_v2.file_sha(ROOT / 'scripts/jev_benchmark.py'),
        'full_core_sha256': smoke_v2.file_sha(full.__file__),
        'jev_adapter_sha256': smoke_v2.file_sha(jev.__file__),
        'proposal_controller_sha256': smoke_v2.file_sha(__file__),
        'model': decision.ROUTES['jev']['model'], 'returned_model': decision.ROUTES['jev']['version'],
        'provider_tag': decision.ROUTES['jev']['tag'],
        'provider': decision.ROUTES['jev']['provider'], 'context_tokens': 32000,
        'ids': IDS, 'request_sha256': [x['payload_sha256'] for x in requests],
        'request_bytes': [len(decision.canonical(x['payload'])) for x in requests],
        'per_request_full_context_bound_usd': str(BOUND),
        'whole_suffix_full_context_bound_usd': str(TAIL_BOUND),
        'authority_snapshot': AUTHORITY_SNAPSHOT,
        'authority_shortfall_usd_at_snapshot': str(TAIL_BOUND - Decimal(AUTHORITY_SNAPSHOT['headroom_usd'])),
        'admission': {'independent_shared_authority_increase_required': True,
                      'fresh_live_authority_and_child_allocation_required': True,
                      'reviewed_receipt_and_new_execution_controller_required': True,
                      'no_DEV018_replay': True,
                      'parent_terminal_hash_must_match': True,
                      'parent_child_closed_and_reconciled': True}}
    return proposal


def prepare(base=BASE, *, parent_dir=PARENT, root=ROOT):
    value = build_manifest(parent_dir=parent_dir, root=root)
    path = Path(base) / 'proposal.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        handle.write(json.dumps(value, indent=2) + '\n')
    return smoke_v2.file_sha(path)


def verify(base=BASE, *, parent_dir=PARENT, root=ROOT):
    expected = build_manifest(parent_dir=parent_dir, root=root)
    path = Path(base) / 'proposal.json'
    if path.read_bytes() != (json.dumps(expected, indent=2) + '\n').encode():
        raise ValueError('Jev unsent suffix proposal differs from frozen source')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    else:
        print(json.dumps(verify()['admission'], indent=2))


if __name__ == '__main__':
    main()
