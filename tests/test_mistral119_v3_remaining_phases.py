import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mistral119_v3_remaining_phases as s
from development_benchmark import KEYS,VALUES


class FakeChild:
    def __init__(self,cap):
        self.cap=cap;self.master_cap=Decimal('12.38');self.closed=False
        self.events=[];self.pending=set();self.blocked=False
    def state(self):return {},set(self.pending),self.blocked
    def accounted(self):return sum((value for _,value in self.events),Decimal(0))
    def reserve(self,amount,rid):
        if self.pending or self.blocked or self.accounted()+amount>self.cap:raise ValueError('budget')
        aid='attempt-'+rid;self.events.append((aid,amount));self.pending.add(aid);return aid
    def settle(self,aid,actual):
        reserved=dict(self.events)[aid];self.pending.remove(aid)
        self.events=[(a,actual if a==aid else value) for a,value in self.events]
        self.blocked=actual>reserved or self.accounted()>self.cap
        return not self.blocked
    def close(self):self.closed=True


def response(cost='0.001'):
    prediction={key:VALUES[key][0] for key in KEYS}
    return {'model':s.study.MODEL,'provider':s.study.PROVIDER_NAME,
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(prediction),
                        'reasoning':None,'refusal':None,'role':'assistant'}}],
            'usage':{'cost':cost,'prompt_tokens':900,'completion_tokens':20}}


