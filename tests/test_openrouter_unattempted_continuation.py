import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_unattempted_continuation as c


class FrozenOfflinePreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = c.read_inventory()
        cls.manifests = {}
        for candidate in cls.inventory['candidate_conditions']:
            key = (candidate['configuration_id'], candidate['condition'])
            path = c.DEST / (key[0]+'-'+key[1].lower()) / 'draft-manifest.json'
            cls.manifests[key] = json.loads(path.read_text())

    def test_all_ten_exact_suffixes_validate(self):
        self.assertEqual(len(self.manifests), 10)
        self.assertEqual(sum(len(m['remaining_ids']) for m in self.manifests.values()), 400)
        for key, manifest in self.manifests.items():
            with self.subTest(key=key):
                c.validate(manifest, frozen=False)
                self.assertEqual(manifest['remaining_ids'], c.ids(61-len(manifest['remaining_ids'])))
                self.assertFalse(manifest['reference_labels_read'])

    def test_prior_attempt_cannot_be_replayed(self):
        manifest = copy.deepcopy(self.manifests[('qwen27-low-hosted-addendum-v1','P1')])
        manifest['remaining_ids'].insert(0,'DEV-010')
        with self.assertRaises(ValueError): c.validate(manifest, frozen=False)

    def test_missing_source_binding_or_smoke_blocks(self):
        manifest = copy.deepcopy(self.manifests[('openrouter-paid-deepseek-v41-flash-high','P1')])
        manifest['smoke']['sha256']='0'*64
        with self.assertRaises(ValueError): c.validate(manifest, frozen=False)
        manifest = copy.deepcopy(self.manifests[('openrouter-paid-deepseek-v41-flash-high','P1')])
        manifest['source_evidence'][0]['sha256']='0'*64
        with self.assertRaises(ValueError): c.validate(manifest, frozen=False)

    def test_unapproved_execution_stops_before_network(self):
        manifest = self.manifests[('qwen27-low-hosted-addendum-v1','P1')]
        # Even a correctly hashed draft has no authority to call a provider.
        with patch.object(c.paid,'fetch',side_effect=AssertionError('network touched')):
            with self.assertRaisesRegex(ValueError,'Manifest not frozen'):
                c.execute(type('A',(),{'manifest':str(c.DEST/'qwen27-low-hosted-addendum-v1-p1/draft-manifest.json'),
                    'sha256':c.digest((c.DEST/'qwen27-low-hosted-addendum-v1-p1/draft-manifest.json').read_bytes()),
                    'review':'unused','env_file':None})())

    def test_endpoint_metadata_drift_is_ignored_but_price_drift_blocks(self):
        manifest = self.manifests[('qwen27-low-hosted-addendum-v1','P1')]
        row = c.lines(manifest['smoke'])[0]
        endpoint = copy.deepcopy(row['provider_endpoint'])
        endpoint['uptime_last_5m'] = 0
        endpoint['latency_last_30m'] = 9999
        self.assertEqual(c.endpoint_facts(endpoint), manifest['endpoint_facts'])
        endpoint['pricing']['completion'] = '0.0000020'
        self.assertNotEqual(c.endpoint_facts(endpoint), manifest['endpoint_facts'])

    def test_response_stop_policy_rejects_control_and_unknown_billing(self):
        base={'status':'ok','billing_ok':True,'cost_unknown':False,
              'raw_response':{'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}}
        clear={'blockers':[]}
        self.assertTrue(c.may_continue(base,clear,True))
        variants=[]
        for field,value in [('cost_unknown',True),('billing_ok',False),('status','service_error')]:
            item=copy.deepcopy(base);item[field]=value;variants.append(item)
        for field,value in [('tool_calls',[{}]),('function_call',{}),('refusal','no')]:
            item=copy.deepcopy(base);item['raw_response']['choices'][0]['message'][field]=value;variants.append(item)
        item=copy.deepcopy(base);item['raw_response']['error']={'code':429};variants.append(item)
        item=copy.deepcopy(base);item['raw_response']['choices'][0]['error']={'code':429};variants.append(item)
        for item in variants:self.assertFalse(c.may_continue(item,clear,True))
        length=copy.deepcopy(base);length['status']='invalid_output';length['raw_response']['choices'][0]['finish_reason']='length'
        self.assertTrue(c.may_continue(length,{'blockers':['truncation:length']},True))
        self.assertFalse(c.may_continue(length,{'blockers':['truncation:length']},False))

    def test_unknown_billing_requires_full_bound(self):
        manifest = copy.deepcopy(self.manifests[('qwen27-low-hosted-addendum-v1','P1')])
        ledger = c.lines(manifest['historical_ledgers'][0])
        historical = c.lines(manifest['histories'][0]['output'])
        failed_attempt = next(x['attempt_id'] for x in historical if x.get('cost_unknown'))
        unknown = next(x for x in ledger if x['event']=='unknown_cost_accounted_as_upper_bound' and x['attempt_id']==failed_attempt)
        corrupted = [dict(x) for x in ledger]
        for x in corrupted:
            if x.get('attempt_id')==unknown['attempt_id'] and x['event']=='unknown_cost_accounted_as_upper_bound': x['usd']='0'
        with patch.object(c,'lines',side_effect=lambda binding: corrupted if binding==manifest['historical_ledgers'][0] else [json.loads(line) for line in c.bound(binding).splitlines() if line.strip()]):
            with self.assertRaisesRegex(ValueError,'not fully bound'): c.history_attempts(manifest)

if __name__=='__main__':unittest.main()
