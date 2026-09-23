#!/usr/bin/env python3
"""Render offline paired evaluations as a separate, self-contained HTML report.

The report presents evaluator evidence; it never upgrades its audit status,
re-scores predictions, runs inference or reads labels independently.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
from frozen_prompt_variants import load_frozen_bundle, MANIFEST_SHA256

VARIANTS = ('P0', 'P1', 'P2')
COMPARISONS = ('P0_to_P1', 'P0_to_P2', 'P1_to_P2')


def esc(value):
    return html.escape(str(value), quote=True)


def display(value):
    if value is None:
        return 'unknown'
    if isinstance(value, float):
        return f'{value:.4f}'
    return str(value)


def dump(value):
    return '<pre>' + esc(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'


def validate(result):
    if result.get('contract') != 'prompt-pairs-v1' or result.get('denominator') != 60:
        raise ValueError('Require a 60-record prompt-pairs-v1 evaluation')
    if set(result.get('conditions', {})) != set(VARIANTS) or set(result.get('comparisons', {})) != set(COMPARISONS):
        raise ValueError('Require all three conditions and comparisons')
    if not isinstance(result.get('parent_baseline_id'), str) or not result['parent_baseline_id']:
        raise ValueError('Missing parent baseline identity')
    if type(result.get('eligible_paired_comparison')) is not bool or type(result.get('controls_verified')) is not bool:
        raise ValueError('Missing explicit verification status')
    for condition in result['conditions'].values():
        evaluation = condition['evaluation']
        if evaluation['records'] != 60 or not 0 <= evaluation['valid_outputs'] <= 60:
            raise ValueError('Invalid condition coverage')
        if any(metric['denominator'] != 60 for metric in evaluation['metrics'].values()):
            raise ValueError('Invalid field denominator')
    for comparison in result['comparisons'].values():
        if comparison['denominator'] != 60:
            raise ValueError('Invalid comparison denominator')
        ids = [case['id'] for case in comparison['cases']]
        if len(ids) != len(set(ids)) or len(ids) != comparison['changed_record_count']:
            raise ValueError('Inconsistent changed-case coverage')


def render(evaluations):
    """Each entry contains source_file, source_sha256 and the complete result."""
    _, additions = load_frozen_bundle()
    seen = set()
    sections = []
    for entry in evaluations:
        result = entry['result']
        validate(result)
        baseline_audit = result['conditions']['P0']['prompt_provenance']
        for variant in VARIANTS:
            audit = result['conditions'][variant]['prompt_provenance']
            expected = hashlib.sha256(additions[variant].encode()).hexdigest() if variant != 'P0' else None
            if audit.get('manifest_sha256') != MANIFEST_SHA256 or audit.get('addition_sha256') != expected:
                raise ValueError('Prompt diff does not match evaluator provenance')
            if audit.get('variant') != variant or audit.get('parent_baseline_id') != result['parent_baseline_id']:
                raise ValueError('Prompt condition or parent identity mismatch')
            if any(audit.get(key) != baseline_audit.get(key) for key in ('baseline_instruction_sha256', 'baseline_instruction_bytes', 'instruction_role')):
                raise ValueError('Baseline instruction or role changed between conditions')
            added_bytes = len(additions[variant].encode()) if variant != 'P0' else 0
            separator = '\n\n' if variant != 'P0' else ''
            if audit.get('composition_separator') != separator or audit.get('addition_bytes') != added_bytes or audit.get('composed_instruction_bytes') != audit['baseline_instruction_bytes'] + len(separator) + added_bytes:
                raise ValueError('Prompt composition byte accounting mismatch')
            if result['conditions'][variant]['prompt_bytes_added'] != len(separator) + added_bytes:
                raise ValueError('Prompt overhead differs from provenance')
            if variant == 'P0' and audit.get('composed_instruction_sha256') != audit.get('baseline_instruction_sha256'):
                raise ValueError('P0 instruction changed')
        identity = result['parent_baseline_id']
        if identity in seen:
            raise ValueError('Duplicate parent baseline; choose one evaluation explicitly')
        seen.add(identity)
        verified = 'verified' if result['controls_verified'] else 'unverified'
        eligibility = 'eligible according to evaluator' if result['eligible_paired_comparison'] else 'NOT eligible: protocol evidence incomplete'
        parts = [f'<section><h2>{esc(identity)}</h2>',
                 f'<p class="audit">Controls: {verified}. Paired comparison: {esc(eligibility)}.</p>',
                 f'<p>Source: {esc(entry["source_file"])}<br>SHA-256: <code>{esc(entry["source_sha256"])}</code></p>',
                 '<table><thead><tr><th>Condition</th><th>Valid / 60</th><th>All-four agreement / 60</th><th>Input tokens</th><th>Output tokens</th><th>Reasoning tokens</th><th>Total attempt seconds</th><th>Added prompt bytes</th><th>Added prompt tokens</th></tr></thead><tbody>']
        for variant in VARIANTS:
            c = result['conditions'][variant]
            t = c['telemetry']
            values = [variant, c['evaluation']['valid_outputs'], c['all_four_correct'], t.get('input_tokens'), t.get('output_tokens'), t.get('reasoning_tokens'), t.get('attempt_seconds'), c['prompt_bytes_added'], c.get('prompt_token_overhead')]
            parts.append('<tr>' + ''.join('<td>' + esc(display(v)) + '</td>' for v in values) + '</tr>')
        parts.append('</tbody></table><p>Timing and usage are totals at the actual request unit, including audited retries. Batch shares are not individual-record latency. Unknown values stay unknown. Agreement uses provisional development references.</p>')
        for comparison_name in COMPARISONS:
            comp = result['comparisons'][comparison_name]
            parts.append(f'<h3>{esc(comparison_name.replace("_to_", " to "))}</h3><p>{comp["changed_record_count"]} changed records; {len(comp["valid_to_failed"])} valid-to-failed; {len(comp["failed_to_valid"])} failed-to-valid; {len(comp["both_failed"])} failed in both conditions. Denominator: 60.</p>')
            parts.append('<details><summary>Field transitions and failure accounting</summary>' + dump({k: v for k, v in comp.items() if k != 'cases'}) + '</details>')
            for case in comp['cases']:
                search = ' '.join([identity, comparison_name, case['id'], case.get('feedback', ''), case['from_state'], case['to_state']]).lower()
                parts.append(f'<details class="case" data-search="{esc(search)}"><summary>{esc(case["id"])}: {esc(case["from_state"])} to {esc(case["to_state"])}</summary><p class="feedback">{esc(case.get("feedback", "Feedback unavailable"))}</p>' + dump({k: v for k, v in case.items() if k != 'feedback'}) + '</details>')
        parts.append('<details><summary>Complete evaluator evidence, concern errors, controlled pairs, costs and limitations</summary>' + dump(result) + '</details></section>')
        sections.append(''.join(parts))
    if not sections:
        raise ValueError('No evaluations; do not publish an empty experiment report')
    prompt_diff = '<details><summary>Exact frozen additions: P0 to P1, then P1 to P2</summary><p>The complete P0 instruction and its role remain unchanged. Each new condition appends two newline bytes followed by its frozen addition. P2 contains all of P1 verbatim.</p><h3>P0 to P1: appended classifier framing</h3><pre>' + esc(additions['P1']) + '</pre><h3>P1 to P2: additional SOP</h3><pre>' + esc(additions['P2'][len(additions['P1']):]) + '</pre><p>Bundle SHA-256: <code>' + MANIFEST_SHA256 + '</code></p></details>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prompt sensitivity: development comparisons</title>
<style>body{font:16px/1.5 system-ui,sans-serif;color:#202124;background:#fafafa;margin:2rem auto;padding:0 1.5rem;max-width:1200px}h1,h2,h3{line-height:1.2}section{border-top:2px solid #bbb;margin-top:2rem;padding-top:1rem}table{display:block;overflow:auto;border-collapse:collapse}th,td{border:1px solid #ccc;padding:.5rem;text-align:left}th{background:#eee}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}details{background:white;border:1px solid #ccc;padding:.7rem;margin:.5rem 0}summary{cursor:pointer}.audit{font-weight:700;background:#fff1cc;padding:.8rem}.feedback{white-space:pre-wrap}input{font:inherit;padding:.5rem;width:min(90%,36rem)}code{overflow-wrap:anywhere}[hidden]{display:none!important}</style>
<h1>Prompt sensitivity: development comparisons</h1><p>Separate from the original model benchmark. P0 is the existing task prompt; P1 adds classifier framing; P2 adds the frozen SOP and decision tree. These are single-pass development comparisons, not held-out evidence or causal improvement estimates. Failed outputs remain in the denominator.</p>
<label for="filter">Filter changed cases by configuration, record, feedback or state</label><br><input id="filter" type="search"><p id="count" aria-live="polite"></p>
''' + prompt_diff + ''.join(sections) + '''<script>const filter=document.getElementById('filter');const cases=[...document.querySelectorAll('.case')];function update(){const q=filter.value.toLowerCase();let shown=0;for(const row of cases){row.hidden=!row.dataset.search.includes(q);if(!row.hidden)shown++;}document.getElementById('count').textContent=shown+' of '+cases.length+' changed-case entries shown (a record can appear in multiple comparisons).';}filter.addEventListener('input',update);update();</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    entries = []
    for path in args.evaluation:
        raw = path.read_bytes()
        entries.append({'source_file': str(path), 'source_sha256': hashlib.sha256(raw).hexdigest(), 'result': json.loads(raw)})
    document = render(entries)
    with args.output.open('x') as out:
        out.write(document)
    print(json.dumps({'output': str(args.output), 'evaluations': len(entries)}))


if __name__ == '__main__':
    main()
