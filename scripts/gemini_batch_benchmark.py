#!/usr/bin/env python3
"""Native Antigravity subscription batch workflow; audited wrapper, not bare-model inference."""
import argparse, hashlib, json, os, re, subprocess, tempfile, time
from pathlib import Path
from development_benchmark import ROOT, digest, read_rows
from codex_batch_benchmark import batch_prompt, batch_schema, parse_batch, select_inputs, durable_write
from gemini_benchmark import clean_environment

AGENT='''---
name: recruitment-benchmark
description: Classify supplied fictional feedback without tools or external context.
mainAgent: true
subagent: false
model: inherit
excludeDefaultComponents: true
inheritCustomizations: false
inheritMcp: false
tools: []
mcpServers: []
skills: []
plugins: []
commandExecutionPolicy: "off"
---
# System Prompt
Classify only the supplied feedback using the supplied policy. Do not use tools, memory, files, external context or delegation. Return only the requested structured output.
'''

def context_audit(home):
    paths=['.gemini/GEMINI.md','.gemini/antigravity-cli/rules','.gemini/antigravity-cli/skills','.gemini/antigravity-cli/plugins','.gemini/config/agents','.gemini/config/mcp_config.json','.gemini/config/hooks.json']
    result=[]
    for name in paths:
        p=home/name
        item={'path':name,'exists':p.exists()}
        if p.is_file():
            raw=p.read_bytes();item.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            if raw.strip():raise RuntimeError('Nonempty global context requires review: '+name)
        elif p.exists() and any(p.iterdir()):raise RuntimeError('Nonempty global context directory requires review: '+name)
        result.append(item)
    return result

