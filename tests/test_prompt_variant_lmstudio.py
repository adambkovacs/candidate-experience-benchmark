import copy,json,hashlib,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import evaluate_prompt_variants as e
import test_prompt_variant_evaluation as fixture_module
write=fixture_module.write
class SDKTests(unittest.TestCase):
 def fixture(self,d,role='system'):
  root,m=fixture_module.PairedTests().fixture(d);base='enable_thinking TEMPLATE <think>';template="{%- set enable_thinking = true %}\n"+base;artifact={'artifact_sha256':'a'*64,'model_path':'publisher/model.gguf','template_sha256':hashlib.sha256(base.encode()).hexdigest(),'metadata':{'tokenizer.chat_template':base}}
  evidence=write(root,'artifact.json',artifact)
  for variant in ['P0','P1','P2']:
   spec=m['conditions'][variant]['request_evidence'];old=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()];rows=[]
   for o in old:
    text=o['request']['messages'][0]['content'];feedback=json.loads(o['request']['messages'][1]['content'])
    messages=[{'role':'system','content':text},{'role':'user','content':json.dumps(feedback,separators=(',',':'))}]
    config={'temperature':.6,'maxTokens':4096,'contextOverflowPolicy':'stopAtLimit','promptTemplate':{'type':'jinja','jinjaPromptTemplate':{'template':template},'stopStrings':[]},'reasoningParsing':{'enabled':True,'startString':'<think>','endString':'</think>'},'topKSampling':20,'topPSampling':.95,'minPSampling':False}
    pred=o['prediction'];non=json.dumps(pred);reason='analysis';load={'fields':[{'key':'llm.load.contextLength','value':8192}]};resolved={'fields':[{'key':'llm.prediction.promptTemplate','value':config['promptTemplate']},{'key':'llm.prediction.temperature','value':.6},{'key':'llm.prediction.maxPredictedTokens','value':{'checked':True,'value':4096}},{'key':'llm.prediction.contextOverflowPolicy','value':'stopAtLimit'},{'key':'llm.prediction.reasoning.parsing','value':config['reasoningParsing']},{'key':'llm.prediction.topKSampling','value':20},{'key':'llm.prediction.topPSampling','value':{'checked':True,'value':.95}},{'key':'llm.prediction.minPSampling','value':{'checked':False,'value':.05}},{'key':'llm.prediction.tools','value':{'type':'none'}}]}
    rows.append({'id':o['id'],'attempt_id':o['attempt_id'],'started_utc':o['started_utc'],'status':'ok','prediction':pred,'requested_model':'loaded-id','surface':'LM Studio JavaScript SDK','thinking':'on','format':'prompt','instruction_role':'system','artifact_family':'template-controlled','artifact_sha256':'a'*64,'artifact_path':'publisher/model.gguf','template_sha256':hashlib.sha256(template.encode()).hexdigest(),'input_sha256':o['input_sha256'],'reference_labels_read':False,'request':{'messages':messages,'config':config},'model_info':{'identifier':'loaded-id','path':'publisher/model.gguf','quantization':{'name':'Q4_K_M'},'contextLength':8192,'instanceReference':'ephemeral'},'load_config':load,'prediction_config':resolved,'raw_response':'<think>'+reason+'</think>'+non,'reasoning_content':reason,'non_reasoning_content':non,'stats':{'stopReason':'eosFound','promptTokensCount':100,'predictedTokensCount':50},'timeout_seconds':600})
   m['conditions'][variant]={'predictions':write(root,variant+'.jsonl',rows,True),'request_evidence':write(root,variant+'-raw.jsonl',rows,True),'extractor':'lmstudio_sdk_v1','request_evidence_phase':'development','artifact_evidence':evidence}
  m['controls']=e.extract_lmstudio_controls(rows[0]);m['controls_sha256']=e.canonical_hash(m['controls']);return root,m
 def mutate(self,root,m,change):
  for key in ['predictions','request_evidence']:
   spec=m['conditions']['P1'][key];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()];change(rows[0]);m['conditions']['P1'][key]=write(root,spec['file'],rows,True)
 def test_actual_sdk_controls_and_native_split(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);r=e.evaluate(m,root);self.assertTrue(r['controls_verified']);self.assertFalse(r['eligible_paired_comparison']);self.assertEqual(r['conditions']['P1']['evaluation']['valid_outputs'],60);self.assertEqual(r['conditions']['P1']['telemetry']['input_tokens'],6000);self.assertIsNone(r['conditions']['P1']['telemetry']['reasoning_tokens'])
 def test_control_artifact_role_and_no_repair_guards(self):
  for kind in ['load','resolved','artifact','model','template','role','input','split','repair']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d)
    def mutate(row):
     if kind=='load':row['load_config']['fields'][0]['value']=4096
     if kind=='resolved':row['prediction_config']['fields'][1]['value']=.9
     if kind=='artifact':row['artifact_sha256']='b'*64
     if kind=='model':row['model_info']['identifier']='other'
     if kind=='template':row['request']['config']['promptTemplate']['jinjaPromptTemplate']['template']='other'
     if kind=='role':row['request']['messages'][0]['role']='user'
     if kind=='input':row['request']['messages'][1]['content']='{"feedback":"wrong"}'
     if kind=='split':row['non_reasoning_content']='wrong'
     if kind=='repair':row['non_reasoning_content']='```json\\n'+json.dumps(row['prediction'])+'\\n```';row['raw_response']='<think>'+row['reasoning_content']+'</think>'+row['non_reasoning_content']
    self.mutate(root,m,mutate)
    with self.assertRaises(ValueError):e.evaluate(m,root)
 def test_budget_failure_preserved_without_repair(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d)
   def fail(row):row.update(status='invalid_output',prediction=None,raw_response='<think>unfinished',reasoning_content='unfinished',non_reasoning_content='');row['stats']['stopReason']='maxPredictedTokensReached'
   self.mutate(root,m,fail);r=e.evaluate(m,root);self.assertEqual(r['conditions']['P1']['evaluation']['valid_outputs'],59);self.assertEqual(r['comparisons']['P0_to_P1']['valid_to_failed'],['DEV-001'])
 def test_native_user_role_exact_prefix_and_prefilled_reasoning(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);m['role']='user';artifact=json.loads((root/'artifact.json').read_text());template='add_generation_prompt <｜Assistant｜><think>';artifact['metadata']['tokenizer.chat_template']=template;artifact['template_sha256']=hashlib.sha256(template.encode()).hexdigest();artifact['artifact_sha256']='d0f0b016bb20e4e9f4978ef82123240a7f31750f675154e469664b8f292a0f1a';artifact_spec=write(root,'artifact.json',artifact)
   for variant in ['P0','P1','P2']:
    m['conditions'][variant]['artifact_evidence']=artifact_spec
    for key in ['predictions','request_evidence']:
     spec=m['conditions'][variant][key];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()]
     for row in rows:
      messages=row['request']['messages'];row['request']['messages']=[{'role':'user','content':messages[0]['content']+'\n\n'+messages[1]['content']}];row.update(artifact_sha256=artifact['artifact_sha256'],instruction_role='user',artifact_family='deepseek-r1-distill-qwen32b',thinking='native',template_sha256=hashlib.sha256(template.encode()).hexdigest());row['request']['config']['promptTemplate']['jinjaPromptTemplate']['template']=template;row['prediction_config']['fields'][0]['value']=copy.deepcopy(row['request']['config']['promptTemplate']);row['raw_response']=row['reasoning_content']+'</think>'+row['non_reasoning_content']
     m['conditions'][variant][key]=write(root,spec['file'],rows,True)
   m['controls']=e.extract_lmstudio_controls(rows[0]);m['controls_sha256']=e.canonical_hash(m['controls']);self.assertTrue(e.evaluate(m,root)['controls_verified'])

 def test_non_json_constants_are_preserved_failures(self):
  for token in ['NaN','Infinity','-Infinity']:
   with self.subTest(token=token),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d)
    self.mutate(root,m,lambda row:row.update(raw_response=token,reasoning_content='',non_reasoning_content=token,prediction=None,status='invalid_output'))
    self.assertEqual(e.evaluate(m,root)['conditions']['P1']['evaluation']['valid_outputs'],59)
 def test_canonical_runner_rejects_unsupported_capability_or_parser(self):
  for kind in ['unsupported_template','disabled_parser','wrong_parser','unsupported_effort']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d)
    artifact=json.loads((root/'artifact.json').read_text())
    if kind=='unsupported_template':
     artifact['metadata']['tokenizer.chat_template']='TEMPLATE <think>'
     artifact['template_sha256']=e.digest(artifact['metadata']['tokenizer.chat_template'])
    artifact_spec=write(root,'artifact.json',artifact)
    for variant in ['P0','P1','P2']:
     m['conditions'][variant]['artifact_evidence']=artifact_spec
     for key in ['predictions','request_evidence']:
      spec=m['conditions'][variant][key];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()]
      for row in rows:
       config=row['request']['config']
       if kind=='unsupported_template':config['promptTemplate']['jinjaPromptTemplate']['template']="{%- set enable_thinking = true %}\n"+artifact['metadata']['tokenizer.chat_template']
       if kind=='disabled_parser':config['reasoningParsing']={'enabled':False}
       if kind=='wrong_parser':config['reasoningParsing']['startString']='FAKE'
       if kind=='unsupported_effort':
        row['effort']='high';config['promptTemplate']['jinjaPromptTemplate']['template']="{%- set enable_thinking = true %}\n{%- set reasoning_effort = 'high' %}\n"+artifact['metadata']['tokenizer.chat_template']
       row['template_sha256']=e.digest(config['promptTemplate']['jinjaPromptTemplate']['template'])
       for field in row['prediction_config']['fields']:
        if field['key']=='llm.prediction.promptTemplate':field['value']=copy.deepcopy(config['promptTemplate'])
        if field['key']=='llm.prediction.reasoning.parsing':field['value']=copy.deepcopy(config['reasoningParsing'])
       row.update(raw_response=row['non_reasoning_content'],reasoning_content='')
      m['conditions'][variant][key]=write(root,spec['file'],rows,True)
    m['controls']=e.extract_lmstudio_controls(rows[0]);m['controls_sha256']=e.canonical_hash(m['controls'])
    with self.assertRaises(ValueError):e.evaluate(m,root)

if __name__=='__main__':unittest.main()
