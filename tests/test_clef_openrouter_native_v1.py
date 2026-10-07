import json
import io
from decimal import Decimal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_openrouter_native_v1 as plan
import clef_openrouter_smoke_v1 as smoke
import openrouter_decision_smoke as native


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = plan.build(ROOT)

    def test_all_three_native_routes_have_nine_unadmitted_stages_and_exact_review_inputs(self):
        value = self.value
        self.assertEqual((value['status'], value['inference_performed'], value['allocation_performed'],
                          value['reference_labels_read']), ('prepared_not_admitted', False, False, False))
        self.assertEqual(set(value['models']), {'clef', 'clef-flash', 'luna-decisions'})
        for key, model in value['models'].items():
            self.assertEqual(len(model['stages']), 9)
            self.assertEqual([stage['id'] for stage in model['stages']],
                             [f'{p}/{c}' for p in plan.PASSES for c in plan.CONDITIONS])
            self.assertTrue(all(stage['smoke_status'] == 'unadmitted' and
                                stage['development_status'] == 'unadmitted' for stage in model['stages']))
            for condition in plan.CONDITIONS:
                requests = model['requests'][condition]
                self.assertEqual([item['id'] for item in requests], list(plan.IDS))
                self.assertTrue(all(item['payload']['state']['feedback'] and
                                    set(item['payload']['state']) == {'feedback', 'policy'} and
                                    list(item['payload']['questions']) == ['sentiment', 'follow_up_needed',
                                        'serious_concern_reported', 'testimonial_potential'] and
                                    item['payload']['provider']['only'] == [plan.TAG[key]] and
                                    item['payload']['provider']['allow_fallbacks'] is False
                                    for item in requests))
            self.assertLessEqual(model['state_feedback_max_characters'], 206)
        encoded = json.dumps(value)
        self.assertNotIn('proposed_labels', encoded)
        self.assertTrue(all('reference' not in item['payload']['state']
                            for model in value['models'].values()
                            for requests in model['requests'].values() for item in requests))

    def test_changed_variant_provider_and_public_snapshot_are_rejected(self):
        model = self.value['models']['clef']
        item = model['requests']['P1'][0]
        payload = json.loads(json.dumps(item['payload']))
        payload['provider']['only'] = ['cloudflare/other']
        with self.assertRaisesRegex(ValueError, 'changed input'):
            plan.verify_request(payload, item['payload']['state']['feedback'],
                                item['payload']['state']['policy'], 'clef', 'P1')
        payload = json.loads(json.dumps(item['payload']))
        payload['questions']['sentiment']['instructions'] += ' change'
        with self.assertRaisesRegex(ValueError, 'variant differs'):
            plan.verify_request(payload, item['payload']['state']['feedback'],
                                item['payload']['state']['policy'], 'clef', 'P1')
        snapshot = json.loads((ROOT / plan.catalog_path('clef')).read_text())
        snapshot['response']['data']['endpoints'][0]['pricing']['prompt'] = '0.00000001'
        with self.assertRaisesRegex(ValueError, 'price'):
            plan.validate_catalog('clef', snapshot)

    def test_four_context_bounds_and_saved_plan(self):
        expected = {'clef': '0.06291456', 'clef-flash': '0.02359296',
                    'luna-decisions': '0.4200000'}
        for key, amount in expected.items():
            self.assertEqual(Decimal(amount), plan.bound(key, 1))
            self.assertEqual(plan.bound(key, 3), Decimal(self.value['models'][key]['pricing']['three_smoke_bound_usd']))
        saved, digest = plan.verify(ROOT)
        self.assertEqual(saved, self.value)
        self.assertEqual(digest, native.sha(native.canonical(self.value)))

    def test_money_reader_drift_rejects_saved_plan_before_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = (*plan.SOURCES, *(plan.catalog_path(key) for key in plan.MODELS), plan.PLAN)
            for path in paths:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, root / path)
            plan.verify(root)
            reader = root / 'scripts/openrouter_authority_release_v4.py'
            reader.write_bytes(reader.read_bytes() + b'\n# changed after root review\n')
            with self.assertRaisesRegex(ValueError, 'plan differs'):
                plan.verify(root)


