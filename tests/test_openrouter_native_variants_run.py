"""Offline fake-transport tests for receipt-gated native Decisions execution."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_native_variants_run as run
import openrouter_decision_smoke as smoke
from tests.test_openrouter_decision_smoke import catalog, valid_body

CONFIG = 'kev-openrouter-native-p1-choice-v1'


class NativeVariantsRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'plans'
        self.base.mkdir()
        shutil.copyfile(run.BASE / (CONFIG + '.json'), self.base / (CONFIG + '.json'))
        self.ledger = Path(self.temp.name) / 'master.jsonl'
        self.ledger.write_text(json.dumps({'event': 'budget', 'cap_usd': '10'}) + '\n')
        self.manifest = run.load_manifest(CONFIG, self.base)
        self.route = smoke.ROUTES['kev']
        self.raw = json.dumps(valid_body(self.route)).encode()
        self.calls = []

    def receipt(self, stage, proof=None):
        path = Path(self.temp.name) / (stage + '-review.json')
        record = {'approved': True, 'reviewer': 'offline-test-reviewer',
                  'stage_id': run.stage_id(self.manifest, stage),
                  'manifest_sha256': smoke.sha(smoke.canonical(self.manifest)),
                  'runner_sha256': smoke.sha(Path(run.__file__).read_bytes()),
                  'whole_pass_bound_usd': self.manifest['full_pass_catalog_bound_usd'],
                  'stage_bound_usd': (self.manifest['three_record_smoke_catalog_bound_usd']
                                      if stage == 'smoke' else self.manifest['full_pass_catalog_bound_usd']),
                  'predecessor_proof': proof}
        path.write_text(json.dumps(record))
        return path

    def transport(self, payload, token):
        self.assertEqual(token, 'offline-fake-token')
        self.calls.append(payload)
        return 200, self.raw

    def execute(self, stage, receipt, **kwargs):
        return run.execute(CONFIG, stage, receipt, base=self.base, ledger_path=self.ledger,
                           catalog_fetch=lambda route: catalog(route),
                           transport=self.transport, token='offline-fake-token', **kwargs)

    def test_successful_smoke_then_reviewed_full_pass_and_duplicate_rejection(self):
        self.execute('smoke', self.receipt('smoke'))
        self.assertEqual(len(self.calls), 3)
        proof = run.inspect_completed(self.manifest, 'smoke', self.base, self.ledger)
        self.assertEqual(proof['stage_id'], CONFIG + '-smoke')
        self.execute('fresh1', self.receipt('fresh1', {'smoke': proof}))
        self.assertEqual(len(self.calls), 63)
        full = run.inspect_completed(self.manifest, 'fresh1', self.base, self.ledger)
        self.assertEqual(full['stage_id'], CONFIG + '-fresh1')
        with self.assertRaises(FileExistsError):
            self.execute('fresh1', self.receipt('fresh1', {'smoke': proof}))
        self.assertEqual(len(self.calls), 63)

    def test_all_three_passes_require_prior_terminal_evidence(self):
        self.execute('smoke', self.receipt('smoke'))
        smoke_proof = run.inspect_completed(self.manifest, 'smoke', self.base, self.ledger)
        for stage, previous in [('fresh1', None), ('fresh2', 'fresh1'), ('fresh3', 'fresh2')]:
            proof = {'smoke': smoke_proof}
            if previous:
                proof['previous_pass'] = run.inspect_completed(self.manifest, previous, self.base, self.ledger)
            self.execute(stage, self.receipt(stage, proof))
            self.assertEqual(run.inspect_completed(self.manifest, stage, self.base, self.ledger)['stage_id'],
                             CONFIG + '-' + stage)
        self.assertEqual(len(self.calls), 183)

    def test_tampered_started_request_or_review_blocks_next_pass(self):
        self.execute('smoke', self.receipt('smoke'))
        directory = run.stage_dir(self.base, CONFIG, 'smoke')
        attempts = directory / 'attempts.jsonl'
        original = attempts.read_text()
        rows = [json.loads(x) for x in original.splitlines()]
        rows[1]['request_base64'] = 'e30='
        attempts.write_text(''.join(json.dumps(x) + '\n' for x in rows))
        with self.assertRaises(ValueError):
            run.inspect_completed(self.manifest, 'smoke', self.base, self.ledger)
        attempts.write_text(original)
        review = directory / 'review-receipt.json'
        review.write_text('{}')
        with self.assertRaises(ValueError):
            run.inspect_completed(self.manifest, 'smoke', self.base, self.ledger)

    def test_validated_catalog_is_saved_and_tamper_blocks_reconciliation(self):
        self.execute('smoke', self.receipt('smoke'))
        directory = run.stage_dir(self.base, CONFIG, 'smoke')
        catalog_path = directory / 'endpoint-catalog.json'
        raw = catalog_path.read_bytes()
        self.assertEqual(json.loads(raw)['data']['id'], self.route['model'])
        completion = json.loads((directory / 'completion.json').read_text())
        self.assertEqual(completion['endpoint_catalog_sha256'], smoke.sha(raw))
        changed = json.loads(raw)
        changed['data']['endpoints'][0]['pricing']['prompt'] = '0.000000043'
        catalog_path.write_bytes(smoke.canonical(changed))
        with self.assertRaises(ValueError):
            run.inspect_completed(self.manifest, 'smoke', self.base, self.ledger)

    def test_wrong_receipt_and_changed_endpoint_never_send(self):
        receipt = self.receipt('smoke')
        record = json.loads(receipt.read_text())
        record['whole_pass_bound_usd'] = '0.001'
        receipt.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'reviewed stage receipt'):
            self.execute('smoke', receipt)
        with self.assertRaisesRegex(ValueError, 'Endpoint/provider/version/context changed'):
            run.execute(CONFIG, 'smoke', self.receipt('smoke'), base=self.base,
                ledger_path=self.ledger, token='offline-fake-token', transport=self.transport,
                catalog_fetch=lambda route: self.changed_catalog(route))
        self.assertEqual(self.calls, [])

    def changed_catalog(self, route):
        value = catalog(route)
        value['data']['endpoints'][0]['context_length'] += 1
        return value

    def test_whole_pass_bound_blocks_smoke_before_request(self):
        class TightLedger:
            closed = False
            partitions = {}
            cap = run.Decimal('10')
            def __init__(self, path): pass
            def state(self): return {}, set(), False
            def accounted(self): return run.Decimal('9.99')
            def close(self): pass
        with self.assertRaisesRegex(ValueError, 'Whole-pass bound'):
            self.execute('smoke', self.receipt('smoke'), ledger_factory=TightLedger)
        self.assertEqual(self.calls, [])
        self.assertFalse(run.stage_dir(self.base, CONFIG, 'smoke').exists())

    def test_unknown_cost_keeps_pending_reservation_and_stops(self):
        body = valid_body(self.route)
        del body['usage']['cost']
        self.raw = json.dumps(body).encode()
        with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
            self.execute('smoke', self.receipt('smoke'))
        self.assertEqual(len(self.calls), 1)
        attempts = [json.loads(x) for x in (run.stage_dir(self.base, CONFIG, 'smoke') / 'attempts.jsonl').read_text().splitlines()]
        self.assertEqual([x['stage'] for x in attempts], ['reserved', 'started', 'response'])
        self.assertTrue(attempts[-1]['cost_unknown'])
        self.assertEqual([x['event'] for x in map(json.loads, self.ledger.read_text().splitlines())], ['budget', 'reserve'])

    def test_invalid_distribution_is_retained_and_stops(self):
        body = valid_body(self.route)
        body['answers']['sentiment']['probabilities']['positive'] = 2
        self.raw = json.dumps(body).encode()
        with self.assertRaises(ValueError):
            self.execute('smoke', self.receipt('smoke'))
        self.assertEqual(len(self.calls), 1)
        rows = [json.loads(x) for x in (run.stage_dir(self.base, CONFIG, 'smoke') / 'attempts.jsonl').read_text().splitlines()]
        self.assertEqual([x['stage'] for x in rows], ['reserved', 'started', 'response', 'parsed'])
        self.assertFalse(rows[-1]['valid'])
        self.assertFalse((run.stage_dir(self.base, CONFIG, 'smoke') / 'completion.json').exists())

    def test_transport_failure_preserves_started_request_and_pending_cost(self):
        def fails(payload, token):
            raise TimeoutError('offline simulated timeout')
        with self.assertRaises(TimeoutError):
            run.execute(CONFIG, 'smoke', self.receipt('smoke'), base=self.base,
                ledger_path=self.ledger, catalog_fetch=lambda route: catalog(route),
                transport=fails, token='offline-fake-token')
        rows = [json.loads(x) for x in (run.stage_dir(self.base, CONFIG, 'smoke') / 'attempts.jsonl').read_text().splitlines()]
        self.assertEqual([x['stage'] for x in rows], ['reserved', 'started', 'transport_error'])
        self.assertTrue(rows[-1]['cost_unknown'])
        self.assertEqual([x['event'] for x in map(json.loads, self.ledger.read_text().splitlines())], ['budget', 'reserve'])

    def test_known_cost_non_200_is_settled_and_retained(self):
        calls = []
        def rejects(payload, token):
            calls.append(payload)
            return 429, self.raw
        with self.assertRaisesRegex(ValueError, 'non-200'):
            run.execute(CONFIG, 'smoke', self.receipt('smoke'), base=self.base,
                ledger_path=self.ledger, catalog_fetch=lambda route: catalog(route),
                transport=rejects, token='offline-fake-token')
        self.assertEqual(len(calls), 1)
        rows = [json.loads(x) for x in (run.stage_dir(self.base, CONFIG, 'smoke') / 'attempts.jsonl').read_text().splitlines()]
        self.assertEqual([x['stage'] for x in rows], ['reserved', 'started', 'response', 'parsed'])
        self.assertEqual(rows[-1]['reason'], 'non_200_http')
        self.assertEqual([x['event'] for x in map(json.loads, self.ledger.read_text().splitlines())], ['budget', 'reserve', 'settle'])

    def test_full_pass_requires_reviewed_smoke_proof(self):
        with self.assertRaises(FileNotFoundError):
            self.execute('fresh1', self.receipt('fresh1', {'smoke': {}}))
        self.assertEqual(self.calls, [])

    def test_jev_route_keeps_its_own_revision_provider_and_pass_bound(self):
        config = 'jev-openrouter-native-p2-choice-v1'
        shutil.copyfile(run.BASE / (config + '.json'), self.base / (config + '.json'))
        manifest = run.load_manifest(config, self.base)
        route = smoke.ROUTES['jev']
        self.assertEqual(manifest['full_pass_catalog_bound_usd'], '0.080640000')
        receipt = Path(self.temp.name) / 'jev-review.json'
        receipt.write_text(json.dumps({'approved': True, 'reviewer': 'offline-test-reviewer',
            'stage_id': config + '-smoke',
            'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'runner_sha256': smoke.sha(Path(run.__file__).read_bytes()),
            'whole_pass_bound_usd': manifest['full_pass_catalog_bound_usd'],
            'stage_bound_usd': manifest['three_record_smoke_catalog_bound_usd'],
            'predecessor_proof': None}))
        raw = json.dumps(valid_body(route)).encode()
        calls = []
        run.execute(config, 'smoke', receipt, base=self.base, ledger_path=self.ledger,
                    catalog_fetch=lambda _: catalog(route),
                    transport=lambda payload, token: (calls.append(payload) or (200, raw)),
                    token='offline-fake-token')
        self.assertEqual(len(calls), 3)
        self.assertEqual(run.inspect_completed(manifest, 'smoke', self.base, self.ledger)['stage_id'],
                         config + '-smoke')


if __name__ == '__main__':
    unittest.main()
