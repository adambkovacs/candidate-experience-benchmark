"""Derive the 60 Jev P0 testimonial confidences that place the dots on slide S10.

No public-site feed lists all 60 per-review confidences; jev-confidence-findings.json keeps only the
wrong cases and the threshold counts. This reads the saved TypeSafe Jev 1.13 direct P0 answers and
asserts that the derived values reproduce every published count before writing.

Run: python3 -I public-site/deck/content/build-jev-confidence.py
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'results/openjev/typesafe-development-v2-reconciled.jsonl'
FEED = ROOT / 'public-site/jev-confidence-findings.json'
REVIEWS = ROOT / 'public-site/disputed-reviews-v1.json'
OUT = Path(__file__).with_name('jev-testimonial-confidence.json')
FIELD = 'testimonial_potential'

raw = SOURCE.read_bytes()
rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
reference = {r['id']: r['reference'][FIELD] for r in json.loads(REVIEWS.read_text())['reviews']}
feed = json.loads(FEED.read_text())['conditions']['P0']['fields'][FIELD]

reviews = []
for row in rows:
    answer = row['raw_response']['answers'][FIELD]
    reviews.append({'id': row['id'], 'confidence': answer['confidence'], 'choice': answer['choice'],
                    'reference': reference[row['id']], 'correct': answer['choice'] == reference[row['id']]})
reviews.sort(key=lambda r: (r['confidence'], r['id']))

# Every published number must come back out of the derived values.
assert len(reviews) == 60 == feed['valid']
assert sum(r['correct'] for r in reviews) == feed['correct']
wrong = {r['id']: r['confidence'] for r in reviews if not r['correct']}
assert wrong == {w['id']: w['confidence'] for w in feed['wrongCases']}, wrong
for t, counts in feed['thresholds'].items():
    kept = [r for r in reviews if r['confidence'] >= float(t)]
    assert len(kept) == counts['retained'], (t, len(kept))
    assert sum(not r['correct'] for r in kept) == counts['retainedWrong'], t
    assert 60 - len(kept) == counts['withheldValid'], t

OUT.write_text(json.dumps({
    'schema': 'deck-jev-testimonial-confidence-v1',
    'note': 'Derived for slide S10 dot positions only. Numbers shown on the slide bind to jev-confidence-findings.json.',
    'model': 'jev-1.13.0', 'condition': 'P0 direct (TypeSafe)', 'field': FIELD,
    'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(raw).hexdigest(),
    'checked_against': 'public-site/jev-confidence-findings.json conditions.P0.fields.testimonial_potential (valid, correct, wrongCases, thresholds)',
    'reviews': reviews,
}, indent=1) + '\n')
print(f'wrote {OUT.name}: 60 reviews, {len(wrong)} wrong {sorted(wrong)}, thresholds match the feed')
