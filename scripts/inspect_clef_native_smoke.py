#!/usr/bin/env python3
"""Verify six saved Clef app smokes and write one immutable source-bound receipt."""

import base64
from decimal import Decimal
import json
import math
from pathlib import Path

import clef_native_preparation as prep
import clef_native_smoke_runner as smoke
import clef_connected_app_bridge as bridge

BASE = prep.ROOT / smoke.BASE
OUTPUT = BASE / 'smoke-inspection-v1.json'


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError(f'Incomplete JSONL: {path}')
    return [json.loads(line) for line in raw.splitlines()]


def inspect(base=BASE):
    base = Path(base)
    plan_path = base / 'preparation.json'
    grant_path = base / 'initial-smoke-grant.json'
    ledger_path = base / 'budget.jsonl'
    plan = json.loads(plan_path.read_bytes())
    if plan != prep.build_plan():
        raise ValueError('Current frozen input-only plan differs')
    plan_hash = prep.sha(prep.canonical(plan))
    grant = json.loads(grant_path.read_bytes())
    grant_hash = prep.sha(grant_path.read_bytes())
    if (grant.get('kind') != 'clef-native-initial-smoke-grant-v1' or
            grant.get('approved') is not True or grant.get('authorized_by_user') is not True or
            grant.get('plan_sha256') != plan_hash or
            grant.get('runner_sha256') != prep.sha(Path(smoke.__file__).read_bytes()) or
            grant.get('cap_usd') != '0.10'):
        raise ValueError('Smoke grant provenance differs')
    ledger = rows(ledger_path)
    if len(ledger) != 7 or ledger[0] != {'event': 'budget', 'cap_usd': '0.10',
                                         'grant_sha256': grant_hash,
                                         'plan_sha256': plan_hash}:
        raise ValueError('Expected exact six-reservation smoke ledger')
    source_hashes = {str(path.relative_to(base)): prep.sha(path.read_bytes())
                     for path in (plan_path, grant_path, ledger_path)}
    aggregate = Decimal(0)
    models = {}
    seen_attempts = set()
    for model in prep.MODELS:
        directory = base / model / 'fresh1/P0/smoke'
        review_path = base / f'{model}-app-review.json'
        review = json.loads(review_path.read_bytes())
        if (review.get('kind') != bridge.REVIEW_KIND or review.get('approved') is not True or
                review.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
                review.get('model') != model or review.get('stage') != smoke.STAGE or
                review.get('manifest_sha256') != prep.sha(plan_path.read_bytes()) or
                review.get('grant_sha256') != grant_hash or
                review.get('runner_sha256') != prep.sha(Path(smoke.__file__).read_bytes()) or
                review.get('bridge_sha256') != prep.sha(Path(bridge.__file__).read_bytes()) or
                review.get('account_id_sha256') != grant['account_id_sha256']):
            raise ValueError('Bridge review provenance differs')
        source_hashes[str(review_path.relative_to(base))] = prep.sha(review_path.read_bytes())
        claim = json.loads((directory / 'claim.json').read_bytes())
        completion = json.loads((directory / 'completion.json').read_bytes())
        journal = rows(directory / 'journal.jsonl')
        raw = rows(directory / 'raw.jsonl')
        records = rows(directory / 'records.jsonl')
        for name in ('claim.json', 'completion.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl'):
            path = directory / name
            source_hashes[str(path.relative_to(base))] = prep.sha(path.read_bytes())
        if (claim.get('model') != model or claim.get('stage') != smoke.STAGE or
                claim.get('plan_sha256') != plan_hash or claim.get('grant_sha256') != grant_hash or
                claim.get('account_id_sha256') != grant['account_id_sha256'] or
                claim.get('runner_sha256') != grant['runner_sha256'] or
                completion != {'kind': 'clef-native-initial-smoke-completion-v1',
                               'model': model, 'stage': smoke.STAGE, 'status': 'complete',
                               'attempted': 3, 'counts': {'valid': 3, 'invalid_output': 0,
                               'service_error': 0, 'unknown_outcome': 0}, 'never_sent': [],
                               'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
                               'journal_sha256': prep.sha((directory / 'journal.jsonl').read_bytes()),
                               'raw_sha256': prep.sha((directory / 'raw.jsonl').read_bytes()),
                               'records_sha256': prep.sha((directory / 'records.jsonl').read_bytes()),
                               'unknown_cost_reserved_usd': str(prep.reservation_usd(model, 3))} or
                len(journal) != 9 or len(raw) != 3 or len(records) != 3):
            raise ValueError('Smoke completion or closure differs')
        usage = []
        for index, rid in enumerate(prep.SMOKE_IDS):
            reserve, started, finished = journal[index * 3:index * 3 + 3]
            raw_row, record = raw[index], records[index]
            ledger_row = ledger[1 + (0 if model == 'clef' else 3) + index]
            attempt_id = reserve.get('attempt_id')
            request_hash = plan['models'][model]['requests']['P0'][index]['payload_sha256']
            if (attempt_id in seen_attempts or
                    reserve != {'event': 'reserved', 'attempt_id': attempt_id, 'id': rid,
                                'request_sha256': request_hash,
                                'usd': str(prep.reservation_usd(model, 1))} or
                    started != {'event': 'started', 'attempt_id': attempt_id, 'id': rid} or
                    finished != {'event': 'finished', 'attempt_id': attempt_id,
                                 'id': rid, 'status': 'valid'} or
                    ledger_row != {'event': 'reserve', 'attempt_id': attempt_id,
                                   'model': model, 'id': rid, 'stage': smoke.STAGE,
                                   'usd': reserve['usd']}):
                raise ValueError('Reservation or attempt order differs')
            seen_attempts.add(attempt_id)
            bridge_dir = directory / 'app-bridge'
            files = {suffix: bridge_dir / f'{attempt_id}.{suffix}.json'
                     for suffix in ('request', 'tool-result', 'app-result', 'response')}
            for path in files.values():
                source_hashes[str(path.relative_to(base))] = prep.sha(path.read_bytes())
            ready, tool, app, response = (json.loads(files[suffix].read_bytes())
                                          for suffix in files)
            app_bytes = files['app-result'].read_bytes()
            body = prep.canonical(ready['body'])
            if (ready != {'kind': bridge.KIND + '-request', 'attempt_id': attempt_id,
                          'id': rid, 'model': model, 'stage': smoke.STAGE,
                          'review_sha256': prep.sha(review_path.read_bytes()),
                          'account_id_sha256': grant['account_id_sha256'],
                          'request_sha256': request_hash, 'method': 'POST',
                          'path': '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[model]['route'],
                          'body': ready['body']} or prep.sha(body) != request_hash or
                    tool.get('isError') is not False or
                    len(tool.get('content', [])) != 1 or
                    tool['content'][0].get('type') != 'text' or
                    json.loads(tool['content'][0]['text']) != app or
                    app.get('status') != 200 or app.get('success') is not True or
                    app.get('errors') != [] or app.get('result', {}).get('model') != model or
                    response != {'kind': bridge.KIND + '-response', 'attempt_id': attempt_id,
                                 'request_sha256': request_hash, 'http_status': 200,
                                 'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                    raw_row.get('attempt_id') != attempt_id or raw_row.get('id') != rid or
                    raw_row.get('request_sha256') != request_hash or
                    raw_row.get('http_status') != 200 or raw_row.get('error_type') is not None or
                    raw_row.get('redacted') is not False or
                    base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                    raw_row.get('response_sha256') != prep.sha(app_bytes) or
                    record.get('attempt_id') != attempt_id or record.get('id') != rid or
                    record.get('request_sha256') != request_hash or
                    record.get('status') != 'valid' or record.get('reason') is not None or
                    record.get('charge_status') != 'unknown_reserved' or
                    record.get('reservation_usd') != reserve['usd'] or
                    record.get('reference_labels_read') is not False or
                    record.get('parsed') != prep.parse_rest_response(app, model)):
                raise ValueError('Connected app or raw response evidence differs')
            answers = app['result']['answers']
            if set(answers) != set(prep.KEYS):
                raise ValueError('Not exactly four native choices')
            for field, values in prep.VALUES.items():
                answer = answers[field]
                probs = answer['probabilities']
                if (answer.get('type') != 'choice' or answer.get('choice') not in values or
                        set(probs) != set(values) or
                        any(type(value) not in (float, int) or not math.isfinite(value) or
                                not 0 <= value <= 1 for value in probs.values()) or
                        not math.isclose(sum(probs.values()), 1, abs_tol=1e-6)):
                    raise ValueError('Native probabilities invalid')
            tokens = app['result']['usage']
            if (type(tokens.get('input_tokens')) is not int or
                    tokens['input_tokens'] < 0 or
                    type(tokens.get('output_tokens')) is not int or
                    tokens['output_tokens'] < 0):
                raise ValueError('Usage missing or invalid')
            usage.append({'id': rid, 'input_tokens': tokens['input_tokens'],
                          'output_tokens': tokens['output_tokens']})
        model_hold = prep.reservation_usd(model, 3)
        aggregate += model_hold
        models[model] = {'status': 'complete', 'valid': 3, 'failed': 0, 'never_sent': 0,
                         'unknown_cost_reserved_usd': str(model_hold),
                         'observed_usage': usage,
                         'input_tokens_total': sum(item['input_tokens'] for item in usage),
                         'output_tokens_total': sum(item['output_tokens'] for item in usage)}
    if aggregate != Decimal('0.064884') or aggregate > Decimal('0.10'):
        raise ValueError('Cloudflare smoke reservation cap differs')
    return {'kind': 'clef-native-smoke-inspection-v1',
            'status': 'six_valid_unknown_charge', 'models': models,
            'attempts': 6, 'valid': 6, 'failed': 0, 'never_sent': 0,
            'unknown_cost_reserved_usd': str(aggregate),
            'provider_billed_usd': None,
            'timing_note': 'client_seconds includes connected-app operator handoff time',
            'raw_note': 'raw.jsonl stores serialized connector result, not HTTP wire bytes',
            'source_sha256': source_hashes}


if __name__ == '__main__':
    receipt = inspect()
    with OUTPUT.open('xb') as handle:
        smoke.durable(handle, receipt)
    print(OUTPUT)
