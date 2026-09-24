#!/usr/bin/env python3
"""Export descriptive native P0/P1/P2 outcomes from hash-bound saved attempts."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('results/prompt-comparison-v1-2026-09-24/native-outcome-summary-v1/summary.json')
DEST = Path('results/prompt-comparison-v1-2026-09-24/native-public-summary-v1/summary.json')
IDS = [f'DEV-{i:03}' for i in range(1, 61)]
CONFIGS = {
    'anyjev-qwen06-generated-control', 'semif-generated-bf16',
    'openjev-generated-off', 'openjev-generated-on',
}
NOTE = ('Descriptive agreement with 60 provisional AI-reviewed development references. '
        'These saved outcomes have not passed the central paired-protocol audit; differences across P0, P1 and P2 do not establish a causal prompt effect.')
LIMITATIONS = [
    'AnyJev generated output is a separate HF generation control, not its native L0/L1/L2 decision readout.',
    'OpenJev requested-on does not verify effective reasoning.',
    'SemIf P0 request hashes record decision intent rather than actual generated messages; P2 DEV-033 remains unresolved.',
    'The 60 synthetic references were authored and reviewed by the same assistant; no independent human adjudication was performed.',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bound(spec, root):
    path = (root / spec['file']).resolve()
    path.relative_to(root.resolve())
    raw = path.read_bytes()
    if digest(raw) != spec['sha256']:
        raise ValueError('Source hash mismatch: ' + spec['file'])
    return raw


def lines(raw):
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def summarize(source, root):
    if source.get('contract') != 'native-outcome-coverage-v1' or source.get('strict_paired_comparison_eligible') is not False or source.get('inference_performed') is not False:
        raise ValueError('Unsupported native source contract')
    refs = lines(bound(source['references'], root))
    if len(refs) != 60 or [r['id'] for r in refs] != IDS or any(r.get('split') != 'development' or not valid(r.get('proposed_labels')) for r in refs):
        raise ValueError('Expected 60 ordered development references')
    truth = {r['id']: r['proposed_labels'] for r in refs}
    if len(source['rows']) != 12 or {(r['configuration_id'], r['variant']) for r in source['rows']} != {(c, p) for c in CONFIGS for p in ('P0', 'P1', 'P2')}:
        raise ValueError('Expected four native configurations with P0/P1/P2')
    out = []
    for item in source['rows']:
        records = {}
        for spec in item['sources']:
            for row in lines(bound(spec, root)):
                rid = row.get('id')
                if rid not in truth or rid in records:
                    raise ValueError('Unknown or duplicate saved record ID')
                records[rid] = row
        missing = [rid for rid in IDS if rid not in records]
        statuses = dict(Counter(row.get('status') for row in records.values()))
        usable = {rid: row['prediction'] for rid, row in records.items()
                  if row.get('status') == 'ok' and valid(row.get('prediction'))}
        fields = {key: sum(pred[key] == truth[rid][key] for rid, pred in usable.items()) for key in KEYS}
        all_four = sum(pred == truth[rid] for rid, pred in usable.items())
        if (item['denominator'] != 60 or item['saved'] != len(records) or item['missing_ids'] != missing or
                item['statuses'] != statuses or item['all_four_reference_agreement'] != all_four or
                sum(statuses.values()) != len(records)):
            raise ValueError('Saved native outcome disagrees with source summary')
        out.append({
            'id': item['configuration_id'], 'condition': item['variant'], 'denominator': 60,
            'saved': len(records), 'valid': len(usable),
            'correct': {**fields, 'all_four': all_four},
            'missingIds': missing, 'sourceBindings': item['sources'],
        })
    return out


def export(root=ROOT):
    root = Path(root)
    raw = (root / SOURCE).read_bytes()
    source = json.loads(raw)
    return {
        'contract': 'native-public-descriptive-v1', 'denominator': 60,
        'strictPairedComparisonEligible': False, 'referenceNote': NOTE,
        'limitations': LIMITATIONS, 'sourceSummary': {'file': str(SOURCE), 'sha256': digest(raw)},
        'references': source['references'], 'conditions': summarize(source, root),
    }


def main():
    payload = export()
    path = ROOT / DEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
