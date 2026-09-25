#!/usr/bin/env python3
"""Frozen paid repeat plans and execution for three hosted configurations."""
import argparse
import base64
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import http.client
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import quote

from development_benchmark import ROOT, digest, read_rows
import openrouter_paid_benchmark as paid
import openrouter_benchmark as transport
import paid_budget_partitions_v2 as partitions
from prompt_admission import audit_response

MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
HOSTED = 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
COVERAGE = 'results/repeatability-v1/coverage.json'
WAVE = 'results/repeatability-v1/paid-wave-preflight-v1.json'
RECEIPT_SCHEMA = 'openrouter-repeat-wave-root-review-v1'
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class Spec:
    id: str
    model: str
    provider: str
    provider_name: str
    quantization: str
    effort: str
    prompt_price: str
    completion_price: str
    context: int
    timeout: float
    cap: str
    historical_order: tuple[str, str, str]
    continue_invalid: bool

    @property
    def orders(self):
        a, b, c = self.historical_order
        return {'repeat2': (b, c, a), 'repeat3': (c, a, b)}

    @property
    def base(self):
        return ROOT / 'results/repeatability-v1' / self.id

    @property
    def pair(self):
        return f'results/prompt-comparison-v1-2026-09-24/paired-reports/{self.id}/paired-manifest.json'


