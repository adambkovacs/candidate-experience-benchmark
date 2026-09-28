#!/usr/bin/env python3
"""Candidate AnyJev L2 repeat wrapper. No model load on import or `verify`."""
import argparse
import dataclasses
import fcntl
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCE = ROOT / 'scripts/anyjev_l2_cv.py'
PROTOCOL = ROOT / 'results/anyjev-l2-protocol-2026-09-24/protocol-v3.json'
FOLDS = ROOT / 'results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json'
HISTORY = ROOT / 'results/anyjev-l2-cv5-hf517-v1-2026-09-24'
SHARED_LOCK = ROOT / 'results/prompt-comparison-v1-2026-09-24/local-gpu.lock'
HOST_LOCK = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
HISTORICAL_HASHES = {
    'protocol': 'fc0e4092d3ad99fe6bc70dd800c516ee7a141c2cf055b16511b4834a6dc7c92d',
    'folds': '7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c',
    'full': '42c5ec0fb172bb33e4cff3b49bd44406332fc1e594cca3bfdc5e6c82dc1ee17e',
    'collection': '41d27495291170ddd312e9a3e81a4fc23806b515d2e7879d44d0823620d83ab1',
}
PHASES = ('repeat2', 'repeat3')
STAGES = ('smoke', 'full')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def verify_history():
    for name, path in {'protocol': PROTOCOL, 'folds': FOLDS,
                       'full': HISTORY / 'full.jsonl',
                       'collection': HISTORY / 'collection-manifest.json'}.items():
        if sha(path) != HISTORICAL_HASHES[name]:
            raise ValueError(f'historical {name} bytes changed')
    collection = read_json(HISTORY / 'collection-manifest.json')
    if (collection.get('rows') != 60 or collection.get('fit_count') != 20 or
            collection.get('composition', {}).get('reviewed_smoke_rows') != 3 or
            collection.get('composition', {}).get('new_held_out_rows') != 57):
        raise ValueError('historical L2 staged composition changed')


