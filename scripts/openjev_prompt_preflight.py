#!/usr/bin/env python3
"""Offline OpenJev P0/P1/P2 native-render and capacity admission only.

No server, network request, model load, MLX inference, or reference labels.
The resulting preflight is evidence for review, not authority to execute.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from development_benchmark import read_rows, digest
from frozen_prompt_variants import compose_instruction
from jev_benchmark import make_payload

EXPECTED_COMMIT = 'e04794ab36e4f7e6040c2547baecdb2737ce2e79'
EXPECTED_REVISION = 'a7a81407613811e8ba63af92ac0d852b809e191f'
ELIGIBLE = {'generated-off': 'openjev-generated-off', 'generated-on': 'openjev-generated-on'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bound(path):
    path = Path(path)
    return {'file': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    manifest_path = Path(args.manifest).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if sha(manifest_path) != args.manifest_sha256:
        raise ValueError('Draft manifest hash mismatch')
    manifest = json.loads(manifest_path.read_text())
    if manifest['contract'] != 'openjev-generated-exact-draft-v1' or manifest['status'] != 'offline_preparation_review_required':
        raise ValueError('Not the reviewed OpenJev preparation contract')
    for key in ('inputs', 'schema', 'roster_freeze', 'schedule', 'policy_source'):
        spec = manifest[key]
        if sha(ROOT / spec['file']) != spec['sha256']:
            raise ValueError('Frozen project source changed: ' + key)
    native_audit = manifest['native_setup_audit']
    if sha(ROOT / native_audit['file']) != native_audit['sha256']:
        raise ValueError('Native baseline setup audit changed')
    setup = json.loads((ROOT / native_audit['file']).read_text())
    if (setup['source_commit'] != manifest['source_commit']
            or setup['artifact_revision'] != manifest['artifact_revision']
            or setup['runtime_versions'] != manifest['runtime_versions']
            or setup['quantization'] != manifest['quantization']
            or platform.platform() != manifest['hardware']):
        raise ValueError('Native baseline runtime, artifact, or hardware binding changed')
    scheduled = {item['id']: item['conditions'] for item in json.loads((ROOT / manifest['schedule']['file']).read_text())['order']}
    for condition in manifest['conditions']:
        if scheduled[condition['configuration_id']] != condition['variant_order']:
            raise ValueError('Counterbalanced order changed')
    source = Path(manifest['source_checkout'])
    artifact = Path(manifest['model_artifact'])
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != EXPECTED_COMMIT:
        raise ValueError('OpenJev source revision changed')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
        raise ValueError('OpenJev source checkout is not clean')
    for path, expected in manifest['source_sha256'].items():
        if sha(path) != expected:
            raise ValueError('OpenJev preflight source changed: ' + path)
    model_manifest_path = artifact / 'download-manifest.json'
    if sha(model_manifest_path) != manifest['artifact_manifest_sha256']:
        raise ValueError('Model download manifest changed')
    model_manifest = json.loads(model_manifest_path.read_text())
    if model_manifest['sha'] != EXPECTED_REVISION:
        raise ValueError('Model artifact revision changed')
    verified_artifacts = {}
    for item in model_manifest['siblings']:
        filename = item['rfilename']
        expected = item.get('lfs', {}).get('sha256')
        if expected is None:
            continue  # Nonweight files remain bound through the historical token preflight.
        actual = sha(artifact / filename)
        if actual != expected:
            raise ValueError('Model artifact hash changed: ' + filename)
        verified_artifacts[filename] = actual
    sys.path.insert(0, str(source))
    from openjev.chat import Generator, MlxGenerator
    from openjev.engine import SCAFFOLD_TEXT
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(artifact, local_files_only=True)
    scaffold = tokenizer.encode(SCAFFOLD_TEXT, add_special_tokens=False)
    renderer = SimpleNamespace(engine=SimpleNamespace(tok=tokenizer, scaffold=scaffold),
                               s=SimpleNamespace(upstream_model='diffusiongemma-26b',
                                                 gen_max_tokens=8192, mlx_max_prompt=32768))
    prior_path = ROOT / manifest['prior_token_preflight']['file']
    if sha(prior_path) != manifest['prior_token_preflight']['sha256']:
        raise ValueError('Historical token preflight changed')
    prior = json.loads(prior_path.read_text())
    if prior['source_commit'] != EXPECTED_COMMIT or prior['artifact_revision'] != EXPECTED_REVISION:
        raise ValueError('Historical token preflight identity changed')
    capacity_path = Path(manifest['corrected_capacity_audit']['file'])
    if sha(capacity_path) != manifest['corrected_capacity_audit']['sha256']:
        raise ValueError('Corrected capacity audit changed')
    capacity = json.loads(capacity_path.read_text())
    limits = capacity['source_configuration']
    if (limits['input_guard'], limits['requested_output_tokens'], limits['generation_ceiling_source_default'],
            limits['artifact_context'], limits['native_generation_canvas']) != (32768, 2048, 8192, 262144, 256):
        raise ValueError('Corrected capacity controls changed')
    for filename, expected in prior['verified_nonweight_files'].items():
        if sha(artifact / filename) != expected:
            raise ValueError('Nonweight artifact changed: ' + filename)
    rows = read_rows(ROOT / manifest['inputs']['file'])
    if bound(ROOT / manifest['inputs']['file']) != manifest['inputs'] or [r['id'] for r in rows] != [f'DEV-{n:03d}' for n in range(1, 61)]:
        raise ValueError('Exact input-only 60 changed')
    if any(set(row) != {'id', 'feedback'} for row in rows):
        raise ValueError('Reference fields found in generation inputs')
    policy = (ROOT / manifest['policy_source']['file']).read_text().split('## Simulated routing')[0]
    config = json.loads((artifact / 'config.json').read_text())
    context = config['text_config']['max_position_embeddings']
    if context != 262144 or config['canvas_length'] != 256:
        raise ValueError('Model context or native canvas changed')
    conditions = {}
    for mode, parent_id in ELIGIBLE.items():
        baseline_path = ROOT / manifest['baselines'][mode]['file']
        if bound(baseline_path) != manifest['baselines'][mode]:
            raise ValueError('Historical OpenJev baseline changed')
        saved = read_rows(baseline_path)
        if [r['id'] for r in saved] != [r['id'] for r in rows]:
            raise ValueError('Historical OpenJev baseline membership changed')
        for variant in ('P0', 'P1', 'P2'):
            measured = []
            expected_rows = prior['conditions'][mode + '/' + variant]['records']
            if len(expected_rows) != 60 or [r['id'] for r in expected_rows] != [r['id'] for r in rows]:
                raise ValueError('Historical token preflight coverage changed')
            for row, historical, expected in zip(rows, saved, expected_rows):
                payload = make_payload(row['feedback'], policy, 'diffusiongemma-26b', mode)
                composed = compose_instruction(payload['messages'][0]['content'], variant,
                    role='system', parent_baseline_id=parent_id, root=ROOT)
                payload['messages'][0]['content'] = composed['instruction']
                request_hash = digest(json.dumps(payload, sort_keys=True))
                upstream, _ = Generator.normalize(renderer, payload)
                token_ids = MlxGenerator.prompt_ids(renderer, upstream)
                measurement = {'id': row['id'], 'wire_request_sha256': request_hash,
                    'normalized_messages_sha256': digest(json.dumps(upstream['messages'], sort_keys=True)),
                    'rendered_token_ids_sha256': digest(json.dumps(token_ids)),
                    'input_tokens': len(token_ids), 'normalized_max_tokens': upstream['max_tokens']}
                if any(measurement[k] != expected[k] for k in measurement):
                    raise ValueError('Exact rendered token or request drift: ' + mode + '/' + variant + '/' + row['id'])
                if variant == 'P0' and (request_hash != historical['request_sha256'] or len(token_ids) != historical['usage']['prompt_tokens']):
                    raise ValueError('P0 historical request or prompt-token parity changed')
                if len(token_ids) > 32768 or len(token_ids) + 2048 + 255 > context:
                    raise ValueError('Input guard or generation capacity exceeded')
                measured.append(measurement)
            conditions[mode + '/' + variant] = {'records': measured,
                'min_input_tokens': min(r['input_tokens'] for r in measured),
                'max_input_tokens': max(r['input_tokens'] for r in measured)}
    result = {'contract': 'openjev-generated-exact-offline-preflight-v1',
        'manifest': bound(manifest_path), 'source_commit': EXPECTED_COMMIT,
        'artifact_revision': EXPECTED_REVISION, 'verified_artifact_sha256': verified_artifacts,
        'prior_token_preflight': manifest['prior_token_preflight'],
        'corrected_capacity_audit': manifest['corrected_capacity_audit'],
        'conditions': conditions, 'record_count': 360,
        'input_guard': 32768, 'requested_output_tokens': 2048,
        'normalization_ceiling': 8192, 'artifact_context': 262144,
        'native_canvas': 256, 'canvas_overhang_reserve': 255,
        'model_loaded': False, 'server_started': False, 'inference_performed': False,
        'reference_labels_read': False,
        'remaining_gate': 'A separately reviewed runner must verify loaded server settings and model canvas, then save smoke inspection before development.'}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'preflight': bound(output), 'record_count': 360,
                      'model_loaded': False, 'inference_performed': False}))


if __name__ == '__main__':
    main()
