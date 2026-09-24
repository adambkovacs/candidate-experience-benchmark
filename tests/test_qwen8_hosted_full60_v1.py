import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('full60',ROOT/'scripts/qwen8_hosted_full60_v1.py')
full60=importlib.util.module_from_spec(spec);spec.loader.exec_module(full60)
FOLDER=ROOT/'results/qwen8-hosted-full60-prep-v1'

class Full60Test(unittest.TestCase):
    def plan(self,mode):
        p=FOLDER/f'{mode}-full60-plan.json'
        return p,full60.sha(p)

    def test_both_modes_have_canonical_60_and_inspected_smoke(self):
        for mode in ('off','on'):
            with self.subTest(mode=mode):
                p,d=self.plan(mode);m,paths,budget=full60.prepare(p,d)
                self.assertIsNone(budget)
                self.assertEqual(len(m['record_ids']),60)
                self.assertEqual(m['record_ids'][0:3],['DEV-001','DEV-002','DEV-003'])
                self.assertEqual(m['record_ids'][-1],'DEV-060')
                self.assertEqual(m['full60_bound_usd'],'1.031946240')
                inspection=json.loads(paths['inspection'].read_text())
                self.assertEqual(inspection['statuses'],['ok']*3 if mode=='off' else ['invalid_output']*3)
                self.assertTrue(inspection['control_and_billing_passed'])

    def test_partition_bound_blocks_60_call_overrun(self):
        p,d=self.plan('off')
        with patch.object(full60,'reservation',return_value=full60.number('0.017500001')):
            with self.assertRaisesRegex(ValueError,'Full60 reserve bound'):
                full60.prepare(p,d)

    def test_exclusive_output_prevents_replay(self):
        p,d=self.plan('on');target=ROOT/json.loads(p.read_text())['output'];old=Path.exists
        def exists(path):return True if path==target else old(path)
        with patch.object(Path,'exists',exists):
            with self.assertRaisesRegex(FileExistsError,'no replay'):
                full60.prepare(p,d)

    def test_review_and_partition_are_required(self):
        p,d=self.plan('off')
        with tempfile.TemporaryDirectory(dir=FOLDER) as temp:
            folder=Path(temp);budget=folder/'budget.json';review=folder/'review.json'
            budget.write_text(json.dumps({'partitions':[{'id':'off','model':'qwen/qwen3-8b','provider':'alibaba','reasoning':'off','cap_usd':'1.05'}]}))
            review.write_text(json.dumps({'approved':True,'full60_plan_sha256':d,'wrapper_sha256':'wrong','budget_manifest_sha256':full60.sha(budget),'partition_id':'off'}))
            with self.assertRaisesRegex(ValueError,'Missing exact root review'):
                full60.prepare(p,d,budget,'off',review)

    def test_execution_uses_v2_partition_helper(self):
        p,d=self.plan('on');m,paths,_=full60.prepare(p,d)
        def fake_execute(args):
            self.assertIs(sys.modules['paid_budget_partitions'],full60.partitions_v2)
            self.assertEqual(args.preview_file,str(paths['preview']))
            self.assertEqual(args.partition_id,'on')
            self.assertEqual(args.timeout,300)
        with patch.object(full60.adapter,'execute',side_effect=fake_execute):
            full60.execute(m,paths,(ROOT/'budget.json','on',ROOT/'review.json'))
        self.assertIsNot(sys.modules.get('paid_budget_partitions'),full60.partitions_v2)

if __name__=='__main__':unittest.main()
