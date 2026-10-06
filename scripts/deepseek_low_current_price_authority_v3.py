#!/usr/bin/env python3
"""Separate DEV051-060 authority bridge; frozen current-price v2 stays intact."""
import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import FunctionType
import deepseek_low_current_price_v2 as prior
import openrouter_budget_amendment_v3 as amendment
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

SCHEMA = 'deepseek-low-current-price-authority-v3'
BASE = prior.BASE.parent / 'current-price-authority-v3-051-060' / 'frozen-master-prefix-v1'
MANIFEST = BASE / 'manifest.json'
CANDIDATE = BASE / 'root-review-candidate.json'
PARTITION_ID = SCHEMA + '-dev051-060'
IDS = prior.IDS
CHILD_CAP = prior.CHILD_CAP
AMENDMENT = amendment.BASE / 'proposal.json'
sha = prior.sha


def _historical_current_price():
    """Replay unchanged historical functions against the reviewed master prefix.

    The full master remains the live admission ledger. Only private historical
    rows(master) reads see its original SHA-bound bytes; other evidence reads
    and every frozen source/manifest verifier are unchanged.
    """
    proposal = json.loads(AMENDMENT.read_text())
    master = proposal['master']
    raw = Path(master['path']).read_bytes()[:master['bytes']]
    if amendment.old.sha(raw) != master['sha256']:
        raise ValueError('Reviewed original master prefix changed')
    master_rows, _ = amendment.old._lines(raw)
    current = prior._load_private('_deepseek_v3_historical_current', prior.__file__)

    def historical():
        old = prior._historical()
        third = old.prior
        second = prior._load_private('_deepseek_v3_historical_second', third.prior.__file__)
        first = prior._load_private('_deepseek_v3_historical_first', second.first.__file__)
        for module in (third, second, first):
            original_rows = module.rows
            def rows(path, reader=original_rows):
                if Path(path).resolve() == Path(master['path']).resolve():
                    return deepcopy(master_rows)
                return reader(path)
            module.rows = rows
        second.first = first
        third.prior = second
        return old
    current._historical = historical
    return current


def manifest_value():
    previous = _historical_current_price().verify()
    for name in ('suffix.claim.json', 'suffix.journal.jsonl', 'suffix.raw.jsonl',
                 'suffix.records.jsonl', 'budget.json', 'suffix.root-review.json'):
        if (prior.BASE / name).exists():
            raise ValueError('Previous current-price suffix already admitted or attempted')
    proposal = json.loads(AMENDMENT.read_text())
    if proposal.get('schema') != amendment.SCHEMA or proposal.get('spec') != amendment.SPEC:
        raise ValueError('Require exact additional OpenRouter $10 proposal')
    value = deepcopy(previous)
    value.update(schema=SCHEMA,
        configuration_id=prior.admission.CONFIG + '-exact-prices-0.055-1.32-authority-v3',
        partition_id=PARTITION_ID, global_hold_id=PARTITION_ID,
        global_authority_cap_usd='20.00', global_shared_cap_usd='10.00',
        global_openrouter_additional_cap_usd='10.00', funding_pool='openrouter_additional',
        budget_master_cap_usd='22.38', requested_global_cap_usd='20.00',
        requested_cap_increase_approved=False,
        authority_amendment={'path': str(AMENDMENT), 'sha256': sha(AMENDMENT),
            'prior_0_55_request_superseded': True, 'activation_required': True},
        dispatch_bridge={'frozen_run_source': str(prior.fourth.prior.__file__),
            'change': 'Only run ledger.master_cap comparison: Decimal(12.38) becomes Decimal(22.38)',
            'historical_master': {'path': proposal['master']['path'],
                'prefix_bytes': proposal['master']['bytes'], 'prefix_sha256': proposal['master']['sha256'],
                'scope': 'Private historical rows(master) only; actual admission uses full live ledger'}},
        admission='Separate root stage review; committed joint amendment; exact live route/rates; '
            'fresh exact OpenRouter child and earmarked whole-stage hold; no retry or automatic release')
    value['sources'].update({
        'frozen_current_price_v2_manifest': prior.bound(prior.MANIFEST),
        'authority_bridge_controller': prior.bound(__file__),
        'authority_amendment_proposal': prior.bound(AMENDMENT),
        'authority_amendment_controller': prior.bound(amendment.__file__),
        'authority_v3_module': prior.bound(authority.__file__),
        'budget_partitions_v4_module': prior.bound(partitions.__file__),
        'budget_v4_module': prior.bound(Path(__file__).with_name('openrouter_budget_v4.py'))})
    return value


