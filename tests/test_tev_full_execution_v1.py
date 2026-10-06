import json
import base64
from decimal import Decimal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import tev_full_execution_v1 as full
import tev_native_v1 as tev
import openrouter_decision_smoke as native
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
from development_benchmark import KEYS, VALUES


class TevFullOfflineTest(unittest.TestCase):
    def test_nine_exact_request_sets_and_no_truncation_plan(self):
        value=full.manifest_value()
        plan,_=tev.verify()
        self.assertEqual(value['status'],'offline_prepared_unapproved')
        self.assertFalse(value['inference_authorized'])
        self.assertEqual(value['phase_order'],[p['id'] for p in plan['phases']])
        self.assertEqual(value['new_smoke_stage_count'],8)
        self.assertEqual(value['development_stage_count'],9)
        self.assertEqual(value['per_request_full_context_reserve_usd'],'0.005505024')
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

    def test_archived_smoke_is_reconstructed_from_committed_evidence(self):
        self.assertEqual(full.original_smoke_archived()['status'],'three_record_smoke_closed')

    def test_archived_smoke_rejects_changed_raw_in_copied_checkout(self):
        plan,digest=tev.verify()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            files=('smoke.closure-audit.json','smoke-inspection.root.json',
                   'smoke.reconciliation.json','smoke.raw.jsonl','smoke.attempts.jsonl',
                   'smoke.parsed.jsonl','smoke.journal.jsonl',
                   'smoke.closure-ledger-snapshot.jsonl')
            for name in files:
                shutil.copy2(tev.BASE/name,base/name)
            child=base/full.smoke.CHILD.name
            shutil.copy2(full.smoke.CHILD,child)
            with patch.object(tev,'BASE',base),patch.object(tev,'verify',return_value=(plan,digest)),\
                 patch.object(full.smoke,'CHILD',child):
                self.assertEqual(full.original_smoke_archived()['status'],'three_record_smoke_closed')
                (base/'smoke.raw.jsonl').write_bytes((base/'smoke.raw.jsonl').read_bytes()+b'\n')
                with self.assertRaises(ValueError):full.original_smoke_archived()

    def test_original_smoke_predecessor_survives_v4_authority_release(self):
        reconciliation=json.loads((tev.BASE/'smoke.reconciliation.json').read_text())['partition_reconciled']
        if reconciliation['child_ledger']!=str(full.smoke.CHILD.resolve()):
            self.skipTest('Historical live authority belongs to another checkout path')
        self.assertEqual(full.verify_original_smoke_runtime()['status'],'three_record_smoke_closed')
        full.require_order('fresh1/P0','development')

    def test_no_stage_without_budget_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(full,'BASE',Path(directory)):
                with self.assertRaises((FileNotFoundError,ValueError)):full.stage_template('fresh1/P0','development')
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
            item=tev.verify()[0]['phases'][1]['requests'][0]
            aid='test-attempt-1';rid=item['id'];cost='0.0000042'
            choices={}
            for key in KEYS:
                labels=list(VALUES[key])
                choices[key]={'type':'choice','choice':labels[0]}
            body={'model':tev.VERSION,'provider':tev.PROVIDER,'answers':choices,
                  'usage':{'input_tokens':100,'output_tokens':8,'cost':0.0000042}}
            wire=native.canonical(body)
            catalog=(tev.BASE/'../route-audits/tev-public-20261006-evening/endpoints.json').read_bytes()
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
                     'optional':{key:{'probabilities':None,'confidence':None,
                         'probabilities_available':False,'confidence_available':False} for key in KEYS},
                     'input_tokens':100,'output_tokens':8,'actual_cost_usd':cost}]
            ledger=base/'child.jsonl'
            def write_jsonl(path, records):
                path.write_text(''.join(json.dumps(x)+'\n' for x in records))
            (folder/'development.claim.json').write_text(json.dumps(claim)+'\n')
            for name,records in [('journal',journal),('raw',raw),('attempts',attempts),('parsed',parsed)]:
                write_jsonl(folder/f'development.{name}.jsonl',records)
            pair=[{'event':'budget','cap_usd':'1.00'},
                  {'event':'reserve','attempt_id':aid,'record_id':stage+':'+mode+':'+rid,'usd':str(tev.BOUND)},
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
                write_jsonl(ledger,pair+[{'event':'partition_closed','reason':'terminal reconciliation'}])
                self.assertEqual(full.verify_phase_closure(stage,mode)['known_valid_count'],1)
                write_jsonl(ledger,pair)
                body['answers'][KEYS[0]]['choice']=[]
                invalid_wire=native.canonical(body)
                raw[0]['response_base64']=base64.b64encode(invalid_wire).decode()
                raw[0]['response_sha256']=native.sha(invalid_wire)
                attempts[0]['status']='invalid_native'
                parsed[0]['prediction']=None
                parsed[0]['optional']=None
                journal[3]['status']='invalid_native'
                journal[-1]['intrinsic_invalid_count']=1
                write_jsonl(folder/'development.raw.jsonl',raw)
                write_jsonl(folder/'development.attempts.jsonl',attempts)
                write_jsonl(folder/'development.parsed.jsonl',parsed)
                write_jsonl(folder/'development.journal.jsonl',journal)
                self.assertEqual(full.verify_phase_closure(stage,mode)['intrinsic_invalid_count'],1)

    def test_mocked_full_stage_settles_or_stops_unknown_without_replay(self):
        item=tev.verify()[0]['phases'][0]['requests'][0]
        catalog=json.loads((ROOT/'results/route-audits/tev-public-20261006-evening/endpoints.json').read_text())
        catalog_raw=native.canonical(catalog)
        answers={key:{'type':'choice','choice':next(iter(VALUES[key]))} for key in KEYS}
        good_wire=native.canonical({'model':tev.VERSION,'provider':tev.PROVIDER,
            'answers':answers,'usage':{'input_tokens':100,'output_tokens':8,'cost':0.0000042}})
        for unknown in (False,True):
            with self.subTest(unknown=unknown),tempfile.TemporaryDirectory() as directory:
                base=Path(directory).resolve()
                master=base/'master.jsonl'
                master.write_text(json.dumps({'event':'budget','cap_usd':'1'})+'\n')
                budget=base/'budget.json'
                child=base/f'budget-{full.PARTITION_ID}.jsonl'
                manifest=base/'manifest.json'
                manifest.write_text('{}\n')
                folder=base/'fresh1/P0'
                folder.mkdir(parents=True)
                review=folder/'development.root-review.json'
                template={'schema':'synthetic-reviewed-stage','approved':False,
                          'independent_review':False,'authorized_by_root':False,'reviewer':None}
                accepted=dict(template,approved=True,independent_review=True,
                              authorized_by_root=True,reviewer='root')
                review.write_text(json.dumps(accepted)+'\n')
                with patch.object(budget_v4,'CAP',Decimal('1')):
                    partitions.allocate(master,budget,[{'id':full.PARTITION_ID,'cap_usd':'1.00',
                        'model':tev.MODEL,'provider':tev.PROVIDER,'reasoning':full.REASONING}])
                    with patch.object(full,'BASE',base),patch.object(full,'MANIFEST',manifest),\
                         patch.object(full,'BUDGET',budget),patch.object(full,'CHILD',child),\
                         patch.object(full,'MASTER',master),\
                         patch.object(full,'phase',return_value={'requests_sha256':'synthetic-set'}),\
                         patch.object(full,'stage_rows',return_value=[item]),\
                         patch.object(full,'stage_template',return_value=template),\
                         patch.object(full,'verify',return_value='synthetic-manifest-sha'),\
                         patch.dict('os.environ',{'OPENROUTER_API_KEY':'test-token'}):
                        calls=[]
                        def send(payload,token):
                            self.assertEqual(token,'test-token')
                            calls.append(payload)
                            return (503,b'{"error":"provider unavailable"}') if unknown else (200,good_wire)
                        fetch=lambda:(catalog_raw,catalog)
                        if unknown:
                            with self.assertRaises(ValueError):
                                full.execute('fresh1/P0','development',review,fetch=fetch,send=send)
                        else:
                            closure=full.execute('fresh1/P0','development',review,fetch=fetch,send=send)
                            self.assertEqual((closure['request_count'],closure['known_valid_count']),(1,1))
                        self.assertEqual(len(calls),1)
                        events=[json.loads(line) for line in child.read_text().splitlines()]
                        self.assertEqual(sum(e['event']=='reserve' for e in events),1)
                        self.assertEqual(sum(e['event']=='settle' for e in events),0 if unknown else 1)
                        raw=[json.loads(line) for line in (folder/'development.raw.jsonl').read_text().splitlines()]
                        self.assertEqual(len(raw),1)
                        with self.assertRaises(FileExistsError):
                            full.execute('fresh1/P0','development',review,fetch=fetch,
                                         send=lambda *_:self.fail('replayed a claimed Tev stage'))

if __name__=='__main__':unittest.main()
