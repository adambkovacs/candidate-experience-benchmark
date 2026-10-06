import json
import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import liquid_d1_full_execution_v1 as full
import liquid_d1_native_v1 as liquid
import openrouter_decision_smoke as native
from development_benchmark import KEYS, VALUES


class LiquidFullOfflineTest(unittest.TestCase):
    def test_nine_exact_request_sets_and_no_truncation_plan(self):
        value=full.manifest_value()
        plan,_=liquid.verify()
        self.assertEqual(value['status'],'offline_prepared_unapproved')
        self.assertFalse(value['inference_authorized'])
        self.assertEqual(value['phase_order'],[p['id'] for p in plan['phases']])
        self.assertEqual(value['new_smoke_stage_count'],8)
        self.assertEqual(value['development_stage_count'],9)
        self.assertEqual(value['per_request_full_context_reserve_usd'],'0.01048576')
        self.assertEqual(value['proposed_child_cap_usd'],'1.00')
        for phase in plan['phases']:
            self.assertEqual(len(phase['requests']),60)
            self.assertEqual(value['request_sets'][phase['id']],phase['requests_sha256'])
            self.assertEqual(value['max_canonical_request_bytes'][phase['id']],
                             max(len(native.canonical(r['payload'])) for r in phase['requests']))
        self.assertIn('not an all-record token proof',value['context_preflight'])

    def test_original_smoke_cannot_be_replayed(self):
        with self.assertRaises(ValueError):full.stage_paths('fresh1/P0','smoke')
        self.assertEqual(full.stage_rows('fresh1/P0','development')[0]['id'],'DEV-001')
        self.assertEqual([r['id'] for r in full.stage_rows('fresh1/P1','smoke')],
                         ['DEV-001','DEV-002','DEV-003'])

    @unittest.skipUnless((liquid.BASE/'smoke.raw.jsonl').exists(),
                         'Private original smoke raw evidence is unavailable in clean checkout')
    def test_original_smoke_predecessor_survives_v4_authority_release(self):
        self.assertEqual(full.verify_original_smoke_runtime()['status'],'three_record_smoke_closed')
        full.require_order('fresh1/P0','development')

    def test_no_stage_without_budget_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(full,'BASE',Path(directory)):
                with self.assertRaises(ValueError):full.stage_template('fresh1/P0','development')
            with patch.object(full,'smoke') as fake:
                fake.post.side_effect=AssertionError('network call')
                with self.assertRaises((FileNotFoundError,ValueError)):
                    full.execute('fresh1/P0','development',Path(directory)/'missing.json',send=fake.post)
                fake.post.assert_not_called()

    def test_closure_rejects_absent_stage(self):
        with self.assertRaises(FileNotFoundError):full.verify_phase_closure('fresh1/P0','development')

    def test_synthetic_closure_checks_exact_child_settlement(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);stage='fresh1/P1';mode='development';folder=base/stage
            folder.mkdir(parents=True)
            manifest=base/'manifest.json';manifest.write_text('{}\n')
            review=folder/'development.root-review.json';review.write_text('{}\n')
            item=liquid.verify()[0]['phases'][1]['requests'][0]
            aid='test-attempt-1';rid=item['id'];cost='0.00000400'
            choices={}
            for key in KEYS:
                labels=list(VALUES[key])
                choices[key]={'type':'choice','choice':labels[0],'confidence':1.0,
                              'probabilities':{label:float(label==labels[0]) for label in labels}}
            body={'model':liquid.VERSION,'provider':liquid.PROVIDER,'answers':choices,
                  'usage':{'input_tokens':100,'output_tokens':0,'cost':0.000004}}
            wire=native.canonical(body)
            catalog=(liquid.BASE/'endpoint-public.json').read_bytes()
            expected={'id':stage,'requests_sha256':'synthetic-set','requests':[item]}
            claim={'manifest_sha256':native.sha(manifest.read_bytes()),'stage':stage,'mode':mode,
                   'request_set_sha256':'synthetic-set','root_review_sha256':native.sha(review.read_bytes()),
                   'reference_labels_sent':False}
            journal=[{'event':'phase_started','stage':stage,'mode':mode},
                     {'event':'request_intent','id':rid,'payload_sha256':item['payload_sha256']},
                     {'event':'request_started','id':rid,'attempt_id':aid,
                      'payload_sha256':item['payload_sha256'],
                      'live_endpoint_sha256':native.sha(catalog),
                      'live_endpoint_base64':base64.b64encode(catalog).decode()},
                     {'event':'request_finished','id':rid,'attempt_id':aid,'status':'ok','actual_cost_usd':cost},
                     {'event':'phase_completed','stage':stage,'mode':mode,'request_count':1,'intrinsic_invalid_count':0}]
            raw=[{'id':rid,'attempt_id':aid,'payload_sha256':item['payload_sha256'],
                  'http_status':200,'response_sha256':native.sha(wire),
                  'response_base64':base64.b64encode(wire).decode()}]
            attempts=[{'id':rid,'attempt_id':aid,'status':'ok','cost_unknown':False,'actual_cost_usd':cost}]
            parsed=[{'id':rid,'attempt_id':aid,'prediction':{key:list(VALUES[key])[0] for key in KEYS},
                     'actual_cost_usd':cost}]
            ledger=base/'child.jsonl'
            def write_jsonl(path, records):
                path.write_text(''.join(json.dumps(x)+'\n' for x in records))
            (folder/'development.claim.json').write_text(json.dumps(claim)+'\n')
            for name,records in [('journal',journal),('raw',raw),('attempts',attempts),('parsed',parsed)]:
                write_jsonl(folder/f'development.{name}.jsonl',records)
            pair=[{'event':'budget','cap_usd':'1.00'},
                  {'event':'reserve','attempt_id':aid,'record_id':stage+':'+mode+':'+rid,'usd':str(liquid.BOUND)},
                  {'event':'settle','attempt_id':aid,'usd':cost}]
            write_jsonl(ledger,pair)
            with patch.object(full,'BASE',base),patch.object(full,'MANIFEST',manifest),patch.object(full,'CHILD',ledger),\
                 patch.object(full,'phase',return_value=expected),patch.object(full,'stage_rows',return_value=[item]):
                self.assertEqual(full.verify_phase_closure(stage,mode)['known_valid_count'],1)
                pair[1]['record_id']='wrong'
                write_jsonl(ledger,pair)
                with self.assertRaises(ValueError):full.verify_phase_closure(stage,mode)
                pair[1]['record_id']=stage+':'+mode+':'+rid
                write_jsonl(ledger,pair)
                body['answers'][KEYS[0]]['choice']=[]
                invalid_wire=native.canonical(body)
                raw[0]['response_base64']=base64.b64encode(invalid_wire).decode()
                raw[0]['response_sha256']=native.sha(invalid_wire)
                attempts[0]['status']='invalid_native'
                parsed[0]['prediction']=None
                journal[3]['status']='invalid_native'
                journal[-1]['intrinsic_invalid_count']=1
                write_jsonl(folder/'development.raw.jsonl',raw)
                write_jsonl(folder/'development.attempts.jsonl',attempts)
                write_jsonl(folder/'development.parsed.jsonl',parsed)
                write_jsonl(folder/'development.journal.jsonl',journal)
                self.assertEqual(full.verify_phase_closure(stage,mode)['intrinsic_invalid_count'],1)

if __name__=='__main__':unittest.main()
