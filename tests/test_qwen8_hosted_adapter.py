import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen8_hosted_adapter as q
from openrouter_paid_benchmark import BudgetLedger, reservation


def live():
    return q.load_saved()[:2]


def frozen_case(tmp_path, name='off-p0-smoke3.jsonl', continue_invalid=False):
    source = q.RESULT / 'preview-v1'
    folder = tmp_path / 'frozen'
    folder.mkdir()
    shutil.copy2(source / 'preview-manifest.json', folder / 'preview-manifest.json')
    shutil.copy2(source / name, folder / name)
    file = folder / name
    manifest = json.loads((folder / 'preview-manifest.json').read_text())
    entry = next(c for c in manifest['configs'] if c['file'] == name)
    receipt = {'decision': 'approved', 'preview_sha256': q.sha(file.read_bytes()),
               'preview_manifest_sha256': q.sha((folder / 'preview-manifest.json').read_bytes()),
               'script_sha256': q.sha(Path(q.__file__).read_bytes()),
               'catalog_entry_sha256': manifest['catalog_entry_sha256'],
               'endpoints_sha256': manifest['endpoints_sha256'],
               'reasoning': entry['reasoning'], 'variant': entry['variant'],
               'phase': entry['phase'],
               'continue_on_invalid_output': continue_invalid}
    receipt_path = tmp_path / 'review.json'
    receipt_path.write_text(json.dumps(receipt))
    return file, receipt_path


def test_endpoint_identity_json_mode_and_reasoning():
    model, endpoint = live()
    schema = json.loads(q.SCHEMA_PATH.read_text())
    text, audit = q.instruction(schema, 'P1', 'off')
    assert audit['variant'] == 'P1'
    assert all(key in text for key in schema['required'])
    for mode, value in (('off', False), ('on', True)):
        request = q.payload(model, endpoint, 'example', text, mode)
        assert request['model'] == 'qwen/qwen3-8b'
        assert request['response_format'] == {'type': 'json_object'}
        assert request['provider']['only'] == ['alibaba']
        assert request['provider']['allow_fallbacks'] is False
        assert request['provider']['require_parameters'] is True
        assert request['reasoning'] == {'enabled': value}
        assert 'json_schema' not in request['response_format']


def test_endpoint_change_fails_closed():
    model, endpoint = live()
    altered = dict(endpoint, name='Unknown endpoint')
    with pytest.raises(ValueError, match='identity'):
        q.select(model, {'data': {'id': q.MODEL, 'endpoints': [altered]}})
    altered = dict(endpoint, supported_parameters=['response_format', 'reasoning', 'max_tokens', 'temperature', 'structured_outputs'])
    with pytest.raises(ValueError, match='capability changed'):
        q.select(model, {'data': {'id': q.MODEL, 'endpoints': [altered]}})
    altered = dict(endpoint, pricing=dict(endpoint['pricing'], completion='0.000002'))
    with pytest.raises(ValueError, match='ceiling'):
        q.select(model, {'data': {'id': q.MODEL, 'endpoints': [altered]}})


def test_live_telemetry_drift_allowed_but_control_drift_rejected():
    model, endpoint = live()
    changed = dict(endpoint, uptime_last_5m=0, latency_last_30m=999)
    assert q.experimental_controls(model, changed) == q.experimental_controls(model, endpoint)
    changed = dict(endpoint, quantization='fp8')
    assert q.experimental_controls(model, changed) != q.experimental_controls(model, endpoint)
    changed = dict(endpoint, pricing=dict(endpoint['pricing'], completion='0.000000456'))
    assert q.experimental_controls(model, changed) != q.experimental_controls(model, endpoint)


