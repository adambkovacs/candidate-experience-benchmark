"""Offline frozen additions to an adapter's exact P0 instruction block.

This module does not read feedback/reference data or call inference. Adapters must
supply only their instruction block, retain its existing role and output method,
and perform tokenizer/context checks before any separately authorized request.
Codex combined prompts must insert this block before their feedback serialization.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=Path('prompts/variants-v1')
MANIFEST_SHA256='d4be944de76d94b85743c536997051755a0247ea13f0d27b612dbbf025fb8264'
FILES={'P1':'P1-classifier.txt','P2':'P2-classifier-sop.txt'}
SEPARATOR='\n\n'
ROLES=frozenset(('system','user','cli_combined_prompt'))

def sha(raw):return hashlib.sha256(raw).hexdigest()

def load_frozen_bundle(root=ROOT):
    """Verify exact manifest, both additions, current source policy and nesting."""
    root=Path(root);manifest_bytes=(root/BUNDLE/'manifest.json').read_bytes()
    if sha(manifest_bytes)!=MANIFEST_SHA256:raise ValueError('Frozen variant manifest changed; use a new reviewed version')
    manifest=json.loads(manifest_bytes)
    if manifest.get('version')!='variants-v1' or manifest.get('status')!='frozen_candidate_offline_only':raise ValueError('Unexpected variant bundle')
    if set(manifest.get('files',{}))!=set(FILES.values()):raise ValueError('Unexpected frozen files')
    # Match the baseline adapters' source policy selection. Nothing after the
    # simulated-routing heading enters this hash or the composition.
    policy=(root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if sha(policy.encode())!=manifest['source_policy_sha256']:raise ValueError('Source rubric changed')
    additions={}
    for variant,name in FILES.items():
        raw=(root/BUNDLE/name).read_bytes();entry=manifest['files'][name]
        if len(raw)!=entry['bytes'] or sha(raw)!=entry['sha256']:raise ValueError('Frozen candidate changed: '+name)
        additions[variant]=raw.decode('utf-8')
    if not additions['P2'].encode().startswith(additions['P1'].encode()):raise ValueError('P2 must start with verbatim P1')
    return manifest,additions

def compose_instruction(baseline_instruction,variant,*,role,parent_baseline_id,root=ROOT):
    """Return unchanged role, composed text and provenance; never alter inputs.

    P0 is the exact supplied string including Unicode and line endings. P1/P2
    append two LF bytes then the complete frozen addition. This result does not
    establish baseline eligibility, adequate context length or execution approval.
    """
    if not isinstance(baseline_instruction,str) or not baseline_instruction:raise ValueError('Require a nonempty P0 instruction string')
    if variant not in ('P0','P1','P2'):raise ValueError('Unknown prompt variant')
    if role not in ROLES:raise ValueError('Role must match system, user or cli_combined_prompt')
    if not isinstance(parent_baseline_id,str) or not parent_baseline_id.strip():raise ValueError('Require parent baseline ID')
    manifest,additions=load_frozen_bundle(root)
    addition=additions.get(variant)
    composed=baseline_instruction if addition is None else baseline_instruction+SEPARATOR+addition
    audit={'variant':variant,'parent_baseline_id':parent_baseline_id,'instruction_role':role,
        'bundle_version':manifest['version'],'manifest_path':str(BUNDLE/'manifest.json'),'manifest_sha256':MANIFEST_SHA256,
        'source_policy_sha256':manifest['source_policy_sha256'],
        'baseline_instruction_sha256':sha(baseline_instruction.encode()),'baseline_instruction_bytes':len(baseline_instruction.encode()),
        'addition_path':str(BUNDLE/FILES[variant]) if addition is not None else None,
        'addition_sha256':sha(addition.encode()) if addition is not None else None,
        'addition_bytes':len(addition.encode()) if addition is not None else 0,
        'composition_separator':SEPARATOR if addition is not None else '',
        'composed_instruction_sha256':sha(composed.encode()),'composed_instruction_bytes':len(composed.encode()),
        'token_length':None,'token_length_status':'not_measured; adapter preflight required',
        'reference_labels_read':False,'inference_performed':False}
    return {'instruction':composed,'role':role,'audit':audit}