class FakeLedger:
    def __init__(self, key):
        self.master_cap = Decimal('22.38')
        self.cap = plan.bound(key, 3)
        self.closed = False
        self.reserved = {}
        self.actual = Decimal('0')
        self.close_count = 0

    def state(self):
        return None, self.reserved, False

    def accounted(self):
        return self.actual + sum(self.reserved.values(), Decimal('0'))

    def reserve(self, amount, rid):
        ident = 'attempt-' + rid
        self.reserved[ident] = amount
        return ident

    def settle(self, ident, actual):
        reserved = self.reserved[ident]
        if actual > reserved:
            return False
        del self.reserved[ident]
        self.actual += actual
        return True

    def close(self):
        self.close_count += 1


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.value, self.digest = plan.verify(ROOT)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/clef_openrouter_smoke_v1.py',
                        self.root / 'scripts/clef_openrouter_smoke_v1.py')
        self.stage = 'fresh1/P0'
        self.key = 'clef'
        self.folder = smoke.stage_dir(self.root, self.key, self.stage)
        self.folder.mkdir(parents=True)
        self.receipt = self.folder / 'smoke.root-review.json'
        self.receipt.write_text('{}')
        self.budget = self.root / 'budget.json'
        self.budget.write_text('{}')
        self.ledger = FakeLedger(self.key)
        self.catalog = json.loads((ROOT / plan.catalog_path(self.key)).read_text())['response']

    def response(self, payload):
        answers = {}
        for key, question in payload['questions'].items():
            options = list(question['criteria'])
            answers[key] = {'type': 'choice', 'choice': options[0], 'confidence': 1.0,
                            'probabilities': {option: float(i == 0) for i, option in enumerate(options)}}
        return json.dumps({'model': payload['model'], 'provider': 'Cloudflare', 'answers': answers,
                           'usage': {'input_tokens': 2200, 'output_tokens': 0, 'cost': '0.000528'}}).encode()

    def run_with(self, send):
        with mock.patch.object(plan, 'verify', return_value=(self.value, self.digest)), \
                mock.patch.object(smoke, 'verify_review', return_value={}), \
                mock.patch.object(smoke, 'verify_hold', return_value=None), \
                mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
            smoke.run(self.key, self.stage, self.receipt, self.budget, root=self.root,
                      fetch=lambda _: (native.canonical(self.catalog), self.catalog),
                      send=send, open_child=lambda *args: self.ledger)

    def test_success_saves_three_raw_answers_and_settles_only_reported_cost(self):
        calls = []
        def send(payload, token):
            calls.append(payload['state']['feedback'])
            return 200, self.response(payload)
        self.run_with(send)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.ledger.actual, Decimal('0.001584'))
        self.assertEqual(self.ledger.reserved, {})
        self.assertEqual(self.ledger.close_count, 1)
        raw = [json.loads(line) for line in (self.folder / 'smoke.raw.jsonl').read_text().splitlines()]
        parsed = [json.loads(line) for line in (self.folder / 'smoke.parsed.jsonl').read_text().splitlines()]
        self.assertEqual((len(raw), len(parsed)), (3, 3))
        self.assertTrue(all(row['client_request_elapsed_ns'] >= 0 and row['response_base64'] for row in raw))
        with self.assertRaises(FileExistsError):
            self.run_with(send)
        self.assertEqual(len(calls), 3)

    def test_unknown_http_or_transport_stops_first_attempt_without_replay(self):
        calls = []
        def send(payload, token):
            calls.append(payload['state']['feedback'])
            return 429, b'{"error":"provider busy"}'
        with self.assertRaisesRegex(ValueError, 'cost unknown'):
            self.run_with(send)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger.reserved), 1)
        self.assertEqual(len((self.folder / 'smoke.raw.jsonl').read_text().splitlines()), 1)
        self.assertEqual((self.folder / 'smoke.parsed.jsonl').read_text(), '')
        with self.assertRaises(FileExistsError):
            self.run_with(send)

    def test_missing_review_rejects_before_fetch_allocation_or_post(self):
        send = mock.Mock()
        fetch = mock.Mock()
        child = mock.Mock()
        with mock.patch.object(plan, 'verify', return_value=(self.value, self.digest)), \
                self.assertRaisesRegex(ValueError, 'Root review'):
            smoke.run(self.key, self.stage, self.receipt, self.budget, root=self.root,
                      fetch=fetch, send=send, open_child=child)
        fetch.assert_not_called()
        child.assert_not_called()
        send.assert_not_called()

    def test_v4_authority_reader_accepts_active_hold_and_rejects_released_hold(self):
        pid = smoke.partition_id(self.key, self.stage)
        hold = {'version': 3, 'funding_pool': 'openrouter_additional',
                'usd': str(plan.bound(self.key, 3)),
                'source_sha256': smoke.hold_source(self.digest, self.budget, self.key, self.stage),
                'budget_manifest_sha256': smoke.sha_path(self.budget),
                'budget_manifest_path': str(self.budget.resolve()),
                'master_path': str(smoke.MASTER.resolve()), 'partition_id': pid}
        from contextlib import contextmanager
        @contextmanager
        def locked(_):
            yield io.StringIO('v4 authority fixture')
        with mock.patch.object(smoke.authority.old, '_locked', locked), \
                mock.patch.object(smoke.authority, '_scan', return_value=(object(), {pid: hold}, set())):
            smoke.verify_hold(self.digest, self.budget, self.key, self.stage)
        with mock.patch.object(smoke.authority.old, '_locked', locked), \
                mock.patch.object(smoke.authority, '_scan', return_value=(object(), {pid: hold}, {pid})), \
                self.assertRaisesRegex(ValueError, 'hold missing'):
            smoke.verify_hold(self.digest, self.budget, self.key, self.stage)


if __name__ == '__main__':
    unittest.main()
