"""Verify saved hosted execution evidence for an offline paired report."""
import copy,json
from pathlib import Path
import prompt_admission as admission
import prompt_execution_gates as g
import prompt_schedule as schedule


def audit(manifest,root):
    root=Path(root);evidence=manifest['execution_evidence'];result={}
    if set(evidence)!={'P1','P2'}:raise ValueError('Both new conditions need execution evidence')
    for variant,spec in evidence.items():
        original=g.json_bound(spec['execution_manifest'],root)
        supplemental=g.json_bound(spec['smoke_supplement'],root)
        cid=manifest['parent_baseline_id']
        if supplemental.get('contract')!='prompt-smoke-supplement-v1' or supplemental.get('execution_manifest_sha256')!=spec['execution_manifest']['sha256'] or supplemental.get('configuration_id')!=cid or supplemental.get('condition')!=variant:raise ValueError('Execution supplement binding differs')
        runtime_manifest=copy.deepcopy(original)
        configs=[c for c in runtime_manifest['configurations'] if c['id']==cid]
        if len(configs)!=1:raise ValueError('Missing execution configuration')
        config=configs[0]
        if config['parent_baseline_id']!=cid or config['role']!=manifest['role'] or config['controls']['adapter_controls']!=manifest['controls']:raise ValueError('Paired controls differ from executed controls')
        if g.bound(config['baseline_instruction'],root)!=g.bound(manifest['baseline_instruction'],root) or g.bound(original['inputs'],root)!=g.bound(manifest['inputs'],root):raise ValueError('Paired inputs or baseline instruction differ')
        config['conditions'][variant].update(smoke_evidence=supplemental['smoke_evidence'],development_not_before=supplemental['development_not_before'])
        expected=admission.admit_development(runtime_manifest,root,cid,variant)
        actual=g.json_bound(spec['development_admission'],root)
        if any(actual.get(k)!=v for k,v in expected.items()) or actual.get('execution_manifest_sha256')!=spec['execution_manifest']['sha256'] or actual.get('smoke_supplement')!=spec['smoke_supplement'] or actual.get('live_runtime')!=config['controls']['runtime']:raise ValueError('Saved admission differs from reproduced evidence')
        events=[json.loads(line) for line in g.bound(spec['journal'],root).decode().splitlines() if line.strip()]
        order=schedule._schedule(original['schedule'],root)
        state,_=schedule._replay(events,original['schedule'],order,root)
        phase=state.get(cid,{}).get(variant,{})
        if set(phase)!=set(schedule.STAGES) or any(phase[s]['status']!='completed' for s in schedule.STAGES):raise ValueError('Condition has no complete smoke/inspection/development lifecycle')
        aid=phase['development']['attempt_id'];finish=next(e for e in events if e.get('event')=='finished' and e.get('attempt_id')==aid)
        required=[spec['development_admission'],manifest['conditions'][variant]['predictions'],manifest['conditions'][variant]['request_evidence']]
        if any(binding not in finish['evidence'] for binding in required):raise ValueError('Reported development files differ from journalled outputs')
        raw=[json.loads(line) for line in g.bound(manifest['conditions'][variant]['request_evidence'],root).decode().splitlines() if line.strip()]
        context=config['controls']['context_tokens'];reserve=config['controls']['output_reserve_tokens']
        limit=None if context is None else context-(reserve or 0)
        adapter=g.json_bound(config['conditions'][variant]['observational_evidence'],root)['adapter']
        if not all(admission.audit_response(row,adapter,limit)['passed'] for row in raw):raise ValueError('Development context diagnostics failed')
        result[variant]={'verified':True,'development_attempt_id':aid,'execution_manifest':spec['execution_manifest'],'journal_snapshot':spec['journal'],'observational':True}
    return {'status':'verified_observational','conditions':result,'fully_verified_controls':False,'missing_audit_capabilities':[], 'note':'Frozen roster, client requests, inspected smoke and completed schedule reproduced from saved evidence. Hidden provider rendering remains unverified; historical baseline reuse does not establish causality.'}
