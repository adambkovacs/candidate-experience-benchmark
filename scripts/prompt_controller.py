"""Shared P1/P2 runtime admission and journal integration. No inference here."""
import json
import os
from datetime import datetime,timezone
from pathlib import Path
import prompt_admission as admission
import prompt_execution_gates as gates
import prompt_schedule as schedule


def add_arguments(parser):
    parser.add_argument('--prompt-execution-manifest')
    parser.add_argument('--prompt-execution-manifest-sha256')
    parser.add_argument('--prompt-configuration-id')
    parser.add_argument('--prompt-schedule-journal')
    parser.add_argument('--prompt-smoke-supplement')
    parser.add_argument('--prompt-smoke-supplement-sha256')


def prepare(args,adapter,controller_path,root):
    variant=getattr(args,'prompt_variant',None)
    fields=('prompt_execution_manifest','prompt_execution_manifest_sha256','prompt_configuration_id','prompt_schedule_journal','prompt_smoke_supplement','prompt_smoke_supplement_sha256')
    if variant not in ('P1','P2') or getattr(args,'variant_preview_output',None):
        if any(getattr(args,f,None) for f in fields):raise ValueError('Execution gate flags require live P1/P2')
        return None
    if not all(getattr(args,f,None) for f in fields[:4]):raise ValueError('P1/P2 execution gates require frozen execution manifest, hash, configuration and journal')
    return Guard(args,adapter,Path(controller_path),Path(root))


