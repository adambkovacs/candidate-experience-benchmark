import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import sys,json,hashlib,subprocess,importlib.metadata
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent;repo=Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo');source=root/'openjev-source';artifact=root/'openjev-model';sys.path[:0]=[str(repo/'scripts'),str(source)]
from jev_benchmark import make_payload
from frozen_prompt_variants import compose_instruction
from development_benchmark import digest
from openjev.chat import Generator,MlxGenerator
from openjev.engine import SCAFFOLD_TEXT
from transformers import AutoTokenizer
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()=='e04794ab36e4f7e6040c2547baecdb2737ce2e79'
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()
manifest=json.loads((artifact/'download-manifest.json').read_text());assert manifest['sha']=='a7a81407613811e8ba63af92ac0d852b809e191f'
verified={}
for f in manifest['siblings']:
 if f['rfilename'].endswith('.safetensors'):continue
 p=artifact/f['rfilename'];data=p.read_bytes();expected=f.get('lfs',{}).get('sha256') or f.get('blobId');actual=hashlib.sha256(data).hexdigest() if f.get('lfs',{}).get('sha256') else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert actual==expected
 verified[f['rfilename']]=sha(p)
tok=AutoTokenizer.from_pretrained(artifact,local_files_only=True);scaffold=tok.encode(SCAFFOLD_TEXT,add_special_tokens=False)
engine=SimpleNamespace(tok=tok,scaffold=scaffold);renderer=SimpleNamespace(engine=engine,s=SimpleNamespace(upstream_model='diffusiongemma-26b',gen_max_tokens=8192))
rows=[json.loads(x) for x in (repo/'data/pilot/inputs.jsonl').read_text().splitlines()];assert len(rows)==60 and all(set(r)=={'id','feedback'} for r in rows)
policy=(repo/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];config=json.loads((artifact/'config.json').read_text());conditions={};sources={}
for mode in ['generated-off','generated-on']:
 path=repo/f'results/openjev-local-{mode}-2026-09-23/development.jsonl';saved=[json.loads(x) for x in path.read_text().splitlines()];assert [r['id'] for r in rows]==[r['id'] for r in saved];sources[str(path.relative_to(repo))]=sha(path)
 for variant in ['P0','P1','P2']:
  records=[]
  for row,old in zip(rows,saved):
   payload=make_payload(row['feedback'],policy,'diffusiongemma-26b',mode);composition=compose_instruction(payload['messages'][0]['content'],variant,role='system',parent_baseline_id='openjev-'+mode,root=repo);payload['messages'][0]['content']=composition['instruction']
   wire=digest(json.dumps(payload,sort_keys=True));upstream,_=Generator.normalize(renderer,payload);ids=MlxGenerator.prompt_ids(renderer,upstream);n=len(ids)
   if variant=='P0':assert wire==old['request_sha256'] and n==old['usage']['prompt_tokens']
   records.append({'id':row['id'],'wire_request_sha256':wire,'normalized_messages_sha256':digest(json.dumps(upstream['messages'],sort_keys=True)),'rendered_token_ids_sha256':digest(json.dumps(ids)),'input_tokens':n,'requested_max_tokens':payload['max_tokens'],'normalized_max_tokens':upstream['max_tokens'],'fits_artifact_context':n+2048<=config['text_config']['max_position_embeddings']})
  conditions[mode+'/'+variant]={'composition':composition['audit'],'min_input_tokens':min(r['input_tokens'] for r in records),'max_input_tokens':max(r['input_tokens'] for r in records),'all_fit_artifact_context':all(r['fits_artifact_context'] for r in records),'records':records}
audit={'kind':'offline_openjev_generated_token_preflight','inference_performed':False,'model_loaded':False,'gpu_used':False,'network_used':False,'reference_labels_read':False,'artifact_revision':manifest['sha'],'artifact_manifest_sha256':sha(artifact/'download-manifest.json'),'verified_nonweight_files':verified,'weights_rehashed':False,'source_commit':'e04794ab36e4f7e6040c2547baecdb2737ce2e79','source_clean':True,'source_hashes':{str(p):sha(p) for p in [source/'openjev/chat.py',source/'openjev/engine.py',source/'openjev/mlx_backend.py',repo/'scripts/jev_benchmark.py',repo/'scripts/frozen_prompt_variants.py',Path(__file__)]},'runtime_versions':{p:importlib.metadata.version(p) for p in ['transformers','tokenizers']},'baseline_files':sources,'baseline_wire_hash_matches':120,'baseline_prompt_token_count_matches':120,'rendering':'Exact pinned Generator.normalize and MlxGenerator.prompt_ids reused without constructors/network/model. JSON schema appended to system instruction by server. Requested thinking passed to template; empty thought scaffold always appended. Generation skips thought markers; that does not change prompt counts.','scaffold_text':SCAFFOLD_TEXT,'scaffold_token_ids':scaffold,'settings':{'add_generation_prompt':True,'requested_max_tokens':2048,'normalization_ceiling_used':8192,'normalization_ceiling_status':'Pinned source default; exact historical live ceiling not retained. Original wire requested2048 and historical observed counts reproduced.','artifact_text_max_position_embeddings':config['text_config']['max_position_embeddings'],'tokenizer_model_max_length':tok.model_max_length,'server_input_context_limit':'No explicit input-token/context admission check found in inspected generation path; artifact metadata is not a verified live runtime limit.'},'conditions':conditions,'limitations':['Historical rendered token IDs/hashes not retained; wire hashes and prompt token counts reproduced for both60-record baselines.','Token fit against artifact context only; live backend effective context and generation canvas limits not independently established.','No phase2 smoke, scheduling or paired evaluation gates executed.']}
out=root/'openjev-generated-phase2-token-preflight-2026-09-23-v2.json'
with out.open('x') as f:json.dump(audit,f,indent=2);f.write('\n')
print(json.dumps({'output':str(out),'conditions':{k:{x:v[x] for x in ['min_input_tokens','max_input_tokens','all_fit_artifact_context']} for k,v in conditions.items()}}))
