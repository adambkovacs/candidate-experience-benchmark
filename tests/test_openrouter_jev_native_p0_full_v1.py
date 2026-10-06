import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import openrouter_budget_v3 as budget_v3
import openrouter_jev_native_p0_full_v1 as p0
import paid_budget_partitions_v3 as partitions


class JevNativeP0FullV1Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'proposed'
        self.master = Path(self.temp.name) / 'master.jsonl'
        self.authority = Path(self.temp.name) / 'authority.jsonl'
        p0.prepare(base=self.base)
        self.manifest = p0.verify(base=self.base)
        self.p = p0.paths(self.base, stage='fresh1')
        ledger = budget_v3.BudgetLedger(self.master)
        ledger.close()
        self.authority.write_text(json.dumps({'event': 'authority',
            'kind': 'postapproval-paid-work-v1', 'cap_usd': '10.00',
            'decision_key': p0.smoke_v2.AUTHORITY_DECISION_KEY,
            'approval_sha256': p0.smoke_v2.AUTHORITY_APPROVAL_SHA}) + '\n')

    def review_and_allocation(self):
        self.p['context'].write_text(json.dumps({
            'schema': p0.full.SCHEMA + '-context-estimate-review', 'approved': True,
            'reviewer': 'root', 'configuration_id': p0.CONFIG,
            'estimate_sha256': p0.smoke_v2.file_sha(self.p['estimate']),
            'request_set_sha256': self.manifest['request_set_sha256'],
            'method': 'reviewed_conservative_estimate',
            'provider_guarantee_claimed': False,
            'full_context_money_reservation': True,
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw'}) + '\n')
        self.p['inspection'].write_text(json.dumps({
            'schema': p0.full.SCHEMA + '-p0-smoke-inspection', 'reviewer': 'root',
            'configuration_id': p0.CONFIG,
            'p0_smoke_manifest_sha256': self.manifest['smoke_proof']['p0_smoke_manifest_sha256'],
            'p0_smoke_attempts_sha256': self.manifest['smoke_proof']['p0_smoke_attempts_sha256'],
            'all_three_raw_distributions_inspected': True,
            'approved_for_full_pass_review': True}) + '\n')
        pid = self.manifest['passes'][0]['partition_id']
        partitions.allocate(self.master, self.p['budget'], [{
            'id': pid, 'cap_usd': self.manifest['whole_pass_bound_usd'],
            'model': self.manifest['model'], 'provider': self.manifest['provider_tag'],
            'reasoning': 'none'}])
        context_sha = p0.full.context_proof(p0.CONFIG, self.manifest, base=self.base)
        inspect_sha = p0.smoke_inspection(p0.CONFIG, self.manifest, base=self.base)
        prior = p0.predecessor(p0.CONFIG, 'fresh1', self.manifest, base=self.base)
        identity = p0.full.budget_identity(p0.CONFIG, 'fresh1', self.manifest,
                                           self.p['budget'], base=self.base, master=self.master)
        receipt = p0.expected_receipt(p0.CONFIG, 'fresh1', self.manifest,
            self.p['budget'], context_sha, inspect_sha, prior, identity, base=self.base)
        receipt['global_authority_head_sha256'] = hashlib.sha256(self.authority.read_bytes()).hexdigest()
        self.p['receipt'].write_text(json.dumps(receipt) + '\n')

    def catalog(self, _route):
        return json.loads((ROOT / 'results/route-audits/native-variants-recheck-20261006' /
                           'jev-endpoint.raw.json').read_text())

    def p0_bodies(self):
        rows = [json.loads(x) for x in p0.jev.P0_ATTEMPTS.read_text().splitlines()]
        bodies = [json.dumps(x['body'], separators=(',', ':')).encode() for x in rows
                  if x.get('stage') == 'response']
        return bodies * 20

    def execute(self, transport):
        return p0.execute(p0.CONFIG, 'fresh1', self.p['receipt'], self.p['budget'],
            base=self.base, master=self.master, authority=self.authority,
            catalog_fetch=self.catalog, transport=transport, token='fake')

    def test_exact_sixty_p0_requests_and_smoke_only_status(self):
        plan = p0.build_plan()[p0.CONFIG]
        self.assertEqual(len(plan['requests']), 60)
        self.assertEqual([x['id'] for x in plan['requests']], p0.IDS)
        self.assertTrue(all(x['payload_sha256'] == x['p0_payload_sha256'] for x in plan['requests']))
        self.assertTrue(all(set(x['payload']['state']) == {'feedback', 'policy'} for x in plan['requests']))
        self.assertEqual(self.manifest['smoke_proof']['scope'], 'three_records_only_no_full_P0')
        self.assertEqual([x['stage'] for x in self.manifest['passes']], list(p0.full.PASSES))

    def test_context_estimate_is_bound_to_historical_raw_smoke(self):
        estimate = json.loads(self.p['estimate'].read_text())
        self.assertEqual(len(estimate['per_record']), 60)
        self.assertEqual(estimate['max_canonical_utf8_bytes'], 10722)
        self.assertEqual(estimate['max_estimated_input_token_upper_bound'], 25540)
        self.assertEqual([x['p0_provider_input_tokens'] for x in estimate['smoke_observed_input_tokens']],
                         [2345, 2319, 2343])
        self.assertFalse(estimate['provider_guarantee'])
        self.assertIn('absent', estimate['openrouter_p0_full_pass_status'])

    def test_missing_review_blocks_before_paid_admission(self):
        with self.assertRaises(FileNotFoundError):
            p0.execute(p0.CONFIG, 'fresh1', None, None, base=self.base,
                       master=self.master, authority=self.authority,
                       catalog_fetch=self.catalog, transport=lambda *_: self.fail('sent'),
                       token='fake')
        self.assertFalse(self.p['stage'].exists())
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)

    def test_fake_full_pass_and_no_replay(self):
        self.review_and_allocation()
        responses = iter(self.p0_bodies())
        completed = self.execute(lambda *_: (200, next(responses)))
        self.assertEqual(completed['valid_count'], 60)
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 240)
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        self.assertEqual(p0.predecessor(p0.CONFIG, 'fresh2', self.manifest, base=self.base)
                         ['previous_completion_sha256'], p0.smoke_v2.file_sha(self.p['stage'] / 'completion.json'))
        with self.assertRaises(FileExistsError):
            self.execute(lambda *_: self.fail('replayed'))

    def test_context_rejection_preserves_unknown_reservation(self):
        self.review_and_allocation()
        with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
            self.execute(lambda *_: (422, b'{"error":{"message":"context exceeded"}}'))
        self.assertFalse((self.p['stage'] / 'completion.json').exists())
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 3)
        child = self.p['budget'].parent / (self.p['budget'].stem + '-' +
            self.manifest['passes'][0]['partition_id'] + '.jsonl')
        self.assertEqual([json.loads(x)['event'] for x in child.read_text().splitlines()],
                         ['budget', 'reserve'])

    def test_adapter_receipt_tamper_blocks_before_hold(self):
        self.review_and_allocation()
        receipt = json.loads(self.p['receipt'].read_text())
        receipt['p0_adapter_sha256'] = '0' * 64
        self.p['receipt'].write_text(json.dumps(receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'Independent full-pass receipt differs'):
            self.execute(lambda *_: self.fail('sent'))
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())

    def test_request_drift_blocks_before_hold(self):
        self.review_and_allocation()
        original = p0.build_plan(ROOT)
        changed = deepcopy(original)
        item = changed[p0.CONFIG]['requests'][3]
        item['payload']['state']['feedback'] += ' changed after review'
        item['payload_sha256'] = p0.smoke_v2.sha(p0.decision.canonical(item['payload']))
        item['p0_payload_sha256'] = item['payload_sha256']
        changed[p0.CONFIG]['requests_sha256'] = p0.smoke_v2.sha(
            p0.decision.canonical(changed[p0.CONFIG]['requests']))
        with mock.patch.object(p0, 'build_plan', side_effect=[original] * 2 + [changed]):
            with self.assertRaisesRegex(ValueError, 'Current full request set differs'):
                self.execute(lambda *_: self.fail('sent'))
        self.assertFalse(self.p['stage'].exists())
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
