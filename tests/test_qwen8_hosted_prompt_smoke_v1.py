import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('prompt',ROOT/'scripts/qwen8_hosted_prompt_smoke_v1.py')
prompt=importlib.util.module_from_spec(spec);spec.loader.exec_module(prompt)
FOLDER=ROOT/'results/qwen8-hosted-prompt-smoke-prep-v1'

class PromptSmokeTest(unittest.TestCase):
    def plan(self,mode,variant):
        p=FOLDER/f'{mode}-{variant.lower()}-smoke-plan.json';return p,prompt.sha(p)
    def test_all_four_exact_preview_and_routing(self):
        for mode in ('off','on'):
            for variant in ('P1','P2'):
                with self.subTest(mode=mode,variant=variant):
                    p,d=self.plan(mode,variant);m,paths,budget=prompt.prepare(p,d)
                    self.assertIsNone(budget);self.assertEqual(m['record_ids'],['DEV-001','DEV-002','DEV-003'])
                    for line in paths['preview'].read_text().splitlines():
                        req=json.loads(line)['request']
                        self.assertEqual(req['provider']['only'],['alibaba'])
                        self.assertIs(req['provider']['allow_fallbacks'],False)
                        self.assertEqual(req['response_format'],{'type':'json_object'})
                        self.assertEqual(req['reasoning'],{'enabled':mode=='on'})
                        self.assertEqual(set(json.loads(req['messages'][1]['content'])),{'feedback'})
    def test_partition_bound(self):
        p,d=self.plan('off','P1')
        with patch.object(prompt,'reservation',return_value=prompt.number('0.020000001')):
            with self.assertRaisesRegex(ValueError,'reserve bound'):
                prompt.prepare(p,d)
    def test_exclusive_output(self):
        p,d=self.plan('on','P2');target=ROOT/json.loads(p.read_text())['output'];old=Path.exists
        def exists(path):return True if path==target else old(path)
        with patch.object(Path,'exists',exists):
            with self.assertRaisesRegex(FileExistsError,'no replay'):
                prompt.prepare(p,d)
    def test_receipt_and_v2_helper(self):
        p,d=self.plan('off','P2');m,paths,_=prompt.prepare(p,d)
        with tempfile.TemporaryDirectory(dir=FOLDER) as temp:
            folder=Path(temp);b=folder/'budget.json';r=folder/'review.json'
            b.write_text(json.dumps({'partitions':[{'id':'off-p2','model':'qwen/qwen3-8b','provider':'alibaba','reasoning':'off','cap_usd':'0.06'}]}))
            r.write_text(json.dumps({'approved':False,'prompt_smoke_plan_sha256':d,'wrapper_sha256':prompt.sha(prompt.__file__),'budget_manifest_sha256':prompt.sha(b),'partition_id':'off-p2','continue_on_invalid_output':True}))
            with self.assertRaisesRegex(ValueError,'Missing exact root review'):
                prompt.prepare(p,d,b,'off-p2',r)
        def fake_execute(args):
            self.assertIs(sys.modules['paid_budget_partitions'],prompt.partitions_v2)
            self.assertEqual(args.preview_file,str(paths['preview']))
            self.assertEqual(args.partition_id,'off-p2')
        with patch.object(prompt.adapter,'execute',side_effect=fake_execute):
            prompt.execute(m,paths,(ROOT/'budget.json','off-p2',ROOT/'review.json'))
        self.assertIsNot(sys.modules.get('paid_budget_partitions'),prompt.partitions_v2)
if __name__=='__main__':unittest.main()
