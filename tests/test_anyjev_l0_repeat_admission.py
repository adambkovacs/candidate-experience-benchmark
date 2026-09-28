"""Offline AnyJev L0 admission checks; tests never load model weights."""
import copy
import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import anyjev_l0_repeat_admission as admission


class FakeResult:
    def __init__(self,raw):self.raw=raw
    def to_dict(self):return copy.deepcopy(self.raw)
    def __iter__(self):
        return iter(SimpleNamespace(question=SimpleNamespace(id=key),diagnostics={})
                    for key in admission.KEYS)


class FakeDecider:
    def __init__(self,backend,source_by_feedback):
        self.backend=backend;self.source_by_feedback=source_by_feedback
        self.stats=admission.STATS.copy()
    def decide(self,state,questions,level):
        self.backend.observed_calls=self.backend.expected_calls
        self.backend.prompt_token_counts=[x['input_tokens'] for call in self.backend.expected_calls for x in call]
        return FakeResult(self.source_by_feedback[state['feedback']])


class AnyJevL0RepeatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (Path(sys.executable).resolve()!=admission.PYTHON.resolve()
                or not admission.MODEL.is_dir() or not admission.SOURCE.is_dir()):
            raise unittest.SkipTest('Pinned local specialist Python/source/assets required; no downloads or model calls')
        cls.plan=admission.expected_plan()
        cls.rows,cls.policy=admission.shared.source_rows()
        cls.historical=admission.shared.read_jsonl(admission.HISTORY/'development.jsonl')

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.phase=self.plan['schedule'][0]
        for attr,value in [('PLAN_PATH',self.root/'manifest.json'),('HOST_LOCK',self.root/'host.lock')]:
            patch=mock.patch.object(admission,attr,value);patch.start();self.addCleanup(patch.stop)
        admission.PLAN_PATH.write_text(admission.shared.canonical(self.plan))
        self.plan_sha=admission.shared.file_hash(admission.PLAN_PATH)
        patch=mock.patch.object(admission,'verify_plan',return_value=(self.plan,self.plan_sha))
        patch.start();self.addCleanup(patch.stop)

    def receipt(self,stage,**extra):
        path=self.root/f'{stage}-review.json'
        value={'kind':'root-reviewed-anyjev-l0-native-p0-stage-v1','approved':True,
               'phase':self.phase,'stage':stage,'plan_sha256':self.plan_sha}
        value.update(extra);path.write_text(admission.shared.canonical(value))
        return path

    def fake(self,failure=False):
        backend=SimpleNamespace(expected_calls=None,observed_calls=None,prompt_token_counts=[])
        source={row['feedback']:saved['raw_response'] for row,saved in zip(self.rows,self.historical)}
        decider=FakeDecider(backend,source)
        if failure:
            def failed(*args,**kwargs):raise RuntimeError('offline injected failure')
            decider.decide=failed
        patch=mock.patch.object(admission,'load_backend',return_value=(backend,object(),[]))
        other=mock.patch.object(admission,'make_decider',return_value=decider)
        return patch,other

    def run_smoke(self,failure=False):
        one,two=self.fake(failure)
        with one,two:
            admission.run_stage(self.plan,self.plan_sha,self.phase,'smoke',self.receipt('smoke'))

    def test_history_and_all_probe_shift_signatures_are_bound(self):
        self.assertTrue(self.plan['historical']['eligible_as_pass1'])
        self.assertEqual([len(call) for call in self.plan['requests'][0]['native_calls']],[14,42])
        for request,record in zip(self.plan['requests'],self.historical):
            self.assertEqual([x['input_tokens'] for call in request['native_calls'] for x in call],
                             record['prompt_token_counts'])
        self.assertEqual(self.plan['runtime']['probe_order'],['N/A','','[MASK]'])
        self.assertEqual(self.plan['runtime']['level'],'L0')

    def test_raw_saved_before_projection_and_no_replay(self):
        self.run_smoke()
        folder=admission.phase_path(self.phase)
        self.assertEqual(len(admission.shared.read_jsonl(folder/'smoke.raw.jsonl')),3)
        self.assertEqual([x['event'] for x in admission.shared.read_jsonl(folder/'smoke.journal.jsonl')],
            ['phase_started','request_started','request_completed','request_started',
             'request_completed','request_started','request_completed','phase_completed'])
        one,two=self.fake()
        with one,two,self.assertRaises(FileExistsError):
            admission.run_stage(self.plan,self.plan_sha,self.phase,'smoke',self.receipt('smoke'))

    def test_unknown_start_is_retained_and_never_replayed(self):
        with self.assertRaisesRegex(RuntimeError,'retain started unknown'):
            self.run_smoke(failure=True)
        folder=admission.phase_path(self.phase)
        self.assertEqual([x['event'] for x in admission.shared.read_jsonl(folder/'smoke.journal.jsonl')],
                         ['phase_started','request_started','phase_stopped'])
        with self.assertRaises(FileExistsError):self.run_smoke()

    def test_smoke_inspection_and_predecessor_fence(self):
        self.run_smoke()
        folder=admission.phase_path(self.phase)
        inspection=folder/'smoke-inspection.json'
        smoke_hash=admission.shared.file_hash(folder/'smoke.records.jsonl')
        inspection.write_text(admission.shared.canonical({'phase':self.phase,
            'plan_sha256':self.plan_sha,'smoke_sha256':smoke_hash,
            'inspected_ids':[f'DEV-{i:03d}' for i in range(1,4)],'approved':True}))
        receipt=self.receipt('development',smoke_inspection_sha256=admission.shared.file_hash(inspection))
        one,two=self.fake()
        with one,two:admission.run_stage(self.plan,self.plan_sha,self.phase,'development',receipt)
        self.assertEqual(len(admission.shared.read_jsonl(folder/'development.records.jsonl')),60)
        admission.check_predecessors(self.plan,self.plan_sha,'repeat3/P0')
        completion=admission.shared.read_json(folder/'development.completion.json')
        completion['output_sha256']='0'*64
        (folder/'development.completion.json').write_text(admission.shared.canonical(completion))
        with self.assertRaisesRegex(ValueError,'lacks verified'):
            admission.check_predecessors(self.plan,self.plan_sha,'repeat3/P0')

    def test_raw_signature_tamper_rejected(self):
        self.run_smoke();folder=admission.phase_path(self.phase)
        captures=admission.shared.read_jsonl(folder/'smoke.raw.jsonl')
        captures[0]['native_calls'][1][0]['answer_token_ids']=[0]
        (folder/'smoke.raw.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in captures))
        with self.assertRaisesRegex(ValueError,'output binding failed'):
            admission.verify_output(self.plan,self.phase,'smoke')

    def test_shared_os_lock_blocks_admission_before_claim(self):
        holder=subprocess.Popen([sys.executable,'-c',
            'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("READY",flush=True); sys.stdin.read(1)',
            str(admission.HOST_LOCK)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(),'READY')
            with self.assertRaisesRegex(RuntimeError,'host lock'):
                admission.run_stage(self.plan,self.plan_sha,self.phase,'smoke',self.receipt('smoke'))
            self.assertFalse((admission.phase_path(self.phase)/'smoke.claim.json').exists())
        finally:
            holder.stdin.write('x');holder.stdin.flush();holder.wait(timeout=10)
            holder.stdin.close();holder.stdout.close()


if __name__=='__main__':unittest.main()
