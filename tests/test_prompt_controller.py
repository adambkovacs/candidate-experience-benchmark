import copy,json,shutil,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_prompt_admission as fixtures
import prompt_admission as admission
import prompt_execution_gates as g
import prompt_controller as gate
import claude_batch_benchmark as claude
import codex_batch_benchmark as codex
import codex_benchmark as single
import evaluate_prompt_variants as evaluator
from frozen_prompt_variants import compose_instruction

ROOT=Path(__file__).resolve().parents[1]
class ControllerTests(unittest.TestCase):
 def setup_run(self,d,adapter):
  h,root,m=fixtures.AdmissionTests().fixture(d);c=m['configurations'][0]
  shutil.copytree(ROOT/'schemas',root/'schemas')
  module=claude if adapter=='claude_batch_v1' else codex
  folder=ROOT/'results/subscription-batch-p0-2026-09-23'/('sonnet5-medium-phase2-batch10-p0' if adapter=='claude_batch_v1' else 'codex-gpt-5.6-luna-low-phase2-batch10-p0')
  raw=(folder/('smoke.jsonl.batches.jsonl' if adapter=='claude_batch_v1' else 'smoke-attempts.jsonl')).read_text();saved=json.loads(raw.splitlines()[0])
  raw_spec=h.write(root,'real-historical.jsonl',raw,True)
  extractor=evaluator.extract_claude_controls if adapter=='claude_batch_v1' else evaluator.extract_codex_controls
  c['controls'].update(model=saved['requested_model'],effort=saved['effort'],runtime=saved['cli_version'],adapter_controls=extractor(saved))
  if adapter=='codex_batch_v1':c['controls'].update(output_reserve_tokens=None,output_reserve_source='unexposed_cli_default_unchanged')
  c['controls_sha256']=g.canonical(c['controls']);c['controller_timeout_seconds']=600
  controller=root/'scripts'/Path(module.__file__).name;controller.parent.mkdir(exist_ok=True);shutil.copy(module.__file__,controller)
  c['controller']={'file':str(controller.relative_to(root)),'sha256':g.sha(controller.read_bytes())}
  policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
  baseline=claude.baseline_instruction('batch10') if adapter=='claude_batch_v1' else single.baseline_instruction(policy,'batch10')
  c['role']='system' if adapter=='claude_batch_v1' else 'cli_combined_prompt'
  c['baseline_instruction']=h.write(root,'actual-baseline.txt',baseline,True)
  parent=g.json_bound(c['parent_baseline'],root);parent.update(controls_sha256=c['controls_sha256'],baseline_instruction_sha256=g.sha(baseline.encode()));c['parent_baseline']=h.write(root,'actual-parent.json',parent)
  m['execution_journal']='phase-journal.jsonl'
  (root/'data/pilot').mkdir(parents=True);shutil.copy(root/m['inputs']['file'],root/'data/pilot/inputs.jsonl')
  for variant in ('P1','P2'):
   condition=c['conditions'][variant];instruction=compose_instruction(baseline,variant,role=c['role'],parent_baseline_id=c['parent_baseline_id'],root=root)['instruction'];condition['instruction']=h.write(root,variant+'-actual.txt',instruction,True)
   e=g.json_bound(condition['observational_evidence'],root);e.update(adapter=adapter,controls_sha256=c['controls_sha256'],instruction_sha256=g.sha(instruction.encode()))
   e['historical_usage']=h.write(root,variant+'-usage.json',{'kind':'saved_attempt_usage_v1','raw_attempts':raw_spec})
   if adapter=='claude_batch_v1':context={'kind':'saved_attempt_context_v1','raw_attempts':raw_spec}
   else:
    original=h.write(root,'original-catalogue.json',{'models':[{'slug':saved['requested_model'],'context_window':200000,'effective_context_window_percent':100}]})
    catalogue=h.write(root,'catalogue.json',{'kind':'codex_context_catalogue_v1','source':'official_codex_cli_models_cache','source_sha256':original['sha256']})
    context={'kind':'codex_catalogue_v1','catalogue':catalogue,'raw_catalogue':original}
   e['advertised_context']=h.write(root,variant+'-context.json',context)
   for n,req in enumerate(e['requests']):
    envelope=admission.expected_request(adapter,instruction,[{'id':i,'feedback':'Synthetic text.'} for i in req['record_ids']],c['controls'])
    req['client_request']=h.write(root,variant+str(n)+'-exact.json',envelope);req['request_bytes']=len(g.bound(req['client_request'],root))
   condition['observational_evidence']=h.write(root,variant+'-evidence.json',e)
  spec=h.write(root,'manifest.json',m)
  args=SimpleNamespace(model=saved['requested_model'],effort=saved['effort'],phase='smoke',limit=3,offset=0,batch_size=10,timeout=600,extra_usage_disabled=True,codex=saved.get('command',['codex'])[0],output=str(root/'smoke.jsonl'),attempts=str(root/'smoke-attempts.jsonl'),prompt_variant='P1',parent_baseline_id=c['parent_baseline_id'],variant_preview_output=None,prompt_execution_manifest=str(root/spec['file']),prompt_execution_manifest_sha256=spec['sha256'],prompt_configuration_id=c['id'],prompt_schedule_journal=str(root/m['execution_journal']))
  return h,root,m,c,args,module,controller,saved

 def fake_process(self,saved,adapter,calls):
  def run(cmd,**kw):
   if cmd[1:]==['auth','status']:return SimpleNamespace(returncode=0,stdout=json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}),stderr='')
   if cmd[1:]==['login','status']:return SimpleNamespace(returncode=0,stdout='Logged in using ChatGPT',stderr='')
   if cmd[1:]==['--version']:return SimpleNamespace(returncode=0,stdout=saved['cli_version'],stderr='')
   calls.append(cmd)
   records=json.loads(kw['input'] if adapter=='claude_batch_v1' else kw['input'].rsplit('\n',1)[-1])['records']
   output={'records':[{'id':r['id'],'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'} for r in records]}
   if adapter=='claude_batch_v1':
    events=copy.deepcopy(saved['raw_events'])
    for event in events:
     if event.get('type')=='result':event['structured_output']=output
    return SimpleNamespace(returncode=0,stdout=json.dumps(events),stderr='')
   (kw['cwd']/'response.json').write_text(json.dumps(output))
   return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':50}}),stderr='')
  return run

 def test_real_smoke_inspection_and_development_lifecycle(self):
  for adapter in ('claude_batch_v1','codex_batch_v1'):
   with self.subTest(adapter=adapter),tempfile.TemporaryDirectory() as d:
    h,root,m,c,args,module,controller,saved=self.setup_run(d,adapter);calls=[];manifest_bytes=Path(args.prompt_execution_manifest).read_bytes()
    with patch.object(module,'ROOT',root),patch.object(module,'__file__',str(controller)),patch.object(module.subprocess,'run',side_effect=self.fake_process(saved,adapter,calls)),patch.object(claude.shutil,'which',return_value='claude'):
     module.run(args)
     attempts=Path(str(args.output)+'.batches.jsonl') if adapter=='claude_batch_v1' else Path(args.attempts)
     raw=[json.loads(x) for x in attempts.read_text().splitlines()];pred=[json.loads(x) for x in Path(args.output).read_text().splitlines()]
     e=g.json_bound(c['conditions']['P1']['observational_evidence'],root)
     smoke={k:e[k] for k in ('condition','parent_baseline_id','controls_sha256','instruction_sha256','inputs_sha256','schema_sha256')}
     finished=g.stamp(raw[0]['started_utc'])+timedelta(seconds=raw[0]['elapsed_seconds']);now=datetime.now(timezone.utc)
     smoke.update(extractor=adapter,started_utc=raw[0]['started_utc'],finished_utc=finished.isoformat(),inspected_utc=now.isoformat(),inspection='passed',inspector='offline test inspector',records=[{'id':r['id'],'status':r['status'],'prediction':r['prediction']} for r in pred],raw_attempts={'file':str(attempts.relative_to(root)),'sha256':g.sha(attempts.read_bytes())},raw_predictions={'file':str(Path(args.output).relative_to(root)),'sha256':g.sha(Path(args.output).read_bytes())})
     smoke_spec=h.write(root,'inspection.json',smoke)
     supplement=h.write(root,'supplement.json',{'contract':'prompt-smoke-supplement-v1','execution_manifest_sha256':args.prompt_execution_manifest_sha256,'configuration_id':c['id'],'condition':'P1','smoke_evidence':smoke_spec,'development_not_before':(now+timedelta(microseconds=1)).isoformat()})
     args.phase='development';args.limit=60;args.output=str(root/'development.jsonl');args.attempts=str(root/'development-attempts.jsonl');args.prompt_smoke_supplement=str(root/supplement['file']);args.prompt_smoke_supplement_sha256=supplement['sha256']
     module.run(args)
    self.assertEqual(len(calls),7);self.assertEqual(len(Path(args.output).read_text().splitlines()),60)
    events=[json.loads(x) for x in Path(args.prompt_schedule_journal).read_text().splitlines()]
    self.assertEqual([e['stage'] for e in events if e['event']=='claimed'],['smoke','inspected_admission','development']);self.assertEqual(events[-1]['status'],'completed')
    self.assertEqual(Path(args.prompt_execution_manifest).read_bytes(),manifest_bytes)
    report=json.loads(Path(args.output+'.prompt-admission.json').read_text());self.assertTrue(report['smoke_verification']['verified']);self.assertFalse(report['fully_verified_controls'])
    if adapter=='codex_batch_v1':self.assertIsNone(report['output_reserve_tokens'])

 def test_arguments_and_missing_gate_reject_before_subprocess(self):
  for adapter in ('claude_batch_v1','codex_batch_v1'):
   for change in ('missing','model','timeout','batch','journal'):
    with self.subTest(adapter=adapter,change=change),tempfile.TemporaryDirectory() as d:
     _,root,_,_,args,module,controller,_=self.setup_run(d,adapter)
     if change=='missing':args.prompt_execution_manifest=None
     if change=='model':args.model='other'
     if change=='timeout':args.timeout=1
     if change=='batch':args.limit=10
     if change=='journal':args.prompt_schedule_journal=str(root/'other.jsonl')
     with patch.object(module,'ROOT',root),patch.object(module,'__file__',str(controller)),patch.object(module.subprocess,'run') as subprocess:
      with self.assertRaises(ValueError):module.run(args)
      subprocess.assert_not_called()

 def test_actual_request_drift_is_rejected_before_inference(self):
  with tempfile.TemporaryDirectory() as d:
   _,root,_,_,args,module,controller,saved=self.setup_run(d,'claude_batch_v1');calls=[]
   with patch.object(module,'ROOT',root),patch.object(module,'__file__',str(controller)),patch.object(module.subprocess,'run',side_effect=self.fake_process(saved,'claude_batch_v1',calls)),patch.object(claude.shutil,'which',return_value='claude'),patch.object(module,'baseline_instruction',return_value='Changed instruction'):
    with self.assertRaises(ValueError):module.run(args)
   self.assertFalse(calls)
   events=[json.loads(x) for x in Path(args.prompt_schedule_journal).read_text().splitlines()]
   self.assertEqual(events[-1]['status'],'stopped')

 def test_observed_context_diagnostic_stops_and_is_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   _,root,_,_,args,module,controller,saved=self.setup_run(d,'claude_batch_v1');calls=[]
   bad=copy.deepcopy(saved)
   for event in bad['raw_events']:
    if event.get('type')=='result':event['stop_reason']='max_tokens'
   with patch.object(module,'ROOT',root),patch.object(module,'__file__',str(controller)),patch.object(module.subprocess,'run',side_effect=self.fake_process(bad,'claude_batch_v1',calls)),patch.object(claude.shutil,'which',return_value='claude'):
    module.run(args)
   attempt=json.loads(Path(args.output+'.batches.jsonl').read_text().splitlines()[0])
   self.assertEqual(attempt['status'],'service_error');self.assertFalse(attempt['prompt_response_admission']['passed'])
   events=[json.loads(x) for x in Path(args.prompt_schedule_journal).read_text().splitlines()]
   self.assertEqual(events[-1]['status'],'stopped');self.assertEqual(len(calls),1)

 def test_supplement_cannot_be_attached_to_p0_or_preview(self):
  for variant,preview in [('P0',None),('P1','preview.json')]:
   with self.subTest(variant=variant):
    args=SimpleNamespace(prompt_variant=variant,variant_preview_output=preview,prompt_smoke_supplement='forged.json')
    with self.assertRaises(ValueError):gate.prepare(args,'claude_batch_v1',Path(claude.__file__),ROOT)

if __name__=='__main__':unittest.main()
