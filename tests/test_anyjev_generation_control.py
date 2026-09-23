import json
from pathlib import Path
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import anyjev_generation_control as runner

class GenerationControlTests(unittest.TestCase):
    def test_fresh_requests_keep_policy_and_schema_without_labels(self):
        a=runner.control_messages('First feedback','Full rubric sentinel')
        b=runner.control_messages('Second feedback','Full rubric sentinel')
        self.assertIn('Full rubric sentinel',a[0]['content'])
        self.assertIn('Required JSON schema',a[0]['content'])
        self.assertNotIn('First feedback',json.dumps(b))
        self.assertNotIn('proposed_labels',json.dumps(a))
        self.assertEqual(len(a),2)

    def test_cli_input_budget_is_explicit(self):
        argv=['runner','--model-path','model','--revision','rev','--device','cpu','--dtype','float32','--output','out','--config-note','note','--max-input-tokens','1234']
        with mock.patch.object(sys,'argv',argv),mock.patch.object(runner,'run') as call:
            runner.main()
        self.assertEqual(call.call_args.args[0].max_input_tokens,1234)

    def test_truncated_or_invalid_json_is_not_scored_valid(self):
        good=json.dumps({'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'})
        self.assertIsNotNone(runner.parse_generated(good,True))
        self.assertIsNone(runner.parse_generated(good,False))
        self.assertIsNone(runner.parse_generated('```json\n'+good+'\n```',True))
        self.assertIsNone(runner.parse_generated('{}',True))

if __name__=='__main__':unittest.main()