class Guard:
    def __init__(self,args,adapter,controller_path,root):
        self.args=args;self.adapter=adapter;self.root=root;self.phase=args.phase
        self.variant=args.prompt_variant;self.cid=args.prompt_configuration_id
        if self.phase not in ('smoke','development'):raise ValueError('Unsupported execution phase')
        path=Path(args.prompt_execution_manifest).resolve();path.relative_to(root.resolve())
        raw=path.read_bytes()
        if gates.sha(raw)!=args.prompt_execution_manifest_sha256:raise ValueError('Execution manifest hash mismatch')
        self.manifest=json.loads(raw)
        supplement=getattr(args,'prompt_smoke_supplement',None)
        supplement_hash=getattr(args,'prompt_smoke_supplement_sha256',None)
        self.supplement_binding=None
        if self.phase=='development':
            if not supplement or not supplement_hash:raise ValueError('Development requires separately bound inspected smoke supplement')
            supplement_path=Path(supplement).resolve();relative=supplement_path.relative_to(root.resolve())
            self.supplement_binding={'file':str(relative),'sha256':supplement_hash}
            evidence=gates.json_bound(self.supplement_binding,root)
            if set(evidence)!={'contract','execution_manifest_sha256','configuration_id','condition','smoke_evidence','development_not_before'} or evidence['contract']!='prompt-smoke-supplement-v1' or evidence['execution_manifest_sha256']!=args.prompt_execution_manifest_sha256 or evidence['configuration_id']!=self.cid or evidence['condition']!=self.variant:raise ValueError('Smoke supplement must bind immutable original manifest and condition')
            matches=[c for c in self.manifest['configurations'] if c['id']==self.cid]
            if len(matches)!=1:raise ValueError('Supplement configuration not scheduled')
            condition=matches[0]['conditions'][self.variant]
            condition['smoke_evidence']=evidence['smoke_evidence']
            condition['development_not_before']=evidence['development_not_before']
        elif supplement or supplement_hash:raise ValueError('Smoke cannot use a post-smoke supplement')
        self.config,self.condition,self.evidence,*_=admission._checked(self.manifest,root,self.cid,self.variant)
        if self.evidence['adapter']!=adapter:raise ValueError('Manifest adapter differs from actual controller')
        binding=self.config['controller'];gates.bound(binding,root)
        if (root/binding['file']).resolve()!=controller_path.resolve():raise ValueError('Controller source binding mismatch')
        self.journal=Path(args.prompt_schedule_journal).resolve()
        expected=(root/self.manifest['execution_journal']).resolve();expected.relative_to(root.resolve())
        if self.journal!=expected:raise ValueError('Journal differs from frozen execution path')
        controls=self.config['controls'];self.controls=controls
        effort=getattr(args,'reasoning',None) if adapter=='openrouter_paid_v1' else args.effort
        if args.model!=controls['model'] or effort!=controls['effort'] or args.parent_baseline_id!=self.config['parent_baseline_id']:raise ValueError('Actual model/effort/parent arguments differ')
        if self.config.get('controller_timeout_seconds')!=args.timeout:raise ValueError('Controller timeout differs from frozen controls')
        if adapter=='openrouter_paid_v1':
            if args.max_tokens!=controls['output_reserve_tokens'] or getattr(args,'start',1)!=1:raise ValueError('OpenRouter budget/start differs')
        else:
            if args.limit!=(3 if self.phase=='smoke' else 60) or getattr(args,'offset',0)!=0 or getattr(args,'batch_size',10)!=10:raise ValueError('Phase2 requires complete three-record smoke or six ordered batches of ten')
        if adapter=='claude_batch_v1' and not args.extra_usage_disabled:raise ValueError('Claude extra usage must stay disabled')
        self.result=(admission.admit_smoke if self.phase=='smoke' else admission.admit_development)(self.manifest,root,self.cid,self.variant)
        if self.phase=='development' and datetime.now(timezone.utc)<gates.stamp(self.condition['development_not_before']):raise ValueError('Development cannot precede frozen not-before time')
        requests=self.evidence['requests'];smoke_count=3 if adapter=='openrouter_paid_v1' else 1
        self.requests=requests[:smoke_count] if self.phase=='smoke' else requests[smoke_count:]
        self.index=0;self.responses=0;self.failed=False;self.claimed=None
        self.artifact=Path(str(args.output)+'.prompt-admission.json')
        self.artifact.resolve().relative_to(root.resolve())
        if self.artifact.exists():raise FileExistsError('Admission output already exists')

    def begin(self,version):
        if self.claimed is not None:raise ValueError('Phase already claimed')
        if version!=self.controls['runtime']:raise ValueError('Live runtime differs from frozen controls')
        # Preserve admitted evidence before claiming. A later interruption leaves
        # an unmatched claim; the scheduler never silently retries it.
        result={**self.result,'live_runtime':version,'execution_manifest_sha256':self.args.prompt_execution_manifest_sha256,'smoke_supplement':self.supplement_binding}
        with self.artifact.open('x') as out:
            json.dump(result,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
        if self.phase=='development':
            inspected=schedule.claim(self.manifest['schedule'],self.journal,self.cid,self.variant,'inspected_admission',self.root)
            schedule.finish(self.manifest['schedule'],self.journal,inspected['attempt_id'],'completed',[self._binding(self.artifact)],self.root)
        self.claimed=schedule.claim(self.manifest['schedule'],self.journal,self.cid,self.variant,self.phase,self.root)

    def check_request(self,request,record_ids,adapter_controls):
        if self.claimed is None or self.index>=len(self.requests):raise ValueError('Request outside claimed phase')
        expected=self.requests[self.index]
        if record_ids!=expected['record_ids']:raise ValueError('Actual request membership/order differs')
        envelope={'request':request,'adapter_controls':adapter_controls}
        if envelope!=gates.json_bound(expected['client_request'],self.root):raise ValueError('Actual request or controls differ from admitted bytes')
        self.index+=1

    def check_response(self,record):
        if self.responses>=self.index:raise ValueError('Response has no checked request')
        limit=self.controls['context_tokens'];limit=None if limit is None else limit-(self.controls['output_reserve_tokens'] or 0)
        result=admission.audit_response(record,self.adapter,limit)
        self.responses+=1
        if not result['passed'] or record.get('status') not in ('ok','invalid_output'):self.failed=True
        return result

    def _binding(self,path):
        path=Path(path).resolve();relative=path.relative_to(self.root.resolve())
        return {'file':str(relative),'sha256':gates.sha(path.read_bytes())}

    def finish(self,paths,completed):
        if self.claimed is None:return
        evidence=[self._binding(self.artifact)]
        evidence.extend(self._binding(p) for p in paths if Path(p).exists())
        successful=completed and not self.failed and self.index==self.responses==len(self.requests)
        schedule.finish(self.manifest['schedule'],self.journal,self.claimed['attempt_id'],'completed' if successful else 'stopped',evidence,self.root)
        self.claimed=None