def require_credits_off(home):
    p=home/'.gemini/antigravity-cli/settings.json';settings=json.loads(p.read_text())
    if settings.get('modelProvider') not in (None,'','antigravity'):raise RuntimeError('Native subscription provider required')
    if settings.get('useG1Credits') is not False:raise RuntimeError('Explicit useG1Credits=false required before launch')
    return {'useG1Credits':False,'provider':settings.get('modelProvider','antigravity'),'settings_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

WORKFLOW_MODES=('strict','native-agent-observed-no-external-tools')

def inspect_stream(stdout,code,model,rows,workflow_mode='strict'):
    if workflow_mode not in WORKFLOW_MODES:raise ValueError('Unknown workflow mode')
    events=[];errors=[]
    for line in stdout.splitlines():
        try:
            event=json.loads(line)
            if not isinstance(event,dict):raise ValueError('nonobject event')
            events.append(event)
        except ValueError:errors.append(line)
    init=[e['init'] for e in events if e.get('event')=='init' and isinstance(e.get('init'),dict)]
    final=[e['result'] for e in events if e.get('event')=='result' and isinstance(e.get('result'),dict)]
    calls=[e for e in events if e.get('step_update',{}).get('step_type')=='tool' or e.get('step_update',{}).get('subagent_info')]
    out={'raw_events':events,'event_parse_errors':errors,'observed_tool_items':calls,'reported_model':init[0].get('model') if init else None,'available_tools':init[0].get('tools') if init else None,'status':'service_error','predictions':{},'workflow_mode':workflow_mode}
    if len(final)==1:out.update(usage=final[0].get('usage'),cli_duration_seconds=final[0].get('duration_seconds'),raw_response=final[0].get('structured_output'))
    if len(init)!=1 or len(final)!=1 or code or errors or final[0].get('status')!='SUCCESS':return out
    if init[0].get('model')!=model:out['status']='model_mismatch';return out
    tools=init[0].get('tools')
    if init[0].get('agent')!='recruitment-benchmark' or not isinstance(tools,list) or any(not isinstance(t,str) for t in tools) or (workflow_mode=='strict' and tools not in ([],['finish'])):out['status']='isolation_violation';return out
    if any(e['step_update'].get('tool_name')!='finish' or e['step_update'].get('subagent_info') for e in calls) or len(calls)>1:out['status']='isolation_violation';return out
    if calls and ('finish' not in tools or init[0].get('json_schema')!=batch_schema(rows)):out['status']='isolation_violation';return out
    out['runtime_context_controls']={k:init[0].get(k) for k in ('mcpServers','skills','plugins','memory_enabled')}
    controls_verified=all(k not in init[0] or init[0][k]==[] for k in ('mcpServers','skills','plugins')) and init[0].get('memory_enabled',False) is False
    out['context_control_verification']='Empty custom agent MCP/skills/plugins configuration and audited global context; fields absent from init are not separately runtime-exposed. Builtin/provider context remains unknown.'
    raw=final[0].get('structured_output');out.update(raw_response=raw,usage=final[0].get('usage'),cli_duration_seconds=final[0].get('duration_seconds'))
    try:
        out['predictions']=parse_batch(json.dumps(raw),rows)
        if calls:
            parameters=calls[0]['step_update'].get('tool_info',{}).get('parameters')
            if parse_batch(json.dumps(parameters),rows)!=out['predictions']:raise ValueError('Finish payload differs from structured result')
        out['native_output_mechanism']='schema-constrained finish' if calls else 'direct structured result'
        out['status']='ok' if controls_verified else 'isolation_violation'
    except (ValueError,TypeError) as e:out.update(status='invalid_output',error=str(e))
    return out

def control_warning(stderr):
    return bool(re.search(r'(?i)(warn(?:ing)?|unsupported|unknown (?:flag|agent|model)|invalid (?:flag|agent|schema)|failed to (?:load|parse|apply)|ignoring|fallback)',stderr))

def establish_credits_off(home):
    p=home/'.gemini/antigravity-cli/settings.json';settings=json.loads(p.read_text())
    if settings.get('useG1Credits') not in (None,False):raise RuntimeError('Credit overage enabled')
    # The CLI sparsely persists defaults; explicitly assert off before each call.
    if 'useG1Credits' not in settings:
        settings['useG1Credits']=False;p.write_text(json.dumps(settings,indent=2)+'\n')
    return require_credits_off(home)

def run(a):
    if a.timeout<=0:raise ValueError('Positive timeout required')
    if not a.model.endswith('-'+a.effort):raise ValueError('Model ID and effort must agree')
    workflow_mode=getattr(a,'workflow_mode','strict')
    if workflow_mode not in WORKFLOW_MODES:raise ValueError('Unknown workflow mode')
    env=clean_environment();home=Path(env['HOME']);audit=context_audit(home);credits=establish_credits_off(home)
    inventory=subprocess.run([a.agy,'models'],env=env,text=True,capture_output=True,timeout=45)
    if inventory.returncode or a.model not in [line.split()[0] for line in inventory.stdout.splitlines() if line.strip()]:raise RuntimeError('Requested native model not advertised')
    rows=select_inputs(read_rows(ROOT/'data/pilot/inputs.jsonl'),a.offset,a.limit)
    if any(set(r)!={'id','feedback'} for r in rows):raise ValueError('Unexpected input metadata')
    if a.offset%10:raise ValueError('Offset must preserve batch10 membership')
    policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    paths=[Path(a.output),Path(a.attempts),Path(a.attempts+'.journal.jsonl')]
    if any(p.exists() for p in paths):raise FileExistsError('Exclusive new outputs required')
    version=subprocess.run([a.agy,'--version'],env=env,text=True,capture_output=True,timeout=30,check=True).stdout.strip()
    with paths[0].open('x') as out,paths[1].open('x') as attempts,paths[2].open('x') as journal:
        for offset in range(0,len(rows),10):
            audit=context_audit(home);credits=establish_credits_off(home)
            group=rows[offset:offset+10];prompt=batch_prompt(policy,group);schema=batch_schema(group);bid='batch-'+str((a.offset+offset)//10+1).zfill(2)
            record={'id':bid,'phase':a.phase,'workflow':'antigravity-native-agent-batch','workflow_mode':workflow_mode,'requested_model':a.model,'returned_model':None,'effort':a.effort,'cli_version':version,'cli_binary_sha256':hashlib.sha256(Path(a.agy).read_bytes()).hexdigest(),'model_catalogue_stdout':inventory.stdout,'batch_size':len(group),'configured_batch_size':10,'record_order':[r['id'] for r in group],'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'request':{'prompt':prompt,'output_schema':schema},'request_sha256':digest(prompt),'schema_sha256':digest(json.dumps(schema,sort_keys=True)),'reference_labels_read':False,'context_audit':audit,'billing_audit':credits,'agent_definition':AGENT,'isolation_note':'Native agent workflow; builtin scaffold persists. Empty custom tool/MCP/skill/plugin lists configured; global context paths audited. Runtime init confirms requested agent/model and records advertised tools. Effective tool restriction remains unverified in observed-no-external-tools mode; every observed external tool/delegation event is rejected. No claim of bare-model isolation.','controller_timeout_seconds':a.timeout,'retry_note':'Native CLI supports internal transient retries (documented since1.2.1). Request time includes any internal retries; individual retry count unknown unless emitted in stream.'}
            start=time.perf_counter()
            with tempfile.TemporaryDirectory(prefix='agy-benchmark-',dir='/private/tmp') as t:
                cwd=Path(t);agent=cwd/'.agents/agents/recruitment-benchmark.md';agent.parent.mkdir(parents=True);agent.write_text(AGENT);sp=cwd/'schema.json';sp.write_text(json.dumps(schema))
                cmd=[a.agy,'--agent','recruitment-benchmark','--model',a.model,'--effort',a.effort,'--disable-slash-commands','--sandbox','--output-format','stream-json','--json-schema',str(sp),'--print-timeout',str(a.timeout)+'s','--log-file',str(cwd/'agy.log'),'-p',prompt]
                record['command']=cmd;durable_write(journal,{'event':'request_started',**record})
                try:
                    proc=subprocess.run(cmd,env=env,cwd=cwd,text=True,capture_output=True,timeout=a.timeout+15)
                    record.update(inspect_stream(proc.stdout,proc.returncode,a.model,group,workflow_mode),raw_stdout=proc.stdout,raw_stderr=proc.stderr,returncode=proc.returncode)
                    if control_warning(proc.stderr):
                        record['control_warning']=True
                        if record['status']=='ok':record['status']='unverified_configuration'
                except subprocess.TimeoutExpired as e:
                    decode=lambda v:v.decode(errors='replace') if isinstance(v,bytes) else(v or '')
                    record.update(status='service_error',error_type='TimeoutExpired',raw_stdout=decode(e.stdout),raw_stderr=decode(e.stderr),predictions={})
                log=cwd/'agy.log';record['runtime_log_saved']=False
                if log.exists():record['runtime_log_metadata']={'bytes':log.stat().st_size,'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
            record['elapsed_seconds']=time.perf_counter()-start;durable_write(attempts,record);durable_write(journal,{'event':'request_completed','id':bid,'status':record['status'],'elapsed_seconds':record['elapsed_seconds']})
            for i,row in enumerate(group):
                durable_write(out,{'id':row['id'],'phase':a.phase,'status':record['status'],'prediction':record['predictions'].get(row['id']),'requested_model':a.model,'returned_model':record.get('reported_model'),'surface':'Antigravity native agent subscription workflow','workflow_mode':workflow_mode,'reasoning_effort':a.effort,'batch_id':bid,'batch_size':len(group),'configured_batch_size':10,'batch_position':i,'started_utc':record['started_utc'],'batch_elapsed_seconds':record['elapsed_seconds'],'elapsed_seconds':record['elapsed_seconds']/len(group),'timing_kind':'amortized_batch_share_not_individual_latency','request_sha256':record['request_sha256'],'input_sha256':digest(row['feedback'])})
            print(bid,record['status'],round(record['elapsed_seconds'],2),flush=True)
            if record['status']!='ok':raise RuntimeError('Stopped: inspect native stream before any further request')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workflow-mode',choices=WORKFLOW_MODES,default='strict');p.add_argument('--agy',required=True);p.add_argument('--model',default='gemini-3.8-flash-low');p.add_argument('--effort',choices=['low','medium','high'],default='low');p.add_argument('--limit',type=int,choices=range(1,61),default=3);p.add_argument('--offset',type=int,default=0);p.add_argument('--timeout',type=int,default=600);p.add_argument('--phase',choices=['smoke','development'],required=True);p.add_argument('--output',required=True);p.add_argument('--attempts',required=True);run(p.parse_args())
