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
import clef_native_fresh2_p0 as next_p0
import clef_connected_app_bridge as bridge

ACCOUNT = 'a' * 32
TOKEN = 'offline-only-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}
PRICE = b'offline reviewed Cloudflare price page'


def envelope(model, *, status=200):
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


class ClefFresh2P0Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.base = self.folder / 'clef'
        self.authority = self.folder / 'authority.jsonl'
        self.authority.write_bytes(next_p0.AUTHORITY_SNAPSHOT.read_bytes())
        self.manifest = self.folder / 'manifest.json'
        self.manifest.write_bytes(prep.canonical(next_p0.manifest_value()) + b'\n')

    def grant(self, model='clef', phase='smoke', *, review_hash=None, head=None):
        grant = self.folder / f'{model}-{phase}-grant.json'
        data = {'kind': next_p0.GRANT_KIND, 'approved': True,
            'authorized_by_user': True, 'reviewer': 'independent-offline-fixture',
            'model': model, 'stage': next_p0.stage_name(model, phase), 'phase': phase,
            'manifest_sha256': prep.sha(self.manifest.read_bytes()),
            'controller_sha256': prep.sha(Path(next_p0.__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'account_id_sha256': prep.sha(ACCOUNT.encode()),
            'transport': 'mcp__codex_apps__cloudflare_execute',
            'full_context_hold_usd': str(prep.reservation_usd(model, 3 if phase == 'smoke' else 60)),
            'global_authority_cap_usd': '10.00',
            'global_authority_approval_sha256': next_p0.APPROVAL_SHA256,
            'global_authority_ledger_sha256_at_admission': head or prep.sha(self.authority.read_bytes()),
            'billing_source_sha256': prep.sha(PRICE),
            'smoke_review_sha256': review_hash,
            'exhaustion_policy': 'pause', 'wait_seconds': 1}
        grant.write_bytes(prep.canonical(data) + b'\n')
        return grant

    def execute_stage(self, model, phase, grant, transport, review=None):
        return next_p0.run_stage(model, phase, self.manifest, grant,
            base=self.base, authority_path=self.authority,
            environment=ENV, wait_seconds=1, transport=transport,
            billing_source=lambda _: PRICE, smoke_review_path=review)

    def review(self, model='clef'):
        directory = next_p0.stage_dir(self.base, model, 'smoke')
        completion = json.loads((directory / 'completion.json').read_bytes())
        data = {'kind': next_p0.INSPECTION_KIND, 'approved': True,
            'reviewer': 'separate-offline-fixture', 'model': model,
            'stage': next_p0.stage_name(model, 'smoke'),
            'manifest_sha256': prep.sha(self.manifest.read_bytes()),
            'completion_sha256': prep.sha((directory / 'completion.json').read_bytes()),
            'records_sha256': completion['records_sha256'],
            'raw_sha256': completion['raw_sha256'],
            'decision': 'admit_unchanged_full_p0'}
        path = self.folder / f'{model}-smoke-review.json'
        path.write_bytes(prep.canonical(data) + b'\n')
        return path

    def test_manifest_is_exact_two_model_fresh2_p0_preparation(self):
        manifest, _ = next_p0.checked_manifest(self.manifest)
        self.assertEqual(set(manifest['models']), {'clef', 'clef-flash'})
        self.assertEqual(manifest['models']['clef']['smoke']['ids'], list(prep.SMOKE_IDS))
        self.assertEqual(manifest['models']['clef-flash']['development']['ids'], list(prep.IDS))
        self.assertEqual(manifest['status'], 'prepared_no_grants_or_dispatch')
        self.assertFalse(next_p0.stage_dir(self.base, 'clef', 'smoke').exists())

    def test_missing_or_wrong_grant_fails_before_hold(self):
        bad = self.grant()
        data = json.loads(bad.read_bytes())
        data['stage'] = 'clef/fresh3/P0/smoke'
        bad.write_bytes(prep.canonical(data) + b'\n')
        original = self.authority.read_bytes()
        with self.assertRaisesRegex(ValueError, 'single-stage grant'):
            self.execute_stage('clef', 'smoke', bad, lambda *_: self.fail('must not dispatch'))
        self.assertEqual(self.authority.read_bytes(), original)
        self.assertFalse(next_p0.stage_dir(self.base, 'clef', 'smoke').exists())

    def test_smoke_then_full_with_new_grant_and_review_no_replay(self):
        observed = []
        def transport(url, headers, body):
            observed.append(prep.sha(body))
            self.assertIn('/@cf/cloudflare/clef', url)
            self.assertEqual(headers['Authorization'], 'Bearer ' + TOKEN)
            return 200, prep.canonical(envelope('clef'))
        smoke_grant = self.grant()
        first = self.execute_stage('clef', 'smoke', smoke_grant, transport)
        self.assertEqual((first['status'], first['attempted'], first['counts']['valid']), ('complete', 3, 3))
        self.assertEqual(first['unknown_cost_reserved_usd'], '0.047187')
        review = self.review()
        full_grant = self.grant(phase='development', review_hash=prep.sha(review.read_bytes()))
        second = self.execute_stage('clef', 'development', full_grant, transport, review)
        self.assertEqual((second['status'], second['attempted'], second['counts']['valid']), ('complete', 60, 60))
        self.assertEqual(len(observed), 63)
        self.assertEqual(len(set(observed)), 60)
        events = [json.loads(line) for line in self.authority.read_bytes().splitlines()]
        self.assertEqual([e['id'] for e in events[-2:]],
                         ['cloudflare-clef-fresh2-p0-smoke', 'cloudflare-clef-fresh2-p0-development'])
        self.assertEqual(len((next_p0.stage_dir(self.base, 'clef', 'development') / 'budget.jsonl').read_bytes().splitlines()), 61)
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            self.execute_stage('clef', 'development', full_grant, transport, review)
        self.assertEqual(len(observed), 63)

    def test_full_requires_independently_bound_smoke_review(self):
        grant = self.grant(phase='development', review_hash='f' * 64)
        with self.assertRaisesRegex(ValueError, 'smoke review'):
            self.execute_stage('clef', 'development', grant, lambda *_: self.fail('must not dispatch'))
        self.assertFalse(next_p0.stage_dir(self.base, 'clef', 'development').exists())

    def test_service_failure_stops_and_preserves_unknown_reservation(self):
        grant = self.grant(model='clef-flash')
        seen = []
        def transport(*_):
            seen.append(1)
            return 429, prep.canonical(envelope('clef-flash', status=429))
        result = self.execute_stage('clef-flash', 'smoke', grant, transport)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['counts']['service_error'], 1)
        self.assertEqual(result['never_sent'], list(prep.SMOKE_IDS[1:]))
        self.assertEqual(result['unknown_cost_reserved_usd'], '0.005899')
        self.assertEqual(len(self.authority.read_bytes().splitlines()),
                         len(next_p0.AUTHORITY_SNAPSHOT.read_bytes().splitlines()) + 1)

    def test_connected_app_handoff_keeps_outer_and_inner_evidence(self):
        grant = self.grant(model='clef-flash')
        result = {}
        def worker():
            result['completion'] = self.execute_stage('clef-flash', 'smoke', grant, None)
        thread = threading.Thread(target=worker)
        thread.start()
        directory = next_p0.stage_dir(self.base, 'clef-flash', 'smoke') / 'app-bridge'
        deadline = time.monotonic() + 4
        paths = []
        while time.monotonic() < deadline:
            paths = list(directory.glob('*.request.json')) if directory.exists() else []
            if paths:
                break
            time.sleep(0.01)
        self.assertEqual(len(paths), 1)
        ready = json.loads(paths[0].read_bytes())
        self.assertEqual(ready['stage'], 'clef-flash/fresh2/P0/smoke')
        self.assertEqual(ready['id'], 'DEV-001')
        self.assertNotIn(ACCOUNT, paths[0].read_text())
        self.assertNotIn(TOKEN, paths[0].read_text())
        app_result = prep.canonical(envelope('clef-flash', status=429))
        (directory / f'{ready["attempt_id"]}.dispatch.json').write_bytes(prep.canonical({
            'request_sha256': ready['request_sha256'], 'operator': 'offline-fixture'}))
        (directory / f'{ready["attempt_id"]}.app-result.json').write_bytes(app_result)
        (directory / f'{ready["attempt_id"]}.tool-result.json').write_bytes(prep.canonical({
            'isError': False, 'content': [{'type': 'text', 'text': app_result.decode()}]}))
        source = self.folder / 'result.json'
        source.write_bytes(app_result)
        bridge.submit_response(paths[0], source)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result['completion']['counts']['service_error'], 1)
        self.assertTrue((directory / f'{ready["attempt_id"]}.response.json').exists())

    def test_global_cap_or_changed_head_blocks_before_stage(self):
        grant = self.grant()
        with self.authority.open('ab') as handle:
            handle.write(prep.canonical({'event': 'hold', 'id': 'other-reviewed-work',
                'usd': '8.00', 'source_sha256': 'a' * 64}) + b'\n')
        with self.assertRaisesRegex(ValueError, 'ledger changed'):
            self.execute_stage('clef', 'smoke', grant, lambda *_: self.fail('must not dispatch'))
        self.assertFalse(next_p0.stage_dir(self.base, 'clef', 'smoke').exists())
        grant = self.grant()
        with self.assertRaisesRegex(ValueError, 'cap exhausted'):
            self.execute_stage('clef', 'smoke', grant, lambda *_: self.fail('must not dispatch'))
        self.assertFalse(next_p0.stage_dir(self.base, 'clef', 'smoke').exists())


if __name__ == '__main__':
    unittest.main()