SPECS = {s.id: s for s in (
    Spec('openrouter-paid-gemma4-31b-off', 'google/gemma-4-31b-it', 'deepinfra/turbo',
         'DeepInfra', 'fp4', 'off', '0.09', '0.34', 262144, 300.0, '0.15',
         ('P0', 'P2', 'P1'), False),
    Spec('openrouter-paid-gemma4-31b-on', 'google/gemma-4-31b-it', 'deepinfra/turbo',
         'DeepInfra', 'fp4', 'on', '0.09', '0.34', 262144, 300.0, '0.30',
         ('P0', 'P1', 'P2'), False),
    Spec('openrouter-paid-mistral-small32-24b-venice-not-applicable',
         'mistralai/mistral-small-3.2-24b-instruct', 'venice/fp8', 'Venice',
         'fp8', 'na', '0.09375', '0.25', 256000, 600.0, '0.15',
         ('P0', 'P2', 'P1'), True),
)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_bound(binding):
    path = (ROOT / binding['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != binding['sha256']:
        raise ValueError('Bound file changed: ' + binding['path'])
    return path


def source_requests(spec, condition, pair, inputs):
    evidence = pair['conditions'][condition]['request_evidence']
    path = read_bound({'path': evidence['file'], 'sha256': evidence['sha256']})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 60 or [r['id'] for r in rows] != [x['id'] for x in inputs]:
        raise ValueError('Historical 60-record membership or order changed')
    controls = pair['controls']['request_controls']
    requests = []
    for index, (old, item) in enumerate(zip(rows, inputs), 1):
        if old['status'] != 'ok' or old['reference_labels_read'] is not False:
            raise ValueError('Historical outcome or reference isolation changed')
        payload = old['request']
        if set(payload) != set(controls) | {'messages'} or any(payload[k] != v for k, v in controls.items()):
            raise ValueError('Historical request controls changed')
        if payload['messages'] != [
            {'role': 'system', 'content': payload['messages'][0]['content']},
            {'role': 'user', 'content': json.dumps({'feedback': item['feedback']})},
        ]:
            raise ValueError('Historical message role or input changed')
        if (old['request_sha256'] != digest(json.dumps(payload, sort_keys=True)) or
                old['input_sha256'] != digest(item['feedback']) or
                old['policy_sha256'] != digest(payload['messages'][0]['content'])):
            raise ValueError('Historical request, input or instruction digest changed')
        if (old['requested_model'], old['reasoning_effort'], old['quantization'],
                old['request_timeout_seconds']) != (spec.model, spec.effort, spec.quantization, spec.timeout):
            raise ValueError('Historical model, reasoning, quantization or timeout changed')
        endpoint = old['provider_endpoint']
        if (endpoint['tag'], endpoint['provider_name'], endpoint['context_length']) != (
                spec.provider, spec.provider_name, spec.context):
            raise ValueError('Historical endpoint identity changed')
        requests.append({'position': index, 'record_id': item['id'], 'payload': payload,
                         'request_sha256': old['request_sha256'], 'input_sha256': old['input_sha256'],
                         'instruction_sha256': old['policy_sha256'],
                         'source_attempt_sha256': evidence['sha256']})
    return requests, evidence['file']


def plan_data(spec, repeat):
    if repeat not in spec.orders:
        raise ValueError('Unknown repeat')
    pair = json.loads((ROOT / spec.pair).read_text())
    cover = json.loads((ROOT / COVERAGE).read_text())
    wave = json.loads((ROOT / WAVE).read_text())
    hosted = json.loads((ROOT / HOSTED).read_text())
    groups = [x for x in cover['groups'] if x['id'] == spec.id]
    entries = [x for x in wave['configurations'] if x['id'] == spec.id]
    histories = [x for x in hosted['configurations'] if x['id'] == spec.id]
    if not (len(groups) == len(entries) == len(histories) == 1):
        raise ValueError('Missing or duplicate source configuration')
    group, entry, history = groups[0], entries[0], histories[0]
    if (group['historical_triple_status'] != 'eligible_first_pass' or
            tuple(group['observed_condition_order']) != spec.historical_order or
            tuple(entry['historical_order']) != spec.historical_order):
        raise ValueError('Historical repeat eligibility or order changed')
    if (entry['paired_manifest'] != bind(spec.pair) or
            entry['proposed_partition_cap_usd'] != spec.cap or
            entry['public_route']['status'] != 'verified_public_endpoint'):
        raise ValueError('Wave proposal or paired manifest changed')
    if (history['continue_on_invalid_output'] is not spec.continue_invalid or
            history['controller_timeout_seconds'] != spec.timeout or
            history['controls']['adapter_controls'] != pair['controls']):
        raise ValueError('Historical controller policy changed')
    controls = pair['controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            spec.model, spec.provider, spec.provider_name, spec.quantization, spec.effort, 'single_record'):
        raise ValueError('Paired route controls changed')
    rc = controls['request_controls']
    if (rc['model'], rc['temperature'], rc['max_tokens'], rc['stream']) != (spec.model, 0, 4096, False):
        raise ValueError('Sampling controls changed')
    if rc['provider'] != {'only': [spec.provider], 'allow_fallbacks': False,
                          'require_parameters': True,
                          'max_price': {'prompt': float(spec.prompt_price),
                                        'completion': float(spec.completion_price),
                                        'request': 0, 'image': 0}}:
        raise ValueError('Provider price or fallback guard changed')
    if (rc.get('reasoning') != ({'enabled': spec.effort == 'on'} if spec.effort != 'na' else None)
            or ('reasoning' in rc) != (spec.effort != 'na') or
            rc['response_format']['type'] != 'json_schema' or
            rc['response_format']['json_schema']['strict'] is not True):
        raise ValueError('Reasoning or parser guard changed')
    public = entry['public_route']
    if (entry['controls']['provider_tag'], entry['controls']['quantization'],
            entry['controls']['reasoning_effort'], public['context_tokens_for_reservation']) != (
            spec.provider, spec.quantization, spec.effort, spec.context):
        raise ValueError('Wave route identity changed')
    if (paid.number(public['pricing_usd_per_million']['prompt']) != paid.number(spec.prompt_price) or
            paid.number(public['pricing_usd_per_million']['completion']) != paid.number(spec.completion_price)):
        raise ValueError('Wave public price changed')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(inputs) != 60 or any(set(row) != {'id', 'feedback'} for row in inputs):
        raise ValueError('Input isolation failed')
    paths = [spec.pair, COVERAGE, WAVE, HOSTED, 'data/pilot/inputs.jsonl',
             'schemas/judgments.schema.json', 'docs/REPEATABILITY_PLAN.md',
             'scripts/openrouter_repeat_wave.py', 'scripts/openrouter_paid_benchmark.py',
             'scripts/paid_budget_partitions_v2.py', 'scripts/openrouter_budget_v2.py',
             'scripts/prompt_admission.py']
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        requests, source = source_requests(spec, condition, pair, inputs)
        if entry['historical_request_evidence'][condition] != pair['conditions'][condition]['request_evidence']:
            raise ValueError('Wave historical request source changed')
        paths.append(source)
        conditions[condition] = {'historical_attempts': bind(source),
                                 'smoke': requests[:3], 'development': requests}
    return {'schema': 'openrouter-paid-repeat-wave-plan-v1', 'configuration_id': spec.id,
            'repeat': repeat, 'historical_pass_order': list(spec.historical_order),
            'condition_order': list(spec.orders[repeat]), 'model': spec.model,
            'provider_tag': spec.provider, 'reasoning_effort': spec.effort,
            'request_timeout_seconds': spec.timeout,
            'continue_on_invalid_output': spec.continue_invalid,
            'partition_cap_usd': spec.cap, 'input_count': 60,
            'request_unit': 'single_record_fresh_context', 'smoke_count_per_condition': 3,
            'max_tokens': 4096,
            'seed_policy': 'No explicit seed in historical payload; requested and effective seed unavailable',
            'reference_labels_read': False, 'repeat_status': 'offline_prepared_no_inference',
            'dispatch_gate': 'Root review receipt, live endpoint and child budget partition required',
            'source_bindings': [bind(path) for path in dict.fromkeys(paths)], 'conditions': conditions}


def prepare(spec):
    spec.base.mkdir(parents=True, exist_ok=True)
    for repeat in spec.orders:
        folder = spec.base / repeat
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        raw = json.dumps(plan_data(spec, repeat), indent=2, ensure_ascii=False) + '\n'
        with path.open('x') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        print(repeat, sha(path), path)


def verify(spec, repeat, expected_sha):
    path = spec.base / repeat / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    value = json.loads(path.read_text())
    for binding in value['source_bindings']:
        read_bound(binding)
    if value != plan_data(spec, repeat):
        raise ValueError('Manifest differs from frozen source reconstruction')
    return value


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def review_receipt(spec, path, repeat, manifest_sha):
    receipt = json.loads(Path(path).read_text())
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
        raise ValueError('Root review receipt missing approval')
    if receipt.get('configuration_id') != spec.id or receipt.get('partition_cap_usd') != spec.cap:
        raise ValueError('Root review configuration or cap differs')
    if (receipt.get('controller_sha256') != sha(__file__) or
            receipt.get('hosted_execution_sha256') != sha(ROOT / HOSTED)):
        raise ValueError('Root review controller or original policy hash differs')
    plans = {r: sha(spec.base / r / 'manifest.json') for r in spec.orders}
    if receipt.get('plan_sha256') != plans or plans[repeat] != manifest_sha:
        raise ValueError('Root review plan hashes differ')
    if receipt.get('master_ledger') != str(MASTER):
        raise ValueError('Root review master ledger differs')
    budget = receipt.get('budget_manifest')
    if not isinstance(budget, dict) or not receipt.get('partition_id'):
        raise ValueError('Root review budget binding missing')
    return receipt, read_bound(budget)


def phase_paths(spec, repeat, condition, phase):
    folder = spec.base / repeat / condition
    return folder, folder / (phase + '.claim.json'), folder / (phase + '.journal.jsonl'), folder / (phase + '.attempts.jsonl')


def complete_journal(spec, repeat, condition, phase):
    journal = phase_paths(spec, repeat, condition, phase)[2]
    if not journal.exists():
        return False
    lines = journal.read_text().splitlines()
    return bool(lines) and json.loads(lines[-1]).get('event') == 'phase_completed'


def require_order(spec, plan, condition, phase):
    if condition not in plan['condition_order']:
        raise ValueError('Condition outside frozen order')
    if plan['repeat'] == 'repeat3' and not all(complete_journal(spec, 'repeat2', c, 'development')
                                               for c in spec.orders['repeat2']):
        raise ValueError('Repeat two incomplete')
    for prior in plan['condition_order'][:plan['condition_order'].index(condition)]:
        if not complete_journal(spec, plan['repeat'], prior, 'development'):
            raise ValueError('Prior condition incomplete: ' + prior)
    if phase == 'development':
        folder = phase_paths(spec, plan['repeat'], condition, 'smoke')[0]
        inspection_path = folder / 'smoke-inspection.json'
        if not inspection_path.exists():
            raise ValueError('Inspected smoke required')
        inspection = json.loads(inspection_path.read_text())
        _, _, journal, attempts = phase_paths(spec, plan['repeat'], condition, 'smoke')
        responses = folder / 'smoke.responses.jsonl'
        if (inspection.get('decision') != 'accepted_unchanged' or
                inspection.get('journal_sha256') != sha(journal) or
                inspection.get('attempts_sha256') != sha(attempts) or
                inspection.get('responses_sha256') != sha(responses)):
            raise ValueError('Smoke inspection binding changed')


def live_controls(spec, plan, condition):
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(spec.model, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(spec.model, spec.provider, catalog, endpoints,
                                           Decimal(spec.prompt_price), Decimal(spec.completion_price))
    if endpoint.get('quantization') != spec.quantization or endpoint.get('provider_name') != spec.provider_name:
        raise ValueError('Live endpoint identity differs')
    wave = json.loads((ROOT / WAVE).read_text())
    entry = next(x for x in wave['configurations'] if x['id'] == spec.id)
    public = entry['public_route']
    if endpoint['context_length'] != spec.context or endpoint['context_length'] != public['context_tokens_for_reservation']:
        raise ValueError('Live endpoint context differs from reviewed reserve')
    for key in ('prompt', 'completion'):
        if paid.number(endpoint['pricing'][key]) != paid.number(public['pricing_usd_per_million'][key]) / paid.MILLION:
            raise ValueError('Live endpoint price differs from reviewed rate')
    reserve = paid.reservation(endpoint, 4096, Decimal(spec.prompt_price), Decimal(spec.completion_price))
    if reserve != paid.number(entry['per_call_reserve_usd']) or reserve > paid.number(spec.cap):
        raise ValueError('Live reserve differs from reviewed amount')
    inputs = {x['id']: x['feedback'] for x in paid.read_rows(ROOT / 'data/pilot/inputs.jsonl')}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(spec.model, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    spec.effort, 4096, Decimal(spec.prompt_price),
                                    Decimal(spec.completion_price), model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


def budget_gate(spec, receipt, budget_path):
    ledger = partitions.open_partition(MASTER, budget_path, receipt['partition_id'],
                                       spec.model, spec.provider, spec.effort)
    if ledger.cap != paid.number(spec.cap):
        ledger.close()
        raise ValueError('Child partition cap differs')
    return ledger


def classify(spec, body, endpoint):
    record = {'raw_response': body, 'returned_model': body.get('model'),
              'returned_provider': body.get('provider'), 'usage': body.get('usage') or {}}
    choices = body.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        record.update(status='control_violation', prediction=None)
        return record
    choice = choices[0]
    message = choice.get('message') or {}
    record['finish_reason'] = choice.get('finish_reason')
    try:
        prediction = json.loads(message.get('content'))
    except (ValueError, TypeError):
        prediction = None
    record['prediction'] = prediction
    record['status'] = ('ok' if paid.valid(prediction) and choice.get('finish_reason') == 'stop'
                        and not message.get('refusal') and not message.get('tool_calls')
                        and not message.get('function_call') and not choice.get('error') else 'invalid_output')
    if body.get('model') not in paid.allowed_returned_models(spec.model, endpoint):
        record['status'] = 'model_mismatch'
    if body.get('provider') != endpoint['provider_name']:
        record['status'] = 'provider_mismatch'
    return record


def continue_record(spec, record, phase):
    if not record.get('billing_ok') or record.get('cost_unknown'):
        return False
    if record['status'] == 'ok':
        return record.get('response_diagnostic', {}).get('passed') is True
    if phase != 'development' or not spec.continue_invalid or record['status'] != 'invalid_output':
        return False
    choices = (record.get('raw_response') or {}).get('choices') or []
    if len(choices) != 1 or not isinstance(choices[0], dict):
        return False
    choice = choices[0]
    message = choice.get('message') or {}
    blockers = set(record.get('response_diagnostic', {}).get('blockers', []))
    return (choice.get('finish_reason') in ('stop', 'length') and not choice.get('error')
            and not any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call'))
            and blockers <= {'truncation:length'})


def inspect(spec, repeat, condition, manifest_sha, note):
    plan = verify(spec, repeat, manifest_sha)
    require_order(spec, plan, condition, 'smoke')
    folder, _, journal, attempts = phase_paths(spec, repeat, condition, 'smoke')
    receipt = folder / 'smoke-inspection.json'
    if receipt.exists() or not complete_journal(spec, repeat, condition, 'smoke'):
        raise ValueError('Fresh completed smoke required')
    rows = [json.loads(line) for line in attempts.read_text().splitlines()]
    responses = folder / 'smoke.responses.jsonl'
    raw = [json.loads(line) for line in responses.read_text().splitlines()]
    if len(rows) != 3 or [r['id'] for r in rows] != ['DEV-001', 'DEV-002', 'DEV-003']:
        raise ValueError('Smoke must contain exactly three ordered calls')
    if (len(raw) != 3 or [r['id'] for r in raw] != [r['id'] for r in rows] or
            [r['attempt_id'] for r in raw] != [r['attempt_id'] for r in rows] or
            any('body_base64' not in r or r.get('body_truncated_at_limit') or r.get('read_error')
                for r in raw)):
        raise ValueError('Three matching raw smoke responses required')
    if not all(r['status'] == 'ok' and r['billing_ok'] and not r['cost_unknown'] for r in rows):
        raise ValueError('Three valid, billed smoke calls required')
    if not note.strip():
        raise ValueError('Inspection note required')
    value = {'schema': 'openrouter-repeat-smoke-inspection-v1', 'repeat': repeat,
             'condition': condition, 'decision': 'accepted_unchanged', 'note': note,
             'journal_sha256': sha(journal), 'attempts_sha256': sha(attempts),
             'responses_sha256': sha(responses)}
    with receipt.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return value


def fetch_recorded(payload, token, timeout, raw_output, rid, attempt_id, request_sha):
    """Persist bounded HTTP bytes and metadata before parsing a successful response."""
    request = urllib.request.Request(
        transport.BASE + '/chat/completions',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
        data=json.dumps(payload).encode())
    with transport.OPENER.open(request, timeout=timeout) as response:
        status = response.status
        headers = {key: str(response.headers[key]).replace(token, '[REDACTED]')
                   for key in ('content-type', 'content-length', 'x-request-id',
                               'request-id', 'cf-ray')
                   if response.headers.get(key) is not None}
        read_error = None
        try:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        except http.client.IncompleteRead as exc:
            body = exc.partial
            read_error = 'IncompleteRead'
        oversized = len(body) > MAX_RESPONSE_BYTES
        body = body[:MAX_RESPONSE_BYTES]
        captured_length = len(body)
        declared_length = headers.get('content-length')
        if declared_length is not None and not oversized and read_error is None:
            try:
                if int(declared_length) != captured_length:
                    read_error = 'ContentLengthMismatch'
            except ValueError:
                read_error = 'InvalidContentLength'
        secret = token.encode()
        redacted = bool(secret and secret in body)
        if redacted:
            body = body.replace(secret, b'[REDACTED]')
        paid.durable(raw_output, {
            'id': rid, 'attempt_id': attempt_id, 'request_sha256': request_sha,
            'http_status': status, 'response_headers': headers,
            'body_base64': base64.b64encode(body).decode('ascii'),
            'body_bytes_captured': captured_length, 'body_truncated_at_limit': oversized,
            'body_token_redacted': redacted, 'read_error': read_error,
            'received_utc': utc()})
        if status != 200 or oversized or read_error:
            raise ValueError('HTTP response status or body failed capture controls')
        return json.loads(body)


def execute(spec, repeat, condition, phase, manifest_sha, review_path, env_file=None):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    plan = verify(spec, repeat, manifest_sha)
    require_order(spec, plan, condition, phase)
    folder, claim, journal, attempts = phase_paths(spec, repeat, condition, phase)
    responses = folder / (phase + '.responses.jsonl')
    if any(path.exists() for path in (claim, journal, attempts, responses)):
        raise FileExistsError('Phase already claimed; no implicit retry')
    receipt, budget_path = review_receipt(spec, review_path, repeat, manifest_sha)
    model, endpoint, reserve = live_controls(spec, plan, condition)
    ledger = budget_gate(spec, receipt, budget_path)
    try:
        token = paid.load_key(env_file)
        folder.mkdir(parents=True, exist_ok=True)
        with claim.open('x') as out:
            paid.durable(out, {'repeat': repeat, 'condition': condition, 'phase': phase,
                               'manifest_sha256': manifest_sha, 'root_review_sha256': sha(review_path),
                               'claimed_utc': utc()})
        requests = plan['conditions'][condition][phase]
        complete = True
        with journal.open('x') as audit, attempts.open('x') as output, responses.open('x') as raw_output:
            paid.durable(audit, {'event': 'phase_started', 'repeat': repeat,
                                 'condition': condition, 'phase': phase, 'utc': utc()})
            for request in requests:
                rid, payload = request['record_id'], request['payload']
                paid.durable(audit, {'event': 'request_intent', 'id': rid,
                                     'request_sha256': request['request_sha256'], 'utc': utc()})
                attempt_id = ledger.reserve(reserve, rid)
                start = time.perf_counter()
                record = {'id': rid, 'repeat': repeat, 'condition': condition, 'phase': phase,
                          'attempt_id': attempt_id, 'request': payload,
                          'request_sha256': request['request_sha256'],
                          'manifest_sha256': manifest_sha, 'requested_model': spec.model,
                          'reasoning_effort': spec.effort, 'request_timeout_seconds': spec.timeout,
                          'provider_endpoint': endpoint, 'model_catalog_entry': model,
                          'reference_labels_read': False, 'reserved_cost_usd': str(reserve),
                          'started_utc': utc()}
                paid.durable(audit, {'event': 'request_started', 'id': rid, 'attempt_id': attempt_id,
                                     'request_sha256': request['request_sha256'], 'utc': utc()})
                actual = None
                try:
                    body = fetch_recorded(payload, token, spec.timeout, raw_output,
                                          rid, attempt_id, request['request_sha256'])
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record['raw_response'] = body
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                        record.update(classify(spec, body, endpoint))
                    else:
                        record.update(status='control_violation')
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        record['http_status'] = exc.code
                        record['error_body'] = exc.read().decode('utf-8', errors='replace').replace(token, '[REDACTED]')
                        record['error_headers'] = {key: str(exc.headers[key]).replace(token, '[REDACTED]')
                                                   for key in ('x-request-id', 'request-id', 'retry-after', 'cf-ray')
                                                   if exc.headers is not None and exc.headers.get(key) is not None}
                        paid.durable(raw_output, {'id': rid, 'attempt_id': attempt_id,
                                                  'request_sha256': request['request_sha256'],
                                                  'http_status': exc.code, 'error_body': record['error_body'],
                                                  'error_headers': record['error_headers'], 'received_utc': utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - start,
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                if isinstance(record.get('raw_response'), dict):
                    diagnostic = audit_response(record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                paid.durable(output, record)
                paid.durable(audit, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt_id,
                                     'status': record['status'], 'billing_ok': billing_ok,
                                     'cost_unknown': record['cost_unknown'], 'utc': utc()})
                if not continue_record(spec, record, phase):
                    complete = False
                    paid.durable(audit, {'event': 'phase_stopped', 'id': rid,
                                         'reason': record['status'], 'utc': utc()})
                    break
            if complete:
                paid.durable(audit, {'event': 'phase_completed', 'repeat': repeat,
                                     'condition': condition, 'phase': phase,
                                     'request_count': len(requests), 'utc': utc()})
        return complete
    finally:
        if journal.exists():
            lines = journal.read_text().splitlines()
            terminal = json.loads(lines[-1]).get('event') if lines else None
            if terminal not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                with journal.open('a') as audit:
                    paid.durable(audit, {'event': 'phase_aborted', 'reason': 'exception_or_interruption',
                                         'utc': utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, choices=tuple(SPECS))
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    for action in ('verify', 'smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--repeat', required=True, choices=('repeat2', 'repeat3'))
        p.add_argument('--manifest-sha256', required=True)
        if action != 'verify':
            p.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        if action == 'inspect':
            p.add_argument('--note', required=True)
        elif action in ('smoke', 'development'):
            p.add_argument('--root-review-receipt', required=True)
            p.add_argument('--env-file')
    args = parser.parse_args()
    spec = SPECS[args.config]
    if args.action == 'prepare':
        prepare(spec)
    elif args.action == 'verify':
        verify(spec, args.repeat, args.manifest_sha256)
        print('verified', spec.id, args.repeat)
    elif args.action == 'inspect':
        inspect(spec, args.repeat, args.condition, args.manifest_sha256, args.note)
    else:
        execute(spec, args.repeat, args.condition, args.action, args.manifest_sha256,
                args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
