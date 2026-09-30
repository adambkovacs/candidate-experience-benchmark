"""Build the selected two-pass illustration from closed, immutable evidence."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = 'results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/'
FILES = ['data/pilot/inputs.jsonl', BASE+'fresh1/P1/development.records.jsonl', BASE+'fresh2/P1/development.records.jsonl']
def build():
    source = [ROOT / p for p in FILES]
    rows = [[json.loads(line) for line in p.read_text().splitlines() if line] for p in source]
    inputs, first, second = [{r['id']: r for r in group} for group in rows]
    assert len(inputs) == len(first) == len(second) == 60
    assert set(inputs) == set(first) == set(second)
    changes = []
    for rid in first:
        a, b = first[rid]['decision'], second[rid]['decision']
        assert a['status'] == b['status'] == 'ok'
        if a['prediction'] != b['prediction']:
            changes.append({'id':rid,'feedback':inputs[rid]['feedback'],
                            'first':a['prediction'],'second':b['prediction']})
    return {'schema':'reader-selected-two-pass-v1','configuration':'gemma4-e2b-sdk-thinking-on',
            'condition':'P1','passes':['fresh1','fresh2'],'denominator':60,'changes':changes,
            'sources':[{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source]}
if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    target=ROOT/'public-site/reader-evidence.json';payload=json.dumps(build(),indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if target.read_text()!=payload:raise SystemExit('Reader evidence differs from closed sources')
    else:target.write_text(payload)
