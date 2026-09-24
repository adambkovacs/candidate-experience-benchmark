import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('qwen8_suffix',ROOT/'scripts/qwen8_on_p2_suffix_v1.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Qwen8SuffixTest(unittest.TestCase):
    def setUp(self):
        # The production suffix output may now exist. Exercise the immutable
        # source bindings with a copied plan and an unused, test-owned output.
        self.temp=tempfile.TemporaryDirectory(dir=module.RESULT)
        self.addCleanup(self.temp.cleanup)
        self.test_dir=Path(self.temp.name)
        original_plan=json.loads(module.PLAN.read_text())
        test_plan=self.test_dir/'plan.json'
        test_output=self.test_dir/'output.jsonl'
        original_plan['output']=str(test_output.relative_to(ROOT))
        test_plan.write_text(json.dumps(original_plan)+'\n')
        plan_patch=patch.object(module,'PLAN',test_plan)
        output_patch=patch.object(module,'OUTPUT',test_output)
        plan_patch.start();output_patch.start()
        self.addCleanup(output_patch.stop)
        self.addCleanup(plan_patch.stop)

    def test_exact_prefix_and_never_sent_suffix(self):
        plan, selected, config, _ = module.verify(module.PLAN,module.sha(module.PLAN))
        self.assertEqual(plan['ids'],[f'DEV-{i:03}' for i in range(28,61)])
        self.assertEqual(plan['prefix']['ambiguous_id'],'DEV-027')
        self.assertEqual(len(plan['prefix']['completed_ids']),26)
        self.assertEqual(len(selected),60)
        self.assertEqual(config['reasoning'],'on')
        self.assertEqual(plan['bound_usd'],'0.567570432')

    def test_tampered_plan_and_existing_output_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):
            module.verify(module.PLAN,'0'*64)
        original=Path.exists
        with patch.object(Path,'exists',lambda p: True if p==module.OUTPUT else original(p)):
            with self.assertRaisesRegex(FileExistsError,'no replay'):
                module.verify(module.PLAN,module.sha(module.PLAN))

    def test_attempted_dev028_is_rejected(self):
        journal=module.rows(module.JOURNAL)
        extra=dict(journal[-1],id='DEV-028')
        with patch.object(module,'rows',side_effect=lambda path: journal+[extra] if path==module.JOURNAL else [json.loads(x) for x in path.read_text().splitlines() if x.strip()]):
            with self.assertRaisesRegex(ValueError,'26 finished plus ambiguous'):
                module.prefix(module.ORIGINAL,module.JOURNAL,module.CHILD,module.PREVIEW)

    def test_missing_root_review_stops_before_adapter(self):
        with tempfile.TemporaryDirectory(dir=module.RESULT) as directory:
            tmp=Path(directory);budget=tmp/'budget.json';review=tmp/'review.json'
            budget.write_text(json.dumps({'version':'paid-partitions-v1','master_ledger':str(module.adapter.MASTER_LEDGER),'partitions':[{'id':'suffix','model':module.adapter.MODEL,'provider':module.adapter.PROVIDER,'reasoning':'on','cap_usd':'0.57'}]}))
            review.write_text(json.dumps({'approved':False,'plan_sha256':module.sha(module.PLAN),'script_sha256':module.sha(module.__file__),'budget_manifest_sha256':module.sha(budget),'partition_id':'suffix'}))
            with patch.object(module.adapter,'execute') as call:
                with self.assertRaisesRegex(ValueError,'root suffix review'):
                    module.execute(module.PLAN,module.sha(module.PLAN),budget,'suffix',review,'unused',300)
                call.assert_not_called()

    def test_reviewed_subset_reaches_unchanged_adapter(self):
        original_ledger=module.rows(module.CHILD)
        if original_ledger[-1].get('event')!='partition_closed':
            attempt=next(e['attempt_id'] for e in original_ledger if e.get('event')=='reserve' and e.get('record_id')=='DEV-027')
            sealed=original_ledger+[{'event':'unknown_cost_accounted_as_upper_bound','attempt_id':attempt,'usd':str(module.RESERVE)}, {'event':'partition_closed'}]
        else:
            sealed=original_ledger
        true_rows=module.rows
        def fake_rows(path):
            return sealed if path==module.CHILD else true_rows(path)
        with tempfile.TemporaryDirectory(dir=module.RESULT) as directory:
            tmp=Path(directory);budget=tmp/'budget.json';review=tmp/'review.json'
            budget.write_text(json.dumps({'version':'paid-partitions-v1','master_ledger':str(module.adapter.MASTER_LEDGER),'partitions':[{'id':'suffix','model':module.adapter.MODEL,'provider':module.adapter.PROVIDER,'reasoning':'on','cap_usd':'0.57'}]}))
            review.write_text(json.dumps({'approved':True,'plan_sha256':module.sha(module.PLAN),'script_sha256':module.sha(module.__file__),'budget_manifest_sha256':module.sha(budget),'partition_id':'suffix','ambiguous_id':'DEV-027','continue_on_invalid_output':True}))
            def fake_execute(args):
                rows, config, _, receipt, _, receipt_sha = module.adapter.reviewed_preview(args.preview_file,args.review_receipt)
                self.assertEqual([r['id'] for r in rows],module.IDS)
                self.assertEqual(config['phase'],'development_suffix')
                self.assertTrue(receipt['continue_on_invalid_output'])
                self.assertEqual(receipt_sha,module.sha(review))
                self.assertIs(sys.modules['paid_budget_partitions'],module.partitions)
            with patch.object(module,'rows',side_effect=fake_rows), patch.object(module.adapter,'execute',side_effect=fake_execute) as call:
                module.execute(module.PLAN,module.sha(module.PLAN),budget,'suffix',review,'unused',300)
                call.assert_called_once()

if __name__=='__main__':unittest.main()
