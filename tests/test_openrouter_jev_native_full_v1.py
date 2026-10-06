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
import openrouter_jev_native_full_v1 as jev
import paid_budget_partitions_v3 as partitions


class JevNativeFullV1Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'proposed'
        self.master = Path(self.temp.name) / 'master.jsonl'
        self.authority = Path(self.temp.name) / 'authority.jsonl'
        self.config = jev.CONFIGS[0]
        jev.prepare(self.config, self.base)
        self.manifest = jev.verify(self.config, self.base)
        self.p = jev.paths(self.base, self.config, 'fresh1')
        ledger = budget_v3.BudgetLedger(self.master)
        ledger.close()
        self.authority.write_text(json.dumps({'event': 'authority',
            'kind': 'postapproval-paid-work-v1', 'cap_usd': '10.00',
            'decision_key': jev.smoke_v2.AUTHORITY_DECISION_KEY,
            'approval_sha256': jev.smoke_v2.AUTHORITY_APPROVAL_SHA}) + '\n')

    def review_and_allocation(self):
        self.p['context'].write_text(json.dumps({
            'schema': jev.full.SCHEMA + '-context-estimate-review', 'approved': True,
            'reviewer': 'root', 'configuration_id': self.config,
            'estimate_sha256': jev.smoke_v2.file_sha(self.p['estimate']),
            'request_set_sha256': self.manifest['request_set_sha256'],
            'method': 'reviewed_conservative_estimate',
            'provider_guarantee_claimed': False,
            'full_context_money_reservation': True,
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw'}) + '\n')
        self.p['inspection'].write_text(json.dumps({
            'schema': jev.full.SCHEMA + '-smoke-inspection', 'reviewer': 'root',
            'configuration_id': self.config,
            'smoke_completion_sha256': self.manifest['smoke_proof']['completion_sha256'],
            'smoke_attempts_sha256': self.manifest['smoke_proof']['attempts_sha256'],
            'all_three_raw_distributions_inspected': True,
            'approved_for_full_pass_review': True}) + '\n')
        pid = self.manifest['passes'][0]['partition_id']
        partitions.allocate(self.master, self.p['budget'], [{
            'id': pid, 'cap_usd': self.manifest['whole_pass_bound_usd'],
            'model': self.manifest['model'], 'provider': self.manifest['provider_tag'],
            'reasoning': 'none'}])
        context_sha = jev.full.context_proof(self.config, self.manifest, base=self.base)
        inspect_sha = jev.full.smoke_inspection(self.config, self.manifest, base=self.base)
        prior = jev.full.predecessor(self.config, 'fresh1', self.manifest, base=self.base)
        identity = jev.full.budget_identity(self.config, 'fresh1', self.manifest,
                                            self.p['budget'], base=self.base, master=self.master)
        receipt = jev.expected_receipt(self.config, 'fresh1', self.manifest,
            self.p['budget'], context_sha, inspect_sha, prior, identity, base=self.base)
        receipt['global_authority_head_sha256'] = hashlib.sha256(self.authority.read_bytes()).hexdigest()
        self.p['receipt'].write_text(json.dumps(receipt) + '\n')

    def catalog(self, _route):
        return json.loads((ROOT / 'results/route-audits/native-variants-recheck-20261006' /
                           'jev-endpoint.raw.json').read_text())

    def p0_bodies(self):
        rows = [json.loads(x) for x in jev.P0_ATTEMPTS.read_text().splitlines()]
        bodies = [json.dumps(x['body'], separators=(',', ':')).encode() for x in rows
                  if x.get('stage') == 'response']
        return (bodies * 20)

    def execute(self, transport):
        return jev.execute(self.config, 'fresh1', self.p['receipt'], self.p['budget'],
            base=self.base, master=self.master, authority=self.authority,
            catalog_fetch=self.catalog, transport=transport, token='fake')

    def test_context_estimate_binds_smokes_and_all_sixty_exact_byte_deltas(self):
        estimate = json.loads(self.p['estimate'].read_text())
        self.assertEqual(len(estimate['per_record']), 60)
        self.assertEqual(estimate['max_estimated_input_token_upper_bound'], 27596)
        self.assertEqual({x['added_instruction_utf8_bytes'] for x in estimate['per_record']}, {1028})
        self.assertEqual([x['observed_added_tokens'] for x in estimate['smoke_observed_input_tokens']],
                         [204, 204, 204])
        self.assertIn('absent', estimate['openrouter_p0_full_pass_status'])
        self.assertFalse(estimate['provider_guarantee'])

    def test_p2_separate_smoke_and_maximum(self):
        config = jev.CONFIGS[1]
        estimate = jev.jev_context_estimate(config, jev.frozen.build_plan()[config])
        self.assertEqual(estimate['max_estimated_input_token_upper_bound'], 29592)
        self.assertEqual({x['added_instruction_utf8_bytes'] for x in estimate['per_record']}, {2026})
        self.assertEqual([x['observed_added_tokens'] for x in estimate['smoke_observed_input_tokens']],
                         [381, 381, 381])

    def test_missing_root_review_prevents_admission(self):
        with self.assertRaises(FileNotFoundError):
            jev.execute(self.config, 'fresh1', None, None, base=self.base,
                        master=self.master, authority=self.authority,
                        catalog_fetch=self.catalog, transport=lambda *_: self.fail('sent'),
                        token='fake')
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())

    def test_fake_full_pass_and_no_replay(self):
        self.review_and_allocation()
        responses = iter(self.p0_bodies())
        result = self.execute(lambda *_: (200, next(responses)))
        self.assertEqual(result['valid_count'], 60)
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 240)
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        with self.assertRaises(FileExistsError):
            self.execute(lambda *_: self.fail('replayed'))

    def test_context_rejection_retains_unknown_reservation(self):
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
        receipt['execution_adapter_sha256'] = '0' * 64
        self.p['receipt'].write_text(json.dumps(receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'Independent full-pass receipt differs'):
            self.execute(lambda *_: self.fail('sent'))
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())

    def test_request_drift_blocks_before_hold(self):
        self.review_and_allocation()
        original = jev.frozen.build_plan(ROOT)
        changed = deepcopy(original)
        item = changed[self.config]['requests'][3]
        item['payload']['state']['feedback'] += ' changed after review'
        item['payload_sha256'] = jev.smoke_v2.sha(jev.decision.canonical(item['payload']))
        changed[self.config]['requests_sha256'] = jev.smoke_v2.sha(
            jev.decision.canonical(changed[self.config]['requests']))
        with mock.patch.object(jev.frozen, 'build_plan', side_effect=[original] * 4 + [changed]):
            with self.assertRaisesRegex(ValueError, 'Current full request set differs'):
                self.execute(lambda *_: self.fail('sent'))
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())


if __name__ == '__main__':
    unittest.main()
