#!/usr/bin/env python3
"""Distinct unchanged-payload suffix accepting prompt prices within its ceiling."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import quote
import deepseek_low_current_price_authority_v3 as prior

SCHEMA = 'deepseek-low-prompt-ceiling-v4'
BASE = prior.BASE.parent / 'prompt-ceiling-v4'
MANIFEST = BASE / 'manifest.json'
CANDIDATE = BASE / 'root-review-candidate.json'
PARTITION_ID = SCHEMA + '-dev051-060'
IDS, CHILD_CAP = prior.IDS, prior.CHILD_CAP
INPUT_CEILING, OUTPUT_CEILING = prior.prior.INPUT_CEILING, prior.prior.OUTPUT_CEILING
RESERVE = prior.prior.RESERVE
REFUSAL = prior.BASE / 'live-route-refusal.json'
paid, admission, authority, partitions = prior.prior.paid, prior.prior.admission, prior.authority, prior.partitions
sha = prior.sha
MODEL_FIELDS = ('id', 'canonical_slug', 'hugging_face_id', 'context_length', 'architecture', 'reasoning')


def manifest_value():
    value = deepcopy(prior.verify())
    for name in ('budget.json', 'suffix.root-review.json', 'suffix.claim.json',
                 'suffix.raw.jsonl', 'suffix.records.jsonl', 'suffix.journal.jsonl'):
        if (prior.BASE / name).exists():
            raise ValueError('Previous authority bridge admitted or attempted')
    refusal = json.loads(REFUSAL.read_text())
    if refusal.get('inference_sent') is not False:
        raise ValueError('Require saved pre-inference route refusal')
    recorded_model, recorded_endpoint = prior._historical_current_price().route_context()
    check_controls(refusal['model'], refusal['endpoint'], recorded_model, recorded_endpoint)
    value.update(schema=SCHEMA, configuration_id=admission.CONFIG + '-prompt-ceiling-authority-v4',
        partition_id=PARTITION_ID, global_hold_id=PARTITION_ID,
        exact_live_rates_usd_per_token={'prompt': refusal['endpoint']['pricing']['prompt'],
            'completion': refusal['endpoint']['pricing']['completion']},
        current_public_route={**value['current_public_route'], 'retrieved_utc': refusal['time'],
            'pricing': refusal['endpoint']['pricing'], 'status': refusal['endpoint']['status']},
        admission='Separate root stage review; committed joint amendment; exact model/provider/interface; '
            'prompt rate at or below unchanged ceiling; exact other prices; same request hashes/reserve; '
            'fresh child and earmarked hold; no retry or automatic release',
        price_admission={'prompt_rate_policy': 'nonnegative and at or below unchanged request max_price',
            'prompt_ceiling_usd_per_million': str(INPUT_CEILING),
            'observed_prompt_usd_per_token': refusal['endpoint']['pricing']['prompt'],
            'observed_at': refusal['time'], 'other_price_policy': 'exact frozen values',
            'operational_statistics': 'recorded in endpoint snapshot; excluded from admission',
            'payload_change': False, 'reservation_change': False})
    value['sources'].update({'prior_authority_bridge_manifest': prior.prior.bound(prior.MANIFEST),
        'prior_authority_bridge_controller': prior.prior.bound(prior.__file__),
        'preallocation_live_refusal': prior.prior.bound(REFUSAL),
        'prompt_ceiling_controller': prior.prior.bound(__file__)})
    return value


def check_controls(model, endpoint, recorded_model, recorded):
    if (any(model.get(k) != recorded_model.get(k) for k in MODEL_FIELDS) or
            any(endpoint.get(k) != recorded.get(k) for k in prior.prior.fourth.ROUTE_FIELDS) or
            endpoint.get('status') != 0 or set(endpoint['pricing']) != set(recorded['pricing']) or
            paid.number(endpoint['pricing']['prompt']) > INPUT_CEILING / paid.MILLION or
            any(paid.number(endpoint['pricing'][k]) != paid.number(recorded['pricing'][k])
                for k in recorded['pricing'] if k != 'prompt') or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'} or
            paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('Live model, interface, route, price ceiling or reserve changed')


def prepare():
    value = manifest_value()
    if MANIFEST.exists() or CANDIDATE.exists(): raise FileExistsError('Proposal already exists')
    prior.prior._write_new(MANIFEST, value)
    prior.prior._write_new(CANDIDATE, {'schema': SCHEMA + '-design-root-review',
        'approved': False, 'authorized_by_root': False, 'independent_review': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__), 'inference_authorized': False})
    return sha(MANIFEST)


def verify():
    value = manifest_value()
    if json.loads(MANIFEST.read_text()) != value: raise ValueError('Prompt-ceiling proposal changed')
    return value


def live_controls():
    historical = prior._historical_current_price()
    recorded_model, recorded_endpoint = historical.route_context()
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints', timeout=300)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER, catalog, endpoints,
                                           INPUT_CEILING, OUTPUT_CEILING)
    check_controls(model, endpoint, recorded_model, recorded_endpoint)
    if historical.requests(endpoint, model) != verify()['requests']:
        raise ValueError('Live request identities changed')
    return model, endpoint


def _private_core():
    core = prior._private_core()
    for name, value in {'SCHEMA': SCHEMA, 'BASE': BASE, 'MANIFEST': MANIFEST,
            'PARTITION_ID': PARTITION_ID, 'AUTHORITY_ID': PARTITION_ID,
            'verify': verify, 'live_controls': live_controls, '__file__': __file__}.items():
        setattr(core, name, value)
    def hold(expected_head, budget_path, expected_source):
        source = core.global_hold_source(budget_path)
        if source != expected_source: raise ValueError('Reviewed earmarked hold source differs')
        return authority.hold_authority(core.AUTHORITY, PARTITION_ID, str(CHILD_CAP), source,
            expected_head, stage_path=core.stage_paths()['claim'], funding_pool='openrouter_additional',
            budget_path=budget_path, partition_id=PARTITION_ID)
    core.hold_authority = hold
    return core


def global_hold_source(budget_path): return _private_core().global_hold_source(budget_path)


def run(receipt_path, budget_path, env_file=None):
    if Path(receipt_path).resolve() != (BASE / 'suffix.root-review.json').resolve():
        raise ValueError('Exact stage review path differs')
    receipt = json.loads(Path(receipt_path).read_text())
    if receipt.get('approved') is not True or receipt.get('reviewer') != 'root':
        raise ValueError('Independent root stage review required')
    return _private_core().run(receipt_path, budget_path, env_file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'execute-stage'))
    parser.add_argument('--review', type=Path); parser.add_argument('--budget', type=Path)
    parser.add_argument('--env-file'); args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'verify': verify(); print(sha(MANIFEST))
    elif args.review and args.budget: print(json.dumps(run(args.review, args.budget, args.env_file)))
    else: parser.error('execute-stage requires --review and --budget')


if __name__ == '__main__': main()
