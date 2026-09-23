import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import sys,json,hashlib,importlib.metadata
from pathlib import Path
repo=Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo');sys.path.insert(0,str(repo/'scripts'))
from anyjev_generation_control import control_messages,variant_instruction
from anyjev_benchmark import verify_artifact
from development_benchmark import digest
from transformers import AutoTokenizer
root=Path(__file__).resolve().parent;artifact=root/'anyjev-qwen06-model';baseline=repo/'results/anyjev-qwen06-generated-mps-2026-09-23/development.jsonl'
rows=[json.loads(x) for x in (repo/'data/pilot/inputs.jsonl').read_text().splitlines()];saved=[json.loads(x) for x in baseline.read_text().splitlines()]
assert len(rows)==len(saved)==60 and [r['id'] for r in rows]==[r['id'] for r in saved]
assert all(set(r)=={'id','feedback'} for r in rows)
revision=saved[0]['artifact_revision'];manifest=verify_artifact(artifact,revision)
tok=AutoTokenizer.from_pretrained(artifact,local_files_only=True)
policy=(repo/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];config=json.loads((artifact/'config.json').read_text());parent='anyjev-qwen06-generated-control'
conditions={}
for variant in ['P0','P1','P2']:
 records=[]
 for row,old in zip(rows,saved):
  assert old['policy_sha256']==digest(policy) and old['input_sha256']==digest(row['feedback']) and old['artifact_revision']==revision
  assert old['enable_thinking'] is False and old['max_input_tokens']==4096 and old['max_new_tokens']==4096
  messages=control_messages(row['feedback'],policy,variant,parent)
  rendered=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
  ids=tok(rendered,add_special_tokens=False)['input_ids'];n=len(ids);requesthash=digest(json.dumps(messages,sort_keys=True))
  if variant=='P0':assert requesthash==old['request_sha256'] and n==old['input_tokens']
  records.append({'id':row['id'],'input_sha256':digest(row['feedback']),'messages_sha256':requesthash,'rendered_prompt_sha256':digest(rendered),'input_tokens':n,'fits_original_input_limit':n<=4096,'fits_original_combined_context':n+4096<=config['max_position_embeddings']})
 _,audit=variant_instruction(control_messages('',policy)[0]['content'],variant,parent)
 conditions[variant]={'composition':audit,'min_input_tokens':min(r['input_tokens'] for r in records),'max_input_tokens':max(r['input_tokens'] for r in records),'all_fit':all(r['fits_original_input_limit'] and r['fits_original_combined_context'] for r in records),'records':records}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit={'kind':'offline_tokenizer_preflight','inference_performed':False,'model_loaded':False,'gpu_used':False,'network_used':False,'reference_labels_read':False,'baseline_file':str(baseline.relative_to(repo)),'baseline_sha256':sha(baseline),'baseline_messages_hash_matches':60,'baseline_input_token_count_matches':60,'baseline_rendered_hash_status':'Not retained historically; current rendered hashes recorded, historical message hashes and token counts reproduced.','artifact_repo':manifest['repo'],'artifact_revision':revision,'artifact_manifest_sha256':sha(artifact/'download-manifest.json'),'artifact_verification':'All manifest files verified by pinned LFS SHA256 or Git blob SHA1, including tokenizer/config/weights; no model loaded.','artifact_files':{f['rfilename']:sha(artifact/f['rfilename']) for f in manifest['siblings'] if not f['rfilename'].endswith('.safetensors')},'runtime_versions':{p:importlib.metadata.version(p) for p in ['transformers','tokenizers']},'baseline_runtime_versions':saved[0]['runtime_versions'],'settings':{'add_generation_prompt':True,'enable_thinking':False,'add_special_tokens':False,'truncation':False,'max_input_tokens':4096,'max_new_tokens':4096,'model_max_position_embeddings':config['max_position_embeddings'],'tokenizer_model_max_length':tok.model_max_length},'source_hashes':{p:sha(repo/p) for p in ['scripts/anyjev_generation_control.py','scripts/frozen_prompt_variants.py','docs/LABELING_GUIDE.md','data/pilot/inputs.jsonl']},'conditions':conditions,'protocol_eligibility':'Token/context gate evidence only. Does not authorize phase2 inference or establish smoke, frozen roster, counterbalance schedule or paired evaluation eligibility.'}
out=root/'anyjev-generated-phase2-token-preflight-2026-09-23-v2.json'
with out.open('x') as f:json.dump(audit,f,indent=2);f.write('\n')
print(json.dumps({'output':str(out),'baseline_matches':60,'limits':audit['settings'],'conditions':{k:{x:v[x] for x in ['min_input_tokens','max_input_tokens','all_fit']} for k,v in conditions.items()}}))
