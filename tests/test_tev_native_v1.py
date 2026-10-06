import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import tev_native_v1 as tev
import tev_smoke_v1 as smoke
import openrouter_decision_smoke as native
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority_v4
from development_benchmark import KEYS, VALUES


class TevOfflineTest(unittest.TestCase):
    def test_frozen_input_only_nine_phase_plan(self):
        plan, digest = tev.verify()
        self.assertEqual(digest, native.sha(native.canonical(plan)))
        self.assertEqual([p['id'] for p in plan['phases']],
                         [f'fresh{i}/{condition}' for i in (1, 2, 3)
                          for condition in ('P0', 'P1', 'P2')])
        self.assertEqual([len(p['requests']) for p in plan['phases']], [60] * 9)
        self.assertEqual(plan['smoke_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(plan['max_aggregate_billable_input_tokens'], 131072)
        self.assertEqual(plan['full_context_bound_per_request_usd'], '0.005505024')
        self.assertEqual(plan['three_record_smoke_bound_usd'], '0.016515072')
        for source in ('scripts/openrouter_budget_v2.py', 'scripts/openrouter_budget_v3.py',
                       'scripts/openrouter_budget_v4.py', 'scripts/paid_budget_partitions_v3.py',
                       'scripts/paid_budget_partitions_v4.py',
                       'scripts/openrouter_authority_release_v4.py'):
            self.assertEqual(plan['source_sha256'][source],
                             native.sha((ROOT / source).read_bytes()))
        for phase in plan['phases']:
            for row in phase['requests']:
                request = row['payload']
                self.assertEqual(set(request['state']), {'feedback', 'policy'})
                self.assertEqual(request['provider'], {'only': ['together'], 'allow_fallbacks': False,
                    'max_price': {'prompt': 0.042, 'completion': 0, 'request': 0, 'image': 0}})
                self.assertEqual(native.sha(native.canonical(request)), row['payload_sha256'])

    def test_p0_questions_match_frozen_native_choice_and_variant_only_changes_instructions(self):
        plan, _ = tev.verify()
        cells = {p['id']: p for p in plan['phases']}
        for condition in ('P0', 'P1', 'P2'):
            for row in cells[f'fresh1/{condition}']['requests']:
                request = row['payload']
                tev.check_payload(request, request['state']['feedback'], request['state']['policy'], condition)
            self.assertEqual(cells[f'fresh1/{condition}']['requests_sha256'],
                             cells[f'fresh3/{condition}']['requests_sha256'])

    def test_catalog_route_and_price_drift_rejected(self):
        catalog = json.loads((ROOT / 'results/route-audits/tev-public-20261006-evening/endpoints.json').read_text())
        tev.validate_catalog(catalog)
        for key, replacement in [('tag', 'other'), ('name', 'Together | next'),
                                 ('context_length', 1000), ('max_completion_tokens', 20)]:
            changed = json.loads(json.dumps(catalog))
            changed['data']['endpoints'][0][key] = replacement
            with self.assertRaises(ValueError): tev.validate_catalog(changed)
        changed = json.loads(json.dumps(catalog))
        changed['data']['endpoints'][0]['pricing']['prompt'] = '0.00000005'
        with self.assertRaises(ValueError): tev.validate_catalog(changed)

    def test_choice_parser_retains_optional_measurements_without_inventing_them(self):
        answers = {key: {'type': 'choice', 'choice': next(iter(VALUES[key]))} for key in KEYS}
        body = {'model': tev.VERSION, 'provider': tev.PROVIDER, 'answers': answers,
                'usage': {'input_tokens': 1200, 'output_tokens': 0, 'cost': 0.00001}}
        prediction, optional = smoke.validate_returned(body)
        self.assertEqual(set(prediction), set(KEYS))
        self.assertTrue(all(not item['probabilities_available'] and not item['confidence_available']
                            for item in optional.values()))
        first = KEYS[0]
        body['answers'][first]['probabilities'] = {name: int(name == prediction[first]) for name in VALUES[first]}
        body['answers'][first]['confidence'] = 0.75
        _, optional = smoke.validate_returned(body)
        self.assertTrue(optional[first]['probabilities_available'])
        self.assertEqual(optional[first]['confidence'], 0.75)
        body['answers'][first]['confidence'] = None
        with self.assertRaises(ValueError): smoke.validate_returned(body)

    def test_review_and_exact_budget_precede_send(self):
        self.assertEqual(smoke.CHILD,
                         smoke.BUDGET.parent / f'{smoke.BUDGET.stem}-{smoke.PARTITION_ID}.jsonl')
        with patch.object(smoke, 'post', side_effect=AssertionError('sent')):
            with self.assertRaises(FileNotFoundError):
                smoke.run(smoke.REVIEW, smoke.BUDGET, send=smoke.post)
        with tempfile.TemporaryDirectory() as directory:
            arbitrary = Path(directory) / 'budget.json'
            arbitrary.write_text('{}\n')
            with self.assertRaises(ValueError): smoke.exact_budget(arbitrary)

    def test_exact_budget_accepts_allocator_child_name_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            budget = base / 'budget-manifest.json'
            child = base / f'budget-manifest-{smoke.PARTITION_ID}.jsonl'
            master = base / 'master.jsonl'
            entry = {'id': smoke.PARTITION_ID, 'cap_usd': str(smoke.CAP),
                     'child_ledger': str(child), 'model': tev.MODEL,
                     'provider': tev.PROVIDER, 'reasoning': smoke.REASONING}
            value = {'version': 'paid-partitions-v1', 'master_ledger': str(master),
                     'partitions': [entry]}
            budget.write_text(json.dumps(value) + '\n')
            with patch.object(smoke, 'BUDGET', budget), patch.object(smoke, 'CHILD', child), patch.object(smoke, 'MASTER', master):
                self.assertEqual(smoke.exact_budget(budget), entry)
                value['partitions'][0]['child_ledger'] = str(base / 'budget-wrong.jsonl')
                budget.write_text(json.dumps(value) + '\n')
                with self.assertRaises(ValueError): smoke.exact_budget(budget)

    def test_three_request_run_and_unknown_cost_stop_use_real_temporary_child_ledger(self):
        plan, digest = tev.verify()
        catalog = json.loads((ROOT / 'results/route-audits/tev-public-20261006-evening/endpoints.json').read_text())
        catalog_raw = native.canonical(catalog)
        answers = {key: {'type': 'choice', 'choice': next(iter(VALUES[key]))} for key in KEYS}
        good_wire = native.canonical({'model': tev.VERSION, 'provider': tev.PROVIDER,
            'answers': answers, 'usage': {'input_tokens': 1200, 'output_tokens': 0,
                                          'cost': 0.00001}})
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                master = base / 'master.jsonl'
                master.write_text(json.dumps({'event': 'budget', 'cap_usd': '1'}) + '\n')
                budget = base / 'budget-manifest.json'
                authority_path = base / 'authority.jsonl'
                authority_path.write_text('{}\n')
                child = base / f'{budget.stem}-{smoke.PARTITION_ID}.jsonl'
                with patch.object(budget_v4, 'CAP', Decimal('1')):
                    partitions.allocate(master, budget, [{'id': smoke.PARTITION_ID,
                        'cap_usd': str(smoke.CAP), 'model': tev.MODEL,
                        'provider': tev.PROVIDER, 'reasoning': smoke.REASONING}])
                    review = base / 'smoke.root-review.json'
                    with patch.object(smoke, 'BASE', base), patch.object(smoke, 'BUDGET', budget), \
                         patch.object(smoke, 'CHILD', child), patch.object(smoke, 'MASTER', master), \
                         patch.object(smoke, 'AUTHORITY', authority_path), \
                         patch.object(tev, 'verify', return_value=(plan, digest)), \
                         patch.object(authority_v4, '_scan') as scan, \
                         patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-token'}):
                        receipt = smoke.expected_receipt(plan, digest, budget)
                        receipt['reviewer'] = 'root'
                        review.write_text(json.dumps(receipt) + '\n')
                        scan.return_value = (None, {smoke.PARTITION_ID: {
                            'version': 3, 'funding_pool': 'openrouter_additional',
                            'usd': str(smoke.CAP), 'source_sha256': smoke.hold_source(digest, budget),
                            'budget_manifest_sha256': smoke.sha_path(budget),
                            'budget_manifest_path': str(budget), 'master_path': str(master),
                            'partition_id': smoke.PARTITION_ID}}, {'historical-release'})
                        calls = []
                        def send(payload, token):
                            self.assertEqual(token, 'test-token')
                            calls.append(payload)
                            return (503, b'{"error":"provider unavailable"}') if unknown else (200, good_wire)
                        def fetch():
                            return catalog_raw, catalog
                        if unknown:
                            with self.assertRaises(ValueError):
                                smoke.run(review, budget, base=base, master=master,
                                          authority_path=authority_path, fetch=fetch, send=send)
                        else:
                            smoke.run(review, budget, base=base, master=master,
                                      authority_path=authority_path, fetch=fetch, send=send)
                        self.assertEqual(len(calls), 1 if unknown else 3)
                        events = [json.loads(x) for x in child.read_text().splitlines()]
                        self.assertEqual(sum(x['event'] == 'reserve' for x in events), len(calls))
                        self.assertEqual(sum(x['event'] == 'settle' for x in events), 0 if unknown else 3)
                        raw = [json.loads(x) for x in (base / 'smoke.raw.jsonl').read_text().splitlines()]
                        self.assertEqual(len(raw), len(calls))
                        self.assertEqual(sum(x['event'] == 'stage_completed' for x in
                            (json.loads(line) for line in (base / 'smoke.journal.jsonl').read_text().splitlines())),
                            0 if unknown else 1)
                        with self.assertRaises(FileExistsError):
                            smoke.run(review, budget, base=base, master=master,
                                      authority_path=authority_path, fetch=fetch,
                                      send=lambda *_: self.fail('replayed a claimed Tev request'))


if __name__ == '__main__':
    unittest.main()
