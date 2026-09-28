import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch

REPO=pathlib.Path(__file__).resolve().parents[1]
if not (REPO/'scripts/evaluate_prompt_variants.py').exists():
    REPO=pathlib.Path.cwd().resolve()
SOURCE=REPO/'scripts/evaluate_hosted_continuation_pairs_v1.py'
if not SOURCE.exists():SOURCE=pathlib.Path('/private/tmp/evaluate_hosted_continuation_pairs_v1.py')
spec=importlib.util.spec_from_file_location('hosted_adapter',SOURCE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class HostedContinuationPairsTest(unittest.TestCase):
    def test_real_seven_are_source_bound_and_scored(self):
        for config in module.IDS:
            with self.subTest(config=config):
                result=module.evaluate_one(REPO,config)
                self.assertTrue(result['offline_pairing_supported'])
                self.assertEqual(result['full_protocol_eligibility'],'blocked_by_observed_schedule_change')
                self.assertFalse(result['eligible_paired_comparison'])
                self.assertFalse(result['protocol_controls_verified'])
                self.assertTrue(result['protocol_gaps'])
                self.assertEqual(set(result['conditions']),{'P0','P1','P2'})
                self.assertEqual(set(result['comparisons']),{'P0_to_P1','P0_to_P2','P1_to_P2'})
                for condition in result['conditions'].values():
                    self.assertEqual(sum(condition['status_counts'].values()),60)
                    self.assertEqual(condition['evaluation']['records'],60)
    def test_gemma_stopped_suffix_then_separate_terminal_continuation(self):
        result=module.evaluate_one(REPO,'openrouter-paid-gemma4-26b-a4b-on')
        self.assertEqual(result['conditions']['P2']['status_counts'],{'ok':58,'service_error':2})
        self.assertEqual(len(result['conditions']['P2']['sources']),3)
    def test_journal_order_or_request_hash_tamper_fails(self):
        config='openrouter-paid-qwen3.8-27b-medium'
        path='results/hosted-unattempted-continuation-v2/openrouter-paid-qwen3.8-27b-medium-p1/attempts.jsonl'
        original=module.read_bound
        def tampered(root,spec):
            raw=original(root,spec)
            if spec['file']==path:
                rows=module.json_lines(raw)
                rows[1]['request_sha256']='0'*64
                return b''.join(json.dumps(x).encode()+b'\n' for x in rows)
            return raw
        with patch.object(module,'read_bound',side_effect=tampered):
            with self.assertRaisesRegex(ValueError,'Journal request hash mismatch'):
                module.evaluate_one(REPO,config)
    def test_swapped_journal_attempt_order_fails(self):
        config='openrouter-paid-qwen3.8-27b-medium'
        path='results/hosted-unattempted-continuation-v2/openrouter-paid-qwen3.8-27b-medium-p1/attempts.jsonl'
        original=module.read_bound
        def swapped(root,spec):
            raw=original(root,spec)
            if spec['file']==path:
                rows=module.json_lines(raw)
                rows[1:3],rows[3:5]=rows[3:5],rows[1:3]
                return b''.join(json.dumps(x).encode()+b'\n' for x in rows)
            return raw
        with patch.object(module,'read_bound',side_effect=swapped):
            with self.assertRaisesRegex(ValueError,'Continuation event/order/status mismatch'):
                module.evaluate_one(REPO,config)
    def test_missing_finished_event_fails(self):
        config='openrouter-paid-qwen3.8-27b-medium'
        path='results/hosted-unattempted-continuation-v2/openrouter-paid-qwen3.8-27b-medium-p1/attempts.jsonl'
        original=module.read_bound
        def missing(root,spec):
            raw=original(root,spec)
            if spec['file']==path:
                rows=module.json_lines(raw);del rows[2]
                return b''.join(json.dumps(x).encode()+b'\n' for x in rows)
            return raw
        with patch.object(module,'read_bound',side_effect=missing):
            with self.assertRaisesRegex(ValueError,'journal incomplete'):
                module.evaluate_one(REPO,config)
    def test_qwen_suffix_phase_and_plan_are_exact(self):
        x=module.evaluate_one(REPO,'openrouter-paid-qwen36-35b-a3b-off')
        self.assertTrue(any('development_suffix' in note for note in x['limitations']))
        audit=json.loads((REPO/module.AUDIT_DIR/'openrouter-paid-qwen36-35b-a3b-off.json').read_text())
        source=audit['conditions']['P2']['source_bindings'][-1]
        rows=module.json_lines(module.read_bound(REPO,source))
        changed=dict(rows[0],phase='development')
        cfg=json.loads((REPO/'results/hosted-prompt-preparation-2026-09-24/openrouter-paid-qwen36-35b-a3b-off/configuration.json').read_text())
        baseline=(REPO/cfg['baseline_instruction']['file']).read_text()
        instruction=module.compose_instruction(baseline,'P2',role='system',parent_baseline_id=cfg['id'],root=REPO)['instruction']
        inputs=module.indexed(module.json_lines((REPO/'data/pilot/inputs.jsonl').read_bytes()),set(module.EXPECTED),True)
        with self.assertRaisesRegex(ValueError,'phase/baseline mismatch'):
            module.verify_row(changed,changed['id'],'P2',instruction,{'adapter_controls':cfg['controls']['adapter_controls'],'parent_baseline_id':cfg['id']},inputs[changed['id']]['feedback'],suffix=True)
    def test_raw_request_change_rejected_before_reference_read(self):
        config='openrouter-paid-qwen3.8-27b-medium'
        rawpath='results/hosted-unattempted-continuation-v2/openrouter-paid-qwen3.8-27b-medium-p1/development.jsonl'
        original=module.read_bound;references_opened=[]
        def changed(root,spec):
            if spec['file']=='data/pilot/proposed_labels.jsonl':references_opened.append(True)
            raw=original(root,spec)
            if spec['file']==rawpath:
                rows=module.json_lines(raw);rows[0]['request']['messages'][0]['content']='tampered'
                return b''.join(json.dumps(x).encode()+b'\n' for x in rows)
            return raw
        with patch.object(module,'read_bound',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'Pinned continuation request mismatch|Frozen instruction mismatch'):
                module.evaluate_one(REPO,config)
        self.assertFalse(references_opened)

if __name__=='__main__':unittest.main()