def load_base():
    """Private module instance: never mutate canonical anyjev_l2_cv globals."""
    spec = importlib.util.spec_from_file_location('_anyjev_l2_repeat_base', BASE_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_plan(path, *, phase, stage):
    verify_history()
    plan = read_json(path)
    if phase not in PHASES or stage not in STAGES:
        raise ValueError('Unscheduled phase or stage')
    expected = {
        'contract': 'anyjev-l2-repeat-plan-v1', 'phase': phase,
        'controller_sha256': sha(__file__), 'base_runner_sha256': sha(BASE_SOURCE),
        'protocol_sha256': HISTORICAL_HASHES['protocol'],
        'fold_sha256': HISTORICAL_HASHES['folds'],
        'historical_full_sha256': HISTORICAL_HASHES['full'],
        'historical_collection_sha256': HISTORICAL_HASHES['collection'],
        'gpu_lock': str(SHARED_LOCK), 'host_lock': str(HOST_LOCK),
        'smoke_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
        'model_revision': 'c1899de289a04d12100db370d81485cdf75e47ca',
        'device': 'mps', 'dtype': 'bfloat16', 'batch_size': 4,
        'max_context': 4096, 'quantization': 'none',
        'fit_controls': {'layers': None, 'kinds': ['lda', 'ridge'],
                         'n_folds': 5, 'seed': 0, 'listing': 'auto'},
        'label_boundary': 'code-enforced 48 train labels per fold; no OS isolation',
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise ValueError(f'plan {key} differs')
    output_dir = Path(plan['output_dir']).resolve()
    if output_dir != ROOT / 'results/repeatability-v1/anyjev-l2-cv5-v1' / phase:
        raise ValueError('phase output identity differs')
    if not Path(plan['model_path']).is_absolute():
        raise ValueError('model path must be absolute')
    run_manifest = Path(plan['run_manifest'])
    if sha(run_manifest) != plan.get('run_manifest_sha256'):
        raise ValueError('pinned base run manifest changed')
    if phase == 'repeat3':
        prior = ROOT / 'results/repeatability-v1/anyjev-l2-cv5-v1/repeat2/full.repeat-completion.json'
        if not prior.exists() or sha(prior) != plan.get('prior_completion_sha256'):
            raise ValueError('repeat2 completion missing or changed')
        verify_completion(prior, phase='repeat2', stage='full')
    return plan


def validate_review(path, *, plan_path, phase, stage, output_dir):
    receipt = read_json(path)
    expected = {'decision': 'approved', 'phase': phase, 'stage': stage,
                'plan_sha256': sha(plan_path), 'controller_sha256': sha(__file__),
                'scope': 'one native L2 stage only'}
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError(f'stage review {key} differs')
    if stage == 'full':
        raw = output_dir / 'smoke.raw.jsonl'
        rows = output_dir / 'smoke.jsonl'
        smoke_completion = output_dir / 'smoke.repeat-completion.json'
        if not raw.exists() or not rows.exists():
            raise ValueError('smoke raw/rows missing')
        if receipt.get('smoke_raw_sha256') != sha(raw) or receipt.get('smoke_rows_sha256') != sha(rows):
            raise ValueError('inspected smoke bytes changed')
        if not smoke_completion.exists() or receipt.get('smoke_completion_sha256') != sha(smoke_completion):
            raise ValueError('inspected smoke completion changed')
        verify_completion(smoke_completion, phase=phase, stage='smoke')
    return receipt


def _jsonable(value):
    """Lossless for native decision fields; represent nonfinite numbers explicitly."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {'nonfinite_float': repr(value)}
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, 'tolist'):
        return _jsonable(value.tolist())
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name))
                for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError('native raw dictionary has non-string key')
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise TypeError(f'cannot durably capture native type {type(value).__name__}')


def append_raw(path, operation, identity, result):
    item = {'operation': operation, 'identity': identity, 'result': _jsonable(result)}
    line = json.dumps(item, ensure_ascii=False, allow_nan=False, sort_keys=True) + '\n'
    path = Path(path)
    with path.open('a') as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return item


def capturing_audited_call(base, raw_path):
    """Persist returned native object before caller projection or fit validation."""
    def audited(handle, operation, identity, callback):
        base.append_event(handle, 'started', operation=operation, **identity)
        try:
            result = callback()
            append_raw(raw_path, operation, identity, result)
            if operation == 'predict' and (not isinstance(result, list) or len(result) != 1
                                           or getattr(result[0], 'level', None) != 'L2'):
                raise ValueError('native prediction level differs from required L2')
        except BaseException as exc:
            base.append_event(handle, 'finished', operation=operation,
                              status='failed', error_type=type(exc).__name__,
                              error_message=str(exc), **identity)
            raise
        base.append_event(handle, 'finished', operation=operation, status='ok', **identity)
        return result
    return audited


def verify_raw_stage(output_dir, stage):
    """Reconcile one raw capture per completed native operation."""
    path = Path(output_dir) / f'{stage}.raw.jsonl'
    journal = Path(output_dir) / f'{stage}.operations.jsonl'
    if not path.exists() or not journal.exists():
        raise ValueError('native raw or operation journal missing')
    raw = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    events = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    completed = [e for e in events if e.get('event') == 'finished' and e.get('status') == 'ok'
                 and e.get('operation') in ('fit_head', 'predict')]
    if len(raw) != len(completed):
        raise ValueError('raw capture count differs from completed native operations')
    for capture, event in zip(raw, completed):
        if capture['operation'] != event['operation'] or capture['identity'] != {
                key: event[key] for key in capture['identity']}:
            raise ValueError('raw capture identity differs from journal')
    return {'raw_sha256': sha(path), 'completed_native_operations': len(completed)}


def stage_binding_paths(output_dir, stage):
    folder = Path(output_dir)
    names = [f'{stage}.raw.jsonl', f'{stage}.operations.jsonl',
             f'{stage}.attempts.jsonl', f'{stage}.jsonl']
    if stage == 'smoke':
        names += [f'fold-{fold}-artifacts.json' for fold in (1, 4, 5)]
    else:
        names += ['collection-manifest.json', 'smoke.repeat-completion.json']
        names += [f'fold-{fold}-artifacts.json' for fold in range(1, 6)]
    return {name: folder / name for name in names}


def verify_completion(path, *, phase, stage):
    """Check terminal wrapper evidence, including every bound stage byte."""
    path = Path(path)
    record = read_json(path)
    expected = {'contract': 'anyjev-l2-repeat-completion-v1',
                'phase': phase, 'stage': stage, 'status': 'completed',
                'controller_sha256': sha(__file__)}
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError('wrapper completion identity differs')
    expected_names = set(stage_binding_paths(path.parent, stage))
    if set(record.get('stage_bindings', {})) != expected_names:
        raise ValueError('wrapper completion stage files differ')
    for name, target in stage_binding_paths(path.parent, stage).items():
        if not target.is_file() or sha(target) != record['stage_bindings'][name]:
            raise ValueError(f'wrapper completion {name} changed')
    external = record.get('external_bindings')
    if not isinstance(external, dict) or set(external) != {'plan', 'review', 'run_manifest', 'base_runner'}:
        raise ValueError('wrapper completion external sources missing')
    for item in external.values():
        target = Path(item['path'])
        if not target.is_file() or sha(target) != item['sha256']:
            raise ValueError('wrapper completion source changed')
    journal = [json.loads(line) for line in
               (path.parent / f'{stage}.operations.jsonl').read_text().splitlines() if line.strip()]
    if not journal or journal[-1].get('event') != 'terminal' or journal[-1].get('status') != 'completed':
        raise ValueError('base native stage is not terminal complete')
    reconciled = verify_raw_stage(path.parent, stage)
    expected_count = 24 if stage == 'smoke' else 236
    if reconciled['completed_native_operations'] != expected_count:
        raise ValueError('native operation count differs from staged protocol')
    if record.get('raw_sha256') != reconciled['raw_sha256']:
        raise ValueError('wrapper raw digest differs')
    if stage == 'full':
        smoke = path.parent / 'smoke.repeat-completion.json'
        verify_completion(smoke, phase=phase, stage='smoke')
        if record.get('smoke_completion_sha256') != sha(smoke):
            raise ValueError('wrapper full smoke dependency changed')
        if record.get('base_smoke_review_sha256') != sha(Path(record['base_smoke_review_path'])):
            raise ValueError('base smoke review changed')
    return record


def write_completion(output_dir, *, phase, stage, plan_path, review_path,
                     run_manifest, base_smoke_review=None):
    folder = Path(output_dir)
    if stage == 'full':
        verify_completion(folder / 'smoke.repeat-completion.json', phase=phase, stage='smoke')
    reconciled = verify_raw_stage(folder, stage)
    journal = [json.loads(line) for line in
               (folder / f'{stage}.operations.jsonl').read_text().splitlines() if line.strip()]
    if not journal or journal[-1].get('status') != 'completed':
        raise ValueError('cannot seal nonterminal native stage')
    record = {'contract': 'anyjev-l2-repeat-completion-v1',
              'phase': phase, 'stage': stage, 'status': 'completed',
              'controller_sha256': sha(__file__),
              'raw_sha256': reconciled['raw_sha256'],
              'stage_bindings': {name: sha(path)
                                 for name, path in stage_binding_paths(folder, stage).items()},
              'external_bindings': {key: {'path': str(Path(path).resolve()), 'sha256': sha(path)}
                                    for key, path in {'plan': plan_path, 'review': review_path,
                                                      'run_manifest': run_manifest,
                                                      'base_runner': BASE_SOURCE}.items()}}
    if stage == 'full':
        record['smoke_completion_sha256'] = sha(folder / 'smoke.repeat-completion.json')
        record['base_smoke_review_path'] = str(Path(base_smoke_review).resolve())
        record['base_smoke_review_sha256'] = sha(base_smoke_review)
    path = folder / f'{stage}.repeat-completion.json'
    with path.open('x') as handle:
        json.dump(record, handle, sort_keys=True, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    verify_completion(path, phase=phase, stage=stage)
    return {'wrapper_completion_path': str(path), 'wrapper_completion_sha256': sha(path)}


@contextmanager
def common_host_lock(path):
    """Coordinate with Laya, SemIf, and AnyJev native repeat controllers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('common native host lock is busy') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_stage(plan_path, review_path, stage, smoke_review=None):
    phase = read_json(plan_path)['phase']
    plan = validate_plan(plan_path, phase=phase, stage=stage)
    output_dir = Path(plan['output_dir'])
    validate_review(review_path, plan_path=plan_path, phase=phase,
                    stage=stage, output_dir=output_dir)
    if stage == 'full':
        verify_completion(output_dir / 'smoke.repeat-completion.json', phase=phase, stage='smoke')
    if stage == 'smoke' and output_dir.exists():
        raise FileExistsError('smoke phase already claimed')
    if stage == 'full' and (not smoke_review or not Path(smoke_review).exists()):
        raise ValueError('full stage requires base runner smoke review')
    if (output_dir / f'{stage}.raw.jsonl').exists():
        raise FileExistsError('native raw capture already exists')
    base = load_base()
    if base.GPU_LOCK != SHARED_LOCK:
        raise ValueError('base runner common GPU lock changed')
    if base.FIT_KWARGS != {'layers': None, 'kinds': ('lda', 'ridge'),
                           'n_folds': 5, 'seed': 0, 'listing': 'auto'}:
        raise ValueError('base fit controls changed')
    base.audited_call = capturing_audited_call(base, output_dir / f'{stage}.raw.jsonl')
    original_make_decider = base.make_decider
    def make_raw_decider(backend, decider_class):
        class RawDecider(decider_class):
            def decide_batch(self, states, question, level=None, require=None):
                # Let the wrapper persist the native object before L2 level validation.
                if level == 'L2' and require == 'L2':
                    return super().decide_batch(states, question, level=level, require=None)
                return super().decide_batch(states, question, level=level, require=require)
        return original_make_decider(backend, RawDecider)
    base.make_decider = make_raw_decider
    args = argparse.Namespace(stage=stage, output_dir=output_dir,
                              model_path=Path(plan['model_path']),
                              model_revision=plan['model_revision'],
                              device=plan['device'], dtype=plan['dtype'],
                              batch_size=plan['batch_size'], max_context=plan['max_context'],
                              run_native=True, smoke_review=smoke_review,
                              run_manifest=Path(plan['run_manifest']))
    with common_host_lock(HOST_LOCK):
        result = base.run(args)
        completion = write_completion(output_dir, phase=phase, stage=stage,
                                      plan_path=plan_path, review_path=review_path,
                                      run_manifest=plan['run_manifest'],
                                      base_smoke_review=smoke_review)
    return {**result, **completion}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'run'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--smoke-review', type=Path)
    args = parser.parse_args()
    phase = read_json(args.plan)['phase']
    if args.command == 'verify':
        for stage in STAGES:
            validate_plan(args.plan, phase=phase, stage=stage)
        print(json.dumps({'phase': phase, 'plan_sha256': sha(args.plan),
                          'native_work_performed': False}, sort_keys=True))
    else:
        if not args.stage or not args.review:
            parser.error('run requires --stage and --review')
        print(json.dumps(run_stage(args.plan, args.review, args.stage,
                                   args.smoke_review), sort_keys=True))


if __name__ == '__main__':
    main()
