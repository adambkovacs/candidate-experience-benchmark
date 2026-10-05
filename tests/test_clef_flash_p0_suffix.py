import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_flash_p0_suffix as suffix
import clef_native_preparation as prep

ACCOUNT = 'a' * 32
TOKEN = 'offline-only-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}


def envelope(model='clef-flash'):
    answers = {}
    for field in prep.KEYS:
        values = {label: 0.0 for label in prep.VALUES[field]}
        values[prep.VALUES[field][0]] = 1.0
        answers[field] = {'type': 'choice', 'choice': prep.VALUES[field][0],
                          'probabilities': values, 'confidence': 0.8}
    return {'success': True, 'status': 200, 'errors': [], 'messages': [],
            'result': {'model': model, 'answers': answers,
                       'usage': {'input_tokens': 100, 'output_tokens': 0}}}


class FlashSuffixExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / 'suffix-child'
        self.authority = self.root / 'authority.jsonl'
        self.snapshot = self.root / 'authority-snapshot.jsonl'
        self.manifest = self.root / 'manifest.json'
        self.grant_path = self.root / 'grant.json'
        for rel in ('data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md',
                    'results/clef-native-v1/repeat-continuation-v1/remaining-admission-v1.json',
                    'results/clef-native-v1/clef-flash-billing-source.md',
                    'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/completion.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/claim.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/journal.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/raw.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/records.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/app-bridge/31df0e2b-ac36-4001-9bc3-e9b08d47f37f.request.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/app-bridge/31df0e2b-ac36-4001-9bc3-e9b08d47f37f.dispatch.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/app-bridge/31df0e2b-ac36-4001-9bc3-e9b08d47f37f.tool-result.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/app-bridge/31df0e2b-ac36-4001-9bc3-e9b08d47f37f.app-result.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/development/external-error-audit.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/claim.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/journal.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/raw.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/records.jsonl',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/completion.json',
                    'results/clef-native-v1/clef-flash/fresh3/P0/smoke/smoke-review.json'):
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)
        first = suffix.AUTHORITY_SNAPSHOT.read_bytes().splitlines(keepends=True)[0]
        self.snapshot.write_bytes(first)
        self.authority.write_bytes(first)
        # Rebind copied parent/smoke claims to the fixture account while
        # preserving their frozen structures and updating dependent hashes.
        parent_dir = self.root / suffix.PARENT.relative_to(ROOT)
        parent_claim = json.loads((parent_dir / 'claim.json').read_bytes())
        parent_claim['account_id_sha256'] = prep.sha(ACCOUNT.encode())
        (parent_dir / 'claim.json').write_bytes(prep.canonical(parent_claim) + b'\n')
        parent_completion = json.loads((parent_dir / 'completion.json').read_bytes())
        parent_completion['claim_sha256'] = suffix.sha(parent_dir / 'claim.json')
        (parent_dir / 'completion.json').write_bytes(prep.canonical(parent_completion) + b'\n')
        audit_path = parent_dir / 'external-error-audit.json'
        audit = json.loads(audit_path.read_bytes())
        audit['completion_sha256'] = suffix.sha(parent_dir / 'completion.json')
        audit_path.write_bytes(prep.canonical(audit) + b'\n')
        smoke_review_file = self.root / suffix.PARENT_SMOKE_REVIEW.relative_to(ROOT)
        smoke_dir = smoke_review_file.parent
        smoke_claim = json.loads((smoke_dir / 'claim.json').read_bytes())
        smoke_claim['account_id_sha256'] = prep.sha(ACCOUNT.encode())
        (smoke_dir / 'claim.json').write_bytes(prep.canonical(smoke_claim) + b'\n')
        smoke_completion = json.loads((smoke_dir / 'completion.json').read_bytes())
        smoke_completion['claim_sha256'] = suffix.sha(smoke_dir / 'claim.json')
        (smoke_dir / 'completion.json').write_bytes(prep.canonical(smoke_completion) + b'\n')
        review_path = smoke_review_file
        review = json.loads(review_path.read_bytes())
        review['completion_sha256'] = suffix.sha(smoke_dir / 'completion.json')
        review_path.write_bytes(prep.canonical(review) + b'\n')
        value = suffix.manifest_value(self.root)
        self.manifest.write_bytes(prep.canonical(value) + b'\n')
        self.addCleanup(self.temp.cleanup)

    def grant(self, *, ledger=None):
        ledger = self.authority if ledger is None else ledger
        value = {
            'kind': suffix.GRANT_KIND, 'approved': True, 'authorized_by_user': True,
            'reviewer': 'offline-root-fixture', 'model': suffix.MODEL, 'stage': suffix.STAGE,
            'pass': suffix.REPEAT, 'condition': suffix.CONDITION, 'phase': suffix.PHASE,
            'manifest_sha256': suffix.sha(self.manifest),
            'controller_sha256': suffix.sha(Path(suffix.__file__)),
            'bridge_sha256': suffix.sha(Path(suffix.bridge.__file__)),
            'account_id_sha256': prep.sha(ACCOUNT.encode()),
            'transport': 'mcp__codex_apps__cloudflare_execute',
            'full_context_hold_usd': str(suffix.HOLD), 'global_authority_cap_usd': '10.00',
            'global_authority_approval_sha256': suffix.APPROVAL_SHA256,
            'smoke_review_sha256': suffix.sha(self.root / suffix.PARENT_SMOKE_REVIEW.relative_to(ROOT)),
            'prior_completion_sha256': suffix.sha(self.root / suffix.PARENT_COMPLETION.relative_to(ROOT)),
            'exhaustion_policy': 'pause', 'wait_seconds': 1,
            'global_authority_ledger_sha256_at_admission': suffix.sha(ledger),
            'billing_source_sha256': suffix.sha(self.root / 'results/clef-native-v1/clef-flash-billing-source.md'),
            'parent_external_error_audit_sha256': suffix.sha(self.root / suffix.PARENT_AUDIT.relative_to(ROOT)),
        }
        self.grant_path.write_bytes(prep.canonical(value) + b'\n')
        return self.grant_path

    def execute(self, transport, base=None, authority=None):
        authority = authority or self.authority
        return suffix.run_stage(self.manifest, self.grant(ledger=authority),
                                root=self.root, base=base or self.base,
                                authority_path=authority, snapshot_path=self.snapshot,
                                environment=ENV, wait_seconds=1, transport=transport,
                                billing_source=lambda _: (self.root / 'results/clef-native-v1/clef-flash-billing-source.md').read_bytes())

    def test_exact_59_requests_and_durable_completion(self):
        seen = []
        result = self.execute(lambda url, headers, body: (seen.append(prep.sha(body)) or
                                                       (200, prep.canonical(envelope()))))
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['attempted'], 59)
        self.assertEqual(result['counts'], {'valid': 59, 'invalid_output': 0,
                                             'service_error': 0, 'unknown_outcome': 0})
        self.assertEqual(result['never_sent'], [])
        self.assertEqual(len(seen), 59)
        records = [json.loads(line) for line in (self.base / 'records.jsonl').read_bytes().splitlines()]
        self.assertEqual([r['id'] for r in records], list(suffix.SUFFIX_IDS))
        self.assertNotIn('DEV-001', [r['id'] for r in records])
        self.assertEqual(result['records_sha256'], suffix.sha(self.base / 'records.jsonl'))

    def test_malformed_response_stops_and_preserves_never_sent(self):
        seen = []
        def transport(*_):
            seen.append(1)
            return 200, b'{malformed'
        result = self.execute(transport)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['counts']['service_error'], 1)
        self.assertEqual(result['never_sent'], list(suffix.SUFFIX_IDS[1:]))

    def test_invalid_output_and_service_error_stop(self):
        invalid = envelope()
        del invalid['result']['answers'][prep.KEYS[0]]
        for bad, expected in ((invalid, 'invalid_output'),
                              ({'success': False, 'status': 500, 'errors': ['x'],
                                'messages': [], 'result': None}, 'service_error')):
            with self.subTest(expected=expected):
                self.authority.write_bytes(self.snapshot.read_bytes())
                result = self.execute(lambda *_: (200, prep.canonical(bad)),
                                  base=self.root / ('bad-' + expected))
                self.assertEqual(result['attempted'], 1)
                self.assertEqual(result['counts'][expected], 1)
                self.assertEqual(result['never_sent'], list(suffix.SUFFIX_IDS[1:]))

    def test_source_drift_and_insufficient_cap_do_not_hold_or_send(self):
        changed = json.loads(self.manifest.read_bytes())
        changed['requests'][0]['payload_sha256'] = '0' * 64
        self.manifest.write_bytes(prep.canonical(changed) + b'\n')
        before = self.authority.read_bytes()
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.execute(lambda *_: self.fail('send'))
        self.assertEqual(self.authority.read_bytes(), before)
        self.manifest.write_bytes(prep.canonical(suffix.manifest_value(self.root)) + b'\n')
        hold = {'event': 'hold', 'id': 'existing', 'usd': '9.80', 'source_sha256': 'b' * 64}
        self.authority.write_bytes(self.snapshot.read_bytes() + prep.canonical(hold) + b'\n')
        before = self.authority.read_bytes()
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            self.execute(lambda *_: self.fail('send'))
        self.assertEqual(self.authority.read_bytes(), before)

    def test_duplicate_claim_and_concurrent_flock_refusal(self):
        self.execute(lambda *_: (200, prep.canonical(envelope())))
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            self.execute(lambda *_: self.fail('replay'))
        path = self.root / 'lock-authority.jsonl'
        path.write_bytes(self.snapshot.read_bytes())
        first = suffix.AuthorityLedger(path, suffix.sha(path), self.snapshot)
        try:
            with self.assertRaises(OSError):
                suffix.AuthorityLedger(path, suffix.sha(path), self.snapshot)
        finally:
            first.close()

    def test_native_apptransport_submit_handshake_binds_dispatch_and_tool_result(self):
        directory = self.root / 'transport-child'
        directory.mkdir()
        body = prep.canonical(prep.request_payload('fixture feedback', 'fixture policy', suffix.MODEL, suffix.CONDITION))
        attempt = 'fixture-attempt'
        (directory / 'journal.jsonl').write_text(json.dumps({'event': 'reserved', 'attempt_id': attempt,
            'id': 'DEV-002', 'request_sha256': prep.sha(body), 'usd': '0.005899'}) + '\n' +
            json.dumps({'event': 'started', 'attempt_id': attempt, 'id': 'DEV-002'}) + '\n')
        transport = suffix.AppTransport(directory, ACCOUNT, 'f' * 64, 2)
        result = {}
        def call():
            try:
                result['value'] = transport(
                    f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/{prep.MODELS[suffix.MODEL]["route"]}',
                    {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json', 'Accept': 'application/json'}, body)
            except Exception as exc:
                result['error'] = exc
        thread = threading.Thread(target=call); thread.start()
        request_path = directory / 'app-bridge' / (attempt + '.request.json')
        for _ in range(100):
            if request_path.exists(): break
            time.sleep(0.01)
        self.assertTrue(request_path.exists())
        app_bytes = prep.canonical(envelope())
        bridge_dir = directory / 'app-bridge'
        (bridge_dir / (attempt + '.dispatch.json')).write_bytes(prep.canonical({'request_sha256': prep.sha(body), 'operator': 'offline-fixture'}) + b'\n')
        (bridge_dir / (attempt + '.tool-result.json')).write_bytes(prep.canonical({'isError': False, 'content': [{'type': 'text', 'text': app_bytes.decode()}]}) + b'\n')
        app_path = bridge_dir / (attempt + '.app-result.json')
        app_path.write_bytes(app_bytes)
        suffix.submit_response(request_path, app_path, bridge_dir / (attempt + '.tool-result.json'))
        thread.join(3)
        self.assertNotIn('error', result)
        self.assertEqual(result['value'], (200, app_bytes))


if __name__ == '__main__':
    unittest.main()
