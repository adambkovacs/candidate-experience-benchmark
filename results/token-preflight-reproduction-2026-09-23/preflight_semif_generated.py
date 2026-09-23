import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import sys,json,hashlib,subprocess,importlib.metadata
from pathlib import Path
root=Path(__file__).resolve().parent;repo=Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo');sys.path.insert(0,str(repo/'scripts'))
from specialist_benchmark import generated_messages
from development_benchmark import digest
from transformers import AutoTokenizer
artifact=root/'semif-model';source=root/'semif-source';site=root/'specialist-venv/lib/python3.12/site-packages/mlx_lm';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((artifact/'download-manifest.json').read_text());assert manifest['sha']=='851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
verified={}
for f in manifest['siblings']:
 if f['rfilename'].endswith('.safetensors'):continue
 p=artifact/f['rfilename'];data=p.read_bytes();expected=f.get('lfs',{}).get('sha256') or f.get('blobId');actual=hashlib.sha256(data).hexdigest() if f.get('lfs',{}).get('sha256') else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert actual==expected;verified[f['rfilename']]=sha(p)
tc=json.loads((artifact/'tokenizer_config.json').read_text());assert not tc.get('chat_template_type')
tok=AutoTokenizer.from_pretrained(artifact,local_files_only=True,trust_remote_code=False)
assert tok.bos_token is None
config=json.loads((artifact/'config.json').read_text());policy=(repo/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];rows=[json.loads(x) for x in (repo/'data/pilot/inputs.jsonl').read_text().splitlines()];assert len(rows)==60 and all(set(r)=={'id','feedback'} for r in rows)
conditions={}
for variant in ['P0','P1','P2']:
 rr=[]
 for row in rows:
  messages=generated_messages(row['feedback'],policy,variant,'semif-generated-bf16')
  prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
  guard=tok.encode(prompt)
  add_special_tokens=tok.bos_token is None or not prompt.startswith(tok.bos_token)
  generation=tok.encode(prompt,add_special_tokens=add_special_tokens)
  assert guard==generation
  rr.append({'id':row['id'],'messages_sha256':digest(json.dumps(messages,sort_keys=True)),'rendered_prompt_sha256':digest(prompt),'guard_input_tokens':len(guard),'generation_input_tokens':len(generation),'generation_token_ids_sha256':digest(json.dumps(generation)),'generation_add_special_tokens':add_special_tokens,'fits_original_guard':len(guard)<=4096,'fits_artifact_combined_context':len(generation)+2048<=config['text_config']['max_position_embeddings']})
 conditions[variant]={'min_tokens':min(r['generation_input_tokens'] for r in rr),'max_tokens':max(r['generation_input_tokens'] for r in rr),'all_fit':all(r['fits_original_guard'] and r['fits_artifact_combined_context'] for r in rr),'records':rr}
sourcehead=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();dirty=subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip();assert not dirty
smoke=repo/'results/semif-generated-bf16-2026-09-23/smoke.jsonl'
audit={'kind':'offline_semif_generated_token_preflight','inference_performed':False,'model_loaded':False,'gpu_used':False,'network_used':False,'reference_labels_read':False,'historical_parity':'Source reconstruction only. Saved request_sha256 hashes official decision intent, not generated messages; historical generated prompt hashes and input token counts absent. No historical generated-message/count parity claimed.','artifact_revision':manifest['sha'],'artifact_manifest_sha256':sha(artifact/'download-manifest.json'),'verified_nonweight_files':verified,'weights_rehashed':False,'semif_source_commit':sourcehead,'semif_source_clean':True,'runtime_versions':{p:importlib.metadata.version(p) for p in ['transformers','tokenizers','mlx-lm']},'baseline_smoke_sha256':sha(smoke),'source_hashes':{str(p):sha(p) for p in [source/'src/semif_phase1/mlx_backend.py',site/'generate.py',site/'tokenizer_utils.py',repo/'scripts/specialist_benchmark.py',repo/'scripts/frozen_prompt_variants.py',root/'semif_smoke_command.sh',Path(__file__)]},'settings':{'enable_thinking':False,'add_generation_prompt':True,'template_tokenize':False,'guard_tokenization':'tok.encode(prompt), default add_special_tokens=True','generation_tokenization':'Exact installed stream_generate rule: bos_token is None or not prompt.startswith(bos_token); here bos_token=None so add_special_tokens=True','tokenizer_wrapper':'encode delegated to HF tokenizer; no chat_template_type override configured','max_input_guard':4096,'max_new_tokens':2048,'temperature':0,'model_context_metadata':config['text_config']['max_position_embeddings'],'tokenizer_model_max_length':tok.model_max_length},'conditions':conditions,'limitations':['No model or runtime initialization; combined context fit is against pinned artifact metadata, not a live allocation test.','Historical generated messages/counts were not retained; this is source reconstruction.','Phase2 inference and protocol gates remain pending.'],'reproduction_command':'work/specialist-venv/bin/python work/preflight_semif_generated.py','reproduction_cwd':str(root.parent)}
out=root/'semif-generated-phase2-token-preflight-2026-09-23.json'
with out.open('x') as f:json.dump(audit,f,indent=2);f.write('\n')
print(json.dumps({'output':str(out),'sha256':sha(out),'conditions':{k:{x:v[x] for x in ['min_tokens','max_tokens','all_fit']} for k,v in conditions.items()}}))
