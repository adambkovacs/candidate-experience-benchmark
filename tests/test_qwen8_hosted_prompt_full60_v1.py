import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('prompt_full60',ROOT/'scripts/qwen8_hosted_prompt_full60_v1.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
FOLDER=ROOT/'results/qwen8-hosted-prompt-full60-prep-v1'

class PromptFull60Test(unittest.TestCase):
    def plan(self,mode,variant):
        p=FOLDER/f'{mode}-{variant.lower()}-full60-plan.json';return p,module.sha(p)
    def test_four_smoke_inspections_and_60_inputs(self):
        for mode in ('off','on'):
            for variant in ('P1','P2'):
                with self.subTest(mode=mode,variant=variant):
                    p,d=self.plan(mode,variant);plan,paths,budget=module.prepare(p,d)
                    self.assertIsNone(budget)
                    self.assertEqual(len(plan['record_ids']),60)
                    self.assertEqual(plan['record_ids'][0:3],['DEV-001','DEV-002','DEV-003'])
                    self.assertEqual(plan['record_ids'][-1],'DEV-060')
                    self.assertEqual(plan['full60_bound_usd'],'1.031946240')
                    inspection=json.loads(paths['inspection'].read_text())
                    self.assertEqual(inspection['statuses'],plan['smoke_statuses'])
                    self.assertTrue(inspection['control_and_billing_passed'])
    def test_intrinsic_length_preserved_for_on_p2(self):
        p,d=self.plan('on','P2');plan,paths,_=module.prepare(p,d)
        rows=[json.loads(x) for x in paths['smoke'].read_text().splitlines()]
        self.assertEqual([r['finish_reason'] for r in rows],['length','stop','length'])
        self.assertEqual(plan['smoke_statuses'],['invalid_output']*3)
        self.assertTrue(all(r['billing_ok'] and not r['cost_unknown'] for r in rows))
    def test_partition_bound_and_output_exclusivity(self):
        p,d=self.plan('off','P1')
        with patch.object(module,'reservation',return_value=module.number('0.017500001')):
            with self.assertRaisesRegex(ValueError,'reserve bound'):
                module.prepare(p,d)
        target=ROOT/json.loads(p.read_text())['output'];old=Path.exists
        def exists(path):return True if path==target else old(path)
        with patch.object(Path,'exists',exists):
            with self.assertRaisesRegex(FileExistsError,'no replay'):
                module.prepare(p,d)
    def test_review_required_and_v2_execution(self):
        p,d=self.plan('on','P1');plan,paths,_=module.prepare(p,d)
        with tempfile.TemporaryDirectory(dir=FOLDER) as temp:
            folder=Path(temp);b=folder/'budget.json';r=folder/'review.json'
            b.write_text(json.dumps({'partitions':[{'id':'on-p1','model':'qwen/qwen3-8b','provider':'alibaba','reasoning':'on','cap_usd':'1.05'}]}))
            r.write_text(json.dumps({'approved':False,'full60_plan_sha256':d,'wrapper_sha256':module.sha(module.__file__),'budget_manifest_sha256':module.sha(b),'partition_id':'on-p1'}))
            with self.assertRaisesRegex(ValueError,'Missing exact root review'):
                module.prepare(p,d,b,'on-p1',r)
        def fake_execute(args):
            self.assertIs(sys.modules['paid_budget_partitions'],module.partitions_v2)
            self.assertEqual(args.preview_file,str(paths['preview']))
            self.assertEqual(args.partition_id,'on-p1')
        with patch.object(module.adapter,'execute',side_effect=fake_execute):
            module.execute(plan,paths,(ROOT/'budget.json','on-p1',ROOT/'review.json'))
        self.assertIsNot(sys.modules.get('paid_budget_partitions'),module.partitions_v2)
if __name__=='__main__':unittest.main()
