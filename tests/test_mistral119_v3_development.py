import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mistral119_v3_development as s
from development_benchmark import KEYS,VALUES


class FakeChild:
    def __init__(self,cap=s.CAP):
        self.cap=cap;self.master_cap=Decimal('12.38');self.closed=False
        self.events=[];self.pending=set();self.blocked=False
    def state(self):return {},set(self.pending),self.blocked
    def accounted(self):return sum((value for _,value in self.events),Decimal(0))
    def reserve(self,amount,rid):
        if self.blocked or self.pending or self.accounted()+amount>self.cap:raise ValueError('budget')
        aid='attempt-'+rid;self.events.append((aid,amount));self.pending.add(aid);return aid
    def settle(self,aid,actual):
        reserved=dict(self.events)[aid];self.pending.remove(aid)
        self.events=[(a,actual if a==aid else value) for a,value in self.events]
        self.blocked=actual>reserved or self.accounted()>self.cap
        return not self.blocked
    def close(self):self.closed=True


def body(cost='0.001',provider=s.study.PROVIDER_NAME):
    prediction={key:VALUES[key][0] for key in KEYS}
    return {'model':s.study.MODEL,'provider':provider,
            'choices':[{'finish_reason':'stop','message':
                        {'content':json.dumps(prediction),'refusal':None,'tool_calls':None}}],
            'usage':{'cost':cost,'prompt_tokens':900,'completion_tokens':20}}


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'stage'
        self.budget=Path(self.tmp.name)/'budget.json';self.budget.write_text('{}\n')
        self.digest=s.prepare(self.base)
        self.manifest=json.loads((self.base/'manifest.json').read_text())
        self.review=self.base/'development.root-review.json'
        self.review.write_text(json.dumps({**s.expected_receipt(self.manifest,self.digest,self.budget),
                                           'reviewer':'root'})+'\n')
        original,_=s.study.historical(s.smoke.CONFIG)
        self.model=original['model_catalog_entry'];self.endpoint=original['provider_endpoint']
        self.calls=[];self.live_calls=[]
    def live(self,plan,condition):
        self.live_calls.append(condition)
        return self.model,self.endpoint,s.study.RESERVE
    def execute(self,send=None,child=None,live=None):
        child=child or FakeChild()
        send=send or (lambda *_:(200,json.dumps(body()).encode(),False))
        def wrapped(payload,token):
            self.calls.append(payload)
            return send(payload,token)
        with patch.object(s,'verify',return_value=(self.manifest,self.digest)):
            s.run(self.review,self.budget,self.base,send=wrapped,live=live or self.live,
                  open_child=lambda *args:child,load_key=lambda env:'fake-key')
        return child

    def test_smoke_gate_reparses_three_and_binds_root_inspection(self):
        gate=s.smoke_closure()
        self.assertEqual((gate['valid_count'],gate['invalid_count']),(3,0))
        self.assertEqual(gate['ids'],['DEV-002','DEV-003','DEV-004'])
        self.assertEqual(Decimal(gate['known_cost_usd']),Decimal('0.000337980'))
        self.assertEqual(s.verify(self.base)[1],self.digest)

    def test_full_frozen_inputs_and_no_reference_labels(self):
        self.assertEqual(self.manifest['ids'],[f'DEV-{i:03d}' for i in range(1,61)])
        self.assertFalse(self.manifest['reference_labels_read'])
        self.assertEqual(self.manifest['frozen_plan_sha256'],s.smoke.PLAN_SHA)
        for item in self.manifest['requests']:
            self.assertEqual([m['role'] for m in item['payload']['messages']],['system','user'])
            self.assertNotIn('reference_labels',item['payload'])
            self.assertEqual(item['payload']['provider']['only'],[s.study.PROVIDER])

    def test_inspection_evidence_drift_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            import shutil
            source=s.smoke.BASE;copy=Path(temp)
            for name in (*s.SMOKE_FILES,'manifest.json','smoke.root-review.json',
                         'smoke.inspection.json','budget-reconciliation.json'):
                shutil.copyfile(source/name,copy/name)
            with patch.object(s.smoke,'verify',return_value=s.smoke.verify(source)):
                (copy/'smoke.attempts.jsonl').write_text('[]\n')
                with self.assertRaisesRegex(ValueError,'hash differs'):s.smoke_closure(copy)

    def test_receipt_drift_blocks_before_child_or_send(self):
        value=json.loads(self.review.read_text());value['ids']=['DEV-001']
        self.review.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'receipt differs'):
            self.execute(send=lambda *_:self.fail('sent'))
        self.assertFalse((self.base/'development.claim.json').exists())

    def test_success_60_records_and_duplicate_refusal(self):
        child=self.execute()
        self.assertEqual(len(self.calls),60)
        self.assertEqual([p['messages'][1]['content'] for p in self.calls],
                         [r['payload']['messages'][1]['content'] for r in self.manifest['requests']])
        self.assertEqual(child.accounted(),Decimal('0.060'))
        self.assertFalse(child.pending)
        self.assertEqual(len((self.base/'development.raw.jsonl').read_text().splitlines()),60)
        self.assertEqual(len((self.base/'development.parsed.jsonl').read_text().splitlines()),60)
        journal=[json.loads(x) for x in (self.base/'development.journal.jsonl').read_text().splitlines()]
        self.assertEqual(journal[-1]['event'],'stage_completed')
        with self.assertRaises(FileExistsError):self.execute(send=lambda *_:self.fail('replay'))

    def test_capacity_stops_before_next_send(self):
        child=FakeChild()
        with self.assertRaisesRegex(ValueError,'lacks next full reserve'):
            self.execute(send=lambda *_:(200,json.dumps(body('0.04')).encode(),False),child=child)
        self.assertEqual(len(self.calls),6)
        self.assertFalse(child.pending)
        self.assertEqual(child.accounted(),Decimal('0.24'))
        attempts=[json.loads(x) for x in (self.base/'development.attempts.jsonl').read_text().splitlines()]
        self.assertEqual(len(attempts),6)

    def test_unknown_cost_retains_bound_and_no_retry(self):
        value=body();del value['usage']['cost'];child=FakeChild()
        with self.assertRaisesRegex(ValueError,'full reserve retained'):
            self.execute(send=lambda *_:(200,json.dumps(value).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(child.pending,{'attempt-DEV-001'})
        self.assertEqual(child.accounted(),s.study.RESERVE)

    def test_overbound_known_cost_settled_and_blocks(self):
        child=FakeChild()
        with self.assertRaisesRegex(ValueError,'blocked child'):
            self.execute(send=lambda *_:(200,json.dumps(body('0.05')).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertTrue(child.blocked)
        self.assertEqual(child.accounted(),Decimal('0.05'))

    def test_live_route_change_stops_without_second_send(self):
        def live(plan,condition):
            self.live_calls.append(condition)
            if len(self.live_calls)==3:raise ValueError('route drift')
            return self.model,self.endpoint,s.study.RESERVE
        with self.assertRaisesRegex(ValueError,'route drift'):self.execute(live=live)
        self.assertEqual(len(self.calls),1)


if __name__=='__main__':unittest.main()