class RemainingTests(unittest.TestCase):
    def test_exact_eight_order_and_frozen_membership(self):
        self.assertEqual(s.STAGES,(('fresh1','P1'),('fresh1','P2'),('fresh2','P1'),
                                    ('fresh2','P2'),('fresh2','P0'),('fresh3','P2'),
                                    ('fresh3','P0'),('fresh3','P1')))
        self.assertEqual(s.predecessor('fresh1','P1'),('fresh1','P0'))
        self.assertEqual(s.predecessor('fresh3','P1'),('fresh3','P0'))
        for repeat,condition in s.STAGES:
            m=s.manifest_value(repeat,condition)
            self.assertEqual([x['record_id'] for x in m['smoke_requests']],
                             ['DEV-001','DEV-002','DEV-003'])
            self.assertEqual([x['record_id'] for x in m['development_requests']],
                             [f'DEV-{i:03d}' for i in range(1,61)])
            self.assertFalse(m['reference_labels_read'])

    def test_suffix_exactly_unsent_and_not_failed(self):
        m=s.suffix_manifest_value()
        self.assertEqual([x['record_id'] for x in m['suffix_requests']],
                         [f'DEV-{i:03d}' for i in range(49,61)])
        self.assertEqual(m['original_failed_id'],'DEV-048')
        self.assertEqual(s.partition_id('fresh1','P0','suffix'),
                         'mistral119-none-v3-fresh1-p0-suffix-049-060-v1')

    def test_source_and_payload_drift_block(self):
        with tempfile.TemporaryDirectory() as temp:
            digest=s.prepare('fresh1','P1',temp)
            self.assertEqual(s.verify('fresh1','P1',temp)[1],digest)
            path=s.folder('fresh1','P1',temp)/'manifest.json'
            value=json.loads(path.read_text());value['smoke_requests'][0]['record_id']='DEV-048'
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'drift'):s.verify('fresh1','P1',temp)

    def test_allocator_accepts_distinct_smoke_then_development_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            stage=Path(temp)/'fresh1'/'P1';stage.mkdir(parents=True)
            master=Path(temp)/'master.jsonl'
            smoke_path=s.budget_manifest_path(stage,'smoke')
            full_path=s.budget_manifest_path(stage,'development')
            self.assertNotEqual(smoke_path,full_path)
            def spec(phase,cap):
                return {'id':s.partition_id('fresh1','P1',phase),'cap_usd':str(cap),
                        'model':s.study.MODEL,'provider':s.study.PROVIDER,'reasoning':'none'}
            s.partitions.allocate(master,smoke_path,[spec('smoke',s.SMOKE_CAP)])
            closed=s.partitions.reconcile_partition(master,smoke_path,
                                                     s.partition_id('fresh1','P1','smoke'))
            self.assertEqual(closed['event'],'partition_reconciled')
            s.partitions.allocate(master,full_path,[spec('development',s.DEVELOPMENT_CAP)])
            self.assertTrue(smoke_path.exists())
            self.assertTrue(full_path.exists())

    def test_interrupted_gate_requires_root_review_and_no_replay(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            copy=Path(temp)
            for name in ('manifest.json','development.claim.json','development.journal.jsonl',
                         'development.attempts.jsonl','development.raw.jsonl',
                         'development.parsed.jsonl','development.root-review.json',
                         'development.terminal-public.json','budget-reconciliation.json'):
                shutil.copyfile(s.FIRST_BASE/name,copy/name)
            review=copy/'development.interruption-review.json'
            with patch.object(s,'FIRST_BASE',copy):
                with self.assertRaises(FileNotFoundError):s.interrupted_gate()
                data={'schema':'mistral119-v3-development-interruption-review-v1',
                      'reviewer':'root','verdict':'accepted_unchanged',
                      'terminal_public_sha256':s.INTERRUPTION_SHA,'failed_id':'DEV-048',
                      'permitted_unsent_ids':[f'DEV-{i:03d}' for i in range(49,61)],
                      'unknown_upper_bound_usd':str(s.study.RESERVE),
                      'no_replay_of_failed_id':True}
                review.write_text(json.dumps(data)+'\n')
                self.assertEqual(s.interrupted_gate()['unknown_id'],'DEV-048')
                data['permitted_unsent_ids'][0]='DEV-048';review.write_text(json.dumps(data)+'\n')
                with self.assertRaisesRegex(ValueError,'review gate'):s.interrupted_gate()

    def test_smoke_execution_requires_gate_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            stage=Path(temp)/'fresh1'/'P1';stage.mkdir(parents=True)
            manifest=s.manifest_value('fresh1','P1')
            digest=s.smoke.digest_bytes(s.smoke.canonical(manifest))
            budget=stage/'smoke.budget-manifest.json';budget.write_text('{}\n')
            gate={'predecessor':{'closed':'fake-only'}}
            receipt=stage/'smoke.root-review.json'
            receipt.write_text(json.dumps({**s.expected_receipt('fresh1','P1','smoke',manifest,digest,budget,gate),
                                           'reviewer':'root'})+'\n')
            original,_=s.study.historical(s.smoke.CONFIG)
            model,endpoint=original['model_catalog_entry'],original['provider_endpoint']
            child=FakeChild(s.SMOKE_CAP);calls=[]
            def send(payload,token):calls.append(payload);return 200,json.dumps(response()).encode(),False
            with patch.object(s,'folder',return_value=stage),\
                 patch.object(s,'verify',return_value=(manifest,digest)),\
                 patch.object(s,'gate',return_value=gate):
                s.run('fresh1','P1','smoke',receipt,budget,send=send,
                      live=lambda *_:(model,endpoint,s.study.RESERVE),
                      open_child=lambda *args:child,load_key=lambda env:'fake-key')
                self.assertEqual(len(calls),3)
                self.assertEqual(child.accounted(),Decimal('0.003'))
                with self.assertRaises(FileExistsError):
                    s.run('fresh1','P1','smoke',receipt,budget,send=lambda *_:self.fail('replay'),
                          live=lambda *_:(model,endpoint,s.study.RESERVE),
                          open_child=lambda *args:child,load_key=lambda env:'fake-key')

    def test_suffix_dispatches_only_twelve_never_sent_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            stage=Path(temp);manifest=s.suffix_manifest_value()
            digest=s.smoke.digest_bytes(s.smoke.canonical(manifest))
            budget=stage/'suffix.budget-manifest.json';budget.write_text('{}\n')
            gate={'interrupted':{'unknown_id':'DEV-048','unsent_ids':[f'DEV-{i:03d}' for i in range(49,61)]}}
            receipt=stage/'suffix.root-review.json'
            receipt.write_text(json.dumps({**s.expected_receipt('fresh1','P0','suffix',manifest,digest,budget,gate),
                                           'reviewer':'root'})+'\n')
            original,_=s.study.historical(s.smoke.CONFIG)
            model,endpoint=original['model_catalog_entry'],original['provider_endpoint']
            child=FakeChild(s.SUFFIX_CAP);calls=[]
            def send(payload,token):calls.append(payload);return 200,json.dumps(response()).encode(),False
            with patch.object(s,'SUFFIX_BASE',stage),\
                 patch.object(s,'verify_suffix',return_value=(manifest,digest)),\
                 patch.object(s,'gate',return_value=gate):
                s.run('fresh1','P0','suffix',receipt,budget,send=send,
                      live=lambda *_:(model,endpoint,s.study.RESERVE),
                      open_child=lambda *args:child,load_key=lambda env:'fake-key')
            self.assertEqual(len(calls),12)
            self.assertEqual([p['messages'][1]['content'] for p in calls],
                             [r['payload']['messages'][1]['content'] for r in manifest['suffix_requests']])
            self.assertEqual(child.accounted(),Decimal('0.012'))
            attempts=[json.loads(x) for x in (stage/'suffix.attempts.jsonl').read_text().splitlines()]
            self.assertEqual([x['id'] for x in attempts],[f'DEV-{i:03d}' for i in range(49,61)])
            self.assertNotIn('DEV-048',[x['id'] for x in attempts])
            child_path=stage/'child.jsonl';child_path.write_text('{"event":"partition_closed"}\n')
            (stage/'suffix.budget-reconciliation.json').write_text(json.dumps({
                'event':'partition_reconciled','partition_id':s.partition_id('fresh1','P0','suffix'),
                'known_actual_usd':'0.012','unknown_upper_bound_usd':'0',
                'child_ledger':str(child_path),'child_sha256':s.smoke.sha(child_path)})+'\n')
            binding=s.closed_phase(stage,'suffix',manifest['suffix_requests'],digest)
            self.assertEqual(binding['count'],12)

    def test_known_overbound_and_unknown_hold(self):
        for cost,expected in [('0.05','blocked child'),(None,'full reserve retained')]:
            with self.subTest(cost=cost),tempfile.TemporaryDirectory() as temp:
                stage=Path(temp)/'fresh1'/'P1';stage.mkdir(parents=True)
                manifest=s.manifest_value('fresh1','P1')
                digest=s.smoke.digest_bytes(s.smoke.canonical(manifest))
                budget=stage/'smoke.budget-manifest.json';budget.write_text('{}\n')
                gate={'predecessor':{'closed':'fake-only'}}
                receipt=stage/'smoke.root-review.json'
                receipt.write_text(json.dumps({**s.expected_receipt('fresh1','P1','smoke',manifest,digest,budget,gate),
                                               'reviewer':'root'})+'\n')
                original,_=s.study.historical(s.smoke.CONFIG)
                model,endpoint=original['model_catalog_entry'],original['provider_endpoint']
                child=FakeChild(s.SMOKE_CAP);body=response(cost or '0.001')
                if cost is None:del body['usage']['cost']
                with patch.object(s,'folder',return_value=stage),\
                     patch.object(s,'verify',return_value=(manifest,digest)),\
                     patch.object(s,'gate',return_value=gate):
                    with self.assertRaisesRegex(ValueError,expected):
                        s.run('fresh1','P1','smoke',receipt,budget,
                              send=lambda *_:(200,json.dumps(body).encode(),False),
                              live=lambda *_:(model,endpoint,s.study.RESERVE),
                              open_child=lambda *args:child,load_key=lambda env:'fake-key')
                self.assertEqual(len(child.events),1)
                self.assertEqual(bool(child.pending),cost is None)
                if cost is not None:self.assertEqual(child.accounted(),Decimal('0.05'))


if __name__=='__main__':unittest.main()
