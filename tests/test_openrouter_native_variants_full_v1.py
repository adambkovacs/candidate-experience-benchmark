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
import openrouter_native_variants_full_v1 as full
import paid_budget_partitions_v3 as partitions


class NativeFullV1Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'proposed'
        self.master = Path(self.temp.name) / 'master.jsonl'
        self.authority = Path(self.temp.name) / 'authority.jsonl'
        self.config = 'kev-openrouter-native-p1-choice-v1'
        full.prepare(self.config, self.base)
        self.manifest = full.verify(self.config, self.base)
        self.p = full.paths(self.base, self.config, 'fresh1')
        master = budget_v3.BudgetLedger(self.master)
        master.close()
        self.authority.write_text(json.dumps({'event': 'authority',
            'kind': 'postapproval-paid-work-v1', 'cap_usd': '10.00',
            'decision_key': full.smoke_v2.AUTHORITY_DECISION_KEY,
            'approval_sha256': full.smoke_v2.AUTHORITY_APPROVAL_SHA}) + '\n')

    def reviews_and_allocation(self):
        self.p['context'].write_text(json.dumps({
            'schema': full.SCHEMA + '-context-estimate-review', 'approved': True,
            'reviewer': 'root', 'configuration_id': self.config,
            'estimate_sha256': full.smoke_v2.file_sha(self.p['estimate']),
            'request_set_sha256': self.manifest['request_set_sha256'],
            'method': 'reviewed_conservative_estimate',
            'provider_guarantee_claimed': False,
            'full_context_money_reservation': True,
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw'}) + '\n')
        self.p['inspection'].write_text(json.dumps({
            'schema': full.SCHEMA + '-smoke-inspection', 'reviewer': 'root',
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
        context_sha = full.context_proof(self.config, self.manifest, base=self.base)
        inspect_sha = full.smoke_inspection(self.config, self.manifest, base=self.base)
        prior = full.predecessor(self.config, 'fresh1', self.manifest, base=self.base)
        identity = full.budget_identity(self.config, 'fresh1', self.manifest,
                                        self.p['budget'], base=self.base, master=self.master)
        receipt = full.expected_receipt(self.config, 'fresh1', self.manifest,
            self.p['budget'], context_sha, inspect_sha, prior, identity, base=self.base)
        receipt['global_authority_head_sha256'] = hashlib.sha256(self.authority.read_bytes()).hexdigest()
        self.p['receipt'].write_text(json.dumps(receipt) + '\n')

    def catalog(self, _route):
        return json.loads((ROOT / 'results/route-audits/native-variants-recheck-20261006' /
                           'kev-endpoint.raw.json').read_text())

    def p0_bodies(self):
        path = ROOT / 'results/route-audits/decision-kev-development-20260930/attempts.jsonl'
        return [json.dumps(x['body'], separators=(',', ':')).encode() for x in
                (json.loads(line) for line in path.read_text().splitlines() if line.strip())
                if x.get('stage') == 'response']

    def execute(self, transport):
        return full.execute(self.config, 'fresh1', self.p['receipt'], self.p['budget'],
            base=self.base, master=self.master, authority=self.authority,
            catalog_fetch=self.catalog, transport=transport, token='fake')

    def test_estimate_is_bound_to_two_actual_p0_passes_and_smoke(self):
        estimate = json.loads(self.p['estimate'].read_text())
        self.assertEqual(estimate['max_p0_provider_input_tokens'], 1879)
        self.assertEqual(estimate['max_estimated_input_token_upper_bound'], 4191)
        self.assertEqual(len(estimate['per_record']), 60)
        self.assertEqual({x['added_instruction_utf8_bytes'] for x in estimate['per_record']}, {1028})
        self.assertEqual([x['observed_added_tokens'] for x in estimate['smoke_observed_input_tokens']],
                         [200, 200, 200])
        self.assertFalse(estimate['provider_guarantee'])

    def test_p2_estimate_binds_its_separate_closed_smoke(self):
        config = 'kev-openrouter-native-p2-choice-v1'
        value = full.build_manifest(config)
        estimate = full.kev_context_estimate(config, full.frozen.build_plan(ROOT)[config])
        self.assertEqual(value['context_review_mode'], 'reviewed_conservative_estimate')
        self.assertEqual(estimate['max_estimated_input_token_upper_bound'], 6187)
        self.assertEqual({x['added_instruction_utf8_bytes'] for x in estimate['per_record']},
                         {2026})
        self.assertEqual([x['observed_added_tokens'] for x in estimate['smoke_observed_input_tokens']],
                         [371, 371, 371])

    def test_missing_review_blocks_before_paid_admission(self):
        with self.assertRaises(FileNotFoundError):
            full.execute(self.config, 'fresh1', None, None, base=self.base,
                         master=self.master, authority=self.authority,
                         catalog_fetch=self.catalog, transport=lambda *_: self.fail('sent'),
                         token='fake')
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())

    def test_fake_sixty_record_success_and_no_replay(self):
        self.reviews_and_allocation()
        replies = iter(self.p0_bodies())
        result = self.execute(lambda *_: (200, next(replies)))
        self.assertEqual(result['valid_count'], 60)
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 240)
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        with self.assertRaises(FileExistsError):
            self.execute(lambda *_: self.fail('replayed'))

    def test_provider_context_rejection_stops_without_retry(self):
        self.reviews_and_allocation()
        with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
            self.execute(lambda *_: (422, b'{"error":{"message":"context exceeded"}}'))
        self.assertFalse((self.p['stage'] / 'completion.json').exists())
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 3)
        child = self.p['budget'].parent / (self.p['budget'].stem + '-' +
            self.manifest['passes'][0]['partition_id'] + '.jsonl')
        self.assertEqual([json.loads(x)['event'] for x in child.read_text().splitlines()],
                         ['budget', 'reserve'])

    def test_intrinsic_invalid_is_retained_and_later_ids_complete(self):
        self.reviews_and_allocation()
        replies = self.p0_bodies()
        second = json.loads(replies[1])
        second['answers']['sentiment']['probabilities']['positive'] = 2
        replies[1] = json.dumps(second, separators=(',', ':')).encode()
        stream = iter(replies)
        result = self.execute(lambda *_: (200, next(stream)))
        self.assertEqual(result['valid_count'], 59)
        self.assertEqual(result['invalid_count'], 1)
        self.assertEqual(result['invalid_ids'], ['DEV-002'])
        self.assertEqual(len((self.p['stage'] / 'attempts.jsonl').read_text().splitlines()), 240)

    def test_second_build_drift_blocks_before_hold(self):
        self.reviews_and_allocation()
        original = full.frozen.build_plan(ROOT)
        changed = deepcopy(original)
        item = changed[self.config]['requests'][3]
        item['payload']['state']['feedback'] += ' changed after review'
        item['payload_sha256'] = full.smoke_v2.sha(full.decision.canonical(item['payload']))
        changed[self.config]['requests_sha256'] = full.smoke_v2.sha(
            full.decision.canonical(changed[self.config]['requests']))
        # Initial verify rebuilds via smoke_v2 and full; feed correct state for
        # both, then mutate only the lock-protected final rebuild.
        with mock.patch.object(full.frozen, 'build_plan', side_effect=[original, original,
                                                                      original, changed]):
            with self.assertRaisesRegex(ValueError, 'Current full request set differs'):
                self.execute(lambda *_: self.fail('sent'))
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())


if __name__ == '__main__':
    unittest.main()