def test_preview_is_offline_and_inputs_only(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Preview must not use network or budget')
    monkeypatch.setattr(q, 'fetch', forbidden)
    monkeypatch.setattr(q, 'load_key', forbidden)
    output = tmp_path / 'preview'
    manifest = q.preview(output)
    assert len(manifest['configs']) == 12
    assert {c['rows'] for c in manifest['configs']} == {3, 60}
    assert all(c['ids'][0] == 'DEV-001' for c in manifest['configs'])
    assert manifest['reference_labels_read'] is False
    assert manifest['inference_performed'] is False
    assert all('reference_label' not in row['request']['messages'][0]['content']
               and 'reference_label' not in row['request']['messages'][1]['content']
               for p in output.glob('*.jsonl')
               for row in (json.loads(line) for line in p.read_text().splitlines()))
    with pytest.raises(FileExistsError):
        q.preview(output)


def test_billing_reservation_and_unknown_charge_block(tmp_path):
    _, endpoint = live()
    amount = reservation(endpoint, q.MAX_TOKENS, q.INPUT_CEILING, q.OUTPUT_CEILING)
    assert amount == q.Decimal('0.017199104')
    ledger = BudgetLedger(tmp_path / 'budget.jsonl', cap_limit=q.Decimal('1'))
    try:
        attempt = ledger.reserve(amount, 'DEV-001')
        assert ledger.settle(attempt, None) is False
        with pytest.raises(ValueError, match='Unresolved charge'):
            ledger.reserve(amount, 'DEV-002')
    finally:
        ledger.close()


def test_execute_requires_review_before_key_or_budget(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('Key or network accessed before review')
    monkeypatch.setattr(q, 'load_key', forbidden)
    monkeypatch.setattr(q, 'fetch', forbidden)
    path, receipt = frozen_case(tmp_path)
    value = json.loads(receipt.read_text())
    value['preview_sha256'] = 'wrong'
    receipt.write_text(json.dumps(value))
    args = type('Args', (), dict(preview_file=str(path), review_receipt=str(receipt),
                                 partition_manifest='partition.json', partition_id='x',
                                 output=str(tmp_path / 'out'), env_file=None, timeout=1))()
    with pytest.raises(ValueError, match='root review'):
        q.execute(args)


def test_preview_tamper_rejected_even_with_rehashed_manifest_and_receipt(tmp_path):
    path, receipt_path = frozen_case(tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['request']['messages'][1]['content'] = json.dumps({'feedback': 'tampered'})
    rows[0]['request_sha256'] = q.sha(q.canonical(rows[0]['request']))
    rows[0]['input_sha256'] = q.sha(b'tampered')
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    manifest_path = path.parent / 'preview-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    next(c for c in manifest['configs'] if c['file'] == path.name)['file_sha256'] = q.sha(path.read_bytes())
    manifest_path.write_text(json.dumps(manifest))
    receipt = json.loads(receipt_path.read_text())
    receipt['preview_sha256'] = q.sha(path.read_bytes())
    receipt['preview_manifest_sha256'] = q.sha(manifest_path.read_bytes())
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='canonical frozen condition'):
        q.reviewed_preview(path, receipt_path)


def test_invalid_reasoning_rejected_even_with_rehashed_review(tmp_path):
    path, receipt_path = frozen_case(tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['request']['reasoning'] = {'enabled': False, 'effort': 'low'}
    rows[0]['request_sha256'] = q.sha(q.canonical(rows[0]['request']))
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    manifest_path = path.parent / 'preview-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    next(c for c in manifest['configs'] if c['file'] == path.name)['file_sha256'] = q.sha(path.read_bytes())
    manifest_path.write_text(json.dumps(manifest))
    receipt = json.loads(receipt_path.read_text())
    receipt['preview_sha256'] = q.sha(path.read_bytes())
    receipt['preview_manifest_sha256'] = q.sha(manifest_path.read_bytes())
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='canonical frozen condition'):
        q.reviewed_preview(path, receipt_path)


def test_full60_requires_reviewed_smoke_evidence(tmp_path):
    path, receipt_path = frozen_case(tmp_path, name='off-p0-full60.jsonl')
    with pytest.raises(ValueError, match='smoke inspection'):
        q.reviewed_preview(path, receipt_path)


def test_execute_records_controls_and_continues_known_billed_invalid(tmp_path, monkeypatch):
    path, receipt_path = frozen_case(tmp_path, continue_invalid=True)
    model, endpoint = live()
    live_endpoint = dict(endpoint, latency_last_30m=900, uptime_last_5m=0)
    responses = [
        {'model': q.MODEL, 'provider': 'Alibaba', 'usage': {'cost': 0.001},
         'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]},
        *[{'model': q.MODEL, 'provider': 'Alibaba', 'usage': {'cost': 0.001},
           'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
               'sentiment': 'neutral', 'follow_up_needed': 'no',
               'serious_concern_reported': 'no', 'testimonial_potential': 'no'})}}]}
          for _ in range(2)]]

    def fake_fetch(path, token=None, payload=None, timeout=0):
        if path == '/models':
            return {'data': [model]}
        if path.endswith('/endpoints'):
            return {'data': {'id': q.MODEL, 'endpoints': [live_endpoint]}}
        assert path == '/chat/completions'
        assert payload['response_format'] == {'type': 'json_object'}
        return responses.pop(0)

    class FakeLedger:
        cap = q.Decimal('1')
        master_cap = q.Decimal('5')
        def __init__(self):
            self.settled = []
        def reserve(self, amount, record_id):
            return f'attempt-{record_id}'
        def settle(self, attempt, actual):
            self.settled.append((attempt, actual))
            return actual is not None
        def accounted(self):
            return sum((cost for _, cost in self.settled), q.Decimal(0))
        def close(self):
            pass

    ledger = FakeLedger()
    import paid_budget_partitions
    monkeypatch.setattr(paid_budget_partitions, 'open_partition', lambda *args: ledger)
    monkeypatch.setattr(q, 'load_key', lambda *args: 'fake-token')
    monkeypatch.setattr(q, 'fetch', fake_fetch)
    output = tmp_path / 'attempts.jsonl'
    args = type('Args', (), dict(preview_file=str(path), review_receipt=str(receipt_path),
                                 partition_manifest='preallocated.json', partition_id='unit-test',
                                 output=str(output), env_file=None, timeout=1))()
    q.execute(args)
    records = [json.loads(line) for line in output.read_text().splitlines()]
    events = [json.loads(line) for line in Path(str(output) + '.attempts.jsonl').read_text().splitlines()]
    assert [r['status'] for r in records] == ['invalid_output', 'ok', 'ok']
    assert all(r['elapsed_seconds'] >= 0 and r['input_sha256'] and r['script_sha256']
               and r['preview_manifest_sha256'] and r['prompt_variant']['variant'] == 'P0'
               and r['phase'] == 'smoke3' and r['request_timeout_seconds'] == 1
               and r['hardware'] == 'Remote provider undisclosed' for r in records)
    assert events[-1]['event'] == 'terminal'
    assert events[-1]['attempted_records'] == 3 and events[-1]['completed'] is True
    assert len(ledger.settled) == 3
