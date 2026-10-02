import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_native_preparation as prep
import clef_native_smoke_runner as smoke
import clef_connected_app_bridge as bridge
import clef_native_full_p0 as full

ACCOUNT = 'a' * 32
TOKEN = 'offline-test-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}
SOURCES = {name: (name + '-reviewed-source').encode() for name in prep.MODELS}


def envelope(model, status=200):
    answers = {}
    for field in prep.KEYS:
        values = {label: 0.0 for label in prep.VALUES[field]}
        values[prep.VALUES[field][0]] = 1.0
        answers[field] = {'type': 'choice', 'choice': prep.VALUES[field][0],
                          'probabilities': values, 'confidence': 0.8}
    return {'success': status == 200, 'status': status,
            'errors': [] if status == 200 else [{'code': 9001, 'message': 'fixture'}],
            'messages': [], 'result': {'model': model, 'answers': answers,
            'usage': {'input_tokens': 100, 'output_tokens': 0}} if status == 200 else None}


class ClefFullP0Tests(unittest.TestCase):
    def files(self, folder, model='clef', wait_seconds=1, extra_hold=None):
        manifest = folder / 'manifest.json'
        manifest.write_bytes(prep.canonical(full.manifest_value()) + b'\n')
        authority = folder / 'authority.jsonl'
        events = [{'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                   'cap_usd': '10.00', 'decision_key': full.AUTHORITY_KEY,
                   'approval_sha256': full.APPROVAL_SHA256},
                  {'event': 'hold', 'id': 'cloudflare-initial-smoke',
                   'usd': '0.064884', 'source_sha256': prep.sha((full.BASE / 'budget.jsonl').read_bytes())},
                  {'event': 'hold', 'id': 'openrouter-gemma-fifth', 'usd': '0.60',
                   'source_sha256': prep.sha(full.GEMMA_BUDGET.read_bytes())}]
        if extra_hold is not None:
            events.append({'event': 'hold', 'id': 'other-postapproval', 'usd': extra_hold,
                           'source_sha256': 'a' * 64})
        authority.write_bytes(b''.join(prep.canonical(event) + b'\n' for event in events))
        grant = folder / 'grant.json'
        grant.write_bytes(prep.canonical({
            'kind': 'clef-native-full-p0-grant-v1', 'approved': True,
            'authorized_by_user': True, 'reviewer': 'offline-fixture',
            'model': model, 'stage': full.STAGE,
            'manifest_sha256': prep.sha(manifest.read_bytes()),
            'controller_sha256': prep.sha(Path(full.__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'smoke_inspector_sha256': prep.sha(Path(full.inspection.__file__).read_bytes()),
            'smoke_inspection_sha256': prep.sha(full.inspection.OUTPUT.read_bytes()),
            'account_id_sha256': prep.sha(ACCOUNT.encode()),
            'transport': 'mcp__codex_apps__cloudflare_execute',
            'full_context_reservation_usd': str(prep.reservation_usd(model, 60)),
            'development_cap_usd': '1.30', 'global_authority_cap_usd': '10.00',
            'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds,
            'global_authority_approval_sha256': full.APPROVAL_SHA256,
            'global_authority_ledger_sha256_at_admission': prep.sha(authority.read_bytes()),
            'billing_source_sha256': {name: prep.sha(raw) for name, raw in SOURCES.items()},
        }) + b'\n')
        return manifest, grant, authority

    def billing(self, url):
        model = next(name for name, spec in prep.MODELS.items() if spec['source'] == url)
        return SOURCES[model]

    def test_exact_sixty_valid_and_monotonic_cross_provider_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, authority = self.files(folder)
            output = folder / 'results'
            observed = []
            def transport(url, headers, body):
                observed.append(prep.sha(body))
                self.assertIn('/@cf/cloudflare/clef', url)
                self.assertEqual(headers['Authorization'], 'Bearer ' + TOKEN)
                return 200, prep.canonical(envelope('clef'))
            completion = full.run_full('clef', manifest, grant, base=output,
                authority_path=authority, environment=ENV, wait_seconds=1,
                transport=transport, billing_source=self.billing)
            self.assertEqual(completion['status'], 'complete')
            self.assertEqual(completion['counts']['valid'], 60)
            self.assertEqual(completion['never_sent'], [])
            self.assertEqual(len(set(observed)), 60)
            self.assertEqual(completion['unknown_cost_reserved_usd'], '0.94374')
            events = [json.loads(line) for line in authority.read_bytes().splitlines()]
            self.assertEqual(events[-1]['id'], 'cloudflare-clef-fresh1-p0-development')
            self.assertEqual(events[-1]['usd'], '0.94374')
            budget = [json.loads(line) for line in (output / 'development-budget.jsonl').read_bytes().splitlines()]
            self.assertEqual(len(budget), 61)
            self.assertEqual(sum(float(item['usd']) for item in budget[1:]), 0.94374)
            with self.assertRaisesRegex(ValueError, 'head changed'):
                full.run_full('clef', manifest, grant, base=output,
                    authority_path=authority, environment=ENV, wait_seconds=1,
                    transport=transport, billing_source=self.billing)
            self.assertEqual(len(observed), 60)

    def test_global_cap_blocks_before_any_development_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, authority = self.files(folder, extra_hold='9.00')
            with self.assertRaisesRegex(ValueError, 'Global authority exhausted'):
                full.run_full('clef', manifest, grant, base=folder / 'results',
                    authority_path=authority, environment=ENV, wait_seconds=1,
                    transport=lambda *_: self.fail('Must not send'),
                    billing_source=self.billing)
            self.assertFalse((folder / 'results/development-budget.jsonl').exists())
            self.assertEqual(len(authority.read_bytes().splitlines()), 4)

    def test_connector_error_stops_and_leaves_unsent_59(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, authority = self.files(folder)
            output = folder / 'results'
            result = {}
            def worker():
                result['completion'] = full.run_full('clef', manifest, grant,
                    base=output, authority_path=authority, environment=ENV,
                    wait_seconds=1, billing_source=self.billing)
            thread = threading.Thread(target=worker)
            thread.start()
            bridge_dir = output / 'clef/fresh1/P0/development/app-bridge'
            deadline = time.monotonic() + 5
            requests = []
            while time.monotonic() < deadline:
                requests = list(bridge_dir.glob('*.request.json')) if bridge_dir.exists() else []
                if requests:
                    break
                time.sleep(0.01)
            self.assertEqual(len(requests), 1)
            ready = bridge.read_json(requests[0])
            self.assertEqual(ready['id'], 'DEV-001')
            self.assertEqual(ready['stage'], full.STAGE)
            self.assertNotIn(ACCOUNT, requests[0].read_text())
            self.assertNotIn(TOKEN, requests[0].read_text())
            first_reserve = [json.loads(line) for line in
                             (output / 'development-budget.jsonl').read_bytes().splitlines()][-1]
            self.assertEqual(first_reserve['attempt_id'], ready['attempt_id'])
            response_file = folder / 'app-result.json'
            response_file.write_bytes(prep.canonical(envelope('clef', 429)))
            (bridge_dir / f'{ready["attempt_id"]}.app-result.json').write_bytes(
                response_file.read_bytes())
            (bridge_dir / f'{ready["attempt_id"]}.tool-result.json').write_bytes(
                prep.canonical({'isError': False, 'content': [{'type': 'text',
                    'text': response_file.read_text()}]}))
            bridge.submit_response(requests[0], response_file)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result['completion']['counts']['service_error'], 1)
            self.assertEqual(result['completion']['attempted'], 1)
            self.assertEqual(result['completion']['never_sent'], list(prep.IDS[1:]))
            self.assertEqual(result['completion']['unknown_cost_reserved_usd'], '0.015729')


if __name__ == '__main__':
    unittest.main()