def prepare():
    value = manifest_value()
    if MANIFEST.exists() or CANDIDATE.exists():
        raise FileExistsError('Bridge proposal already exists')
    prior._write_new(MANIFEST, value)
    prior._write_new(CANDIDATE, {'schema': SCHEMA + '-design-root-review',
        'approved': False, 'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__), 'inference_authorized': False})
    return sha(MANIFEST)


def verify():
    value = manifest_value()
    if json.loads(MANIFEST.read_text()) != value:
        raise ValueError('Authority bridge proposal differs from frozen sources')
    return value


def _run_with_amended_cap(core):
    # Bind the existing run bytecode to its isolated module globals.
    # Demand exactly one explicit ledger.master_cap == old-cap control before
    # replacing that literal. Every request/receipt/transport check is inherited.
    source = Path(prior.fourth.prior.__file__).read_text()
    module = ast.parse(source)
    run = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    matches = []
    for node in ast.walk(run):
        if (isinstance(node, ast.Compare) and ast.dump(node.left) ==
                ast.dump(ast.parse('ledger.master_cap', mode='eval').body) and
                len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq) and
                len(node.comparators) == 1 and ast.dump(node.comparators[0]) ==
                ast.dump(ast.parse("Decimal('12.38')", mode='eval').body)):
            matches.append(node)
    if (len(matches) != 1 or
            sum(isinstance(node, ast.Constant) and node.value == '12.38' for node in ast.walk(run)) != 1 or
            core.run.__code__.co_consts.count('12.38') != 1):
        raise ValueError('Frozen run master-cap control differs')
    constants = tuple('22.38' if value == '12.38' else value for value in core.run.__code__.co_consts)
    code = core.run.__code__.replace(co_consts=constants)
    core.run = FunctionType(code, core.__dict__, core.run.__name__, core.run.__defaults__)


def _private_core():
    core = prior._private_core()
    for name, value in {'SCHEMA': SCHEMA, 'BASE': BASE, 'MANIFEST': MANIFEST,
            'PARTITION_ID': PARTITION_ID, 'AUTHORITY_ID': PARTITION_ID,
            'verify': verify, 'live_controls': _historical_current_price().live_controls,
            'partitions': partitions, '__file__': __file__}.items():
        setattr(core, name, value)
    _run_with_amended_cap(core)

    def hold(expected_head, budget_path, expected_source):
        source = core.global_hold_source(budget_path)
        if source != expected_source:
            raise ValueError('Reviewed earmarked hold source differs')
        return authority.hold_authority(core.AUTHORITY, PARTITION_ID, str(CHILD_CAP),
            source, expected_head, stage_path=core.stage_paths()['claim'],
            funding_pool='openrouter_additional', budget_path=budget_path,
            partition_id=PARTITION_ID)
    core.hold_authority = hold
    return core


def global_hold_source(budget_path):
    return _private_core().global_hold_source(budget_path)


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
    parser.add_argument('--review', type=Path)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'verify': verify(); print(sha(MANIFEST))
    elif args.review and args.budget:
        print(json.dumps(run(args.review, args.budget, args.env_file)))
    else: parser.error('execute-stage requires --review and --budget')


if __name__ == '__main__': main()
