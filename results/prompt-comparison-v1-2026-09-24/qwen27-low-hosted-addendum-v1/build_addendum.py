#!/usr/bin/env python3
"""Freeze a Qwen27 LOW hosted prompt addendum without inference or budget writes."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import prompt_admission
import prompt_execution_gates as gates
import prompt_schedule
from evaluate_prompt_variants import extract_controls
from development_benchmark import valid

BASE = Path('results/prompt-comparison-v1-2026-09-24')
DIR = BASE / 'qwen27-low-hosted-addendum-v1'
TARGET = 'openrouter-qwen27-low-darkbloom-fp4'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def spec(path):
    path = Path(path)
    return {'file': str(path), 'sha256': sha((ROOT / path).read_bytes())}


def write(path, value):
    path = ROOT / path
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    return spec(path.relative_to(ROOT))


def main():
    add = ROOT / DIR
    fragment = add / 'offline-fragments' / TARGET
    index = json.loads((add / 'offline-fragments/index.json').read_text())
    if index['full_source_count'] != 17 or len(index['configurations']) != 14:
        raise ValueError('Prepared source count changed')
    snapshots = json.loads((add / 'full-paid-registry-snapshot.json').read_text())
    if len(snapshots) != 17 or len([r for r in snapshots if r['id'] == TARGET]) != 1:
        raise ValueError('Full paid snapshot or target changed')
    target = next(r for r in snapshots if r['id'] == TARGET)
    if target['status'] != 'complete' or target['provider'] != 'darkbloom/fp4' or target['effort'] != 'low':
        raise ValueError('P0 target is not the complete frozen condition')
    config = json.loads((fragment / 'configuration.json').read_text())
    if config['id'] != TARGET or set(config['conditions']) != {'P1', 'P2'}:
        raise ValueError('Wrong prepared target fragment')
    if spec((DIR / 'offline-fragments' / TARGET / 'configuration.json')) != next(x['configuration'] for x in index['configurations'] if x['id'] == TARGET):
        raise ValueError('Prepared fragment hash changed')
    parent = json.loads((fragment / 'parent.json').read_text())
    if parent['id'] != TARGET or parent['controls_sha256'] != config['controls_sha256']:
        raise ValueError('Parent controls mismatch')
    baseline = ROOT / target['predictions_file']
    attempts = [json.loads(x) for x in baseline.read_text().splitlines() if x.strip()]
    if len(attempts) != 60 or [r.get('id') for r in attempts] != [f'DEV-{n:03}' for n in range(1, 61)]:
        raise ValueError('Canonical complete P0 development records required')
    if any(r.get('status') != 'ok' or not valid(r.get('prediction')) or r.get('cost_unknown') is not False
           or extract_controls(r) != config['controls']['adapter_controls'] for r in attempts):
        raise ValueError('P0 validity, billing or paired controls mismatch')
    original_manifest = json.loads((ROOT / BASE / 'hosted-execution.json').read_text())
    roster = json.loads((ROOT / BASE / 'roster.json').read_text())
    inventory = json.loads((ROOT / BASE / 'baseline-inventory.json').read_text())
    schedule = json.loads((ROOT / BASE / 'schedule.json').read_text())
    if len(roster['entries']) != len(inventory['entries']) or len(schedule['order']) != 79:
        raise ValueError('Original roster/schedule changed')
    scheduled = [r for r in roster['entries'] if r['state'] == 'scheduled']
    if len(scheduled) != 79 or [r['id'] for r in scheduled] != [r['id'] for r in schedule['order']]:
        raise ValueError('Original 79 conditions no longer reconciled')
    if TARGET in [r['id'] for r in roster['entries']]:
        raise ValueError('Target already in original roster')
    new_roster = {'entries': [*roster['entries'], {'id': TARGET, 'parent_baseline_id': TARGET,
                  'state': 'scheduled', 'reason': 'Complete separately hosted Darkbloom FP4 P0; append-only P1/P2 addendum.'}]}
    new_inventory = {'entries': [*inventory['entries'], {'id': TARGET, 'disposition': 'completed',
                     'reason': 'Canonical 60 valid and known-billing P0 attempts with matched saved controls.',
                     'status': 'complete', 'source_registry': str(DIR / 'full-paid-registry-snapshot.json'),
                     'source_registry_sha256': spec(DIR / 'full-paid-registry-snapshot.json')['sha256'],
                     'evidence': [dict(spec(target['predictions_file']), available=True,
                                       bytes=baseline.stat().st_size),
                                  dict(spec(target['smoke_files'][0]), available=True,
                                       bytes=(ROOT / target['smoke_files'][0]).stat().st_size)]}]}
    new_schedule = {'order': [*schedule['order'], {'id': TARGET, 'conditions': ['P2', 'P1']}]}
    if new_roster['entries'][:-1] != roster['entries'] or new_inventory['entries'][:-1] != inventory['entries'] or new_schedule['order'][:-1] != schedule['order']:
        raise ValueError('Original roster/schedule prefix changed')
    roster_spec = write(DIR / 'roster-addendum.json', new_roster)
    inventory_spec = write(DIR / 'baseline-inventory-addendum.json', new_inventory)
    schedule_spec = write(DIR / 'schedule-addendum.json', new_schedule)
    manifest = {'contract': 'prompt-execution-gates-v1',
                'frozen_utc': datetime.now(timezone.utc).isoformat(),
                'manifest_scope': [TARGET], 'configurations': [config],
                'inputs': index['inputs'], 'schema': index['schema'],
                'prompt_bundle': index['prompt_bundle'],
                'roster': roster_spec, 'source_inventory': inventory_spec,
                'schedule': schedule_spec,
                'execution_journal': str(DIR / 'execution-journal.jsonl'),
                'append_only_lineage': {
                    'original_hosted_execution': spec(BASE / 'hosted-execution.json'),
                    'original_roster': spec(BASE / 'roster.json'),
                    'original_inventory': spec(BASE / 'baseline-inventory.json'),
                    'original_schedule': spec(BASE / 'schedule.json'),
                    'full_paid_registry_snapshot': spec(DIR / 'full-paid-registry-snapshot.json'),
                    'prepared_fragment_index': spec(DIR / 'offline-fragments/index.json'),
                    'original_scheduled_count': 79, 'addendum_scheduled_ordinal': 80,
                    'counterbalanced_order': ['P2', 'P1']}}
    manifest_spec = write(DIR / 'execution-manifest.json', manifest)
    if prompt_schedule._schedule(schedule_spec, ROOT)[TARGET] != ['P2', 'P1']:
        raise ValueError('Append-only schedule failed')
    admissions = {variant: prompt_admission.admit_smoke(manifest, ROOT, TARGET, variant)
                  for variant in ('P2', 'P1')}
    preflight = {'contract': 'qwen27-low-hosted-addendum-preflight-v1',
                 'status': 'OFFLINE_SMOKE_ADMITTED_ONLY',
                 'inference_performed': False, 'reference_labels_read': False,
                 'execution_manifest': manifest_spec,
                 'configuration_id': TARGET, 'condition_order': ['P2', 'P1'],
                 'original_roster_preserved': True,
                 'original_schedule_preserved': True,
                 'new_journal_exists': (add / 'execution-journal.jsonl').exists(),
                 'admissions': admissions,
                 'development_blockers': [
                     'P2 smoke3 not yet executed, inspected, or bound by prompt-smoke-supplement-v1.',
                     'P1 cannot start before the P2 condition is terminal under the frozen schedule.',
                     'No addendum budget partition has been allocated or authorized.',
                     'Prospective provider-rendered token count remains unknown; admission is observational.'
                 ]}
    write(DIR / 'preflight.json', preflight)
    print(json.dumps({'manifest_sha256': manifest_spec['sha256'],
                      'admitted_smoke': list(admissions), 'scheduled': 80,
                      'development_admitted': False, 'inference_performed': False}))


if __name__ == '__main__':
    main()
