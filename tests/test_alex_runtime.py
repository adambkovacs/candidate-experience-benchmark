"""Runtime boundary tests; model doubles perform no loading or inference."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import specialist_benchmark as s

class AlexRuntimeTests(unittest.TestCase):
    def build(self,device='mps:0',dtype='torch.float32'):
        parameter=SimpleNamespace(device=device,dtype=dtype)
        model=SimpleNamespace(parameters=lambda:iter([parameter]))
        agent=SimpleNamespace(model=model,template='{premise} {hypothesis}',
            tok=mock.Mock(return_value={'input_ids':[1,2]}),
            predict=mock.Mock(return_value=SimpleNamespace(tolist=lambda:[[.1,.8,.1]]*14)))
        factory=mock.Mock(return_value=agent)
        modules={'torch':SimpleNamespace(float32='requested-float32'),
                 'modeling_openjev':SimpleNamespace(OpenJevCrossEncoder=factory)}
        args=SimpleNamespace(kind='alex',model_path='/offline/model',device='mps')
        return agent,factory,modules,args

    def test_reject_cpu_fallback_before_inference(self):
        agent,_,modules,args=self.build(device='cpu')
        with mock.patch.dict(sys.modules,modules),mock.patch.object(sys,'path',list(sys.path)):
            with self.assertRaisesRegex(RuntimeError,'device or dtype'):s.build_runner(args)
        agent.predict.assert_not_called()

    def test_reject_unexpected_dtype_before_inference(self):
        agent,_,modules,args=self.build(dtype='torch.bfloat16')
        with mock.patch.dict(sys.modules,modules),mock.patch.object(sys,'path',list(sys.path)):
            with self.assertRaisesRegex(RuntimeError,'device or dtype'):s.build_runner(args)
        agent.predict.assert_not_called()

    def test_actual_device_and_dtype_recorded_for_valid_runtime(self):
        agent,_,modules,args=self.build()
        with mock.patch.dict(sys.modules,modules),mock.patch.object(sys,'path',list(sys.path)):
            runner=s.build_runner(args)
            prediction,raw,metadata=runner('feedback','rubric')
        self.assertEqual(metadata['device'],'mps:0')
        self.assertEqual(metadata['dtype'],'torch.float32')
        self.assertEqual(metadata['quantization'],'none')
        self.assertEqual(metadata['input_tokens'],[2]*14)
        self.assertTrue(s.valid(prediction))
        self.assertEqual(len(raw['nli_probabilities']),14)

if __name__=='__main__':unittest.main()
