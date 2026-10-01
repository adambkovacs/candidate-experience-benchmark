import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mistral119_v3_smoke as s
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


def body(cost='0.001',model=s.study.MODEL,provider=s.study.PROVIDER_NAME):
    prediction={key:VALUES[key][0] for key in KEYS}
    return {'model':model,'provider':provider,'choices':[{'finish_reason':'stop',
        'message':{'content':json.dumps(prediction),'refusal':None,'tool_calls':None}}],
        'usage':{'cost':cost,'prompt_tokens':900,'completion_tokens':20}}


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'stage'
        self.budget=Path(self.tmp.name)/'budget.json';self.budget.write_text('{}\n')
        self.digest=s.prepare(self.base)
        manifest=json.loads((self.base/'manifest.json').read_text())
        self.review=self.base/'smoke.root-review.json'
        self.review.write_text(json.dumps({**s.expected_receipt(manifest,self.digest,self.budget),
                                           'reviewer':'root'})+'\n')
        original,_=s.study.historical(s.CONFIG)
        self.model=original['model_catalog_entry'];self.endpoint=original['provider_endpoint']
        self.calls=[];self.live_calls=[]
    def live(self,plan,condition):
        self.live_calls.append((plan['configuration_id'],condition))
        return self.model,self.endpoint,s.study.RESERVE
    def execute(self,send=None,child=None,live=None):
        child=child or FakeChild()
        send=send or (lambda payload,token:(200,json.dumps(body()).encode(),False))
        def wrapped(payload,token):
            self.calls.append(payload)
            return send(payload,token)
        s.run(self.review,self.budget,self.base,send=wrapped,live=live or self.live,
              open_child=lambda *args:child,load_key=lambda env:'fake-key')
        return child

    def test_never_sent_membership_and_payload_identity(self):
        manifest,digest=s.verify(self.base)
        self.assertEqual(digest,self.digest)
        self.assertEqual(manifest['ids'],['DEV-002','DEV-003','DEV-004'])
        self.assertEqual(manifest['historical_dev001_failed_smoke_count'],5)
        self.assertEqual(len(manifest['historical_failed_smoke_source_sha256']),5)
        self.assertEqual(manifest['full_three_request_admission_usd'],'0.12533760')
        self.assertTrue(manifest['not_a_repeat_pass'])
        self.assertFalse(manifest['reference_labels_read'])
        for item in manifest['requests']:
            self.assertEqual(item['payload']['provider']['only'],[s.study.PROVIDER])
            self.assertIs(item['payload']['provider']['allow_fallbacks'],False)
            self.assertEqual([m['role'] for m in item['payload']['messages']],['system','user'])
            self.assertNotIn('reference_labels',item['payload'])

    def test_manifest_or_receipt_drift_blocks_without_send(self):
        path=self.base/'manifest.json';v=json.loads(path.read_text())
        v['requests'][0]['record_id']='DEV-001';path.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'drift'):s.verify(self.base)
        path.write_text(json.dumps(s.manifest_value()))
        r=json.loads(self.review.read_text());r['ids']=['DEV-001','DEV-002','DEV-003']
        self.review.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'review receipt'):
            self.execute(send=lambda *_:self.fail('sent'))
        self.assertFalse((self.base/'smoke.claim.json').exists())

    def test_full_three_bound_and_route_gate_before_claim(self):
        with self.assertRaisesRegex(ValueError,'full three-request admission'):
            self.execute(child=FakeChild(Decimal('0.10')),send=lambda *_:self.fail('sent'))
        self.assertFalse((self.base/'smoke.claim.json').exists())
        with self.assertRaisesRegex(ValueError,'reserve differs'):
            self.execute(live=lambda *_:(self.model,self.endpoint,Decimal('0.05')),
                         send=lambda *_:self.fail('sent'))
        self.assertFalse((self.base/'smoke.claim.json').exists())

    def test_success_records_three_and_prevents_replay(self):
        child=self.execute()
        self.assertEqual(len(self.calls),3)
        self.assertEqual([m['content'] for p in self.calls for m in p['messages'] if m['role']=='user'],
                         [m['content'] for x in s.manifest_value()['requests'] for m in x['payload']['messages'] if m['role']=='user'])
        self.assertEqual(child.accounted(),Decimal('0.003'))
        self.assertFalse(child.pending)
        journal=[json.loads(x) for x in (self.base/'smoke.journal.jsonl').read_text().splitlines()]
        self.assertEqual(journal[-1]['event'],'stage_completed')
        self.assertFalse(journal[-1]['repeat_pass_credit'])
        self.assertEqual(len((self.base/'smoke.raw.jsonl').read_text().splitlines()),3)
        self.assertEqual(len((self.base/'smoke.parsed.jsonl').read_text().splitlines()),3)
        with self.assertRaises(FileExistsError):self.execute(send=lambda *_:self.fail('replay'))

    def test_route_drift_after_first_request_stops_before_second_send(self):
        def live(plan,condition):
            self.live_calls.append(condition)
            if len(self.live_calls)>=3:raise ValueError('route changed')
            return self.model,self.endpoint,s.study.RESERVE
        with self.assertRaisesRegex(ValueError,'route changed'):
            self.execute(live=live)
        self.assertEqual(len(self.calls),1)

    def test_unknown_cost_retains_full_reserve(self):
        value=body();del value['usage']['cost'];child=FakeChild()
        with self.assertRaisesRegex(ValueError,'full reserve retained'):
            self.execute(send=lambda *_:(200,json.dumps(value).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(child.pending,{'attempt-DEV-002'})
        self.assertEqual(child.accounted(),s.study.RESERVE)
        self.assertEqual(len((self.base/'smoke.raw.jsonl').read_text().splitlines()),1)

    def test_known_overbound_settles_actual_and_blocks(self):
        child=FakeChild()
        with self.assertRaisesRegex(ValueError,'blocked child'):
            self.execute(send=lambda *_:(200,json.dumps(body('0.05')).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertFalse(child.pending);self.assertTrue(child.blocked)
        self.assertEqual(child.accounted(),Decimal('0.05'))
        attempt=json.loads((self.base/'smoke.attempts.jsonl').read_text().splitlines()[0])
        self.assertEqual(attempt['actual_cost_usd'],'0.05')

    def test_invalid_provider_or_distribution_stops_after_known_settle(self):
        child=FakeChild()
        with self.assertRaisesRegex(ValueError,'Invalid Mistral output'):
            self.execute(send=lambda *_:(200,json.dumps(body(provider='Other')).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(child.accounted(),Decimal('0.001'))
        self.assertFalse(child.pending)

    def test_malformed_billed_choice_is_recorded_and_stops(self):
        value=body();value['choices']=[None];child=FakeChild()
        with self.assertRaisesRegex(ValueError,'Invalid Mistral output'):
            self.execute(send=lambda *_:(200,json.dumps(value).encode(),False),child=child)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(child.accounted(),Decimal('0.001'))
        attempt=json.loads((self.base/'smoke.attempts.jsonl').read_text().splitlines()[0])
        self.assertEqual(attempt['status'],'invalid_response')
        self.assertEqual(attempt['response_status'],'malformed_response')
        journal=[json.loads(x) for x in (self.base/'smoke.journal.jsonl').read_text().splitlines()]
        self.assertEqual(journal[-1]['event'],'stage_aborted')

    def test_transport_error_keeps_reserve_and_no_retry(self):
        child=FakeChild()
        def fail(*_):raise TimeoutError('unobserved')
        with self.assertRaises(TimeoutError):self.execute(send=fail,child=child)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(child.pending,{'attempt-DEV-002'})
        self.assertEqual(child.accounted(),s.study.RESERVE)


if __name__=='__main__':unittest.main()
